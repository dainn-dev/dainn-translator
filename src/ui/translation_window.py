import html
import pyautogui
import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QApplication,
    QHBoxLayout,
    QShortcut
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QCoreApplication, QAbstractNativeEventFilter
from PyQt5.QtGui import QFont, QColor, QCursor, QKeySequence
from src.config_manager import ConfigManager
from src.text_processing import TextProcessor
from typing import Tuple, Optional, Callable, Dict, List
import os
import ctypes
from ctypes import wintypes
import logging
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
import time
import threading
import hashlib
import cv2
try:
    import keyboard
except ImportError:
    keyboard = None

logger = logging.getLogger(__name__)

IS_WINDOWS = os.name == 'nt'
WM_HOTKEY = 0x0312
MOD_CONTROL = 0x0002
VK_1 = 0x31
HOTKEY_ID_BASE = 0xA000

if IS_WINDOWS:

    class WindowsHotkeyFilter(QAbstractNativeEventFilter):
        """Event filter to capture native WM_HOTKEY events."""

        def __init__(self, callback: Callable):
            super().__init__()
            self.callback = callback
            self.hotkey_id: Optional[int] = None

        def set_hotkey_id(self, hotkey_id: Optional[int]):
            self.hotkey_id = hotkey_id

        def nativeEventFilter(self, event_type, message):
            if self.hotkey_id is None:
                return False, 0
            if event_type == "windows_generic_MSG":
                try:
                    msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
                except (ValueError, TypeError):
                    return False, 0
                if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                    QTimer.singleShot(0, self.callback)
                    return True, 0
            return False, 0


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
        self.cleanup_timer.start(30000)  # Check every 30 seconds
        
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
    
    def __init__(self, max_calls: Optional[int], time_window: Optional[int]):
        self.max_calls = max_calls  # None means unlimited
        self.time_window = time_window  # in seconds, ignored when max_calls is None
        self.calls: List[float] = []
        self.lock = threading.Lock()
        
    def can_make_request(self) -> bool:
        """Check if a new request can be made."""
        with self.lock:
            if self.max_calls is None:
                return True

            now = time.time()
            # Remove old calls when a time window is defined
            if self.time_window is not None:
                self.calls = [t for t in self.calls if now - t < self.time_window]
            return len(self.calls) < self.max_calls
            
    def add_request(self):
        """Record a new request."""
        with self.lock:
            if self.max_calls is None:
                return
            self.calls.append(time.time())

