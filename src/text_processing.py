from typing import Dict, List, Optional, Tuple
import os
import json
import sys
import io
from datetime import datetime
from google.cloud import translate_v2 as translate
from google.cloud import vision
import numpy as np
from collections import OrderedDict
from src.config_manager import ConfigManager
import logging
import cv2

logger = logging.getLogger(__name__)

# Helper function to safely import owocr, catching DLL errors
def safe_import_owocr():
    """Safely import owocr, catching DLL errors that shouldn't prevent Windows OCR."""
    try:
        # Suppress stderr to catch DLL errors
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            from owocr import OCR
            stderr_output = sys.stderr.getvalue()
            sys.stderr = old_stderr
            
            # Check if there were DLL errors in stderr
            if stderr_output and 'dll' in stderr_output.lower():
                logger.warning("DLL error detected during import (this is expected if some DLLs are missing)")
                # The import succeeded, so Windows OCR should still work
                return OCR, True
            else:
                return OCR, True
        except ImportError as e:
            sys.stderr = old_stderr
            # ImportError means the module is not installed, not a DLL issue
            logger.debug(f"owocr not installed: {str(e)}")
            return None, False
        except Exception as e:
            sys.stderr = old_stderr
            error_str = str(e).lower()
            if 'dll' in error_str:
                # DLL error - this is expected and shouldn't prevent Windows OCR
                logger.warning(f"DLL error during import (expected): {str(e)}")
                # Don't try to import again - it will likely fail the same way
                return None, False
            else:
                # Other errors - log and return None
                logger.warning(f"Error importing owocr: {str(e)}")
                return None, False
    except Exception as e:
        logger.warning(f"Unexpected error in safe_import_owocr: {str(e)}")
        return None, False

# OCR and translator availability flags
TESSERACT_AVAILABLE = False
PADDLEOCR_AVAILABLE = False
EASYOCR_AVAILABLE = False
WINDOW_OCR_AVAILABLE = False
WINDOW_OCR_OWOCR = False
OWOCR = None  # Initialize to None - will be imported lazily when needed

# Try to import optional dependencies
_OPTIONAL_IMPORTS = {
    'pytesseract': ('TESSERACT_AVAILABLE', 'pytesseract not available. Install it to use local OCR mode.'),
    'paddleocr': ('PADDLEOCR_AVAILABLE', 'PaddleOCR not available. Install it to use PaddleOCR mode.'),
    'easyocr': ('EASYOCR_AVAILABLE', 'EasyOCR not available. Install it to use EasyOCR mode.'),
}

for module_name, (flag_name, warning_msg) in _OPTIONAL_IMPORTS.items():
    try:
        if module_name == 'pytesseract':
            import pytesseract
        elif module_name == 'paddleocr':
            from paddleocr import PaddleOCR
        elif module_name == 'easyocr':
            import easyocr
        globals()[flag_name] = True
    except ImportError:
        globals()[flag_name] = False
        logger.warning(warning_msg)

# Windows OCR - lazy import to avoid hanging during module load
if os.name == 'nt':  # Windows only
    WINDOW_OCR_AVAILABLE = True  # Assume available, will verify when used
    WINDOW_OCR_OWOCR = True  # Assume owocr will work, will verify when used
    logger.debug("Windows OCR: Marked as potentially available (lazy import)")
else:
    logger.warning("Windows OCR is only available on Windows.")


# Function to check OCR engine availability
def check_ocr_availability(ocr_mode: str) -> bool:
    """Check if an OCR engine is available."""
    try:
        if ocr_mode == 'tesseract':
            return TESSERACT_AVAILABLE
        elif ocr_mode == 'paddleocr':
            return PADDLEOCR_AVAILABLE
        elif ocr_mode == 'window_ocr':
            return WINDOW_OCR_AVAILABLE
        elif ocr_mode == 'easyocr':
            return EASYOCR_AVAILABLE
        return False
    except (NameError, AttributeError) as e:
        # Handle case where variables might not be defined
        logger.warning(f"OCR availability variable not found for {ocr_mode}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error checking OCR availability for {ocr_mode}: {str(e)}", exc_info=True)
        return False

