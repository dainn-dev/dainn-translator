"""Mistral translator for translation using Mistral AI API."""
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MistralTranslator:
    """Translator using Mistral AI API."""
    
    def __init__(self, api_url: str = "https://api.mistral.ai/v1", api_key: str = "", model_name: str = "mistral-tiny"):
        """
        Initialize Mistral translator.
        
        Args:
            api_url: Base URL for Mistral API (default: https://api.mistral.ai/v1)
            api_key: API key for authentication
            model_name: Model name to use (default: mistral-tiny)
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.model_name = model_name
        logger.info(f"Initialized Mistral translator with API URL: {self.api_url}, Model: {self.model_name}")
    
    def translate(self, text: str, source_language: str, target_language: str) -> str:
        """
        Translate text using Mistral.
        
        Args:
            text: Text to translate
            source_language: Source language code (e.g., 'en', 'ja')
            target_language: Target language code (e.g., 'vi', 'en')
        
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return ""
        
        if not self.api_key:
            logger.error("Mistral API key is not set")
            return text
        
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
            
            # Prepare request payload
            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 1000
            }
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # Try different endpoint variations
            endpoints_to_try = [
                f"{self.api_url}/chat/completions",
                f"{self.api_url}/v1/chat/completions",
            ]
            
            # Remove duplicates while preserving order
            seen = set()
            unique_endpoints = []
            for ep in endpoints_to_try:
                if ep not in seen:
                    seen.add(ep)
                    unique_endpoints.append(ep)
            
            # Try each endpoint
            last_error = None
            for endpoint in unique_endpoints:
                try:
                    response = requests.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # Check for API errors in the response
                        if 'error' in result:
                            error_msg = result.get('error', 'Unknown error')
                            logger.warning(f"API error from {endpoint}: {error_msg}")
                            last_error = f"API error: {error_msg}"
                            continue
                        
                        # Extract translated text from response
                        if 'choices' in result and len(result['choices']) > 0:
                            translated_text = result['choices'][0]['message']['content'].strip()
                            logger.debug(f"Translation successful: {text[:50]}... -> {translated_text[:50]}...")
                            return translated_text
                        else:
                            logger.warning(f"Unexpected response format from {endpoint}: {result}")
                            last_error = f"Unexpected response format: {result}"
                            continue
                    elif response.status_code == 401:
                        error_msg = "Invalid API key"
                        logger.error(f"Authentication failed: {error_msg}")
                        return text
                    elif response.status_code == 404:
                        continue
                    else:
                        error_data = response.text
                        try:
                            error_json = response.json()
                            error_data = error_json.get('error', error_data)
                        except:
                            pass
                        last_error = f"HTTP {response.status_code}: {error_data}"
                        continue
                        
                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    continue
            
            # If we get here, all endpoints failed
            error_details = (
                f"Translation failed. All endpoints returned errors.\n\n"
                f"Last error: {last_error}\n\n"
                f"Tried {len(unique_endpoints)} endpoints:\n" + 
                "\n".join(f"  - {ep}" for ep in unique_endpoints)
            )
            logger.error(error_details)
            return text
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Mistral API error: {str(e)}")
            return text
        except Exception as e:
            logger.error(f"Translation error: {str(e)}", exc_info=True)
            return text
    
    def test_connection(self) -> bool:
        """
        Test if Mistral API is accessible.
        
        Returns:
            True if connection is successful, False otherwise
        """
        if not self.api_key:
            return False
        
        try:
            # Simple test request
            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 5
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            endpoint = f"{self.api_url}/chat/completions"
            response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return True
            elif response.status_code == 401:
                logger.error("Invalid API key")
                return False
            else:
                logger.debug(f"Connection test returned status {response.status_code}")
                return False
        except Exception as e:
            logger.debug(f"Mistral connection test failed: {str(e)}")
            return False

