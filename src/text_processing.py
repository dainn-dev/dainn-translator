from typing import Dict, List, Optional, Tuple
import os
import json
import time
import html
from datetime import datetime
from google.cloud import translate_v2 as translate
from google.cloud import vision
from google.cloud import speech
import numpy as np
from collections import OrderedDict
from src.config_manager import ConfigManager
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import platform
import cv2
import tempfile
import wave
import pyaudio

logger = logging.getLogger(__name__)

class TextProcessor:
    """Handle text translation and history logging."""
    
    def __init__(self, translate_client: Optional[translate.Client], vision_client: Optional[vision.ImageAnnotatorClient] = None, cache_size: int = 1000000):
        logger.info("Initializing TextProcessor...")
        self.translate_client = translate_client
        self.vision_client = vision_client
        self.speech_client = speech.SpeechClient() if os.getenv('GOOGLE_APPLICATION_CREDENTIALS') else None
        self.translation_cache = OrderedDict()
        self.max_cache_size = cache_size
        self.api_error_count = 0
        self.max_retries = 3
        self.backoff_factor = 1.5
        self.api_quota_limit = 1000
        self.translation_api_calls_today = 0
        self.vision_api_calls_today = 0
        self.speech_api_calls_today = 0
        self.last_quota_reset = datetime.now().date()
        self.config_manager = ConfigManager()
        self.translation_history: List[Dict] = []
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.use_local_ocr = False
        self.use_speech_to_text = False
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.available_devices = self.list_input_devices()
        self.selected_device_index = self._find_stereo_mix()
        logger.info("TextProcessor initialization complete.")

    def list_input_devices(self):
        """List available input devices and return them as a list of (index, name) tuples."""
        devices = []
        try:
            info = self.audio.get_host_api_info_by_index(0)
            numdevices = info.get('deviceCount')
            for i in range(0, numdevices):
                device = self.audio.get_device_info_by_host_api_device_index(0, i)
                if device.get('maxInputChannels') > 0:
                    devices.append((i, device.get('name')))
                    logger.info(f"Found input device: {device.get('name')} (index: {i})")
        except Exception as e:
            logger.error(f"Error listing input devices: {str(e)}", exc_info=True)
        return devices

    def _find_stereo_mix(self):
        """Find Stereo Mix device index if available."""
        for index, name in self.available_devices:
            if "stereo mix" in name.lower() or "what u hear" in name.lower():
                logger.info(f"Found Stereo Mix device: {name} (index: {index})")
                return index
        logger.warning("Stereo Mix device not found. Using default input device.")
        return None

    def start_recording(self):
        """Start recording audio for speech-to-text."""
        if not self.speech_client or self.is_recording:
            return

        self.frames = []
        self.is_recording = True
        logger.info(f"Starting audio recording using device index: {self.selected_device_index}")
        
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=self.selected_device_index,
                frames_per_buffer=1024,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
            logger.info("Audio recording started successfully")
        except Exception as e:
            logger.error(f"Error starting audio recording: {str(e)}", exc_info=True)
            self.is_recording = False
            if self.stream:
                self.stream.close()
                self.stream = None

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback function to collect audio data."""
        if self.is_recording:
            self.frames.append(in_data)
            logger.debug(f"Collected {len(in_data)} bytes of audio data")
        return (in_data, pyaudio.paContinue)

    def stop_recording(self):
        """Stop recording audio and process speech-to-text."""
        if not self.is_recording:
            return ""

        self.is_recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        if not self.frames:
            logger.warning("No audio frames collected")
            return ""

        logger.info(f"Processing {len(self.frames)} audio frames")
        
        # Save audio to temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            with wave.open(temp_file.name, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b''.join(self.frames))

            # Read the audio file
            with open(temp_file.name, 'rb') as audio_file:
                content = audio_file.read()

            # Process with Speech-to-Text API
            audio = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-US"
            )

            try:
                response = self.speech_client.recognize(config=config, audio=audio)
                self.speech_api_calls_today += 1
                text = " ".join([result.alternatives[0].transcript for result in response.results])
                logger.info(f"Speech-to-text result: {text}")
                return text
            except Exception as e:
                logger.error(f"Error in speech-to-text: {str(e)}", exc_info=True)
                return ""

        return ""

    def detect_text(self, image: np.ndarray) -> str:
        """Detect text in an image using Google Cloud Vision API or Speech-to-Text."""
        if self.use_speech_to_text:
            if not self.is_recording:
                self.start_recording()
            return ""  # Return empty string while recording, actual text will be processed when recording stops

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

            # Cache the result
            if len(self.translation_cache) >= self.max_cache_size:
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
            self.api_error_count += 1
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
            self.speech_api_calls_today = 0
            self.last_quota_reset = current_date

    def check_api_quota(self) -> bool:
        """Check if API quota is available."""
        self.reset_quota_if_new_day()
        return self.translation_api_calls_today < self.api_quota_limit

    def increment_translation_api_calls(self) -> None:
        """Increment the translation API call counter."""
        self.translation_api_calls_today += 1