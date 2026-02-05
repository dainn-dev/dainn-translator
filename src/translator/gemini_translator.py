"""Gemini translator for translation using Google Gemini API."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import google-generativeai
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not available. Install it with: pip install google-generativeai")


class GeminiTranslator:
    """Translator using Google Gemini API."""
    
    def __init__(self, api_key: str = "", model_name: str = "gemini-1.5-flash"):
        """
        Initialize Gemini translator.
        
        Args:
            api_key: Google Gemini API key
            model_name: Gemini model name (e.g., 'gemini-1.5-flash', 'gemini-pro', 'gemini-1.5-pro')
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai package is not installed. Install it with: pip install google-generativeai")
        
        if not api_key:
            raise ValueError("Gemini API key is required")
        
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=api_key)
        
        # Initialize the model
        try:
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Initialized Gemini translator with {model_name} model")
        except Exception as e:
            logger.warning(f"Failed to initialize {model_name}, trying gemini-1.5-flash: {e}")
            try:
                # Fallback to gemini-1.5-flash if specified model fails
                if model_name != 'gemini-1.5-flash':
                    self.model = genai.GenerativeModel('gemini-1.5-flash')
                    self.model_name = 'gemini-1.5-flash'
                    logger.info("Initialized Gemini translator with gemini-1.5-flash model (fallback)")
                else:
                    raise
            except Exception as e2:
                logger.error(f"Failed to initialize Gemini model: {e2}")
                raise
    
    def translate(self, text: str, source_language: str, target_language: str) -> str:
        """
        Translate text using Gemini.
        
        Args:
            text: Text to translate
            source_language: Source language code (e.g., 'en', 'ja', 'auto')
            target_language: Target language code (e.g., 'vi', 'en')
        
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return ""
        
        try:
            # Map language codes to full names for better translation
            lang_map = {
                'en': 'English',
                'vi': 'Vietnamese',
                'ja': 'Japanese',
                'ko': 'Korean',
                'zh-cn': 'Chinese',
                'fr': 'French',
                'es': 'Spanish'
            }
            
            # Handle 'auto' source language detection
            if source_language == 'auto':
                source_lang_name = 'the detected language'
            else:
                source_lang_name = lang_map.get(source_language, source_language)
            
            target_lang_name = lang_map.get(target_language, target_language)
            
            # Create translation prompt
            prompt = f"Translate the following text from {source_lang_name} to {target_lang_name}. Only return the translated text, nothing else:\n\n{text}"
            
            # Generate translation
            response = self.model.generate_content(prompt)
            
            # Extract translated text
            if response and response.text:
                translated_text = response.text.strip()
                logger.debug(f"Gemini translation successful: '{text[:50]}...' -> '{translated_text[:50]}...'")
                return translated_text
            else:
                logger.warning("Gemini returned empty response")
                return text
                
        except Exception as e:
            logger.error(f"Gemini translation error: {str(e)}", exc_info=True)
            return text
    
    def test_connection(self) -> bool:
        """
        Test if Gemini API is accessible.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try a simple translation test
            test_response = self.model.generate_content("Translate 'hello' to Vietnamese")
            if test_response and test_response.text:
                logger.info("Gemini connection test successful")
                return True
            else:
                logger.warning("Gemini connection test returned empty response")
                return False
        except Exception as e:
            logger.debug(f"Gemini connection test failed: {str(e)}")
            return False

