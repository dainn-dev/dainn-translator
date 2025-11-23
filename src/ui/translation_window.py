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
from PyQt5.QtCore import Qt, QTimer, QPoint, QCoreApplication, QAbstractNativeEventFilter, QEvent
from PyQt5.QtGui import QFont, QColor, QKeySequence
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

logger = logging.getLogger(__name__)

IS_WINDOWS = os.name == 'nt'
WM_HOTKEY = 0x0312
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_ALT = 0x0001
HOTKEY_ID_BASE = 0xA000

# Virtual key code mapping
VK_CODES = {
    # Numbers
    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
    # Letters
    'A': 0x41, 'B': 0x42, 'C': 0x43, 'D': 0x44, 'E': 0x45,
    'F': 0x46, 'G': 0x47, 'H': 0x48, 'I': 0x49, 'J': 0x4A,
    'K': 0x4B, 'L': 0x4C, 'M': 0x4D, 'N': 0x4E, 'O': 0x4F,
    'P': 0x50, 'Q': 0x51, 'R': 0x52, 'S': 0x53, 'T': 0x54,
    'U': 0x55, 'V': 0x56, 'W': 0x57, 'X': 0x58, 'Y': 0x59, 'Z': 0x5A,
    # Function keys
    'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73, 'F5': 0x74, 'F6': 0x75,
    'F7': 0x76, 'F8': 0x77, 'F9': 0x78, 'F10': 0x79, 'F11': 0x7A, 'F12': 0x7B,
    # Special keys
    'SPACE': 0x20, 'PAGEUP': 0x21, 'PAGEDOWN': 0x22, 'END': 0x23, 'HOME': 0x24,
    'LEFT': 0x25, 'UP': 0x26, 'RIGHT': 0x27, 'DOWN': 0x28,
    'INSERT': 0x2D, 'DELETE': 0x2E,
    # Symbol keys
    '`': 0xC0, '-': 0xBD, '=': 0xBB, '[': 0xDB, ']': 0xDD,
    '\\': 0xDC, ';': 0xBA, "'": 0xDE, ',': 0xBC, '.': 0xBE, '/': 0xBF,
}

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
        self.name_label.setVisible(True)  # Ensure it's visible
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
        self.dialogue_label.setVisible(True)  # Ensure it's visible
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
        self.resize_button.installEventFilter(self)
        self.resize_button.raise_()

        # Position buttons
        self.position_buttons()

    def init_translation(self):
        """Initialize translation variables and timer."""
        self.is_dragging = False
        self.drag_start_pos = None
        # Resize variables
        self.is_resizing = False
        self.resize_start_pos = None
        self.resize_start_geometry = None
        self.min_width = 100
        self.min_height = 50
        self.ui_visible = True  # Track UI visibility state

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
        
        # Auto-pause feature variables
        self.consecutive_no_text_captures = 0
        self.auto_paused = False
        
        # Frame change detection variables
        self.last_frame_hash = None
        self.last_frame = None
        self.consecutive_same_frames = 0
        self.max_same_frames = 10  # After 10 same frames, increase interval
        self.frame_change_threshold = 0.95  # Hash similarity threshold
        self.min_change_threshold = 0.85  # Minimum similarity to consider frames different

    def init_shortcuts(self):
        """Register application shortcuts."""
        hotkey = self.settings.get('toggle_hotkey', 'Ctrl+1')
        self.toggle_shortcut = QShortcut(QKeySequence(hotkey), self)
        self.toggle_shortcut.setContext(Qt.ApplicationShortcut)
        self.toggle_shortcut.activated.connect(self.toggle_all_operations)
        self.register_global_hotkey()
    
    def parse_hotkey(self, hotkey: str) -> Tuple[int, int]:
        """Parse hotkey string and return (modifier, virtual_key) tuple."""
        parts = hotkey.split('+')
        modifier = 0
        key = None
        
        # Parse each part
        for part in parts:
            part_upper = part.strip().upper()
            
            # Check for modifiers
            if part_upper == 'CTRL':
                modifier |= MOD_CONTROL
            elif part_upper == 'SHIFT':
                modifier |= MOD_SHIFT
            elif part_upper == 'ALT':
                modifier |= MOD_ALT
            else:
                # This should be the key
                # Try to find it in VK_CODES (check uppercase for letters)
                if part_upper in VK_CODES:
                    key = VK_CODES[part_upper]
                elif part in VK_CODES:  # For symbols that might be case-sensitive
                    key = VK_CODES[part]
                else:
                    logger.warning(f"Unknown key in hotkey: {part}")
        
        # Default to VK_1 if no key was found
        if key is None:
            logger.warning(f"No valid key found in hotkey '{hotkey}', defaulting to '1'")
            key = VK_CODES['1']
        
        return (modifier, key)

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
        
        # Parse the hotkey from settings
        hotkey = self.settings.get('toggle_hotkey', 'Ctrl+1')
        modifier, vk_key = self.parse_hotkey(hotkey)
        
        if not user32.RegisterHotKey(None, self.global_hotkey_id, modifier, vk_key):
            error_code = ctypes.windll.kernel32.GetLastError()
            logger.error(f"Failed to register global hotkey {hotkey} (error {error_code})")
            self.global_hotkey_id = None
            return
        if self.global_hotkey_filter:
            self.global_hotkey_filter.set_hotkey_id(self.global_hotkey_id)
        logger.info(f"Global hotkey {hotkey} registered")

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
        hotkey = self.settings.get('toggle_hotkey', 'Ctrl+1')
        logger.info(f"Global hotkey {hotkey} triggered")
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
        logger.info(f"Capture toggled: is_capturing={self.is_capturing}, region={self.region}")
        
        # Reset auto-pause state when manually toggling
        if self.is_capturing:
            self.auto_paused = False
            self.consecutive_no_text_captures = 0
        
        self.update_capture_button_state()
        
        if self.is_capturing:
            self.running = True
            self.timer.start(int(self.current_interval))
            logger.info(f"Translation started: interval={self.current_interval}ms, region={self.region}")
        else:
            self.running = False
            self.timer.stop()
            logger.info("Translation stopped")
    
    def update_capture_button_state(self):
        """Update capture button appearance based on state."""
        if self.is_capturing:
            self.capture_button.setText("⏸")
            self.capture_button.setStyleSheet(
                f"QPushButton {{ background-color: rgba(255,255,255,40); color: #ff0000; border: 1px solid #ff0000; border-radius: 12px; }}"
                f"QPushButton:hover {{ background-color: rgba(255,255,255,100); color: #ffffff; }}"
            )
            logger.info("Screen capture enabled")
        else:
            self.capture_button.setText("▶")
            self.capture_button.setStyleSheet(
                f"QPushButton {{ background-color: rgba(255,255,255,40); color: #00ff00; border: 1px solid #00ff00; border-radius: 12px; }}"
                f"QPushButton:hover {{ background-color: rgba(255,255,255,100); color: #ffffff; }}"
            )
            logger.info("Screen capture disabled")
    
    def update_auto_pause_status(self):
        """Update UI to reflect auto-pause status."""
        if self.auto_paused:
            # Show auto-pause indicator
            self.capture_button.setText("💤")
            self.capture_button.setStyleSheet(
                f"QPushButton {{ background-color: rgba(100,100,100,200); color: white; border: 1px solid #666666; border-radius: 12px; font-size: 10pt; }}"
                f"QPushButton:hover {{ background-color: rgba(100,100,100,255); }}"
            )
            # Update name label to show status
            if hasattr(self, 'name_label'):
                self.name_label.setText("Auto-Paused (No text detected)")
        else:
            # Resume normal state
            self.update_capture_button_state()

    def toggle_all_operations(self):
        """Start/stop all translation activity via global shortcut."""
        logger.info("Global toggle shortcut triggered")
        if self.is_capturing:
            self.toggle_capture()
            self.processing = False
            self.consecutive_same_frames = 0
            self.consecutive_empty_frames = 0
            self.consecutive_no_text_captures = 0
            self.auto_paused = False
        else:
            if not self.region:
                logger.warning("Cannot start capturing without a selected region")
                return
            self.toggle_capture()

    def continuous_translate(self):
        """Continuously translate screen region text with optimizations."""
        if not self.running or not self.region or not self.text_processor or self.processing or not self.is_capturing:
            logger.debug(f"Skipping translation: running={self.running}, region={self.region}, "
                        f"text_processor={self.text_processor is not None}, processing={self.processing}, "
                        f"is_capturing={self.is_capturing}")
            return

        try:
            self.processing = True
            x, y, w, h = self.region
            logger.debug(f"Capturing screen region: ({x}, {y}, {w}, {h})")
            
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
            
            # Process the frame with Vision API or Tesseract OCR
            text = self.text_processor.detect_text(screenshot)
            logger.debug(f"Detected text: '{text[:100] if text else '(empty)'}'")
            
            # Update Vision API counter (or OCR status for local/libretranslate mode)
            translation_mode = self.config_manager.get_translation_mode()
            if translation_mode == 'local' or translation_mode == 'libretranslate':
                # For local/libretranslate mode, show OCR status instead
                ocr_mode = self.config_manager.get_ocr_mode()
                ocr_name_map = {
                    'tesseract': 'Tesseract',
                    'paddleocr': 'PaddleOCR',
                    'window_ocr': 'Windows OCR',
                    'easyocr': 'EasyOCR',
                }
                ocr_name = ocr_name_map.get(ocr_mode, 'Tesseract')
                status = f"{ocr_name}: Ready" if text else f"{ocr_name}: No text"
                self.vision_counter_label.setText(status)
            else:
                self.vision_counter_label.setText(f"Vision API: {self.text_processor.vision_api_calls_today} requests")
            
            # Check for auto-pause feature
            # Note: This works for both Google Cloud and Local (Tesseract) translation modes
            # because it checks text detection results regardless of the detection method used
            auto_pause_enabled = self.settings.get('auto_pause_enabled', False)
            auto_pause_threshold = self.settings.get('auto_pause_threshold', 5)
            
            if not text or text.strip() == "":
                # No text detected (works for both Vision API and Tesseract OCR)
                self.consecutive_no_text_captures += 1
                
                # Check if we should auto-pause
                if auto_pause_enabled and self.consecutive_no_text_captures >= auto_pause_threshold:
                    if not self.auto_paused:
                        self.auto_paused = True
                        self.is_capturing = False
                        logger.info(f"Auto-paused after {self.consecutive_no_text_captures} captures without text")
                        # Update UI to show paused state
                        self.update_auto_pause_status()
                    self.processing = False
                    return
            else:
                # Text detected, reset counter and resume if auto-paused
                if self.auto_paused:
                    self.auto_paused = False
                    self.is_capturing = True
                    logger.info("Auto-resuming - text detected")
                    self.update_auto_pause_status()
                self.consecutive_no_text_captures = 0
            
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
                logger.debug(f"Starting translation: '{text[:50]}...' ({self.settings['source_language']} -> {self.settings['target_language']})")
                self.rate_limiter.add_request()
                translated = self.text_processor.translate_text(
                    text, 
                    self.settings['target_language'], 
                    self.settings['source_language']
                )
                logger.debug(f"Translation completed: '{translated[:50] if translated else '(empty)'}...'")
                # Only update Translation API counter if we actually made an API call
                if not cached_translation:
                    translation_mode = self.config_manager.get_translation_mode()
                    if translation_mode == 'local':
                        self.translation_counter_label.setText(f"LLM: Ready")
                    elif translation_mode == 'libretranslate':
                        self.translation_counter_label.setText(f"LibreTranslate: Ready")
                    else:
                        self.translation_counter_label.setText(f"Translation API: {self.text_processor.translation_api_calls_today} requests")
                return translated
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(translate_text)
                try:
                    # Add timeout to prevent UI freezing (45 seconds should be enough for most translations)
                    # This accounts for endpoint detection + actual translation
                    translated_text = future.result(timeout=45)
                except TimeoutError:
                    logger.error("Translation timed out after 30 seconds")
                    translated_text = text  # Fallback to original text
                except Exception as e:
                    logger.error(f"Translation error: {str(e)}", exc_info=True)
                    translated_text = text  # Fallback to original text
            
            # Check if translation was successful
            if not translated_text or translated_text.strip() == "":
                logger.warning(f"Translation returned empty text. Original: '{text[:50]}...'")
                translated_text = text  # Fallback to original text
            
            # Check if translation is the same as original (might indicate failure)
            if translated_text == text:
                logger.debug(f"Translation same as original (might be cached or failed): '{text[:50]}...'")
            
            # Cache the translation
            self.translation_cache.put(
                text,
                self.settings['source_language'],
                self.settings['target_language'],
                translated_text
            )
            
            # Update display
            logger.info(f"Calling update_text with: '{translated_text[:100]}...'")
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
            if not text:
                logger.warning("update_text called with empty text")
                return
            
            logger.info(f"Updating displayed text: '{text[:100]}...' (length: {len(text)})")
            decoded_text = html.unescape(text)
            
            if ":" in decoded_text:
                name, dialogue = decoded_text.split(":", 1)
                name_text = name.strip()
                dialogue_text = dialogue.strip()
                logger.info(f"Setting name label: '{name_text}'")
                logger.info(f"Setting dialogue label: '{dialogue_text}'")
                self.name_label.setText(name_text)
                self.dialogue_label.setText(dialogue_text)
                
                # Ensure labels are visible
                if not self.name_label.isVisible():
                    logger.warning("Name label is not visible!")
                    self.name_label.setVisible(True)
                if not self.dialogue_label.isVisible():
                    logger.warning("Dialogue label is not visible!")
                    self.dialogue_label.setVisible(True)
            else:
                logger.info(f"Setting single line text: '{decoded_text}'")
                self.name_label.setText("")
                self.dialogue_label.setText(decoded_text)
                
                # Ensure dialogue label is visible
                if not self.dialogue_label.isVisible():
                    logger.warning("Dialogue label is not visible!")
                    self.dialogue_label.setVisible(True)
            
            # Ensure content widget is visible
            if hasattr(self, 'content_widget') and not self.content_widget.isVisible():
                logger.warning("Content widget is not visible, making it visible")
                self.content_widget.setVisible(True)
            
            # Ensure window is visible
            if not self.isVisible():
                logger.info("Window not visible, showing window")
                self.show()
                self.raise_()  # Bring to front
                self.activateWindow()  # Activate the window
            
            # Force update/repaint
            self.name_label.update()
            self.dialogue_label.update()
            if hasattr(self, 'content_widget'):
                self.content_widget.update()
            self.update()
            QApplication.processEvents()  # Force Qt to process events and update UI
            
            logger.info(f"Text update completed. Name label text: '{self.name_label.text()[:50]}...', Dialogue label text: '{self.dialogue_label.text()[:50]}...'")
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
        # Check if hotkey has changed
        old_hotkey = self.settings.get('toggle_hotkey', 'Ctrl+1')
        new_hotkey = settings.get('toggle_hotkey', 'Ctrl+1')
        hotkey_changed = old_hotkey != new_hotkey
        
        self.settings.update(settings)
        
        # Update hotkey if it changed
        if hotkey_changed:
            logger.info(f"Hotkey changed from {old_hotkey} to {new_hotkey}, updating shortcuts")
            # Unregister old global hotkey
            self.unregister_global_hotkey()
            # Update QShortcut
            self.toggle_shortcut.setKey(QKeySequence(new_hotkey))
            # Register new global hotkey
            self.register_global_hotkey()
        
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

    def eventFilter(self, obj, event):
        """Filter events for resize button."""
        if obj == self.resize_button:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.start_resize(event.globalPos())
                return True
            elif event.type() == QEvent.MouseMove and self.is_resizing:
                self.handle_resize(event.globalPos())
                return True
            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self.stop_resize()
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            close_rect = self.close_button.geometry()
            resize_rect = self.resize_button.geometry()
            capture_rect = self.capture_button.geometry()
            toggle_rect = self.toggle_ui_button.geometry()
            if resize_rect.contains(pos):
                self.start_resize(event.globalPos())
                return
            if close_rect.contains(pos) or capture_rect.contains(pos) or toggle_rect.contains(pos):
                return
            self.is_dragging = True
            self.drag_start_pos = event.globalPos() - self.pos()
            self.setCursor(Qt.SizeAllCursor)
            
            # Stop capture when dragging starts
            if self.is_capturing:
                self.toggle_capture()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging and resizing."""
        if self.is_resizing:
            self.handle_resize(event.globalPos())
            return
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
            if self.is_resizing:
                self.stop_resize()
                return
            if self.is_dragging:
                self.is_dragging = False
                if self.config_manager and self.window_id:
                    self.config_manager.set_global_setting(f'window_{self.window_id}_pos', f"{self.x()},{self.y()}")
                # Resume capture when dragging ends
                if not self.is_capturing:
                    self.toggle_capture()
            self.setCursor(Qt.ArrowCursor)

    def start_resize(self, global_pos):
        """Start resizing the window."""
        self.is_resizing = True
        self.resize_start_pos = global_pos
        self.resize_start_geometry = self.geometry()
        self.setCursor(Qt.SizeFDiagCursor)
        # Grab mouse to track movements globally
        self.grabMouse()
        
        # Stop capture when resizing starts
        if self.is_capturing:
            self.toggle_capture()

    def handle_resize(self, global_pos):
        """Handle window resizing."""
        if not self.is_resizing or not self.resize_start_pos or not self.resize_start_geometry:
            return
        
        # Calculate the difference in mouse position
        delta_x = global_pos.x() - self.resize_start_pos.x()
        delta_y = global_pos.y() - self.resize_start_pos.y()
        
        # Calculate new size
        new_width = max(self.min_width, self.resize_start_geometry.width() + delta_x)
        new_height = max(self.min_height, self.resize_start_geometry.height() + delta_y)
        
        # Get screen bounds to ensure window stays within screen
        screens = QApplication.screens()
        current_screen = None
        for screen in screens:
            screen_geometry = screen.geometry()
            if screen_geometry.contains(self.resize_start_geometry.topLeft()):
                current_screen = screen_geometry
                break
        
        if not current_screen:
            current_screen = QApplication.primaryScreen().geometry()
        
        # Limit size to screen bounds
        max_width = current_screen.right() - self.resize_start_geometry.left()
        max_height = current_screen.bottom() - self.resize_start_geometry.top()
        new_width = min(new_width, max_width)
        new_height = min(new_height, max_height)
        
        # Resize the window
        self.resize(new_width, new_height)
        
        # Update label widths
        content_width = new_width - 40
        self.name_label.setFixedWidth(content_width)
        self.dialogue_label.setFixedWidth(content_width)
        
        # Update button positions
        self.position_buttons()

    def stop_resize(self):
        """Stop resizing the window."""
        if self.is_resizing:
            self.is_resizing = False
            self.resize_start_pos = None
            self.resize_start_geometry = None
            self.setCursor(Qt.ArrowCursor)
            # Release mouse grab
            self.releaseMouse()
            
            # Update region if it exists
            if self.region:
                x, y, _, _ = self.region
                self.region = (x, y, self.width(), self.height())
            
            # Resume capture when resizing ends
            if not self.is_capturing:
                self.toggle_capture()