# Function to get installation command for OCR engine
def get_ocr_install_command(ocr_mode: str) -> str:
    """Get the pip install command for an OCR engine."""
    install_commands = {
        'tesseract': 'pip install pytesseract',
        'paddleocr': 'pip install paddlepaddle paddleocr',
        'window_ocr': 'pip install owocr[winocr]',
        'easyocr': 'pip install easyocr'
    }
    return install_commands.get(ocr_mode, '')

class TextProcessor:
    """Handle text translation and history logging."""
    
    def __init__(self, translate_client: Optional[translate.Client] = None, 
                 vision_client: Optional[vision.ImageAnnotatorClient] = None,
                 llm_studio_translator: Optional['LLMStudioTranslator'] = None,
                 libretranslate_translator: Optional['LibreTranslateTranslator'] = None,
                 ollama_translator: Optional['OllamaTranslator'] = None,
                 chatgpt_translator: Optional['ChatGPTTranslator'] = None,
                 gemini_translator: Optional['GeminiTranslator'] = None,
                 mistral_translator: Optional['MistralTranslator'] = None,
                 cache_size: int = None):
        logger.info("Initializing TextProcessor...")
        self.translate_client = translate_client
        self.vision_client = vision_client
        self.llm_studio_translator = llm_studio_translator
        self.libretranslate_translator = libretranslate_translator
        self.ollama_translator = ollama_translator
        self.chatgpt_translator = chatgpt_translator
        self.gemini_translator = gemini_translator
        self.mistral_translator = mistral_translator
        self.translation_cache = OrderedDict()
        self.max_cache_size = cache_size  # None means unlimited
        self.api_quota_limit = None  # None means unlimited
        self.translation_api_calls_today = 0
        self.vision_api_calls_today = 0
        self.last_quota_reset = datetime.now().date()
        self.config_manager = ConfigManager()
        self.translation_history: List[Dict] = []
        logger.info("TextProcessor initialization complete.")
    
    @staticmethod
    def _prepare_image_for_ocr(image: np.ndarray) -> np.ndarray:
        """Prepare image for OCR processing (ensure RGB format)."""
        # pyautogui.screenshot() returns RGB, so use it directly
        if len(image.shape) == 3 and image.shape[2] == 3:
            return image
        return image

    def detect_text(self, image: np.ndarray) -> str:
        """Detect text in an image using Google Cloud Vision API, Tesseract OCR, PaddleOCR, Windows OCR, or EasyOCR."""
        try:
            # Validate image input
            if image is None or image.size == 0:
                logger.warning("Empty or invalid image passed to detect_text")
                return ""
            
            # Ensure image is in correct format (numpy array)
            if not isinstance(image, np.ndarray):
                logger.error(f"Image is not a numpy array: {type(image)}")
                return ""
            
            # Log image info for debugging
            logger.debug(f"Image shape: {image.shape}, dtype: {image.dtype}, min: {image.min()}, max: {image.max()}")
            
            translation_mode = self.config_manager.get_translation_mode()
            
            # Use local OCR for non-Google translation modes
            if translation_mode in ('local', 'libretranslate', 'ollama', 'chatgpt', 'gemini', 'mistral'):
                ocr_mode = self.config_manager.get_ocr_mode()
                logger.debug(f"Using OCR mode: {ocr_mode}, Translation mode: {translation_mode}")
                
                # OCR mode to method mapping
                ocr_handlers = {
                    'paddleocr': self._detect_text_paddleocr,
                    'window_ocr': self._detect_text_window_ocr,
                    'easyocr': self._detect_text_easyocr,
                }
                
                handler = ocr_handlers.get(ocr_mode, self._detect_text_tesseract)
                return handler(image)
            else:
                # Use Google Cloud Vision API
                return self._detect_text_google_vision(image)
        except Exception as e:
            logger.error(f"Error in detect_text: {str(e)}", exc_info=True)
            return ""
    
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
            
            # Prepare image for OCR (ensure RGB format)
            image_rgb = self._prepare_image_for_ocr(image)
            
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
            
            # Prepare image for OCR (ensure RGB format)
            image_rgb = self._prepare_image_for_ocr(image)
            
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
    
    def _detect_text_window_ocr(self, image: np.ndarray) -> str:
        """Detect text using Windows OCR."""
        if os.name != 'nt':
            logger.error("Windows OCR not available. This feature is only available on Windows.")
            return ""
        
        try:
            # Lazy import owocr to avoid hanging during module load
            global OWOCR, WINDOW_OCR_OWOCR, WINDOW_OCR_AVAILABLE
            
            # Try to import owocr if not already imported
            if OWOCR is None:
                try:
                    OWOCR, import_success = safe_import_owocr()
                    if import_success and OWOCR is not None:
                        WINDOW_OCR_AVAILABLE = True
                        WINDOW_OCR_OWOCR = True
                    else:
                        # Try winrt as fallback
                        try:
                            import winrt.windows.media.ocr as ocr
                            import winrt.windows.storage.streams as streams
                            import winrt.windows.graphics.imaging as imaging
                            WINDOW_OCR_AVAILABLE = True
                            WINDOW_OCR_OWOCR = False
                        except Exception:
                            WINDOW_OCR_AVAILABLE = False
                            logger.error("Windows OCR not available. Install owocr or winrt to use Windows OCR mode.")
                            return ""
                except Exception as e:
                    logger.error(f"Error importing Windows OCR: {str(e)}")
                    WINDOW_OCR_AVAILABLE = False
                    return ""
            
            if not WINDOW_OCR_AVAILABLE:
                logger.error("Windows OCR not available.")
                return ""
            
            # Use owocr wrapper (preferred method)
            if WINDOW_OCR_OWOCR and OWOCR is not None:
                if not hasattr(self, '_window_ocr_instance'):
                    logger.info("Initializing Windows OCR via owocr...")
                    self._window_ocr_instance = OWOCR(engine='winocr')
                    logger.info("Windows OCR initialized successfully")
                
                # Convert numpy array to PIL Image
                from PIL import Image
                image_rgb = self._prepare_image_for_ocr(image)
                pil_image = Image.fromarray(image_rgb)
                
                # Save to temporary file
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    pil_image.save(tmp_file.name)
                    tmp_path = tmp_file.name
                
                try:
                    result = self._window_ocr_instance.recognize(tmp_path)
                    detected_text = result if isinstance(result, str) else '\n'.join(result).strip()
                    logger.debug(f"Windows OCR detected text: '{detected_text[:100]}...' (length: {len(detected_text)})")
                    return detected_text
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
            else:
                # Fallback: Use winrt directly (Windows Runtime API) - more complex
                logger.warning("Windows OCR: Direct winrt API not fully implemented. Please install owocr for better support.")
                return ""
                
        except Exception as e:
            logger.error(f"Error detecting text with Windows OCR: {str(e)}", exc_info=True)
            error_str = str(e).lower()
            if 'not found' in error_str or 'install' in error_str:
                error_msg = (
                    "Windows OCR is not available or not configured correctly.\n\n"
                    "Please install it using:\npip install owocr[winocr]\n\n"
                    "Or for direct Windows Runtime API:\npip install winrt\n\n"
                    "Note: Windows OCR is only available on Windows."
                )
                logger.error(error_msg)
                if not hasattr(self, '_window_ocr_error_shown'):
                    self._window_ocr_error_shown = True
            return ""
    
    def _detect_text_easyocr(self, image: np.ndarray) -> str:
        """Detect text using EasyOCR."""
        if not EASYOCR_AVAILABLE:
            logger.error("EasyOCR not available. Please install easyocr.")
            return ""
        
        try:
            # Initialize EasyOCR if not already initialized
            if not hasattr(self, '_easyocr_instance'):
                logger.info("Initializing EasyOCR...")
                # Initialize with common languages (can be customized)
                self._easyocr_instance = easyocr.Reader(['en', 'ja', 'ko', 'zh', 'vi'], gpu=False)
                logger.info("EasyOCR initialized successfully")
            
            # Prepare image for OCR (ensure RGB format)
            image_rgb = self._prepare_image_for_ocr(image)
            
            # Use EasyOCR to extract text
            result = self._easyocr_instance.readtext(image_rgb)
            
            if not result:
                logger.debug("EasyOCR detected no text")
                return ""
            
            # Extract text from EasyOCR result
            # Result format: [[bbox, text, confidence], ...]
            text_lines = []
            for line in result:
                if line and len(line) >= 2:
                    text = line[1] if isinstance(line[1], str) else str(line[1])
                    if text:
                        text_lines.append(text)
            
            detected_text = '\n'.join(text_lines).strip()
            logger.debug(f"EasyOCR detected text: '{detected_text[:100]}...' (length: {len(detected_text)})")
            return detected_text
            
        except Exception as e:
            logger.error(f"Error detecting text with EasyOCR: {str(e)}", exc_info=True)
            error_str = str(e).lower()
            if 'not found' in error_str or 'install' in error_str:
                error_msg = (
                    "EasyOCR is not installed or not configured correctly.\n\n"
                    "Please install it using:\npip install easyocr\n\n"
                    "For more information, visit: https://github.com/JaidedAI/EasyOCR"
                )
                logger.error(error_msg)
                if not hasattr(self, '_easyocr_error_shown'):
                    self._easyocr_error_shown = True
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
            # Translation service mapping
            translation_handlers = {
                'local': (self._translate_with_service, 'llm_studio_translator', 'LLM Studio'),
                'libretranslate': (self._translate_with_service, 'libretranslate_translator', 'LibreTranslate'),
                'ollama': (self._translate_with_service, 'ollama_translator', 'Ollama'),
                'chatgpt': (self._translate_with_service, 'chatgpt_translator', 'ChatGPT'),
                'gemini': (self._translate_with_service, 'gemini_translator', 'Gemini'),
                'mistral': (self._translate_with_service, 'mistral_translator', 'Mistral'),
            }
            
            if translation_mode in translation_handlers:
                handler, translator_attr, service_name = translation_handlers[translation_mode]
                translated_text = handler(text, target_language, source_language, translator_attr, service_name)
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
    
    def _translate_with_service(self, text: str, target_language: str, source_language: Optional[str], 
                                translator_attr: str, service_name: str) -> str:
        """Generic method to translate text using a service translator."""
        translator = getattr(self, translator_attr, None)
        if not translator:
            logger.error(f"{service_name} translator not initialized")
            return text
        
        try:
            # Special handling for Ollama to log model info
            log_level = logger.info if service_name == 'Ollama' else logger.debug
            model_info = ""
            if service_name == 'Ollama' and hasattr(translator, 'model_name') and translator.model_name:
                model_info = f" [Model: {translator.model_name}]"
            elif service_name == 'Ollama' and hasattr(translator, '_get_model_name'):
                try:
                    model = translator._get_model_name()
                    model_info = f" [Model: {model}]"
                except Exception:
                    pass
            
            log_level(f"{service_name} translation{model_info}: '{text[:50]}...' ({source_language} -> {target_language})")
            translated_text = translator.translate(
                text,
                source_language or 'auto',
                target_language
            )
            logger.debug(f"{service_name} translation result: '{translated_text[:50]}...'")
            return translated_text
        except Exception as e:
            logger.error(f"{service_name} translation error: {str(e)}", exc_info=True)
            return text
    
    def set_chatgpt_translator(self, translator: 'ChatGPTTranslator'):
        """Set ChatGPT translator."""
        self._set_translator('chatgpt_translator', translator, 'ChatGPT')
    
    def set_gemini_translator(self, translator: 'GeminiTranslator'):
        """Set Gemini translator."""
        self._set_translator('gemini_translator', translator, 'Gemini')
    
    def set_mistral_translator(self, translator: 'MistralTranslator'):
        """Set Mistral translator."""
        self._set_translator('mistral_translator', translator, 'Mistral')
    
    def _set_translator(self, attr_name: str, translator, service_name: str):
        """Generic method to set a translator."""
        setattr(self, attr_name, translator)
        logger.info(f"{service_name} translator set")

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
        self._update_translator('llm_studio_translator', llm_studio_translator, 'LLM Studio')
    
    def set_libretranslate_translator(self, libretranslate_translator: Optional['LibreTranslateTranslator']) -> None:
        """Update the LibreTranslate translator instance."""
        self._update_translator('libretranslate_translator', libretranslate_translator, 'LibreTranslate')
    
    def set_ollama_translator(self, ollama_translator: Optional['OllamaTranslator']) -> None:
        """Update the Ollama translator instance."""
        self._update_translator('ollama_translator', ollama_translator, 'Ollama')
    
    def _update_translator(self, attr_name: str, translator, service_name: str):
        """Generic method to update a translator instance."""
        logger.info(f"Updating {service_name} translator in TextProcessor")
        setattr(self, attr_name, translator)