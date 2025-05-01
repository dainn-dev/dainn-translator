from typing import Dict, List, Optional, Tuple
import os
import json
import time
import html
from datetime import datetime
import cv2
import numpy as np
import pyautogui
import pytesseract
from google.cloud import vision
from google.cloud import translate_v2 as translate
from collections import OrderedDict
from src.config_manager import ConfigManager
import logging
import hashlib
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import platform
import requests
from urllib.parse import quote
from enum import Enum

class TranslatorService(Enum):
    GOOGLE = "Google"
    DEEPL = "DeepL"
    YANDEX = "Yandex"

# Configure Tesseract path based on operating system
def get_tesseract_path():
    system = platform.system().lower()
    if system == 'windows':
        paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
        ]
    elif system == 'darwin':  # macOS
        paths = [
            '/usr/local/bin/tesseract',
            '/opt/homebrew/bin/tesseract',  # Homebrew on Apple Silicon
            '/usr/bin/tesseract'
        ]
    else:  # Linux and others
        paths = [
            '/usr/bin/tesseract',
            '/usr/local/bin/tesseract'
        ]
    
    # Check each possible path
    for path in paths:
        if os.path.exists(path):
            return path
    
    return None

# Set Tesseract path
TESSERACT_PATH = get_tesseract_path()
if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    logging.info(f"Tesseract found at: {TESSERACT_PATH}")
else:
    logging.warning(
        "Tesseract not found in common installation paths. "
        "Please install Tesseract OCR and ensure it's in your PATH or set the correct path manually."
    )

logger = logging.getLogger(__name__)

