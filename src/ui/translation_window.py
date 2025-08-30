import html
import pyautogui
import numpy as np
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QApplication, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QFont, QColor, QCursor
from src.config_manager import ConfigManager
from src.text_processing import TextProcessor
from typing import Tuple, Optional, Callable, Dict, List
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
import time
import threading
import hashlib
import cv2

logger = logging.getLogger(__name__)

class TranslationCache:
    """Cache for translations to avoid redundant API calls."""
    
    def __init__(self, max_size: int = None, expiration_minutes: int = 20):
        self.cache = OrderedDict()
        self.max_size = max_size  # None means unlimited
        self.expiration_minutes = expiration_minutes
        self.lock = threading.Lock()
        
        # Start the cleanup timer
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_expired_entries)
        self.cleanup_timer.start(60000)  # Check every minute
        
    def get_key(self, text: str, source_lang: str, target_lang: str) -> str:
        """Generate a cache key from text and language pair."""
        return f"{text}|{source_lang}|{target_lang}"
        
    def get(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """Get cached translation if available."""
        with self.lock:
            key = self.get_key(text, source_lang, target_lang)
            if key in self.cache:
                entry = self.cache[key]
                # Check if entry has expired
                if time.time() - entry['timestamp'] > (self.expiration_minutes * 60):
                    self.cache.pop(key)
                    return None
                # Move to end (most recently used)
                self.cache.pop(key)
                self.cache[key] = entry
                return entry['translation']
            return None
            
    def put(self, text: str, source_lang: str, target_lang: str, translation: str):
        """Add translation to cache."""
        with self.lock:
            key = self.get_key(text, source_lang, target_lang)
            entry = {
                'translation': translation,
                'timestamp': time.time()
            }
            if key in self.cache:
                self.cache.pop(key)
            elif self.max_size is not None and len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)  # Remove least recently used
            self.cache[key] = entry
            
    def cleanup_expired_entries(self):
        """Remove expired entries from cache."""
        with self.lock:
            current_time = time.time()
            expired_keys = []
            for key, entry in self.cache.items():
                if current_time - entry['timestamp'] > (self.expiration_minutes * 60):
                    expired_keys.append(key)
            
            for key in expired_keys:
                self.cache.pop(key, None)
                
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
                
    def clear_all(self):
        """Clear all cache entries."""
        with self.lock:
            self.cache.clear()
            logger.info("Translation cache cleared")

class RateLimiter:
    """Rate limiter for API calls."""
    
    def __init__(self, max_calls: int, time_window: int):
        self.max_calls = max_calls
        self.time_window = time_window  # in seconds
        self.calls: List[float] = []
        self.lock = threading.Lock()
        
    def can_make_request(self) -> bool:
        """Check if a new request can be made."""
        with self.lock:
            now = time.time()
            # Remove old calls
            self.calls = [t for t in self.calls if now - t < self.time_window]
            return len(self.calls) < self.max_calls
            
    def add_request(self):
        """Record a new request."""
        with self.lock:
            self.calls.append(time.time())

