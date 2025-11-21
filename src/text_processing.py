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

class TextProcessor:
    """Handle text translation and history logging."""
    
    def __init__(self, translate_client: Optional[translate.Client], vision_client: Optional[vision.ImageAnnotatorClient] = None, cache_size: int = None):
        logger.info("Initializing TextProcessor...")
        self.translate_client = translate_client
        self.vision_client = vision_client
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
        """Detect text in an image using Google Cloud Vision API."""
        if not self.vision_client:
            return ""

        try:
            # Convert numpy array to bytes
            success, encoded_image = cv2.imencode('.png', image)
            if not success:
                return ""
            content = encoded_image.tobytes()

            # Create image object
            image = vision.Image(content=content)

            # Perform text detection
            response = self.vision_client.text_detection(image=image)
            texts = response.text_annotations

            if texts:
                self.vision_api_calls_today += 1
                return texts[0].description.strip()
            return ""

        except Exception as e:
            logger.error(f"Error detecting text: {str(e)}", exc_info=True)
            return ""

    def translate_text(self, text: str, target_language: str, source_language: Optional[str] = None) -> str:
        """Translate text to the target language."""
        if not text:
            return ""

        cache_key = f"{text}_{target_language}_{source_language}"
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]

        try:
            if not self.check_api_quota():
                return text
                
            translation = self.translate_client.translate(
                text,
                target_language=target_language,
                source_language=source_language
            )
            translated_text = translation['translatedText']
            self.increment_translation_api_calls()

            # Cache the result (no size limit if max_cache_size is None)
            if self.max_cache_size is not None and len(self.translation_cache) >= self.max_cache_size:
                self.translation_cache.popitem(last=False)
            self.translation_cache[cache_key] = translated_text
            
            # Save to history
            self.translation_history.append({
                'original': text,
                'translated': translated_text,
                'language': target_language,
                'service': 'Google'
            })
            self._save_translation_history()
            
            return translated_text
        except Exception as e:
            logger.error(f"Translation error: {str(e)}", exc_info=True)
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