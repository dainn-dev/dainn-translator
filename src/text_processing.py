from typing import Dict, List, Optional, Tuple
import os
import json
import time
import html
from datetime import datetime
import cv2
import numpy as np
import pyautogui
import easyocr
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
        self.use_local_ocr = True  # Set this before initializing EasyOCR
        self.easyocr_reader = None
        logger.info("Initializing EasyOCR...")
        self.initialize_easyocr()
        logger.info(f"TextProcessor initialization complete. Local OCR enabled: {self.use_local_ocr}, Translate API enabled: {self.use_translate_api}, Translator: {self.translator_service.value}")

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
        """Use EasyOCR to check if image contains text."""
        try:
            results = self.easyocr_reader.readtext(image, detail=0)
            return bool(results)
        except Exception as e:
            logger.warning(f"EasyOCR check failed: {str(e)}")
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

            # Use EasyOCR for text detection
            try:
                results = self.easyocr_reader.readtext(processed_image, detail=0)
                if results:
                    text = '\n'.join(results)
                    self.last_frame_hash = current_hash
                    self.last_processed_text = text
                    return text
            except Exception as e:
                logger.warning(f"EasyOCR failed: {str(e)}. Falling back to Cloud Vision API.")

            # Use Cloud Vision API if EasyOCR failed
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
                            self.increment_vision_api_calls()
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

    def initialize_easyocr(self):
        """Initialize EasyOCR reader."""
        try:
            # Initialize EasyOCR with supported languages
            self.easyocr_reader = easyocr.Reader(['en'])  # Start with English only for testing
            logger.info("EasyOCR initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {str(e)}")
            self.easyocr_reader = None
            self.use_local_ocr = False