class TranslationWindow(QMainWindow):
    """Window to display real-time translations."""
    
    def __init__(self, on_select_region: Callable, settings: Dict, config_manager: ConfigManager, 
                 window_id: Optional[str] = None, text_processor: Optional[TextProcessor] = None):
        super().__init__()
        self.setWindowTitle("Kết quả dịch")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.on_select_region = on_select_region
        self.config_manager = config_manager
        self.window_id = window_id
        self.text_processor = text_processor
        self.settings = settings
        
        # Initialize translation cache and rate limiter
        self.translation_cache = TranslationCache(max_size=None, expiration_minutes=20)  # Unlimited cache with 20min expiration
        self.rate_limiter = RateLimiter(max_calls=1000, time_window=86400)  # 1000 calls per day
        
        # Set minimum size
        self.setMinimumSize(300, 200)
        
        # Initialize UI
        self.init_ui()
        self.init_translation()

    def init_ui(self):
        """Initialize the user interface."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout with margins
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(0)

        # Create main frame with background
        bg_color = QColor(self.settings['background_color'])
        try:
            opacity = float(self.settings.get('opacity', '0.85'))
            alpha = int(opacity * 255) if 0.0 <= opacity <= 1.0 else 217
        except (ValueError, TypeError):
            alpha = 217
        bg_color.setAlpha(alpha)
        rgba_str = f"rgba({bg_color.red()}, {bg_color.green()}, {bg_color.blue()}, {bg_color.alpha()})"

        self.main_frame = QWidget(self)
        self.main_frame.setStyleSheet(f"background-color: {rgba_str}; border-radius: 5px;")
        self.main_layout.addWidget(self.main_frame)
        
        # Frame layout for content
        self.frame_layout = QVBoxLayout(self.main_frame)
        self.frame_layout.setContentsMargins(0, 0, 0, 0)
        self.frame_layout.setSpacing(0)

        # Top bar container for labels
        self.top_bar_container = QWidget()
        self.top_bar_layout = QHBoxLayout(self.top_bar_container)
        self.top_bar_layout.setContentsMargins(40, 8, 40, 8)  # Add margins for buttons
        self.top_bar_layout.setSpacing(8)

        # API labels container with fixed width
        self.api_labels_container = QWidget()
        self.api_labels_container.setFixedWidth(300)  # Set fixed width for the container
        self.api_labels_layout = QHBoxLayout(self.api_labels_container)
        self.api_labels_layout.setContentsMargins(0, 0, 0, 0)
        self.api_labels_layout.setSpacing(8)
        self.api_labels_layout.setAlignment(Qt.AlignLeft)  # Align labels to the left

        # Vision API counter
        self.vision_counter_label = QLabel("Vision API: 0 requests")
        self.vision_counter_label.setStyleSheet(
            "color: rgba(255, 255, 255, 150); background-color: transparent; font-size: 10px; padding: 2px;"
        )
        self.vision_counter_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.vision_counter_label.setFixedWidth(120)  # Set fixed width for Vision API label
        self.api_labels_layout.addWidget(self.vision_counter_label)

        # Translation API counter
        self.translation_counter_label = QLabel("Translation API: 0 requests")
        self.translation_counter_label.setStyleSheet(
            "color: rgba(255, 255, 255, 150); background-color: transparent; font-size: 10px; padding: 2px;"
        )
        self.translation_counter_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.translation_counter_label.setFixedWidth(150)  # Set fixed width for Translation API label
        self.api_labels_layout.addWidget(self.translation_counter_label)

        # Add API labels container to top bar
        self.top_bar_layout.addWidget(self.api_labels_container)
        self.top_bar_layout.setAlignment(Qt.AlignLeft)  # Align the container to the left

        # Add top bar to frame layout
        self.frame_layout.addWidget(self.top_bar_container)

        # Capture button (fixed in top-left)
        self.capture_button = QPushButton("▶", self)
        self.capture_button.setFixedSize(24, 24)
        self.capture_button.setStyleSheet(
            f"QPushButton {{ background-color: rgba(255,255,255,40); color: #00ff00; border: 1px solid #00ff00; border-radius: 12px; }}"
            f"QPushButton:hover {{ background-color: rgba(255,255,255,100); color: #ffffff; }}"
        )
        self.capture_button.clicked.connect(self.toggle_capture)
        self.capture_button.raise_()

        # Close button (fixed in top-right)
        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet(
            f"QPushButton {{ background-color: rgba(255,255,255,40); color: #ff0000; border: 1px solid #ff0000; border-radius: 12px; }}"
            f"QPushButton:hover {{ background-color: rgba(255,255,255,100); color: #ffffff; }}"
        )
        self.close_button.clicked.connect(self.close_program)
        self.close_button.raise_()

        # Content area with scroll
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(2)
        self.content_layout.setAlignment(Qt.AlignTop)  # Align entire layout to top

        # Name label
        self.name_label = QLabel("")
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        font = QFont(self.settings['font_family'], int(self.settings['font_size']))
        if self.settings['font_style'] == 'bold':
            font.setBold(True)
        elif self.settings['font_style'] == 'italic':
            font.setItalic(True)
        self.name_label.setFont(font)
        self.name_label.setStyleSheet(
            f"color: {self.settings['name_color']}; background-color: transparent;"
            "padding: 2px;"
        )
        self.content_layout.addWidget(self.name_label)

        # Dialogue label
        self.dialogue_label = QLabel("")
        self.dialogue_label.setWordWrap(True)
        self.dialogue_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.dialogue_label.setFont(font)
        self.dialogue_label.setStyleSheet(
            f"color: {self.settings['dialogue_color']}; background-color: transparent;"
            "padding: 2px;"
        )
        self.content_layout.addWidget(self.dialogue_label)

        # Add stretch to push any extra space to the bottom
        self.content_layout.addStretch()

        # Add content widget to frame layout
        self.frame_layout.addWidget(self.content_widget)

        # Resize button in bottom-right corner with padding
        self.resize_button = QPushButton("↘", self)
        self.resize_button.setFixedSize(20, 20)
        self.resize_button.setStyleSheet(
            f"QPushButton {{ background-color: {rgba_str}; color: #00ff00; border: 1px solid #00ff00; border-radius: 10px; }}"
            f"QPushButton:hover {{ background-color: rgba(255,255,255,50); color: #00ff00; }}"
        )
        self.resize_button.setCursor(Qt.SizeFDiagCursor)
        self.resize_button.mousePressEvent = self.start_resize
        self.resize_button.raise_()

        # Position buttons
        self.position_buttons()

    def init_translation(self):
        """Initialize translation variables and timer."""
        self.is_dragging = False
        self.drag_start_pos = None
        self.is_resizing = False
        self.resize_start_pos = None
        self.resize_start_size = None
        self.min_width = 200
        self.min_height = 100
        self.resize_timer = QTimer()
        self.resize_timer.setInterval(16)
        self.resize_timer.timeout.connect(self.update_resize)

        self.running = False
        self.region = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.continuous_translate)
        self.last_text = None
        self.last_translated_text = ""
        self.last_target_language = self.settings['target_language']
        self.hide()
        self.processing = False
        self.frame_queue = []
        self.max_queue_size = 3
        self.min_interval = 100  # Minimum interval in milliseconds
        self.max_interval = 1000  # Maximum interval in milliseconds
        self.current_interval = self.min_interval
        self.consecutive_empty_frames = 0
        self.is_capturing = False
        
        # Frame change detection variables
        self.last_frame_hash = None
        self.last_frame = None
        self.consecutive_same_frames = 0
        self.max_same_frames = 10  # After 10 same frames, increase interval
        self.frame_change_threshold = 0.95  # Hash similarity threshold
        self.min_change_threshold = 0.85  # Minimum similarity to consider frames different

    def get_frame_hash(self, frame: np.ndarray) -> str:
        """Generate a hash for frame change detection."""
        try:
            # Resize frame to reduce computation
            small_frame = cv2.resize(frame, (64, 64))
            # Convert to grayscale
            gray_frame = cv2.cvtColor(small_frame, cv2.COLOR_RGB2GRAY)
            # Generate hash
            frame_hash = hashlib.md5(gray_frame.tobytes()).hexdigest()
            return frame_hash
        except Exception as e:
            logger.error(f"Error generating frame hash: {str(e)}")
            return None

    def frames_are_similar(self, hash1: str, hash2: str) -> bool:
        """Check if two frame hashes are similar (indicating similar content)."""
        if not hash1 or not hash2:
            return False
        return hash1 == hash2
    
    def calculate_frame_similarity(self, frame1: np.ndarray, frame2: np.ndarray) -> float:
        """Calculate similarity between two frames using structural similarity index."""
        try:
            # Resize frames to same size for comparison
            size = (128, 128)
            frame1_resized = cv2.resize(frame1, size)
            frame2_resized = cv2.resize(frame2, size)
            
            # Convert to grayscale
            gray1 = cv2.cvtColor(frame1_resized, cv2.COLOR_RGB2GRAY)
            gray2 = cv2.cvtColor(frame2_resized, cv2.COLOR_RGB2GRAY)
            
            # Calculate structural similarity
            from skimage.metrics import structural_similarity as ssim
            similarity = ssim(gray1, gray2)
            return similarity
        except Exception as e:
            logger.error(f"Error calculating frame similarity: {str(e)}")
            return 0.0

    def position_buttons(self):
        """Position the buttons."""
        # Position capture button in top-left corner with 15px margin
        self.capture_button.move(15, 15)
        
        # Position close button in top-right corner
        self.close_button.move(self.width() - self.close_button.width() - 15, 15)
        
        # Position resize button in bottom-right corner
        self.resize_button.move(
            self.width() - self.resize_button.width() - 15,
            self.height() - self.resize_button.height() - 15
        )

    def resizeEvent(self, event):
        """Handle window resize events."""
        super().resizeEvent(event)
        self.position_buttons()
        # Update content width
        content_width = self.width() - 40  # Account for margins
        self.name_label.setFixedWidth(content_width)
        self.dialogue_label.setFixedWidth(content_width)

    def showEvent(self, event):
        """Handle show events."""
        super().showEvent(event)
        self.position_buttons()
        # Update request counter when window is shown
        if self.text_processor:
            self.vision_counter_label.setText(f"Vision API: {self.text_processor.vision_api_calls_today} requests")

    def close_program(self):
        """Close the translation window."""
        try:
            logger.info("close_program called")
            # Stop the translation process
            self.running = False
            self.is_capturing = False
            
            # Stop timers
            if hasattr(self, 'timer') and self.timer:
                self.timer.stop()
            if hasattr(self, 'resize_timer') and self.resize_timer:
                self.resize_timer.stop()
            if hasattr(self, 'translation_cache') and hasattr(self.translation_cache, 'cleanup_timer'):
                self.translation_cache.cleanup_timer.stop()
            
            # Call the main window's close handler if available
            if hasattr(self, 'area_id') and hasattr(self, 'main_window_close_handler'):
                logger.info(f"Calling main window close handler for area_id: {self.area_id}")
                self.main_window_close_handler(self.area_id)
            
            # Close the window
            self.close()
            
        except Exception as e:
            logger.error(f"Error in close_program: {str(e)}", exc_info=True)
            # Still try to close the window
            self.close()

    def closeEvent(self, event):
        """Handle window close event."""
        try:
            # Stop the translation process
            self.running = False
            self.is_capturing = False
            
            # Stop timers
            if hasattr(self, 'timer') and self.timer:
                self.timer.stop()
            if hasattr(self, 'resize_timer') and self.resize_timer:
                self.resize_timer.stop()
            if hasattr(self, 'translation_cache') and hasattr(self.translation_cache, 'cleanup_timer'):
                self.translation_cache.cleanup_timer.stop()
            
            # Accept the close event
            event.accept()
            
        except Exception as e:
            logger.error(f"Error in translation window closeEvent: {str(e)}", exc_info=True)
            # Still accept the close event even if there's an error
            event.accept()

    def toggle_capture(self):
        """Toggle the capture state."""
        self.is_capturing = not self.is_capturing
        if self.is_capturing:
            self.capture_button.setText("⏸")
            self.capture_button.setStyleSheet(
                f"QPushButton {{ background-color: rgba(255,255,255,40); color: #ff0000; border: 1px solid #ff0000; border-radius: 12px; }}"
                f"QPushButton:hover {{ background-color: rgba(255,255,255,100); color: #ffffff; }}"
            )
            self.running = True
            self.timer.start(int(self.current_interval))
        else:
            self.capture_button.setText("▶")
            self.capture_button.setStyleSheet(
                f"QPushButton {{ background-color: rgba(255,255,255,40); color: #00ff00; border: 1px solid #00ff00; border-radius: 12px; }}"
                f"QPushButton:hover {{ background-color: rgba(255,255,255,100); color: #ffffff; }}"
            )
            self.running = False
            self.timer.stop()

    def continuous_translate(self):
        """Continuously translate screen region text with optimizations."""
        if not self.running or not self.region or not self.text_processor or self.processing or not self.is_capturing:
            return

        try:
            self.processing = True
            x, y, w, h = self.region
            
            # Capture screen in a separate thread
            def capture_screen():
                screenshot = pyautogui.screenshot(region=(x, y, w, h))
                return np.array(screenshot)
            
            # Use ThreadPoolExecutor for screen capture
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(capture_screen)
                screenshot = future.result()
            
            # Check for frame changes before calling Vision API
            current_frame_hash = self.get_frame_hash(screenshot)
            
            # Use both hash comparison and structural similarity for better detection
            frames_similar = False
            if self.last_frame is not None and self.last_frame_hash is not None:
                # Quick hash check first
                if self.frames_are_similar(current_frame_hash, self.last_frame_hash):
                    frames_similar = True
                else:
                    # If hash is different, check structural similarity for subtle changes
                    similarity = self.calculate_frame_similarity(screenshot, self.last_frame)
                    frames_similar = similarity > self.min_change_threshold
            
            # If frame hasn't changed significantly, skip Vision API call
            if frames_similar:
                self.consecutive_same_frames += 1
                # Increase interval if we've had many consecutive same frames
                if self.consecutive_same_frames > self.max_same_frames:
                    self.current_interval = min(self.current_interval * 1.2, self.max_interval)
                    self.timer.setInterval(int(self.current_interval))
                self.processing = False
                return
            
            # Frame has changed, reset counters and call Vision API
            self.consecutive_same_frames = 0
            self.current_interval = self.min_interval
            self.timer.setInterval(int(self.current_interval))
            self.last_frame_hash = current_frame_hash
            self.last_frame = screenshot.copy()
            
            # Process the frame with Vision API
            text = self.text_processor.detect_text(screenshot)
            
            # Update Vision API counter
            if text and not self.text_processor.use_local_ocr:
                self.vision_counter_label.setText(f"Vision API: {self.text_processor.vision_api_calls_today} requests")
            
            # Skip if text is unchanged
            if text == self.last_text:
                self.update_text(self.last_translated_text)
                self.processing = False
                return
            
            # Initialize translation variables
            cached_translation = None
            
            # Check cache first
            cached_translation = self.translation_cache.get(
                text, 
                self.settings['source_language'],
                self.settings['target_language']
            )
            
            if cached_translation:
                self.update_text(cached_translation)
                self.last_text = text
                self.last_translated_text = cached_translation
                self.processing = False
                return
            
            # Check rate limit before making API call
            if not self.rate_limiter.can_make_request():
                logger.warning("Rate limit reached, skipping translation")
                self.update_text(self.last_translated_text)
                self.processing = False
                return
            
            # Translate text in a separate thread
            def translate_text():
                self.rate_limiter.add_request()
                translated = self.text_processor.translate_text(
                    text, 
                    self.settings['target_language'], 
                    self.settings['source_language']
                )
                # Only update Translation API counter if we actually made an API call
                if not cached_translation:
                    self.translation_counter_label.setText(f"Translation API: {self.text_processor.translation_api_calls_today} requests")
                return translated
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(translate_text)
                translated_text = future.result()
            
            # Cache the translation
            self.translation_cache.put(
                text,
                self.settings['source_language'],
                self.settings['target_language'],
                translated_text
            )
            
            # Update display
            self.update_text(translated_text)
            self.last_text = text
            self.last_translated_text = translated_text
            
            # Adjust timer interval based on content
            if not text:
                self.consecutive_empty_frames += 1
                if self.consecutive_empty_frames > 5:
                    self.current_interval = min(self.current_interval * 1.5, self.max_interval)
            else:
                self.consecutive_empty_frames = 0
                self.current_interval = self.min_interval
            
            self.timer.setInterval(int(self.current_interval))
            
        except Exception as e:
            logger.error(f"Translation error: {str(e)}", exc_info=True)
            self.update_text(self.last_translated_text)
        finally:
            self.processing = False

    def update_text(self, text: str):
        """Update displayed text."""
        try:
            logger.debug(f"Updating text: {text}")
            decoded_text = html.unescape(text)
            if ":" in decoded_text:
                name, dialogue = decoded_text.split(":", 1)
                self.name_label.setText(name.strip())
                self.dialogue_label.setText(dialogue.strip())
                logger.debug(f"Name: {name.strip()}")
                logger.debug(f"Dialogue: {dialogue.strip()}")
            else:
                self.name_label.setText("")
                self.dialogue_label.setText(decoded_text)
                logger.debug(f"Single line text: {decoded_text}")
            
            self.show()
        except Exception as e:
            logger.error(f"Error updating text: {str(e)}", exc_info=True)

    def set_region(self, region: Tuple[int, int, int, int]):
        """Set the translation region."""
        self.region = region
        if region:
            x, y, w, h = region
            if self.config_manager and self.window_id:
                saved_pos = self.config_manager.get_global_setting(f'window_{self.window_id}_pos')
                if saved_pos:
                    try:
                        x, y = map(int, saved_pos.split(','))
                    except ValueError:
                        pass
            x, y = self.ensure_window_in_bounds(x, y, w, h)
            self.setGeometry(x, y, w, h)
            self.name_label.setFixedWidth(w - 40)
            self.dialogue_label.setFixedWidth(w - 40)

    def ensure_window_in_bounds(self, x: int, y: int, w: int, h: int) -> Tuple[int, int]:
        """Ensure window stays within screen bounds."""
        # Get all available screens
        screens = QApplication.screens()
        # Find the screen that contains the position
        for screen in screens:
            screen_geometry = screen.geometry()
            if screen_geometry.contains(QPoint(x, y)):
                x = max(screen_geometry.left(), min(x, screen_geometry.right() - w))
                y = max(screen_geometry.top(), min(y, screen_geometry.bottom() - h))
                return x, y
        # If no screen contains the position, use the primary screen
        screen = QApplication.primaryScreen().geometry()
        x = max(0, min(x, screen.width() - w))
        y = max(0, min(y, screen.height() - h))
        return x, y

    def apply_settings(self, settings: Dict):
        """Apply new settings to the window."""
        self.settings.update(settings)
        font = QFont(self.settings['font_family'], int(self.settings['font_size']))
        if self.settings['font_style'] == 'bold':
            font.setBold(True)
        elif self.settings['font_style'] == 'italic':
            font.setItalic(True)
        bg_color = QColor(self.settings['background_color'])
        try:
            opacity = float(self.settings.get('opacity', '0.85'))
            alpha = int(opacity * 255) if 0.0 <= opacity <= 1.0 else 217
        except (ValueError, TypeError):
            alpha = 217
        bg_color.setAlpha(alpha)
        rgba_str = f"rgba({bg_color.red()}, {bg_color.green()}, {bg_color.blue()}, {bg_color.alpha()})"
        self.main_frame.setStyleSheet(f"background-color: {rgba_str}; border-radius: 5px;")
        self.close_button.setStyleSheet(
            f"QPushButton {{ background-color: rgba(255,255,255,40); color: #ff0000; border: 1px solid #ff0000; border-radius: 12px; }}"
            f"QPushButton:hover {{ background-color: rgba(255,255,255,100); color: #ffffff; }}"
        )
        self.resize_button.setStyleSheet(
            f"QPushButton {{ background-color: {rgba_str}; color: #00ff00; border: 1px solid #00ff00; border-radius: 10px; }}"
            f"QPushButton:hover {{ background-color: rgba(255,255,255,50); color: #00ff00; }}"
        )
        self.name_label.setFont(font)
        self.name_label.setStyleSheet(
            f"color: {self.settings['name_color']}; background-color: transparent;"
            "padding: 2px;"
        )
        self.dialogue_label.setFont(font)
        self.dialogue_label.setStyleSheet(
            f"color: {self.settings['dialogue_color']}; background-color: transparent;"
            "padding: 2px;"
        )
        self.position_buttons()
        # Update request counter when settings are applied
        if self.text_processor:
            self.vision_counter_label.setText(f"Vision API: {self.text_processor.vision_api_calls_today} requests")
            self.translation_counter_label.setText(f"Translation API: {self.text_processor.translation_api_calls_today} requests")
        if self.last_text:
            self.continuous_translate()

    def start_resize(self, event):
        """Start resizing the window."""
        if event.button() == Qt.LeftButton:
            self.is_resizing = True
            self.resize_start_pos = event.globalPos()
            self.resize_start_size = self.size()
            self.setCursor(Qt.SizeFDiagCursor)
            self.resize_timer.start()

    def update_resize(self):
        """Update window size during resize."""
        if not self.is_resizing:
            self.resize_timer.stop()
            return
        current_pos = QCursor.pos()
        width_diff = current_pos.x() - self.resize_start_pos.x()
        height_diff = current_pos.y() - self.resize_start_pos.y()
        new_width = max(self.min_width, self.resize_start_size.width() + width_diff)
        new_height = max(self.min_height, self.resize_start_size.height() + height_diff)
        
        # Get all available screens
        screens = QApplication.screens()
        # Find the screen that contains the current position
        current_screen = None
        for screen in screens:
            if screen.geometry().contains(current_pos):
                current_screen = screen
                break
        
        # If no screen contains the position, use the screen that contains the window
        if not current_screen:
            for screen in screens:
                if screen.geometry().contains(self.pos()):
                    current_screen = screen
                    break
        
        # If still no screen found, use primary screen
        if not current_screen:
            current_screen = QApplication.primaryScreen()
        
        screen_geometry = current_screen.geometry()
        new_width = min(new_width, screen_geometry.width() - (self.x() - screen_geometry.x()))
        new_height = min(new_height, screen_geometry.height() - (self.y() - screen_geometry.y()))
        
        self.resize(new_width, new_height)
        content_width = new_width - 40
        self.name_label.setFixedWidth(content_width)
        self.dialogue_label.setFixedWidth(content_width)

    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        if event.button() == Qt.LeftButton and not self.is_resizing:
            pos = event.pos()
            close_rect = self.close_button.geometry()
            resize_rect = self.resize_button.geometry()
            if close_rect.contains(pos) or resize_rect.contains(pos):
                return
            self.is_dragging = True
            self.drag_start_pos = event.globalPos() - self.pos()
            self.setCursor(Qt.SizeAllCursor)
            
            # Stop capture when dragging starts
            if self.is_capturing:
                self.toggle_capture()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging."""
        if self.is_dragging:
            new_pos = event.globalPos() - self.drag_start_pos
            # Get all available screens
            screens = QApplication.screens()
            # Find the screen that contains the new position
            for screen in screens:
                screen_geometry = screen.geometry()
                if screen_geometry.contains(new_pos):
                    # Calculate new position relative to the current screen
                    new_x = max(screen_geometry.left(), min(new_pos.x(), screen_geometry.right() - self.width()))
                    new_y = max(screen_geometry.top(), min(new_pos.y(), screen_geometry.bottom() - self.height()))
                    self.move(new_x, new_y)
                    return
            # If no screen contains the position, use the primary screen
            screen = QApplication.primaryScreen().geometry()
            new_x = max(0, min(new_pos.x(), screen.width() - self.width()))
            new_y = max(0, min(new_pos.y(), screen.height() - self.height()))
            self.move(new_x, new_y)

    def mouseReleaseEvent(self, event):
        """Handle mouse release for dragging and resizing."""
        if event.button() == Qt.LeftButton:
            if self.is_dragging:
                self.is_dragging = False
                if self.config_manager and self.window_id:
                    self.config_manager.set_global_setting(f'window_{self.window_id}_pos', f"{self.x()},{self.y()}")
                # Resume capture when dragging ends
                if not self.is_capturing:
                    self.toggle_capture()
            if self.is_resizing:
                self.is_resizing = False
                self.resize_timer.stop()
            self.setCursor(Qt.ArrowCursor)