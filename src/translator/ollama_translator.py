"""Ollama translator for translation using Ollama API."""
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class OllamaTranslator:
    """Translator using Ollama API."""
    
    def __init__(self, api_url: str = "http://localhost:11434", model_name: str = None):
        """
        Initialize Ollama translator.
        
        Args:
            api_url: Base URL for Ollama API (default: http://localhost:11434)
            model_name: Model name to use. If None, will auto-detect from API.
        """
        self.api_url = api_url.rstrip('/')
        # Convert empty string to None for auto-detect
        self.model_name = model_name if model_name and model_name.strip() else None
        self._detected_model = None
        self._working_endpoint = None  # Cache the working endpoint
        logger.info(f"Initialized Ollama translator with API URL: {self.api_url}, Model: {self.model_name or 'auto-detect'}")
        
        # Auto-detect model if not specified
        if not self.model_name:
            self._detect_model()
        
        # Try to detect the correct endpoint (non-blocking, will try on first request if not found)
        # Don't block initialization - endpoint will be detected on first translation if needed
        try:
            self._detect_endpoint()
        except Exception as e:
            logger.debug(f"Endpoint detection during initialization failed (will retry on first request): {str(e)}")
            self._working_endpoint = None
    
    def translate(self, text: str, source_language: str, target_language: str) -> str:
        """
        Translate text using Ollama.
        
        Args:
            text: Text to translate
            source_language: Source language code (e.g., 'en', 'ja')
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
            
            # Get model name (use detected model if available, otherwise use configured or default)
            model = self._get_model_name()
            logger.debug(f"Using Ollama model: {model} for translation")
            
            # Prepare request payload
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "stream": False
            }
            
            # Try to use cached working endpoint, or try different endpoints
            endpoints_to_try = []
            if self._working_endpoint:
                endpoints_to_try.append(self._working_endpoint)
            
            # Add common endpoint variations for Ollama
            base = self.api_url
            
            # Ollama uses /api/chat endpoint
            endpoints_to_try.extend([
                f"{base}/api/chat",  # Standard Ollama endpoint
                f"{base}/v1/chat/completions",  # OpenAI-compatible endpoint
                f"{base}/chat/completions",
                f"{base}/api/v1/chat/completions",
            ])
            
            # Remove duplicates while preserving order
            seen = set()
            unique_endpoints = []
            for ep in endpoints_to_try:
                if ep not in seen:
                    seen.add(ep)
                    unique_endpoints.append(ep)
            
            # Try each endpoint (limit to first 3 to avoid long waits)
            last_error = None
            max_endpoints_to_try = 3
            for endpoint in unique_endpoints[:max_endpoints_to_try]:
                try:
                    response = requests.post(
                        endpoint,
                        json=payload,
                        timeout=20  # 20 seconds per endpoint should be enough
                    )
                    
                    # Check if this endpoint works
                    if response.status_code == 200:
                        result = response.json()
                        
                        # Check for API errors in the response
                        if 'error' in result:
                            error_msg = result.get('error', 'Unknown error')
                            logger.warning(f"API error from {endpoint}: {error_msg}")
                            last_error = f"API error: {error_msg}"
                            continue
                        
                        # Cache the working endpoint
                        if endpoint != self._working_endpoint:
                            self._working_endpoint = endpoint
                            logger.info(f"Found working endpoint: {endpoint}")
                        
                        # Extract translated text from response
                        # Ollama /api/chat format
                        if 'message' in result and 'content' in result['message']:
                            translated_text = result['message']['content'].strip()
                            logger.debug(f"Translation successful: {text[:50]}... -> {translated_text[:50]}...")
                            return translated_text
                        # OpenAI-compatible format
                        elif 'choices' in result and len(result['choices']) > 0:
                            translated_text = result['choices'][0]['message']['content'].strip()
                            logger.debug(f"Translation successful: {text[:50]}... -> {translated_text[:50]}...")
                            return translated_text
                        elif 'content' in result:
                            # Some APIs return content directly
                            translated_text = result['content'].strip()
                            logger.debug(f"Translation successful: {text[:50]}... -> {translated_text[:50]}...")
                            return translated_text
                        else:
                            logger.warning(f"Unexpected response format from {endpoint}: {result}")
                            last_error = f"Unexpected response format: {result}"
                            continue
                    elif response.status_code == 404:
                        # Endpoint doesn't exist, try next one
                        continue
                    else:
                        # Other error, log and try next
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
                "\n".join(f"  - {ep}" for ep in unique_endpoints[:10]) +
                (f"\n  ... and {len(unique_endpoints) - 10} more" if len(unique_endpoints) > 10 else "")
            )
            logger.error(error_details)
            logger.error(f"API URL: {self.api_url}, Model: {model}")
            return text
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API error: {str(e)}")
            return text
        except Exception as e:
            logger.error(f"Translation error: {str(e)}", exc_info=True)
            return text
    
    def _detect_model(self) -> Optional[str]:
        """
        Auto-detect the model name from Ollama API.
        
        Returns:
            Model name if detected, None otherwise
        """
        try:
            # Ollama uses /api/tags endpoint
            response = requests.get(f"{self.api_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Ollama returns models in 'models' array
                if 'models' in data and len(data['models']) > 0:
                    model_name = data['models'][0].get('name', 'llama2')
                    self._detected_model = model_name
                    logger.info(f"Auto-detected model: {model_name}")
                    return model_name
        except Exception as e:
            logger.debug(f"Model auto-detection failed: {str(e)}")
        
        # Fallback to default
        self._detected_model = "llama2"
        logger.info("Using default model name: llama2")
        return "llama2"
    
    def _get_model_name(self) -> str:
        """Get the model name to use for API requests."""
        if self.model_name:
            return self.model_name
        elif self._detected_model:
            return self._detected_model
        else:
            # Try to detect again if not already detected
            self._detect_model()
            return self._detected_model or "llama2"
    
    def _detect_endpoint(self) -> Optional[str]:
        """
        Try to detect the correct chat endpoint by testing common endpoints.
        
        Returns:
            Working endpoint if found, None otherwise
        """
        # Build list of endpoints to try
        test_endpoints = [
            f"{self.api_url}/api/chat",  # Standard Ollama endpoint
            f"{self.api_url}/v1/chat/completions",  # OpenAI-compatible endpoint
            f"{self.api_url}/chat/completions",
            f"{self.api_url}/api/v1/chat/completions",
        ]
        
        # Simple test payload
        test_payload = {
            "model": self._get_model_name(),
            "messages": [{"role": "user", "content": "test"}],
            "stream": False
        }
        
        logger.debug(f"Trying to detect endpoint. Testing {len(test_endpoints)} endpoints...")
        for endpoint in test_endpoints:
            try:
                response = requests.post(endpoint, json=test_payload, timeout=5)
                result = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                
                # Check if it's a successful response (200) and not an error
                if response.status_code == 200:
                    if 'error' in result:
                        # Endpoint exists but returned an error
                        error_msg = result.get('error', 'Unknown error')
                        logger.debug(f"Endpoint {endpoint} returned error: {error_msg}")
                        continue
                    elif 'message' in result or 'choices' in result or 'content' in result:
                        # Valid response with expected format
                        self._working_endpoint = endpoint
                        logger.info(f"Detected working endpoint: {endpoint}")
                        return endpoint
            except requests.exceptions.Timeout:
                logger.debug(f"Endpoint {endpoint} timed out")
                continue
            except Exception as e:
                logger.debug(f"Endpoint {endpoint} failed: {str(e)}")
                continue
        
        logger.warning("Could not detect working endpoint. Will try all endpoints on first request.")
        logger.info(f"Tested endpoints: {test_endpoints[:5]}...")  # Log first 5
        return None
    
    def test_connection(self) -> bool:
        """
        Test if Ollama API is accessible.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try different model endpoint variations
            model_endpoints = [
                f"{self.api_url}/api/tags",  # Standard Ollama endpoint
                f"{self.api_url}/v1/models",  # OpenAI-compatible endpoint
                f"{self.api_url}/api/models",
            ]
            
            for endpoint in model_endpoints:
                try:
                    response = requests.get(endpoint, timeout=5)
                    if response.status_code == 200:
                        # Also try to detect model while testing
                        self._detect_model()
                        # Try to detect chat endpoint
                        self._detect_endpoint()
                        return True
                except:
                    continue
            
            # If model endpoint doesn't work, try a simple chat request
            return self._detect_endpoint() is not None
        except Exception as e:
            logger.debug(f"Ollama connection test failed: {str(e)}")
            return False