class TranslationWindow(QMainWindow):
    """Window to display real-time translations."""
    
    _global_hotkey_counter = 0

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
        self.global_hotkey_id: Optional[int] = None
        self.global_hotkey_filter: Optional['WindowsHotkeyFilter'] = None
        
        # Initialize translation cache and rate limiter
        self.translation_cache = TranslationCache(max_size=None, expiration_minutes=10/60)  # Unlimited cache with 10s expiration
        self.rate_limiter = RateLimiter(max_calls=None, time_window=None)  # Unlimited requests
        
        # Set minimum size
        self.setMinimumSize(300, 200)
        
        # Initialize UI
        self.init_ui()
        self.init_translation()
        self.init_shortcuts()

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

        # Toggle UI visibility button (fixed near close button)
        self.toggle_ui_button = QPushButton("👁", self)
        self.toggle_ui_button.setFixedSize(24, 24)
        self.toggle_ui_button.setStyleSheet(
            f"QPushButton {{ background-color: rgba(255,255,255,40); color: #ffff00; border: 1px solid #ffff00; border-radius: 12px; }}"
            f"QPushButton:hover {{ background-color: rgba(255,255,255,100); color: #ffffff; }}"
        )
        self.toggle_ui_button.clicked.connect(self.toggle_ui_visibility)
        self.toggle_ui_button.raise_()

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
        self.min_width = 100
        self.min_height = 50
        self.ui_visible = True  # Track UI visibility state
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
        self.was_capturing_before_resize = False
        
        # Frame change detection variables
        self.last_frame_hash = None
        self.last_frame = None
        self.consecutive_same_frames = 0
        self.max_same_frames = 10  # After 10 same frames, increase interval
        self.frame_change_threshold = 0.95  # Hash similarity threshold
        self.min_change_threshold = 0.85  # Minimum similarity to consider frames different

    def init_shortcuts(self):
        """Register application shortcuts."""
        self.toggle_shortcut = QShortcut(QKeySequence("Ctrl+1"), self)
        self.toggle_shortcut.setContext(Qt.ApplicationShortcut)
        self.toggle_shortcut.activated.connect(self.toggle_all_operations)
        self.register_global_hotkey()

    def register_global_hotkey(self):
        """Register a system-wide hotkey using the native Windows API."""
        if not IS_WINDOWS:
            logger.info("Global hotkey registration is only supported on Windows")
            return
        if self.global_hotkey_id is not None:
            logger.info("Global hotkey already registered")
            return
        app = QCoreApplication.instance()
        if app is None:
            logger.warning("No QCoreApplication instance; cannot register global hotkey")
            return
        if self.global_hotkey_filter is None:
            self.global_hotkey_filter = WindowsHotkeyFilter(self.on_global_hotkey_triggered)
            app.installNativeEventFilter(self.global_hotkey_filter)
        TranslationWindow._global_hotkey_counter += 1
        self.global_hotkey_id = HOTKEY_ID_BASE + TranslationWindow._global_hotkey_counter
        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, self.global_hotkey_id, MOD_CONTROL, VK_1):
            error_code = ctypes.windll.kernel32.GetLastError()
            logger.error(f"Failed to register global hotkey Ctrl+1 (error {error_code})")
            self.global_hotkey_id = None
            return
        if self.global_hotkey_filter:
            self.global_hotkey_filter.set_hotkey_id(self.global_hotkey_id)
        logger.info("Global hotkey Ctrl+1 registered")

    def unregister_global_hotkey(self):
        """Remove the system-wide hotkey."""
        if not IS_WINDOWS:
            return
        if self.global_hotkey_id is not None:
            user32 = ctypes.windll.user32
            user32.UnregisterHotKey(None, self.global_hotkey_id)
            self.global_hotkey_id = None
        if self.global_hotkey_filter is not None:
            app = QCoreApplication.instance()
            if app:
                app.removeNativeEventFilter(self.global_hotkey_filter)
            self.global_hotkey_filter = None
            logger.info("Global hotkey listener removed")

    def on_global_hotkey_triggered(self):
        """Handle WM_HOTKEY events and toggle operations on the UI thread."""
        logger.info("Global hotkey Ctrl+1 triggered")
        self.toggle_all_operations()

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
        close_x = self.width() - self.close_button.width() - 15
        self.close_button.move(close_x, 15)
        
        # Position toggle UI button next to close button (to the left of it)
        toggle_x = close_x - self.toggle_ui_button.width() - 8  # 8px spacing between buttons
        self.toggle_ui_button.move(toggle_x, 15)
        
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

    def toggle_ui_visibility(self):
        """Toggle visibility of UI elements, keeping translated text and close button visible."""
        self.ui_visible = not self.ui_visible
        
        # Toggle visibility of buttons and labels (but keep close button and translated text visible)
        self.capture_button.setVisible(self.ui_visible)
        self.resize_button.setVisible(self.ui_visible)
        self.top_bar_container.setVisible(self.ui_visible)
        # Note: close_button and content_widget remain visible always
        
        # Update toggle button icon to indicate state
        if self.ui_visible:
            self.toggle_ui_button.setText("👁")
            self.toggle_ui_button.setToolTip("Hide UI")
        else:
            self.toggle_ui_button.setText("👁‍🗨")
            self.toggle_ui_button.setToolTip("Show UI")
        
        logger.info(f"UI visibility toggled: {self.ui_visible}")

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
            self.unregister_global_hotkey()
            
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
            self.unregister_global_hotkey()
            
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

    def toggle_all_operations(self):
        """Start/stop all translation activity via global shortcut."""
        logger.info("Global toggle shortcut triggered")
        if self.is_capturing:
            self.toggle_capture()
            self.processing = False
            self.consecutive_same_frames = 0
            self.consecutive_empty_frames = 0
        else:
            if not self.region:
                logger.warning("Cannot start capturing without a selected region")
                return
            self.toggle_capture()

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
            self.was_capturing_before_resize = self.is_capturing
            if self.is_capturing:
                self.toggle_capture()
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
        frame_geom = self.frameGeometry()
        self.region = (
            frame_geom.x(),
            frame_geom.y(),
            frame_geom.width(),
            frame_geom.height()
        )

    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        if event.button() == Qt.LeftButton and not self.is_resizing:
            pos = event.pos()
            close_rect = self.close_button.geometry()
            resize_rect = self.resize_button.geometry()
            capture_rect = self.capture_button.geometry()
            toggle_rect = self.toggle_ui_button.geometry()
            if close_rect.contains(pos) or resize_rect.contains(pos) or capture_rect.contains(pos) or toggle_rect.contains(pos):
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
                frame_geom = self.frameGeometry()
                self.region = (
                    frame_geom.x(),
                    frame_geom.y(),
                    frame_geom.width(),
                    frame_geom.height()
                )
                if self.config_manager and self.window_id:
                    try:
                        self.config_manager.set_global_setting(
                            f'window_{self.window_id}_size',
                            f"{frame_geom.width()},{frame_geom.height()}"
                        )
                        self.config_manager.set_global_setting(
                            f'window_{self.window_id}_pos',
                            f"{frame_geom.x()},{frame_geom.y()}"
                        )
                    except Exception as e:
                        logger.error(f"Error saving window size for window {self.window_id}: {e}")
                if hasattr(self, 'area_id') and self.area_id and self.config_manager:
                    try:
                        self.config_manager.save_area(
                            self.area_id,
                            frame_geom.x(),
                            frame_geom.y(),
                            frame_geom.width(),
                            frame_geom.height()
                        )
                    except Exception as e:
                        logger.error(f"Error saving area {self.area_id} after resize: {e}")
                if self.was_capturing_before_resize and not self.is_capturing:
                    self.toggle_capture()
                self.was_capturing_before_resize = False
            else:
                self.was_capturing_before_resize = False
            self.setCursor(Qt.ArrowCursor)