"""LibreTranslate translator for translation using LibreTranslate API."""
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LibreTranslateTranslator:
    """Translator using LibreTranslate API."""
    
    def __init__(self, api_url: str = "http://localhost:5000"):
        """
        Initialize LibreTranslate translator.
        
        Args:
            api_url: Base URL for LibreTranslate API (default: http://localhost:5000)
        """
        self.api_url = api_url.rstrip('/')
        logger.info(f"Initialized LibreTranslate translator with API URL: {self.api_url}")
    
    def translate(self, text: str, source_language: str, target_language: str) -> str:
        """
        Translate text using LibreTranslate.
        
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
            # Map language codes to LibreTranslate format
            # LibreTranslate uses standard ISO 639-1 codes
            lang_map = {
                'en': 'en',
                'vi': 'vi',
                'ja': 'ja',
                'ko': 'ko',
                'zh-cn': 'zh',
                'fr': 'fr',
                'es': 'es'
            }
            
            # Handle 'auto' source language detection
            if source_language == 'auto':
                source_lang_code = 'auto'
            else:
                source_lang_code = lang_map.get(source_language, source_language)
            
            target_lang_code = lang_map.get(target_language, target_language)
            
            # LibreTranslate API endpoint
            endpoint = f"{self.api_url}/translate"
            
            # Prepare request payload
            payload = {
                "q": text,
                "source": source_lang_code,
                "target": target_lang_code,
                "format": "text"
            }
            
            # Make API request
            response = requests.post(
                endpoint,
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                translated_text = result.get('translatedText', text)
                logger.debug(f"LibreTranslate translation successful: '{text[:50]}...' -> '{translated_text[:50]}...'")
                return translated_text
            else:
                error_msg = response.text
                try:
                    error_json = response.json()
                    error_msg = error_json.get('error', error_msg)
                except:
                    pass
                logger.error(f"LibreTranslate API error (HTTP {response.status_code}): {error_msg}")
                return text
                
        except requests.exceptions.RequestException as e:
            logger.error(f"LibreTranslate API error: {str(e)}")
            return text
        except Exception as e:
            logger.error(f"Translation error: {str(e)}", exc_info=True)
            return text
    
    def test_connection(self) -> bool:
        """
        Test if LibreTranslate API is accessible.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to get supported languages
            endpoint = f"{self.api_url}/languages"
            response = requests.get(endpoint, timeout=5)
            
            if response.status_code == 200:
                languages = response.json()
                logger.info(f"LibreTranslate connection successful. Found {len(languages)} supported languages.")
                return True
            else:
                logger.warning(f"LibreTranslate connection test returned HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.debug(f"LibreTranslate connection test failed: {str(e)}")
            return False
        except Exception as e:
            logger.debug(f"LibreTranslate connection test error: {str(e)}")
            return False