class TextProcessor:
    """Handle text detection, translation, and history logging."""
    
    def __init__(self, vision_client: Optional[vision.ImageAnnotatorClient], 
                 translate_client: Optional[translate.Client], 
                 cache_size: int = 1000):
        logger.info("Initializing TextProcessor...")
        self.vision_client = vision_client
        self.translate_client = translate_client
        self.translation_cache = OrderedDict()
        self.max_cache_size = cache_size
        self.api_error_count = 0
        self.max_retries = 3
        self.backoff_factor = 1.5
        self.api_quota_limit = 1000
        self.vision_api_calls_today = 0
        self.translation_api_calls_today = 0
        self.last_quota_reset = datetime.now().date()
        self.config_manager = ConfigManager()
        self.translation_history: List[Dict] = []
        self.region_config: Dict = {}
        self.load_region_config()
        self.last_frame_hash = None
        self.frame_similarity_threshold = 0.95
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.last_processed_text = ""
        self.text_cache = {}
        self.use_translate_api = self.config_manager.get_global_setting('use_translate_api', 'true').lower() == 'true'
        self.translator_service = TranslatorService(self.config_manager.get_global_setting('translator_service', 'Google'))
        logger.info("Checking Tesseract OCR availability...")
        self.use_local_ocr = self._check_tesseract_availability()
        logger.info(f"TextProcessor initialization complete. Local OCR enabled: {self.use_local_ocr}, Translate API enabled: {self.use_translate_api}, Translator: {self.translator_service.value}")

    def _check_tesseract_availability(self) -> bool:
        """Check if Tesseract OCR is available."""
        logger.info("Checking Tesseract OCR availability...")
        
        # Try multiple methods to check Tesseract
        try:
            # Method 1: Try to get version directly
            try:
                version = pytesseract.get_tesseract_version()
                logger.info(f"Tesseract OCR is available (version: {version}) and will be used for pre-filtering")
                return True
            except Exception as e1:
                logger.warning(f"Method 1 failed: {str(e1)}")
                
                # Method 2: Try to find tesseract executable
                import shutil
                tesseract_path = shutil.which('tesseract')
                if tesseract_path:
                    logger.info(f"Found Tesseract at: {tesseract_path}")
                    # Try to get version using subprocess
                    import subprocess
                    try:
                        result = subprocess.run(['tesseract', '--version'], 
                                             capture_output=True, 
                                             text=True, 
                                             check=True)
                        version = result.stdout.split('\n')[0]
                        logger.info(f"Tesseract OCR is available (version: {version}) and will be used for pre-filtering")
                        return True
                    except subprocess.CalledProcessError as e2:
                        logger.warning(f"Method 2 failed: {str(e2)}")
                else:
                    logger.warning("Tesseract executable not found in PATH")
                
                # Method 3: Try to set tesseract path explicitly
                try:
                    # Common installation paths
                    possible_paths = [
                        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                        r'/usr/bin/tesseract',
                        r'/usr/local/bin/tesseract'
                    ]
                    
                    for path in possible_paths:
                        if os.path.exists(path):
                            pytesseract.pytesseract.tesseract_cmd = path
                            try:
                                version = pytesseract.get_tesseract_version()
                                logger.info(f"Tesseract OCR is available (version: {version}) at {path}")
                                return True
                            except Exception:
                                continue
                except Exception as e3:
                    logger.warning(f"Method 3 failed: {str(e3)}")
                
                raise Exception("All methods to check Tesseract failed")
                
        except Exception as e:
            logger.warning(
                f"Tesseract OCR is not available. Error: {str(e)}. "
                "Local OCR pre-filtering will be disabled. "
                "To enable it, please ensure Tesseract OCR is installed and in your PATH. "
                "See README.md for installation instructions."
            )
            return False

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better text detection."""
        # Resize image while maintaining aspect ratio
        max_dimension = 1024
        height, width = image.shape[:2]
        if max(height, width) > max_dimension:
            scale = max_dimension / max(height, width)
            image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh)

        return denoised

    def calculate_frame_hash(self, image: np.ndarray) -> str:
        """Calculate perceptual hash of the image."""
        # Resize to 8x8 and convert to grayscale
        small = cv2.resize(image, (8, 8))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        
        # Calculate average
        avg = gray.mean()
        
        # Create hash
        hash_str = ''.join(['1' if pixel > avg else '0' for pixel in gray.flatten()])
        return hash_str

    def calculate_similarity(self, hash1: str, hash2: str) -> float:
        """Calculate similarity between two hashes."""
        if not hash1 or not hash2:
            return 0.0
        return sum(c1 == c2 for c1, c2 in zip(hash1, hash2)) / len(hash1)

    def local_ocr_check(self, image: np.ndarray) -> bool:
        """Use Tesseract to check if image contains text."""
        if not self.use_local_ocr:
            return True  # Skip local OCR check if Tesseract is not available
            
        try:
            text = pytesseract.image_to_string(image)
            return bool(text.strip())
        except Exception as e:
            logger.warning(f"Local OCR check failed: {str(e)}")
            return True  # Return True to allow processing if OCR fails

    def detect_text(self, image: np.ndarray) -> str:
        """Detect text in an image with optimizations."""
        try:
            # Calculate frame hash
            current_hash = self.calculate_frame_hash(image)
            
            # Check if frame is similar to last processed frame
            if self.last_frame_hash:
                similarity = self.calculate_similarity(current_hash, self.last_frame_hash)
                if similarity > self.frame_similarity_threshold:
                    return self.last_processed_text

            # Preprocess image
            processed_image = self.preprocess_image(image)

            # Use Tesseract OCR only if enabled
            if self.use_local_ocr:
                try:
                    text = pytesseract.image_to_string(processed_image)
                    if text.strip():
                        lines = text.strip().split('\n')
                        if len(lines) > 0:
                            lines[0] = lines[0] + ':'
                            result = '\n'.join(lines)
                            self.last_frame_hash = current_hash
                            self.last_processed_text = result
                            return result
                except Exception as e:
                    logger.warning(f"Tesseract OCR failed: {str(e)}. Falling back to Cloud Vision API.")

            # Use Cloud Vision API if Tesseract is disabled or failed
            if not self.vision_client:
                return ""

            # Prepare image for API
            _, encoded_image = cv2.imencode('.png', processed_image)
            content = encoded_image.tobytes()
            vision_image = vision.Image(content=content)

            # Make API call with retry logic
            for attempt in range(self.max_retries):
                try:
                    response = self.vision_client.text_detection(image=vision_image)
                    texts = response.text_annotations
                    
                    if response.error.message:
                        raise Exception(response.error.message)
                    
                    if texts:
                        lines = texts[0].description.split('\n')
                        if len(lines) > 0:
                            lines[0] = lines[0] + ':'
                            result = '\n'.join(lines)
                            self.last_frame_hash = current_hash
                            self.last_processed_text = result
                            self.increment_vision_api_calls()  # Increment counter only when using Vision API
                            return result
                    
                    self.last_frame_hash = current_hash
                    self.last_processed_text = ""
                    return ""
                    
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        raise
                    time.sleep(self.backoff_factor ** attempt)
                    
        except Exception as e:
            logger.error(f"Text detection error: {str(e)}", exc_info=True)
            return ""

    def translate_text(self, text: str, target_language: str, source_language: Optional[str] = None) -> str:
        """Translate text to the target language."""
        if not text:
            return ""

        cache_key = f"{text}_{target_language}_{source_language}_{self.translator_service.value}"
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]

        try:
            if self.use_translate_api and self.translate_client:
                if not self.check_api_quota():
                    return text
                translation = self.translate_client.translate(
                    text,
                    target_language=target_language,
                    source_language=source_language
                )
                translated_text = translation['translatedText']
                self.increment_translation_api_calls()
            else:
                # Use web-based translation based on selected service
                translated_text = self._web_translate(text, target_language, source_language)

            # Cache the result
            if len(self.translation_cache) >= self.max_cache_size:
                self.translation_cache.popitem(last=False)
            self.translation_cache[cache_key] = translated_text
            
            # Save to history
            self.translation_history.append({
                'original': text,
                'translated': translated_text,
                'language': target_language,
                'service': self.translator_service.value
            })
            self._save_translation_history()
            
            return translated_text
        except Exception as e:
            logger.error(f"Translation error: {str(e)}", exc_info=True)
            self.api_error_count += 1
            return text

    def _web_translate(self, text: str, target_language: str, source_language: Optional[str] = None) -> str:
        """Translate text using web-based translation services."""
        encoded_text = quote(text)
        
        if self.translator_service.value == TranslatorService.GOOGLE.value:
            url = f"https://translate.google.com/m?hl={target_language}&sl={source_language or 'auto'}&tl={target_language}&ie=UTF-8&prev=_m&q={encoded_text}"
            return self._translate_with_google(url)
        elif self.translator_service.value == TranslatorService.DEEPL.value:
            url = f"https://www.deepl.com/translator#{source_language or 'auto'}/{target_language}/{encoded_text}"
            return self._translate_with_deepl(url)
        else:
            raise ValueError(f"Unsupported translation service: {self.translator_service.value}")

    def _translate_with_google(self, url: str) -> str:
        """Translate using Google Translate web interface."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return self._extract_translation_from_html(response.text, 'google')
        raise Exception(f"Google translation failed with status code: {response.status_code}")

    def _translate_with_deepl(self, url: str) -> str:
        """Translate using DeepL web interface."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return self._extract_translation_from_html(response.text, 'deepl')
        raise Exception(f"DeepL translation failed with status code: {response.status_code}")

    def _extract_translation_from_html(self, html_content: str, service: str) -> str:
        """Extract translation from web service's HTML response."""
        try:
            if service == 'google':
                start_marker = '<div class="result-container">'
                end_marker = '</div>'
            elif service == 'deepl':
                start_marker = '<div class="lmt__target_textarea">'
                end_marker = '</div>'
            else:
                raise ValueError(f"Unsupported service: {service}")

            start_idx = html_content.find(start_marker)
            if start_idx == -1:
                logger.warning(f"Could not find start marker for {service} translation")
                return ""
                
            start_idx += len(start_marker)
            end_idx = html_content.find(end_marker, start_idx)
            
            if end_idx == -1:
                logger.warning(f"Could not find end marker for {service} translation")
                return ""
                
            translation = html_content[start_idx:end_idx].strip()
            # Clean up HTML entities and extra whitespace
            translation = html.unescape(translation)
            translation = ' '.join(translation.split())
            return translation
        except Exception as e:
            logger.error(f"Error extracting translation from HTML: {str(e)}")
            return ""

    def set_translator_service(self, service: TranslatorService):
        """Set the translation service to use."""
        self.translator_service = service
        self.config_manager.set_global_setting('translator_service', service.value)
        logger.info(f"Translation service set to: {service.value}")

    def set_use_translate_api(self, use_api: bool):
        """Set whether to use the Translate API or web-based translation."""
        self.use_translate_api = use_api
        self.config_manager.set_global_setting('use_translate_api', str(use_api).lower())
        logger.info(f"Translate API usage set to: {use_api}")

    def _save_translation_history(self):
        try:
            with open('translation_history.json', 'w', encoding='utf-8') as f:
                json.dump(self.translation_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving translation history: {str(e)}", exc_info=True)

    def save_region_config(self, region: Tuple[int, int, int, int]) -> None:
        """Save region configuration."""
        try:
            self.config_manager.save_area('1', region[0], region[1], region[2], region[3])
            self.region_config['1'] = {
                'x': region[0],
                'y': region[1],
                'width': region[2],
                'height': region[3]
            }
            with open('region_config.json', 'w') as f:
                json.dump(self.region_config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving region config: {str(e)}", exc_info=True)

    def load_region_config(self) -> Optional[Tuple[int, int, int, int]]:
        """Load region configuration."""
        try:
            area = self.config_manager.get_area('1')
            if area:
                self.region_config['1'] = {
                    'x': area['x'],
                    'y': area['y'],
                    'width': area['width'],
                    'height': area['height']
                }
                return (
                    area['x'],
                    area['y'],
                    area['width'],
                    area['height']
                )
            return None
        except Exception as e:
            logger.error(f"Error loading region config: {str(e)}", exc_info=True)
            self.region_config = {}
            return None

    def reset_quota_if_new_day(self) -> None:
        """Reset API quota if it's a new day."""
        current_date = datetime.now().date()
        if current_date > self.last_quota_reset:
            self.vision_api_calls_today = 0
            self.translation_api_calls_today = 0
            self.last_quota_reset = current_date

    def check_api_quota(self) -> bool:
        """Check if API quota is available."""
        self.reset_quota_if_new_day()
        return (self.vision_api_calls_today + self.translation_api_calls_today) < self.api_quota_limit

    def increment_vision_api_calls(self) -> None:
        """Increment Vision API call count."""
        self.vision_api_calls_today += 1

    def increment_translation_api_calls(self) -> None:
        """Increment Translation API call count."""
        self.translation_api_calls_today += 1