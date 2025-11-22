from typing import Dict, List, Optional, Tuple
import os
import json
from datetime import datetime
from google.cloud import translate_v2 as translate
from google.cloud import vision
import numpy as np
from collections import OrderedDict
from src.config_manager import ConfigManager
import logging
import cv2

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available. Install it to use local OCR mode.")

try:
    from src.translator.llm_studio_translator import LLMStudioTranslator
    LLM_STUDIO_AVAILABLE = True
except ImportError:
    LLM_STUDIO_AVAILABLE = False
    logger.warning("LLM Studio translator not available.")

try:
    from src.translator.libretranslate_translator import LibreTranslateTranslator
    LIBRETRANSLATE_AVAILABLE = True
except ImportError:
    LIBRETRANSLATE_AVAILABLE = False
    logger.warning("LibreTranslate translator not available.")

# Try to import PaddleOCR
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    logger.warning("PaddleOCR not available. Install it to use PaddleOCR mode.")

class TextProcessor:
    """Handle text translation and history logging."""
    
    def __init__(self, translate_client: Optional[translate.Client] = None, 
                 vision_client: Optional[vision.ImageAnnotatorClient] = None,
                 llm_studio_translator: Optional['LLMStudioTranslator'] = None,
                 libretranslate_translator: Optional['LibreTranslateTranslator'] = None,
                 cache_size: int = None):
        logger.info("Initializing TextProcessor...")
        self.translate_client = translate_client
        self.vision_client = vision_client
        self.llm_studio_translator = llm_studio_translator
        self.libretranslate_translator = libretranslate_translator
        self.translation_cache = OrderedDict()
        self.max_cache_size = cache_size  # None means unlimited
        self.api_quota_limit = None  # None means unlimited
        self.translation_api_calls_today = 0
        self.vision_api_calls_today = 0
        self.last_quota_reset = datetime.now().date()
        self.config_manager = ConfigManager()
        self.translation_history: List[Dict] = []
        logger.info("TextProcessor initialization complete.")

    def detect_text(self, image: np.ndarray) -> str:
        """Detect text in an image using Google Cloud Vision API, Tesseract OCR, or PaddleOCR."""
        translation_mode = self.config_manager.get_translation_mode()
        
        if translation_mode == 'local' or translation_mode == 'libretranslate':
            # Use local OCR (Tesseract or PaddleOCR) for local mode and libretranslate mode
            ocr_mode = self.config_manager.get_ocr_mode()
            if ocr_mode == 'paddleocr':
                return self._detect_text_paddleocr(image)
            else:
                return self._detect_text_tesseract(image)
        else:
            # Use Google Cloud Vision API
            return self._detect_text_google_vision(image)
    
    def _detect_text_google_vision(self, image: np.ndarray) -> str:
        """Detect text using Google Cloud Vision API."""
        if not self.vision_client:
            return ""

        try:
            # Convert numpy array to bytes
            success, encoded_image = cv2.imencode('.png', image)
            if not success:
                return ""
            content = encoded_image.tobytes()

            # Create image object
            image_obj = vision.Image(content=content)

            # Perform text detection
            response = self.vision_client.text_detection(image=image_obj)
            texts = response.text_annotations

            if texts:
                self.vision_api_calls_today += 1
                return texts[0].description.strip()
            return ""

        except Exception as e:
            logger.error(f"Error detecting text with Google Vision: {str(e)}", exc_info=True)
            return ""
    
    def _detect_text_tesseract(self, image: np.ndarray) -> str:
        """Detect text using Tesseract OCR."""
        if not TESSERACT_AVAILABLE:
            logger.error("Tesseract OCR not available. Please install pytesseract.")
            return ""
        
        try:
            # Configure Tesseract path if set in config
            tesseract_path = self.config_manager.get_global_setting('tesseract_path', '')
            logger.debug(f"Tesseract OCR: path={tesseract_path}, image shape={image.shape}")
            
            if tesseract_path:
                # Validate path
                if not os.path.exists(tesseract_path):
                    error_msg = f"Tesseract path does not exist: {tesseract_path}\nPlease check the path in Settings."
                    logger.error(error_msg)
                    if not hasattr(self, '_tesseract_path_error_shown'):
                        self._tesseract_path_error_shown = True
                    return ""
                
                # Check if it's a file (not a directory)
                if not os.path.isfile(tesseract_path):
                    error_msg = f"Tesseract path is not a file: {tesseract_path}\nPlease select the tesseract.exe file."
                    logger.error(error_msg)
                    if not hasattr(self, '_tesseract_path_error_shown'):
                        self._tesseract_path_error_shown = True
                    return ""
                
                # Check if it's executable (on Windows, check .exe extension)
                if os.name == 'nt' and not tesseract_path.lower().endswith('.exe'):
                    # Try to find tesseract.exe in the same directory
                    dir_path = os.path.dirname(tesseract_path)
                    exe_path = os.path.join(dir_path, 'tesseract.exe')
                    if os.path.exists(exe_path):
                        tesseract_path = exe_path
                        logger.info(f"Using tesseract.exe from directory: {tesseract_path}")
                    else:
                        error_msg = f"Tesseract path should point to tesseract.exe: {tesseract_path}"
                        logger.error(error_msg)
                        return ""
                
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                logger.debug(f"Using Tesseract at: {tesseract_path}")
            
            # Convert image to RGB if needed (Tesseract expects RGB)
            if len(image.shape) == 3 and image.shape[2] == 3:
                # BGR to RGB conversion
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = image
            
            # Use pytesseract to extract text
            text = pytesseract.image_to_string(image_rgb, lang='eng+jpn+kor+chi_sim')
            detected_text = text.strip()
            logger.debug(f"Tesseract OCR detected text: '{detected_text[:100]}...' (length: {len(detected_text)})")
            return detected_text
        except PermissionError as e:
            error_msg = (
                f"Permission denied when accessing Tesseract: {str(e)}\n\n"
                "Possible solutions:\n"
                "1. Run the application as Administrator\n"
                "2. Check if antivirus is blocking Tesseract\n"
                "3. Verify the Tesseract path is correct in Settings\n"
                "4. Try reinstalling Tesseract to a different location"
            )
            logger.error(error_msg)
            if not hasattr(self, '_tesseract_permission_error_shown'):
                self._tesseract_permission_error_shown = True
            return ""
        except Exception as e:
            # Check if it's a TesseractNotFoundError
            error_type = type(e).__name__
            error_str = str(e).lower()
            
            if 'TesseractNotFoundError' in error_type or 'tesseract' in error_str and 'not found' in error_str:
                error_msg = (
                    "Tesseract OCR is not installed or not found in PATH.\n\n"
                    "Please:\n"
                    "1. Download and install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki\n"
                    "2. Add Tesseract to your system PATH, OR\n"
                    "3. Configure the Tesseract path in Settings → LLM Studio Settings"
                )
                logger.error(error_msg)
                # Only log once to avoid spam
                if not hasattr(self, '_tesseract_error_shown'):
                    self._tesseract_error_shown = True
                return ""
            elif 'access is denied' in error_str or 'permission' in error_str:
                error_msg = (
                    f"Access denied when running Tesseract: {str(e)}\n\n"
                    "Possible solutions:\n"
                    "1. Run the application as Administrator\n"
                    "2. Check if antivirus/Windows Defender is blocking Tesseract\n"
                    "3. Verify the Tesseract executable path is correct\n"
                    "4. Try reinstalling Tesseract"
                )
                logger.error(error_msg)
                if not hasattr(self, '_tesseract_permission_error_shown'):
                    self._tesseract_permission_error_shown = True
                return ""
            else:
                logger.error(f"Error detecting text with Tesseract: {str(e)}", exc_info=True)
                return ""
    
    def _detect_text_paddleocr(self, image: np.ndarray) -> str:
        """Detect text using PaddleOCR."""
        if not PADDLEOCR_AVAILABLE:
            logger.error("PaddleOCR not available. Please install paddleocr.")
            return ""
        
        try:
            # Initialize PaddleOCR if not already initialized
            if not hasattr(self, '_paddleocr_instance'):
                logger.info("Initializing PaddleOCR with PP-OCRv4 model...")
                # Use PP-OCRv4 model for better accuracy
                # PP-OCRv4 provides improved accuracy compared to older PP-OCR versions
                # Note: Requires PaddleOCR 2.7.0+ for ocr_version parameter support
                # Note: GPU is automatically detected and used in PaddleOCR 3.x+
                try:
                    # Initialize PaddleOCR with PP-OCRv4 explicitly
                    self._paddleocr_instance = PaddleOCR(
                        ocr_version='PP-OCRv4',
                        lang='en',
                        use_angle_cls=True
                    )
                    logger.info("PaddleOCR initialized successfully with PP-OCRv4 model")
                except Exception as e:
                    # If initialization fails, try without ocr_version (newer versions default to PP-OCRv4)
                    error_msg = str(e).lower()
                    if 'ocr_version' in error_msg or 'unknown argument' in error_msg:
                        logger.warning(f"ocr_version parameter not supported, using default PP-OCRv4: {e}")
                        self._paddleocr_instance = PaddleOCR(
                            lang='en',
                            use_angle_cls=True
                        )
                        logger.info("PaddleOCR initialized successfully (using default PP-OCRv4 model)")
                    else:
                        logger.error(f"Error initializing PaddleOCR with PP-OCRv4: {e}", exc_info=True)
                        raise
            
            # Convert numpy array to RGB if needed (PaddleOCR expects RGB)
            if len(image.shape) == 3 and image.shape[2] == 3:
                # BGR to RGB conversion
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = image
            
            # Use PaddleOCR to extract text
            result = self._paddleocr_instance.ocr(image_rgb, cls=True)
            
            if not result or not result[0]:
                logger.debug("PaddleOCR detected no text")
                return ""
            
            # Extract text from PaddleOCR result
            # Result format: [[[bbox], (text, confidence)], ...]
            text_lines = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0] if isinstance(line[1], (list, tuple)) else line[1]
                    if text:
                        text_lines.append(text)
            
            detected_text = '\n'.join(text_lines).strip()
            logger.debug(f"PaddleOCR detected text: '{detected_text[:100]}...' (length: {len(detected_text)})")
            return detected_text
            
        except Exception as e:
            logger.error(f"Error detecting text with PaddleOCR: {str(e)}", exc_info=True)
            # Check if it's an initialization error
            error_str = str(e).lower()
            if 'not found' in error_str or 'install' in error_str:
                error_msg = (
                    "PaddleOCR is not installed or not configured correctly.\n\n"
                    "Please install it using:\npip install paddlepaddle paddleocr\n\n"
                    "For more information, visit: https://github.com/PaddlePaddle/PaddleOCR"
                )
                logger.error(error_msg)
                if not hasattr(self, '_paddleocr_error_shown'):
                    self._paddleocr_error_shown = True
            return ""

    def translate_text(self, text: str, target_language: str, source_language: Optional[str] = None) -> str:
        """Translate text to the target language."""
        if not text:
            return ""

        translation_mode = self.config_manager.get_translation_mode()
        
        cache_key = f"{text}_{target_language}_{source_language}_{translation_mode}"
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]

        try:
            if translation_mode == 'local':
                # Use LLM Studio for local translation
                translated_text = self._translate_text_llm_studio(text, target_language, source_language)
                service_name = 'LLM Studio'
            elif translation_mode == 'libretranslate':
                # Use LibreTranslate for translation
                translated_text = self._translate_text_libretranslate(text, target_language, source_language)
                service_name = 'LibreTranslate'
            else:
                # Use Google Cloud Translate
                if not self.check_api_quota():
                    return text
                    
                translation = self.translate_client.translate(
                    text,
                    target_language=target_language,
                    source_language=source_language
                )
                translated_text = translation['translatedText']
                self.increment_translation_api_calls()
                service_name = 'Google'

            # Cache the result (no size limit if max_cache_size is None)
            if self.max_cache_size is not None and len(self.translation_cache) >= self.max_cache_size:
                self.translation_cache.popitem(last=False)
            self.translation_cache[cache_key] = translated_text
            
            # Save to history
            self.translation_history.append({
                'original': text,
                'translated': translated_text,
                'language': target_language,
                'service': service_name
            })
            self._save_translation_history()
            
            return translated_text
        except Exception as e:
            logger.error(f"Translation error: {str(e)}", exc_info=True)
            return text
    
    def _translate_text_llm_studio(self, text: str, target_language: str, source_language: Optional[str] = None) -> str:
        """Translate text using LLM Studio."""
        if not self.llm_studio_translator:
            logger.error("LLM Studio translator not initialized")
            return text
        
        try:
            logger.debug(f"LLM Studio translation: '{text[:50]}...' ({source_language} -> {target_language})")
            translated_text = self.llm_studio_translator.translate(
                text,
                source_language or 'auto',
                target_language
            )
            logger.debug(f"LLM Studio translation result: '{translated_text[:50]}...'")
            return translated_text
        except Exception as e:
            logger.error(f"LLM Studio translation error: {str(e)}", exc_info=True)
            return text
    
    def _translate_text_libretranslate(self, text: str, target_language: str, source_language: Optional[str] = None) -> str:
        """Translate text using LibreTranslate."""
        if not self.libretranslate_translator:
            logger.error("LibreTranslate translator not initialized")
            return text
        
        try:
            logger.debug(f"LibreTranslate translation: '{text[:50]}...' ({source_language} -> {target_language})")
            translated_text = self.libretranslate_translator.translate(
                text,
                source_language or 'auto',
                target_language
            )
            logger.debug(f"LibreTranslate translation result: '{translated_text[:50]}...'")
            return translated_text
        except Exception as e:
            logger.error(f"LibreTranslate translation error: {str(e)}", exc_info=True)
            return text

    def _save_translation_history(self):
        """Save translation history to file."""
        try:
            history_file = os.path.join(os.getenv('APPDATA'), 'DainnScreenTranslator', 'translation_history.json')
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.translation_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving translation history: {str(e)}")

    def reset_quota_if_new_day(self) -> None:
        """Reset API quota if it's a new day."""
        current_date = datetime.now().date()
        if current_date > self.last_quota_reset:
            self.translation_api_calls_today = 0
            self.vision_api_calls_today = 0
            self.last_quota_reset = current_date

    def check_api_quota(self) -> bool:
        """Check if API quota is available."""
        self.reset_quota_if_new_day()
        # None means unlimited, always return True
        if self.api_quota_limit is None:
            return True
        return self.translation_api_calls_today < self.api_quota_limit

    def increment_translation_api_calls(self) -> None:
        """Increment the translation API call counter."""
        self.translation_api_calls_today += 1
    
    def set_llm_studio_translator(self, llm_studio_translator: Optional['LLMStudioTranslator']) -> None:
        """Update the LLM Studio translator instance."""
        logger.info("Updating LLM Studio translator in TextProcessor")
        self.llm_studio_translator = llm_studio_translator
    
    def set_libretranslate_translator(self, libretranslate_translator: Optional['LibreTranslateTranslator']) -> None:
        """Update the LibreTranslate translator instance."""
        logger.info("Updating LibreTranslate translator in TextProcessor")
        self.libretranslate_translator = libretranslate_translator