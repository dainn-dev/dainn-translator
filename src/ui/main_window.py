import os
import sys
import logging
import time
from typing import Optional
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QColorDialog, QMessageBox, QApplication, QCheckBox, QSpinBox
)
from PyQt5.QtCore import Qt, QTimer, QEvent, QThread, pyqtSignal, QAbstractNativeEventFilter, QCoreApplication
from PyQt5.QtGui import QIcon, QColor, QKeySequence
from src.config_manager import ConfigManager
from src.screen_capture import capture_screen_region
from src.ui.translation_window import TranslationWindow
from src.ui.utils import validate_credentials, show_error_message
from src.text_processing import TextProcessor
from src.version_checker import VersionChecker

logger = logging.getLogger(__name__)

# Import Windows hotkey support
IS_WINDOWS = os.name == 'nt'
if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes
    WM_HOTKEY = 0x0312
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_ALT = 0x0001
    HOTKEY_ID_BASE_MAIN = 0xB000
    
    # Virtual key code mapping (from translation_window.py)
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
    
    class WindowsHotkeyFilterMain(QAbstractNativeEventFilter):
        """Event filter to capture native WM_HOTKEY events for MainWindow."""
        
        def __init__(self, callback: callable):
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


class LLMInitializationThread(QThread):
    """Thread for initializing LLM Studio translator in the background."""
    initialized = pyqtSignal(object)  # Emits LLMStudioTranslator instance
    error = pyqtSignal(str)  # Emits error message
    
    def __init__(self, api_url: str, model_name: str = None):
        super().__init__()
        self.api_url = api_url
        self.model_name = model_name
    
    def run(self):
        """Initialize LLM Studio translator in background thread."""
        try:
            logger.info("Background thread: Initializing LLM Studio translator...")
            from src.translator.llm_studio_translator import LLMStudioTranslator
            
            # Use model name if configured, otherwise None for auto-detect
            model_name = self.model_name if self.model_name else None
            llm_studio_translator = LLMStudioTranslator(self.api_url, model_name=model_name)
            
            # Test connection
            if llm_studio_translator.test_connection():
                logger.info("Background thread: LLM Studio connection successful")
                self.initialized.emit(llm_studio_translator)
            else:
                logger.warning("Background thread: LLM Studio connection test failed. The API may not be running.")
                self.error.emit("LLM Studio connection test failed. The API may not be running.")
        except Exception as e:
            error_msg = f"Error initializing LLM Studio translator: {str(e)}"
            logger.error(f"Background thread: {error_msg}", exc_info=True)
            self.error.emit(error_msg)


class HotkeyInput(QLineEdit):
    """Custom QLineEdit for capturing keyboard shortcuts."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Click here, then press your keys...")
        self.setReadOnly(True)
        self.installEventFilter(self)
        self.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 2px solid #2196F3;
                border-radius: 4px;
                background-color: white;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 2px solid #1976D2;
                background-color: #f0f8ff;
            }
        """)
    
    def eventFilter(self, obj, event):
        """Filter key press events to capture shortcuts."""
        if obj == self and event.type() == QEvent.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            
            # Ignore modifier keys pressed alone
            if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
                return True
            
            # Build the key sequence
            key_combo = []
            
            if modifiers & Qt.ControlModifier:
                key_combo.append("Ctrl")
            if modifiers & Qt.ShiftModifier:
                key_combo.append("Shift")
            if modifiers & Qt.AltModifier:
                key_combo.append("Alt")
            
            # Convert key to string
            key_str = self.get_key_string(key)
            if key_str:
                key_combo.append(key_str)
                self.setText("+".join(key_combo))
            
            return True
        
        return super().eventFilter(obj, event)
    
    def get_key_string(self, key):
        """Convert Qt key code to string representation."""
        # Number keys
        if Qt.Key_0 <= key <= Qt.Key_9:
            return chr(key)
        # Letter keys
        elif Qt.Key_A <= key <= Qt.Key_Z:
            return chr(key)
        # Function keys
        elif Qt.Key_F1 <= key <= Qt.Key_F12:
            return f"F{key - Qt.Key_F1 + 1}"
        # Special keys
        special_keys = {
            Qt.Key_Space: "Space",
            Qt.Key_Tab: "Tab",
            Qt.Key_Backspace: "Backspace",
            Qt.Key_Return: "Return",
            Qt.Key_Enter: "Enter",
            Qt.Key_Insert: "Insert",
            Qt.Key_Delete: "Delete",
            Qt.Key_Home: "Home",
            Qt.Key_End: "End",
            Qt.Key_PageUp: "PageUp",
            Qt.Key_PageDown: "PageDown",
            Qt.Key_Left: "Left",
            Qt.Key_Right: "Right",
            Qt.Key_Up: "Up",
            Qt.Key_Down: "Down",
            Qt.Key_QuoteLeft: "`",
            Qt.Key_Minus: "-",
            Qt.Key_Equal: "=",
            Qt.Key_BracketLeft: "[",
            Qt.Key_BracketRight: "]",
            Qt.Key_Backslash: "\\",
            Qt.Key_Semicolon: ";",
            Qt.Key_Apostrophe: "'",
            Qt.Key_Comma: ",",
            Qt.Key_Period: ".",
            Qt.Key_Slash: "/",
        }
        return special_keys.get(key, None)
    
    def focusInEvent(self, event):
        """Clear text when focused to allow new input."""
        super().focusInEvent(event)
        self.selectAll()

class MainWindow(QMainWindow):
    """Main application window for the real-time screen translator."""
    
    def __init__(self, text_processor: TextProcessor, config_manager: ConfigManager = None):
        super().__init__()
        self.setWindowTitle("Real-time Screen Translator - Settings & Areas")
        self.setGeometry(100, 100, 900, 400)
        # Set minimum window size to prevent window from being too small
        self.setMinimumSize(1000, 800)  # Minimum width: 700px, Minimum height: 400px
        try:
            self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "../../resources/logo.ico")))
        except Exception as e:
            logger.warning(f"Could not set window icon: {e}")

        # Colors
        self.bg_color = "#f5f5f5"
        self.accent_color = "#2196F3"
        self.secondary_color = "#1976D2"
        self.text_color = "#212121"
        self.button_bg = "#2196F3"
        self.button_fg = "white"
        self.frame_bg = "#ffffff"

        # Config manager
        self.config_manager = config_manager if config_manager else ConfigManager()
        
        # LLM initialization thread
        self.llm_init_thread = None

        # Version checker
        self.version_checker = VersionChecker()
        
        # Global hotkey for add area
        if IS_WINDOWS:
            self.add_area_hotkey_id: Optional[int] = None
            self.add_area_hotkey_filter: Optional['WindowsHotkeyFilterMain'] = None
        else:
            self.add_area_hotkey_id = None
            self.add_area_hotkey_filter = None
        self.version_check_timer = QTimer()
        self.version_check_timer.timeout.connect(self.check_for_updates)
        self.version_check_timer.start(3600000)  # Check every hour

        # Initialize translation windows dictionary before loading areas
        self.translation_windows = {}
        
        # Initialize UI
        self.init_ui()
        self.load_languages_from_config()
        self.load_saved_areas()
        self.update_button_states()
        
        # Ensure settings are enabled on startup (when no translation windows are running)
        self.update_settings_state(True)

        self.text_processor = text_processor

        # Check for updates after a short delay to ensure the window is fully loaded
        QTimer.singleShot(2000, self.check_for_updates)
        
        # Register add area hotkey
        if IS_WINDOWS:
            QTimer.singleShot(100, self.register_add_area_hotkey)
    
    def init_llm_in_background(self):
        """Initialize LLM Studio translator in a background thread."""
        try:
            logger.info("Starting LLM initialization in background thread...")
            llm_studio_url = self.config_manager.get_llm_studio_url()
            llm_studio_model = self.config_manager.get_llm_studio_model()
            
            # Create and start the initialization thread
            self.llm_init_thread = LLMInitializationThread(llm_studio_url, llm_studio_model)
            self.llm_init_thread.initialized.connect(self.on_llm_initialized)
            self.llm_init_thread.error.connect(self.on_llm_initialization_error)
            self.llm_init_thread.finished.connect(self.on_llm_thread_finished)
            self.llm_init_thread.start()
        except Exception as e:
            logger.error(f"Error starting LLM initialization thread: {str(e)}", exc_info=True)
    
    def on_llm_initialized(self, llm_studio_translator):
        """Handle successful LLM initialization."""
        try:
            logger.info("LLM Studio translator initialized successfully, updating TextProcessor")
            self.text_processor.set_llm_studio_translator(llm_studio_translator)
            logger.info("TextProcessor updated with LLM Studio translator")
        except Exception as e:
            logger.error(f"Error updating TextProcessor with LLM translator: {str(e)}", exc_info=True)
    
    def on_llm_initialization_error(self, error_msg: str):
        """Handle LLM initialization error."""
        logger.warning(f"LLM initialization error: {error_msg}")
    
    def on_llm_thread_finished(self):
        """Handle LLM initialization thread completion."""
        logger.info("LLM initialization thread finished")
        self.llm_init_thread = None

    def init_ui(self):
        """Initialize the user interface."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        # Apply global styling for comboboxes and text boxes
        widget_style = """
            QComboBox {
                padding: 4px 6px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                min-height: 20px;
            }
            QComboBox:hover {
                border: 1px solid #2196F3;
            }
            QComboBox:focus {
                border: 2px solid #2196F3;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                padding: 4px;
                border: 1px solid #ccc;
                border-radius: 4px;
                selection-background-color: #e3f2fd;
            }
            QLineEdit {
                padding: 4px 6px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                min-height: 20px;
            }
            QLineEdit:hover {
                border: 1px solid #2196F3;
            }
            QLineEdit:focus {
                border: 2px solid #2196F3;
                background-color: #fafafa;
            }
        """
        self.setStyleSheet(widget_style)

        # Settings panel
        self.settings_group = QGroupBox("⚙️ Settings & Configuration")
        self.settings_group.setStyleSheet(
            f"QGroupBox {{ font: 10pt 'Google Sans'; color: {self.text_color}; background-color: {self.frame_bg}; padding-top: 10px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}"
        )
        self.main_layout.addWidget(self.settings_group)
        self.settings_layout = QVBoxLayout(self.settings_group)
        self.settings_layout.setSpacing(10)
        self.settings_layout.setContentsMargins(10, 15, 10, 10)

        # Font settings
        self.font_group = QGroupBox("📝 Text Display Settings")
        self.font_group.setStyleSheet(f"background-color: {self.frame_bg}; padding-top: 8px;")
        self.font_group.setToolTip("Customize how translated text appears on screen")
        self.settings_layout.addWidget(self.font_group)
        self.font_layout = QHBoxLayout(self.font_group)
        self.font_layout.setSpacing(8)

        self.font_label = QLabel("Font Family:")
        self.font_label.setToolTip("Choose the font for displaying translated text")
        self.font_layout.addWidget(self.font_label)
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Google Sans", "Segoe UI", "Consolas", "Courier New", "Lucida Console", "Monospace"])
        self.font_combo.setCurrentText(self.config_manager.get_global_setting('font_family', 'Google Sans'))
        self.font_combo.setToolTip("Select the font family for translated text. Changes apply immediately to active translations.")
        self.font_combo.currentTextChanged.connect(self.update_translation_settings)
        self.font_layout.addWidget(self.font_combo)

        self.size_label = QLabel("Size:")
        self.size_label.setToolTip("Font size in pixels")
        self.font_layout.addWidget(self.size_label)
        self.font_size_edit = QLineEdit()
        self.font_size_edit.setFixedWidth(50)
        self.font_size_edit.setText(self.config_manager.get_global_setting('font_size', '14'))
        self.font_size_edit.setPlaceholderText("14")
        self.font_size_edit.setToolTip("Enter font size (recommended: 12-20 pixels)")
        self.font_size_edit.textChanged.connect(self.update_translation_settings)
        self.font_layout.addWidget(self.font_size_edit)

        self.style_label = QLabel("Style:")
        self.style_label.setToolTip("Text style: normal, bold, or italic")
        self.font_layout.addWidget(self.style_label)
        self.font_style_combo = QComboBox()
        self.font_style_combo.addItems(["normal", "bold", "italic"])
        self.font_style_combo.setCurrentText(self.config_manager.get_global_setting('font_style', 'normal'))
        self.font_style_combo.setToolTip("Choose text style. Bold is recommended for better visibility.")
        self.font_style_combo.currentTextChanged.connect(self.update_translation_settings)
        self.font_layout.addWidget(self.font_style_combo)

        # Color settings
        self.color_group = QGroupBox("🎨 Text Color Settings")
        self.color_group.setStyleSheet(f"background-color: {self.frame_bg}; padding-top: 8px;")
        self.color_group.setToolTip("Set colors for character names and dialogue text")
        self.settings_layout.addWidget(self.color_group)
        self.color_layout = QHBoxLayout(self.color_group)
        self.color_layout.setSpacing(8)

        self.name_color_label = QLabel("Character Name:")
        self.name_color_label.setToolTip("Color for character/speaker names")
        self.color_layout.addWidget(self.name_color_label)
        self.name_color_button = QPushButton("Choose Color")
        self.name_color_button.setToolTip("Click to pick a color for character names")
        self.name_color_button.clicked.connect(lambda: self.pick_color('name_color'))
        self.color_layout.addWidget(self.name_color_button)
        self.name_color_preview = QLabel()
        self.name_color_preview.setFixedSize(30, 25)
        self.name_color_value = self.config_manager.get_global_setting('name_color', '#00ffff')
        self.name_color_preview.setStyleSheet(f"background-color: {self.name_color_value}; border: 2px solid #333; border-radius: 3px;")
        self.name_color_preview.setToolTip(f"Current name color: {self.name_color_value}")
        self.color_layout.addWidget(self.name_color_preview)

        self.dialogue_color_label = QLabel("Dialogue Text:")
        self.dialogue_color_label.setToolTip("Color for dialogue/speech text")
        self.color_layout.addWidget(self.dialogue_color_label)
        self.dialogue_color_button = QPushButton("Choose Color")
        self.dialogue_color_button.setToolTip("Click to pick a color for dialogue text")
        self.dialogue_color_button.clicked.connect(lambda: self.pick_color('dialogue_color'))
        self.color_layout.addWidget(self.dialogue_color_button)
        self.dialogue_color_preview = QLabel()
        self.dialogue_color_preview.setFixedSize(30, 25)
        self.dialogue_color_value = self.config_manager.get_global_setting('dialogue_color', '#00ff00')
        self.dialogue_color_preview.setStyleSheet(f"background-color: {self.dialogue_color_value}; border: 2px solid #333; border-radius: 3px;")
        self.dialogue_color_preview.setToolTip(f"Current dialogue color: {self.dialogue_color_value}")
        self.color_layout.addWidget(self.dialogue_color_preview)

        # Background settings
        self.bg_group = QGroupBox("🖼️ Window Background")
        self.bg_group.setStyleSheet(f"background-color: {self.frame_bg}; padding-top: 8px;")
        self.bg_group.setToolTip("Customize the translation window background and transparency")
        self.settings_layout.addWidget(self.bg_group)
        self.bg_layout = QHBoxLayout(self.bg_group)
        self.bg_layout.setSpacing(8)

        self.bg_color_label = QLabel("Background Color:")
        self.bg_color_label.setToolTip("Color of the translation window background")
        self.bg_layout.addWidget(self.bg_color_label)
        self.bg_color_button = QPushButton("Choose Color")
        self.bg_color_button.setToolTip("Click to pick a background color for translation windows")
        self.bg_color_button.clicked.connect(self.pick_background_color)
        self.bg_layout.addWidget(self.bg_color_button)
        self.bg_color_preview = QLabel()
        self.bg_color_preview.setFixedSize(30, 25)
        self.bg_color_value = self.config_manager.get_background_color()
        self.bg_color_preview.setStyleSheet(f"background-color: {self.bg_color_value}; border: 2px solid #333; border-radius: 3px;")
        self.bg_color_preview.setToolTip(f"Current background color: {self.bg_color_value}")
        self.bg_layout.addWidget(self.bg_color_preview)

        self.opacity_label = QLabel("Transparency:")
        self.opacity_label.setToolTip("Window transparency (0.0 = fully transparent, 1.0 = fully opaque)")
        self.bg_layout.addWidget(self.opacity_label)
        self.opacity_edit = QLineEdit()
        self.opacity_edit.setFixedWidth(50)
        self.opacity_edit.setText('0.85')
        self.opacity_edit.setPlaceholderText("0.85")
        self.opacity_edit.setToolTip("Enter opacity value between 0.1 and 1.0 (recommended: 0.7-0.9)")
        self.opacity_edit.textChanged.connect(self.update_opacity)
        self.bg_layout.addWidget(self.opacity_edit)

        # Language settings
        self.language_group = QGroupBox("🌐 Translation Languages")
        self.language_group.setStyleSheet(f"background-color: {self.frame_bg}; padding-top: 8px;")
        self.language_group.setToolTip("Select the source language (text to translate from) and target language (text to translate to)")
        self.settings_layout.addWidget(self.language_group)
        self.language_layout = QHBoxLayout(self.language_group)
        self.language_layout.setSpacing(8)

        self.source_lang_label = QLabel("From:")
        self.source_lang_label.setToolTip("The language of the text on screen (source language)")
        self.language_layout.addWidget(self.source_lang_label)
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.setToolTip("Select the language of the text you want to translate")
        self.language_layout.addWidget(self.source_lang_combo)

        self.target_lang_label = QLabel("To:")
        self.target_lang_label.setToolTip("The language you want to translate to (target language)")
        self.language_layout.addWidget(self.target_lang_label)
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.setToolTip("Select the language you want translations displayed in")
        self.language_layout.addWidget(self.target_lang_combo)

        # Hotkey settings
        self.hotkey_group = QGroupBox("⌨️ Keyboard Shortcuts")
        self.hotkey_group.setStyleSheet(f"background-color: {self.frame_bg}; padding-top: 8px;")
        self.hotkey_group.setToolTip("Configure keyboard shortcuts for quick actions")
        self.settings_layout.addWidget(self.hotkey_group)
        self.hotkey_layout = QVBoxLayout(self.hotkey_group)
        self.hotkey_layout.setSpacing(8)

        # Toggle Hotkey row
        self.toggle_hotkey_layout = QHBoxLayout()
        self.hotkey_label = QLabel("Pause/Resume Translation:")
        self.hotkey_label.setToolTip("Hotkey to pause or resume translation in active windows")
        self.toggle_hotkey_layout.addWidget(self.hotkey_label)
        
        # Use custom HotkeyInput widget instead of combobox
        self.hotkey_input = HotkeyInput()
        self.hotkey_input.setText(self.config_manager.get_toggle_hotkey())
        self.hotkey_input.setToolTip("Click here and press your desired key combination (e.g., Ctrl+1)")
        self.hotkey_input.textChanged.connect(self.on_hotkey_changed)
        self.toggle_hotkey_layout.addWidget(self.hotkey_input)

        self.hotkey_apply_button = QPushButton("Apply")
        self.hotkey_apply_button.setToolTip("Click to save and activate the new hotkey")
        self.hotkey_apply_button.clicked.connect(self.update_hotkey_setting)
        self.hotkey_apply_button.setEnabled(False)
        self.toggle_hotkey_layout.addWidget(self.hotkey_apply_button)

        self.hotkey_info_label = QLabel("💡 Click field and press keys")
        self.hotkey_info_label.setStyleSheet("color: #666666; font-size: 9pt; font-style: italic;")
        self.hotkey_info_label.setToolTip("Instructions: Click the input field, then press your desired key combination")
        self.toggle_hotkey_layout.addWidget(self.hotkey_info_label)
        
        # Store the original hotkey for comparison
        self.original_hotkey = self.config_manager.get_toggle_hotkey()
        
        self.hotkey_layout.addLayout(self.toggle_hotkey_layout)

        # Add Area hotkey settings (below Toggle Hotkey)
        self.add_area_hotkey_layout = QHBoxLayout()
        self.add_area_hotkey_label = QLabel("Add New Area:")
        self.add_area_hotkey_label.setToolTip("Hotkey to quickly add a new translation area")
        self.add_area_hotkey_layout.addWidget(self.add_area_hotkey_label)
        
        # Use custom HotkeyInput widget for add area hotkey
        self.add_area_hotkey_input = HotkeyInput()
        self.add_area_hotkey_input.setText(self.config_manager.get_add_area_hotkey())
        self.add_area_hotkey_input.setToolTip("Click here and press your desired key combination (e.g., Ctrl+2)")
        self.add_area_hotkey_input.textChanged.connect(self.on_add_area_hotkey_changed)
        self.add_area_hotkey_layout.addWidget(self.add_area_hotkey_input)

        self.add_area_hotkey_apply_button = QPushButton("Apply")
        self.add_area_hotkey_apply_button.setToolTip("Click to save and activate the new hotkey")
        self.add_area_hotkey_apply_button.clicked.connect(self.update_add_area_hotkey_setting)
        self.add_area_hotkey_apply_button.setEnabled(False)
        self.add_area_hotkey_layout.addWidget(self.add_area_hotkey_apply_button)

        self.add_area_hotkey_info_label = QLabel("💡 Click field and press keys")
        self.add_area_hotkey_info_label.setStyleSheet("color: #666666; font-size: 9pt; font-style: italic;")
        self.add_area_hotkey_info_label.setToolTip("Instructions: Click the input field, then press your desired key combination")
        self.add_area_hotkey_layout.addWidget(self.add_area_hotkey_info_label)
        
        # Store the original add area hotkey for comparison
        self.original_add_area_hotkey = self.config_manager.get_add_area_hotkey()
        
        self.hotkey_layout.addLayout(self.add_area_hotkey_layout)

        # Auto-pause settings
        self.auto_pause_group = QGroupBox("⏸️ Smart Pause (Resource Saving)")
        self.auto_pause_group.setStyleSheet(f"background-color: {self.frame_bg}; padding-top: 8px;")
        self.auto_pause_group.setToolTip("Automatically pause translation when no text is detected to save resources")
        self.settings_layout.addWidget(self.auto_pause_group)
        self.auto_pause_layout = QHBoxLayout(self.auto_pause_group)
        self.auto_pause_layout.setSpacing(8)

        self.auto_pause_checkbox = QCheckBox("Auto-pause after")
        self.auto_pause_checkbox.setChecked(self.config_manager.get_auto_pause_enabled())
        self.auto_pause_checkbox.setToolTip("Enable automatic pausing when no text is detected")
        self.auto_pause_checkbox.stateChanged.connect(self.update_auto_pause_settings)
        self.auto_pause_layout.addWidget(self.auto_pause_checkbox)

        self.auto_pause_threshold_spinbox = QSpinBox()
        self.auto_pause_threshold_spinbox.setMinimum(1)
        self.auto_pause_threshold_spinbox.setMaximum(100)
        self.auto_pause_threshold_spinbox.setValue(self.config_manager.get_auto_pause_threshold())
        self.auto_pause_threshold_spinbox.setFixedWidth(60)
        self.auto_pause_threshold_spinbox.setToolTip("Number of empty captures before auto-pausing (recommended: 5-10)")
        self.auto_pause_threshold_spinbox.valueChanged.connect(self.update_auto_pause_settings)
        self.auto_pause_layout.addWidget(self.auto_pause_threshold_spinbox)

        self.auto_pause_label = QLabel("empty captures")
        self.auto_pause_label.setToolTip("Translation will pause after this many captures with no text detected")
        self.auto_pause_layout.addWidget(self.auto_pause_label)

        self.auto_pause_info_label = QLabel("💡 Saves resources")
        self.auto_pause_info_label.setStyleSheet("color: #666666; font-size: 9pt; font-style: italic;")
        self.auto_pause_info_label.setToolTip("Saves API calls in Google Cloud mode, saves CPU resources in Local mode")
        self.auto_pause_layout.addWidget(self.auto_pause_info_label)
        self.auto_pause_layout.addStretch()

        # Translation mode settings
        self.translation_mode_group = QGroupBox("⚙️ Translation Service")
        self.translation_mode_group.setStyleSheet(f"background-color: {self.frame_bg}; padding-top: 8px;")
        self.translation_mode_group.setToolTip("Choose your translation service: Google Cloud (paid), Local (free, requires LM Studio), or LibreTranslate (free, self-hosted)")
        self.settings_layout.addWidget(self.translation_mode_group)
        self.translation_mode_layout = QVBoxLayout(self.translation_mode_group)
        self.translation_mode_layout.setSpacing(8)

        # Mode label and combobox in horizontal layout (inline)
        self.mode_layout = QHBoxLayout()
        self.mode_label = QLabel("Service:")
        self.mode_label.setToolTip("Select the translation service to use")
        self.mode_layout.addWidget(self.mode_label)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Google Cloud", "Local (Tesseract + LM Studio)", "LibreTranslate (Tesseract + LibreTranslate)"])
        current_mode = self.config_manager.get_translation_mode()
        if current_mode == 'google':
            mode_index = 0
        elif current_mode == 'local':
            mode_index = 1
        else:  # libretranslate
            mode_index = 2
        self.mode_combo.setCurrentIndex(mode_index)
        self.mode_combo.setToolTip("Google Cloud: Paid, high quality\nLocal: Free, requires LM Studio running\nLibreTranslate: Free, requires LibreTranslate server")
        self.mode_combo.currentIndexChanged.connect(self.on_translation_mode_changed)
        self.mode_layout.addWidget(self.mode_combo)
        self.mode_layout.addStretch()  # Add stretch to align left
        self.translation_mode_layout.addLayout(self.mode_layout)

        # LLM Studio settings (shown only when local mode is selected)
        self.llm_studio_group = QGroupBox("🤖 LM Studio Configuration")
        self.llm_studio_group.setStyleSheet(f"background-color: {self.frame_bg}; padding-top: 8px;")
        self.llm_studio_group.setToolTip("Configure LM Studio API connection for local translation")
        self.translation_mode_layout.addWidget(self.llm_studio_group)
        self.llm_studio_layout = QVBoxLayout(self.llm_studio_group)
        self.llm_studio_layout.setSpacing(8)

        # API URL setting
        self.llm_studio_url_layout = QHBoxLayout()
        self.llm_studio_url_label = QLabel("API URL:")
        self.llm_studio_url_label.setToolTip("LM Studio API endpoint URL")
        self.llm_studio_url_layout.addWidget(self.llm_studio_url_label)
        self.llm_studio_edit = QLineEdit()
        self.llm_studio_edit.setText(self.config_manager.get_llm_studio_url())
        self.llm_studio_edit.setPlaceholderText("http://localhost:1234/v1")
        self.llm_studio_edit.setToolTip("Enter LM Studio API URL (default: http://localhost:1234/v1)\nMake sure LM Studio is running with API enabled")
        self.llm_studio_edit.textChanged.connect(self.on_llm_studio_url_changed)
        self.llm_studio_url_layout.addWidget(self.llm_studio_edit)
        self.llm_studio_layout.addLayout(self.llm_studio_url_layout)

        # Model name setting
        self.llm_studio_model_layout = QHBoxLayout()
        self.llm_studio_model_label = QLabel("Model Name:")
        self.llm_studio_model_label.setToolTip("Specific model to use (optional)")
        self.llm_studio_model_layout.addWidget(self.llm_studio_model_label)
        self.llm_studio_model_edit = QLineEdit()
        self.llm_studio_model_edit.setPlaceholderText("Leave empty for auto-detect")
        self.llm_studio_model_edit.setText(self.config_manager.get_llm_studio_model())
        self.llm_studio_model_edit.setToolTip("Enter a specific model name, or leave empty to auto-detect from LM Studio")
        self.llm_studio_model_edit.textChanged.connect(self.on_llm_studio_model_changed)
        self.llm_studio_model_layout.addWidget(self.llm_studio_model_edit)
        self.llm_studio_layout.addLayout(self.llm_studio_model_layout)

        # OCR mode setting
        self.ocr_mode_layout = QHBoxLayout()
        self.ocr_mode_label = QLabel("Text Detection (OCR):")
        self.ocr_mode_label.setToolTip("OCR engine for detecting text from screen")
        self.ocr_mode_layout.addWidget(self.ocr_mode_label)
        self.ocr_mode_combo = QComboBox()
        self.ocr_mode_combo.addItems(["Tesseract OCR", "PaddleOCR"])
        current_ocr_mode = self.config_manager.get_ocr_mode()
        self.ocr_mode_combo.setCurrentIndex(0 if current_ocr_mode == 'tesseract' else 1)
        self.ocr_mode_combo.setToolTip("Tesseract: Free, widely available\nPaddleOCR: Better accuracy, requires installation")
        self.ocr_mode_combo.currentIndexChanged.connect(self.on_ocr_mode_changed)
        self.ocr_mode_layout.addWidget(self.ocr_mode_combo)
        self.llm_studio_layout.addLayout(self.ocr_mode_layout)

        # Tesseract path setting
        self.tesseract_path_layout = QHBoxLayout()
        self.tesseract_path_label = QLabel("Tesseract Path:")
        self.tesseract_path_label.setToolTip("Path to tesseract.exe (leave empty if Tesseract is in system PATH)")
        self.tesseract_path_layout.addWidget(self.tesseract_path_label)
        self.tesseract_path_edit = QLineEdit()
        self.tesseract_path_edit.setPlaceholderText("Leave empty to use system PATH")
        self.tesseract_path_edit.setText(self.config_manager.get_tesseract_path())
        self.tesseract_path_edit.setToolTip("Enter full path to tesseract.exe, or leave empty if Tesseract is installed and in your system PATH")
        self.tesseract_path_edit.textChanged.connect(self.on_tesseract_path_changed)
        self.tesseract_path_layout.addWidget(self.tesseract_path_edit)
        self.tesseract_browse_button = QPushButton("Browse...")
        self.tesseract_browse_button.setToolTip("Browse for tesseract.exe file")
        self.tesseract_browse_button.clicked.connect(self.browse_tesseract_path)
        self.tesseract_path_layout.addWidget(self.tesseract_browse_button)
        
        self.tesseract_test_button = QPushButton("Test")
        self.tesseract_test_button.setToolTip("Test if Tesseract is installed and working correctly")
        self.tesseract_test_button.clicked.connect(self.test_tesseract)
        self.tesseract_path_layout.addWidget(self.tesseract_test_button)
        self.llm_studio_layout.addLayout(self.tesseract_path_layout)

        # LibreTranslate settings (shown only when libretranslate mode is selected)
        self.libretranslate_group = QGroupBox("🌍 LibreTranslate Configuration")
        self.libretranslate_group.setStyleSheet(f"background-color: {self.frame_bg}; padding-top: 8px;")
        self.libretranslate_group.setToolTip("Configure LibreTranslate API connection (free, open-source translation service)")
        self.translation_mode_layout.addWidget(self.libretranslate_group)
        self.libretranslate_layout = QVBoxLayout(self.libretranslate_group)
        self.libretranslate_layout.setSpacing(8)

        # API URL setting
        self.libretranslate_url_layout = QHBoxLayout()
        self.libretranslate_url_label = QLabel("API URL:")
        self.libretranslate_url_label.setToolTip("LibreTranslate server API endpoint")
        self.libretranslate_url_layout.addWidget(self.libretranslate_url_label)
        self.libretranslate_edit = QLineEdit()
        self.libretranslate_edit.setText(self.config_manager.get_libretranslate_url())
        self.libretranslate_edit.setPlaceholderText("http://localhost:5000")
        self.libretranslate_edit.setToolTip("Enter LibreTranslate API URL (default: http://localhost:5000)\nMake sure LibreTranslate server is running")
        self.libretranslate_edit.textChanged.connect(self.on_libretranslate_url_changed)
        self.libretranslate_url_layout.addWidget(self.libretranslate_edit)
        
        # Test connection button (inline with API URL)
        self.libretranslate_test_button = QPushButton("Test Connection")
        self.libretranslate_test_button.setToolTip("Test if LibreTranslate API is accessible and working")
        self.libretranslate_test_button.clicked.connect(self.test_libretranslate)
        self.libretranslate_url_layout.addWidget(self.libretranslate_test_button)
        
        self.libretranslate_layout.addLayout(self.libretranslate_url_layout)

        # OCR mode setting for LibreTranslate
        self.libretranslate_ocr_mode_layout = QHBoxLayout()
        self.libretranslate_ocr_mode_label = QLabel("Text Detection (OCR):")
        self.libretranslate_ocr_mode_label.setToolTip("OCR engine for detecting text from screen")
        self.libretranslate_ocr_mode_layout.addWidget(self.libretranslate_ocr_mode_label)
        self.libretranslate_ocr_mode_combo = QComboBox()
        self.libretranslate_ocr_mode_combo.addItems(["Tesseract OCR", "PaddleOCR"])
        current_ocr_mode = self.config_manager.get_ocr_mode()
        self.libretranslate_ocr_mode_combo.setCurrentIndex(0 if current_ocr_mode == 'tesseract' else 1)
        self.libretranslate_ocr_mode_combo.setToolTip("Tesseract: Free, widely available\nPaddleOCR: Better accuracy, requires installation")
        self.libretranslate_ocr_mode_combo.currentIndexChanged.connect(self.on_ocr_mode_changed)
        self.libretranslate_ocr_mode_layout.addWidget(self.libretranslate_ocr_mode_combo)
        self.libretranslate_layout.addLayout(self.libretranslate_ocr_mode_layout)

        # Tesseract path setting for LibreTranslate
        self.libretranslate_tesseract_path_layout = QHBoxLayout()
        self.libretranslate_tesseract_path_label = QLabel("Tesseract Path:")
        self.libretranslate_tesseract_path_label.setToolTip("Path to tesseract.exe (leave empty if Tesseract is in system PATH)")
        self.libretranslate_tesseract_path_layout.addWidget(self.libretranslate_tesseract_path_label)
        self.libretranslate_tesseract_path_edit = QLineEdit()
        self.libretranslate_tesseract_path_edit.setPlaceholderText("Leave empty to use system PATH")
        self.libretranslate_tesseract_path_edit.setText(self.config_manager.get_tesseract_path())
        self.libretranslate_tesseract_path_edit.setToolTip("Enter full path to tesseract.exe, or leave empty if Tesseract is installed and in your system PATH")
        self.libretranslate_tesseract_path_edit.textChanged.connect(self.on_tesseract_path_changed)
        self.libretranslate_tesseract_path_layout.addWidget(self.libretranslate_tesseract_path_edit)
        self.libretranslate_tesseract_browse_button = QPushButton("Browse...")
        self.libretranslate_tesseract_browse_button.setToolTip("Browse for tesseract.exe file")
        self.libretranslate_tesseract_browse_button.clicked.connect(self.browse_tesseract_path)
        self.libretranslate_tesseract_path_layout.addWidget(self.libretranslate_tesseract_browse_button)
        
        self.libretranslate_tesseract_test_button = QPushButton("Test")
        self.libretranslate_tesseract_test_button.setToolTip("Test if Tesseract is installed and working correctly")
        self.libretranslate_tesseract_test_button.clicked.connect(self.test_tesseract)
        self.libretranslate_tesseract_path_layout.addWidget(self.libretranslate_tesseract_test_button)
        self.libretranslate_layout.addLayout(self.libretranslate_tesseract_path_layout)

        # Credentials settings
        self.credentials_group = QGroupBox("☁️ Google Cloud Credentials")
        self.credentials_group.setStyleSheet(f"background-color: {self.frame_bg}; padding-top: 8px;")
        self.credentials_group.setToolTip("Configure Google Cloud Translation API credentials (JSON file)")
        self.settings_layout.addWidget(self.credentials_group)
        self.credentials_layout = QHBoxLayout(self.credentials_group)
        self.credentials_layout.setSpacing(8)

        self.credentials_label = QLabel("Credentials File:")
        self.credentials_label.setToolTip("Path to Google Cloud service account JSON file")
        self.credentials_layout.addWidget(self.credentials_label)
        self.credentials_edit = QLineEdit()
        self.credentials_edit.setText(self.config_manager.get_credentials_path())
        self.credentials_edit.setPlaceholderText("Select Google Cloud credentials JSON file...")
        self.credentials_edit.setToolTip("Path to your Google Cloud service account JSON credentials file\nYou can download this from Google Cloud Console")
        self.credentials_layout.addWidget(self.credentials_edit)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.setToolTip("Browse for Google Cloud credentials JSON file")
        self.browse_button.clicked.connect(self.browse_credentials)
        self.credentials_layout.addWidget(self.browse_button)

        # Translation areas panel
        self.areas_group = QGroupBox("📍 Translation Areas")
        self.areas_group.setStyleSheet(
            f"QGroupBox {{ font: 10pt 'Google Sans'; color: {self.text_color}; background-color: {self.frame_bg}; padding-top: 10px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}"
        )
        self.areas_group.setToolTip("Manage your translation areas. Each area monitors a specific screen region for text to translate.")
        self.main_layout.addWidget(self.areas_group)
        self.areas_layout = QVBoxLayout(self.areas_group)
        self.areas_layout.setSpacing(10)
        self.areas_layout.setContentsMargins(10, 15, 10, 10)

        self.areas_tree = QTreeWidget()
        self.areas_tree.setHeaderLabels(["Name", "Position", "Size", "Action"])
        self.areas_tree.setStyleSheet(f"background-color: {self.frame_bg};")
        self.areas_tree.setColumnWidth(3, 80)  # Set Action column width for icon buttons (Start/Stop + Delete)
        self.areas_tree.setToolTip("List of all translation areas. Use ▶ to start/stop translation, ✕ to delete.")
        self.areas_layout.addWidget(self.areas_tree)

        self.buttons_layout = QHBoxLayout()
        self.areas_layout.addLayout(self.buttons_layout)

        self.add_button = QPushButton("➕ Add New Area")
        self.add_button.setToolTip("Add a new translation area by selecting a region on your screen\nYou can also use the 'Add Area' hotkey for quick access")
        self.add_button.clicked.connect(self.add_area)
        self.buttons_layout.addWidget(self.add_button)

        # Styling buttons
        for btn in [self.add_button, self.browse_button,
                    self.name_color_button, self.dialogue_color_button, self.bg_color_button, 
                    self.hotkey_apply_button, self.add_area_hotkey_apply_button,
                    self.tesseract_browse_button, self.tesseract_test_button,
                    self.libretranslate_test_button, self.libretranslate_tesseract_browse_button,
                    self.libretranslate_tesseract_test_button]:
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {self.button_bg}; color: {self.button_fg}; padding: 6px 12px; border-radius: 4px; font-weight: 500; }}"
                f"QPushButton:hover {{ background-color: {self.secondary_color}; }}"
                f"QPushButton:disabled {{ background-color: #cccccc; color: #666666; }}"
            )
        
        # Show/hide credentials group based on mode
        self.on_translation_mode_changed()
        
        # Initialize Tesseract path field visibility based on OCR mode
        self.on_ocr_mode_changed()

        # Translation windows
        self.area_selected = False
        self.language_code_to_name = {}
        self.language_name_to_code = {}

    def load_saved_areas(self):
        """Load saved areas from configuration."""
        try:
            logger.info("Loading saved areas...")
            areas = self.config_manager.get_all_areas()
            logger.info(f"Found {len(areas)} saved areas")
            self.areas_tree.clear()
            if areas:
                for area_id, area_data in areas.items():
                    logger.info(f"Loading area {area_id}: {area_data}")
                    item = QTreeWidgetItem([
                        f"Area {area_id}",
                        f"X: {area_data['x']}, Y: {area_data['y']}",
                        f"W: {area_data['width']}, H: {area_data['height']}",
                        ""  # Empty for Action column, will be filled with button
                    ])
                    item.setData(0, Qt.UserRole, area_id)
                    self.areas_tree.addTopLevelItem(item)
                    # Add action button for this area
                    self._add_action_button(item, area_id)
            self.area_selected = self.areas_tree.topLevelItemCount() > 0
            self.update_button_states()
            logger.info("Areas loaded successfully")
        except Exception as e:
            logger.error(f"Error loading saved areas: {str(e)}", exc_info=True)

    def _add_action_button(self, item: QTreeWidgetItem, area_id: str):
        """Add Start/Stop and Delete buttons to the Action column for a tree item."""
        # Check if translation is running for this area
        is_running = False
        if hasattr(self, 'translation_windows') and area_id in self.translation_windows:
            window = self.translation_windows[area_id]
            is_running = window.isVisible() and \
                        hasattr(window, 'is_capturing') and \
                        window.is_capturing
        
        # Create container widget for action buttons
        action_container = QWidget()
        action_layout = QHBoxLayout(action_container)
        action_layout.setContentsMargins(2, 0, 2, 0)
        action_layout.setSpacing(3)
        
        # Create Start/Stop button with icon
        start_stop_button = QPushButton("⏸" if is_running else "▶")
        start_stop_button.setFixedSize(28, 25)
        start_stop_button.setToolTip("Stop" if is_running else "Start")
        
        # Style the Start/Stop button
        if is_running:
            start_stop_button.setStyleSheet(
                f"QPushButton {{ background-color: #f44336; color: white; padding: 3px; border-radius: 3px; font-size: 14px; }}"
                f"QPushButton:hover {{ background-color: #d32f2f; }}"
            )
        else:
            start_stop_button.setStyleSheet(
                f"QPushButton {{ background-color: {self.button_bg}; color: {self.button_fg}; padding: 3px; border-radius: 3px; font-size: 14px; }}"
                f"QPushButton:hover {{ background-color: {self.secondary_color}; }}"
            )
        
        # Connect Start/Stop button to toggle action
        start_stop_button.clicked.connect(lambda checked, aid=area_id: self._toggle_area_translation(aid))
        action_layout.addWidget(start_stop_button)
        
        # Create Delete button with icon
        delete_button = QPushButton("✕")
        delete_button.setFixedSize(28, 25)
        delete_button.setToolTip("Delete")
        delete_button.setStyleSheet(
            f"QPushButton {{ background-color: #f44336; color: white; padding: 3px; border-radius: 3px; font-size: 14px; }}"
            f"QPushButton:hover {{ background-color: #d32f2f; }}"
        )
        
        # Connect Delete button to delete action
        delete_button.clicked.connect(lambda checked, aid=area_id: self._delete_area_by_id(aid))
        action_layout.addWidget(delete_button)
        
        # Add stretch to align buttons to the left
        action_layout.addStretch()
        
        # Set container widget in the Action column (column 3)
        self.areas_tree.setItemWidget(item, 3, action_container)
        
        # Store button references in item data
        item.setData(3, Qt.UserRole, {'start_stop': start_stop_button, 'delete': delete_button, 'container': action_container})

    def _update_action_button(self, area_id: str, running: bool):
        """Update the action button state for a specific area."""
        # Find the tree item for this area
        for i in range(self.areas_tree.topLevelItemCount()):
            item = self.areas_tree.topLevelItem(i)
            if item.data(0, Qt.UserRole) == area_id:
                # Get button container or create it
                container = self.areas_tree.itemWidget(item, 3)
                if container is None:
                    # Container doesn't exist, create it
                    self._add_action_button(item, area_id)
                    container = self.areas_tree.itemWidget(item, 3)
                
                if container:
                    # Get button references from item data or container
                    button_data = item.data(3, Qt.UserRole)
                    if button_data and isinstance(button_data, dict):
                        start_stop_button = button_data.get('start_stop')
                    else:
                        # Fallback: find button in container layout
                        layout = container.layout()
                        if layout and layout.count() > 0:
                            start_stop_button = layout.itemAt(0).widget()
                        else:
                            start_stop_button = None
                    
                    if start_stop_button:
                        # Update Start/Stop button icon and style
                        start_stop_button.setText("⏸" if running else "▶")
                        start_stop_button.setToolTip("Stop" if running else "Start")
                        if running:
                            start_stop_button.setStyleSheet(
                                f"QPushButton {{ background-color: #f44336; color: white; padding: 3px; border-radius: 3px; font-size: 14px; }}"
                                f"QPushButton:hover {{ background-color: #d32f2f; }}"
                            )
                        else:
                            start_stop_button.setStyleSheet(
                                f"QPushButton {{ background-color: {self.button_bg}; color: {self.button_fg}; padding: 3px; border-radius: 3px; font-size: 14px; }}"
                                f"QPushButton:hover {{ background-color: {self.secondary_color}; }}"
                            )
                break

    def _has_running_translation_windows(self) -> bool:
        """Check if any translation windows are currently running (visible and capturing)."""
        if not hasattr(self, 'translation_windows') or not self.translation_windows:
            return False
        for area_id, window in self.translation_windows.items():
            if window.isVisible() and hasattr(window, 'is_capturing') and window.is_capturing:
                return True
        return False

    def _toggle_area_translation(self, area_id: str):
        """Toggle translation for a specific area (start or stop)."""
        # Check if translation is currently running
        is_running = False
        if hasattr(self, 'translation_windows') and area_id in self.translation_windows:
            window = self.translation_windows[area_id]
            is_running = window.isVisible() and \
                        hasattr(window, 'is_capturing') and \
                        window.is_capturing
        
        if is_running:
            # Stop translation
            self._stop_area_translation(area_id)
        else:
            # Start translation
            self._start_area_translation(area_id)

    def _start_area_translation(self, area_id: str):
        """Start translation for a specific area by ID."""
        # Find the tree item for this area
        for i in range(self.areas_tree.topLevelItemCount()):
            item = self.areas_tree.topLevelItem(i)
            if item.data(0, Qt.UserRole) == area_id:
                # Select the item temporarily
                self.areas_tree.setCurrentItem(item)
                # Start translation using existing method
                self.start_translation()
                break

    def _stop_area_translation(self, area_id: str):
        """Stop translation for a specific area by ID."""
        try:
            if area_id in self.translation_windows:
                window = self.translation_windows[area_id]
                # Stop capturing
                if hasattr(window, 'is_capturing'):
                    window.is_capturing = False
                if hasattr(window, 'toggle_capture'):
                    window.toggle_capture()
                # Stop the timer
                if hasattr(window, 'timer') and window.timer:
                    window.timer.stop()
                # Hide the window
                window.hide()
                
                # Update action button
                self._update_action_button(area_id, running=False)
                
                logger.info(f"Stopped translation for area {area_id}")
            
            # Check if any translation windows are still running
            # If none are running, re-enable settings
            if not self._has_running_translation_windows():
                logger.info("No translation windows are running, re-enabling settings")
                self.update_settings_state(True)
        except Exception as e:
            logger.error(f"Error stopping translation for area {area_id}: {str(e)}", exc_info=True)

    def add_area(self):
        """Add a new translation area."""
        self.hide()
        screenshot, region = capture_screen_region()
        if region:
            x, y, w, h = region
            # Get existing area IDs
            existing_ids = set()
            for i in range(self.areas_tree.topLevelItemCount()):
                item = self.areas_tree.topLevelItem(i)
                existing_ids.add(int(item.data(0, Qt.UserRole)))
            
            # Find the next available ID
            new_id = 1
            while new_id in existing_ids:
                new_id += 1
            
            area_id = str(new_id)
            item = QTreeWidgetItem([
                f"Area {area_id}",
                f"X: {x}, Y: {y}",
                f"W: {w}, H: {h}",
                ""  # Empty for Action column, will be filled with button
            ])
            item.setData(0, Qt.UserRole, area_id)
            self.areas_tree.addTopLevelItem(item)
            # Add action button for this area
            self._add_action_button(item, area_id)
            self.save_area_config(area_id, x, y, w, h)
            self.area_selected = True
            self.update_button_states()
            
            # Select the newly added area and automatically start translation
            self.areas_tree.setCurrentItem(item)
            # Use QTimer.singleShot to ensure UI is updated before starting translation
            QTimer.singleShot(100, self.start_translation)
        self.show()

    def _delete_area_by_id(self, area_id: str):
        """Delete an area by its ID."""
        try:
            # First check if translation window exists and is running
            window = self.translation_windows.get(area_id)
            if window is not None:
                if window.isVisible():
                    # Stop the translation process
                    window.running = False
                    window.timer.stop()
                    
                    # Wait a short moment to ensure cleanup
                    QApplication.processEvents()
                    
                    # Close the window
                    window.close()
                    
                    # Wait a short moment to ensure window is closed
                    QApplication.processEvents()
                
                # Remove from translation windows dictionary
                self.translation_windows.pop(area_id, None)
            
            # Find and remove from tree
            for i in range(self.areas_tree.topLevelItemCount()):
                item = self.areas_tree.topLevelItem(i)
                if item.data(0, Qt.UserRole) == area_id:
                    index = self.areas_tree.indexOfTopLevelItem(item)
                    self.areas_tree.takeTopLevelItem(index)
                    break
            
            # Remove from config
            self.remove_area_from_config(area_id)
            
            # Update area selection state
            self.area_selected = self.areas_tree.topLevelItemCount() > 0
            self.update_button_states()
            
            # If no more translation windows are running, re-enable settings
            if not self._has_running_translation_windows():
                try:
                    self.update_settings_state(True)
                except Exception as e:
                    logger.error(f"Error updating settings state after deletion: {e}")
                    
        except Exception as e:
            logger.error(f"Error deleting area {area_id}: {str(e)}", exc_info=True)
            show_error_message(self, "Error", f"Failed to delete area {area_id}: {str(e)}")

    def save_area_config(self, area_id, x, y, w, h):
        """Save area configuration."""
        try:
            logger.info(f"Saving area {area_id} configuration...")
            self.config_manager.save_area(area_id, x, y, w, h)
            logger.info(f"Area {area_id} configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving area config: {str(e)}", exc_info=True)

    def remove_area_from_config(self, area_id):
        """Remove area configuration."""
        try:
            logger.info(f"Removing area {area_id} from configuration...")
            self.config_manager.delete_area(area_id)
            logger.info(f"Area {area_id} removed from configuration")
        except Exception as e:
            logger.error(f"Error removing area from config: {str(e)}", exc_info=True)

    def start_translation(self):
        """Start translation for a selected area."""
        selected = self.areas_tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select an area to translate")
            return
        area_id = selected[0].data(0, Qt.UserRole)
        
        # Parse position (X: x, Y: y)
        position_text = selected[0].text(1)
        x = int(position_text.split('X:')[1].split(',')[0].strip())
        y = int(position_text.split('Y:')[1].strip())
        
        # Parse size (W: w, H: h)
        size_text = selected[0].text(2)
        w = int(size_text.split('W:')[1].split(',')[0].strip())
        h = int(size_text.split('H:')[1].strip())
        
        try:
            logger.info(f"Starting translation for area {area_id} at ({x}, {y}) with size {w}x{h}")
            
            if area_id in self.translation_windows:
                if self.translation_windows[area_id].isVisible():
                    self.translation_windows[area_id].raise_()
                    self.translation_windows[area_id].activateWindow()
                    return
                else:
                    del self.translation_windows[area_id]
            
            settings = {
                'font_family': self.font_combo.currentText(),
                'font_size': self.font_size_edit.text(),
                'font_style': self.font_style_combo.currentText(),
                'name_color': self.name_color_value,
                'dialogue_color': self.dialogue_color_value,
                'target_language': self.language_name_to_code.get(self.target_lang_combo.currentText(), 'vi'),
                'source_language': self.language_name_to_code.get(self.source_lang_combo.currentText(), 'en'),
                'background_color': self.bg_color_value,
                'opacity': self.opacity_edit.text(),
                'toggle_hotkey': self.hotkey_input.text() or 'Ctrl+1',
                'auto_pause_enabled': self.auto_pause_checkbox.isChecked(),
                'auto_pause_threshold': self.auto_pause_threshold_spinbox.value(),
                'translation_mode': self.config_manager.get_translation_mode(),
                'llm_studio_url': self.config_manager.get_llm_studio_url()
            }
            logger.info(f"Translation settings: {settings}")
            
            logger.info(f"Creating TranslationWindow with text_processor: {hasattr(self, 'text_processor')}")
            translation_window = TranslationWindow(
                self.add_area, 
                settings, 
                self.config_manager, 
                area_id,
                self.text_processor  # Pass the text_processor
            )
            translation_window.set_region((x, y, w, h))
            translation_window.running = True
            translation_window.is_capturing = True  # Enable capturing automatically
            translation_window.update_capture_button_state()  # Update button state
            translation_window.timer.start(1000)
            self.translation_windows[area_id] = translation_window
            
            # Connect the close handler to the translation window
            translation_window.area_id = area_id  # Store area_id for reference
            translation_window.main_window_close_handler = self.handle_translation_window_close_direct
            
            translation_window.show()
            
            # Disable settings when translation window is opened
            self.update_settings_state(False)
            
            # Update action button state to show "Stop"
            self._update_action_button(area_id, running=True)
            
            logger.info("Translation window created and shown")
        except Exception as e:
            logger.error(f"Error in start_translation: {str(e)}", exc_info=True)
            show_error_message(self, "Error", f"Failed to start translation: {str(e)}")

    def handle_translation_window_close_direct(self, area_id):
        """Handle the closure of a translation window directly (called from close button)."""
        try:
            logger.info(f"handle_translation_window_close_direct called for area_id: {area_id}")
            logger.info(f"Translation windows before removal: {list(self.translation_windows.keys())}")
            
            if area_id in self.translation_windows:
                window = self.translation_windows[area_id]
                if hasattr(window, 'running'):
                    window.running = False
                if hasattr(window, 'timer') and window.timer:
                    window.timer.stop()
                del self.translation_windows[area_id]
                logger.info(f"Removed translation window for area_id: {area_id}")
                
                # Update action button to show "Start"
                self._update_action_button(area_id, running=False)
            
            logger.info(f"Translation windows after removal: {list(self.translation_windows.keys())}")
            
            # If no more translation windows are running, re-enable settings
            if not self._has_running_translation_windows():
                logger.info("No translation windows are running, re-enabling settings")
                self.update_settings_state(enabled=True)  # Explicitly pass True
            else:
                logger.info(f"Still have running translation windows")
            
        except Exception as e:
            logger.error(f"Error handling translation window close: {str(e)}", exc_info=True)

    def closeEvent(self, event):
        """Handle window close event."""
        try:
            # Check if there are active translation windows
            active_windows = [window for window in self.translation_windows.values() 
                            if window and window.isVisible()]
            
            if active_windows:
                # Ask user if they want to close all translation windows
                reply = QMessageBox.question(
                    self, 
                    "Close Application", 
                    f"You have {len(active_windows)} active translation window(s).\nDo you want to close all translation windows and exit the application?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    event.ignore()
                    return
            
            # Unregister add area hotkey
            self.unregister_add_area_hotkey()
            
            # Unregister add area hotkey
            self.unregister_add_area_hotkey()
            
            # Save window position
            if self.config_manager:
                self.config_manager.set_global_setting('main_window_pos', f"{self.x()},{self.y()}")
            
            # Close all translation windows gracefully
            for area_id in list(self.translation_windows.keys()):  # Create a copy of keys to avoid modification during iteration
                try:
                    window = self.translation_windows.get(area_id)
                    if window and window.isVisible():
                        # Stop the translation process first
                        if hasattr(window, 'running'):
                            window.running = False
                        if hasattr(window, 'timer') and window.timer:
                            window.timer.stop()
                        
                        # Close the window
                        window.close()
                        
                        # Wait a moment for cleanup
                        QApplication.processEvents()
                    
                    # Remove from dictionary
                    self.translation_windows.pop(area_id, None)
                except Exception as e:
                    logger.error(f"Error closing translation window {area_id}: {str(e)}")
                    # Continue with other windows even if one fails
                    continue
            
            # Stop any remaining timers
            if hasattr(self, 'timer') and self.timer:
                self.timer.stop()
            
            # Accept the close event
            event.accept()
            
        except Exception as e:
            logger.error(f"Error in main window closeEvent: {str(e)}", exc_info=True)
            # Still accept the close event even if there's an error
            event.accept()

    def update_button_states(self):
        """Update button states based on area selection."""
        # Note: Start/Stop and Delete buttons are now in Action column for each area
        pass

    def update_settings_state(self, enabled: bool):
        """Enable or disable all settings controls."""
        try:
            # Ensure enabled is a boolean
            enabled = bool(enabled) if enabled is not None else True
            
            # Add logging to debug the issue
            logger.info(f"update_settings_state called with enabled={enabled}")
            logger.info(f"Number of translation windows: {len(self.translation_windows)}")
            
            # Font settings
            if hasattr(self, 'font_combo'):
                self.font_combo.setEnabled(enabled)
            if hasattr(self, 'font_size_edit'):
                self.font_size_edit.setEnabled(enabled)
            if hasattr(self, 'font_style_combo'):
                self.font_style_combo.setEnabled(enabled)
            
            # Color settings
            if hasattr(self, 'name_color_button'):
                self.name_color_button.setEnabled(enabled)
            if hasattr(self, 'dialogue_color_button'):
                self.dialogue_color_button.setEnabled(enabled)
            
            # Background settings
            if hasattr(self, 'bg_color_button'):
                self.bg_color_button.setEnabled(enabled)
            if hasattr(self, 'opacity_edit'):
                self.opacity_edit.setEnabled(enabled)
            
            # Language settings
            if hasattr(self, 'source_lang_combo'):
                self.source_lang_combo.setEnabled(enabled)
            if hasattr(self, 'target_lang_combo'):
                self.target_lang_combo.setEnabled(enabled)
            
            # Hotkey settings
            if hasattr(self, 'hotkey_input'):
                self.hotkey_input.setEnabled(enabled)
            if hasattr(self, 'hotkey_apply_button'):
                # Apply button should be disabled when settings are disabled OR when no changes are made
                has_changes = hasattr(self, 'original_hotkey') and self.hotkey_input.text() != self.original_hotkey
                self.hotkey_apply_button.setEnabled(enabled and has_changes)
            if hasattr(self, 'add_area_hotkey_input'):
                self.add_area_hotkey_input.setEnabled(enabled)
            if hasattr(self, 'add_area_hotkey_apply_button'):
                # Apply button should be disabled when settings are disabled OR when no changes are made
                has_changes = hasattr(self, 'original_add_area_hotkey') and self.add_area_hotkey_input.text() != self.original_add_area_hotkey
                self.add_area_hotkey_apply_button.setEnabled(enabled and has_changes)
            
            # Auto-pause settings
            if hasattr(self, 'auto_pause_checkbox'):
                self.auto_pause_checkbox.setEnabled(enabled)
            if hasattr(self, 'auto_pause_threshold_spinbox'):
                self.auto_pause_threshold_spinbox.setEnabled(enabled)
            
            # Credentials settings
            if hasattr(self, 'credentials_edit'):
                self.credentials_edit.setEnabled(enabled)
            if hasattr(self, 'browse_button'):
                self.browse_button.setEnabled(enabled)
            
            # Translation mode settings
            if hasattr(self, 'mode_combo'):
                self.mode_combo.setEnabled(enabled)
            if hasattr(self, 'llm_studio_edit'):
                self.llm_studio_edit.setEnabled(enabled)
            if hasattr(self, 'llm_studio_model_edit'):
                self.llm_studio_model_edit.setEnabled(enabled)
            if hasattr(self, 'tesseract_path_edit'):
                self.tesseract_path_edit.setEnabled(enabled)
            if hasattr(self, 'tesseract_browse_button'):
                self.tesseract_browse_button.setEnabled(enabled)
            if hasattr(self, 'tesseract_test_button'):
                self.tesseract_test_button.setEnabled(enabled)
            if hasattr(self, 'ocr_mode_combo'):
                self.ocr_mode_combo.setEnabled(enabled)
            if hasattr(self, 'libretranslate_edit'):
                self.libretranslate_edit.setEnabled(enabled)
            if hasattr(self, 'libretranslate_test_button'):
                self.libretranslate_test_button.setEnabled(enabled)
            if hasattr(self, 'libretranslate_ocr_mode_combo'):
                self.libretranslate_ocr_mode_combo.setEnabled(enabled)
            if hasattr(self, 'libretranslate_tesseract_path_edit'):
                self.libretranslate_tesseract_path_edit.setEnabled(enabled)
            if hasattr(self, 'libretranslate_tesseract_browse_button'):
                self.libretranslate_tesseract_browse_button.setEnabled(enabled)
            if hasattr(self, 'libretranslate_tesseract_test_button'):
                self.libretranslate_tesseract_test_button.setEnabled(enabled)
            
            # Area management buttons - always enabled
            if hasattr(self, 'add_button'):
                self.add_button.setEnabled(True)
            # Note: Start/Stop and Delete buttons are now in Action column for each area

            # Update button styles - match the style from initial button styling
            disabled_style = """
                QPushButton {
                    background-color: #cccccc;
                    color: #666666;
                    border: 1px solid #999999;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-weight: 500;
                    opacity: 0.7;
                }
                QPushButton:hover {
                    background-color: #cccccc;
                }
            """
            enabled_style = f"""
                QPushButton {{
                    background-color: {self.button_bg};
                    color: {self.button_fg};
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {self.secondary_color};
                }}
                QPushButton:disabled {{
                    background-color: #cccccc;
                    color: #666666;
                }}
            """

            # Apply styles to color, browse, and hotkey apply buttons - match Test Connection button style
            for btn in [self.name_color_button, self.dialogue_color_button, 
                       self.bg_color_button, self.browse_button, 
                       self.hotkey_apply_button, self.add_area_hotkey_apply_button]:
                if btn is not None:
                    btn.setStyleSheet(disabled_style if not enabled else enabled_style)
        except Exception as e:
            logger.error(f"Error updating settings state: {e}")
            # Set a default state if there's an error
            widget_names = [
                'font_combo', 'font_size_edit', 'font_style_combo',
                'name_color_button', 'dialogue_color_button',
                'bg_color_button', 'opacity_edit',
                'source_lang_combo', 'target_lang_combo',
                'credentials_edit', 'browse_button'
            ]
            for widget_name in widget_names:
                if hasattr(self, widget_name):
                    widget = getattr(self, widget_name)
                    if widget is not None:
                        widget.setEnabled(True)

    def pick_color(self, color_type: str):
        """Pick a color for name or dialogue."""
        try:
            current_color = self.name_color_value if color_type == 'name_color' else self.dialogue_color_value
            color = QColorDialog.getColor(QColor(current_color), self, f"Choose {color_type.replace('_', ' ').title()}")
            if color.isValid():
                hex_color = color.name()
                if color_type == 'name_color':
                    self.name_color_value = hex_color
                    self.name_color_preview.setStyleSheet(f"background-color: {hex_color}; border: 1px solid black;")
                else:
                    self.dialogue_color_value = hex_color
                    self.dialogue_color_preview.setStyleSheet(f"background-color: {hex_color}; border: 1px solid black;")
                self.config_manager.set_global_setting(color_type, hex_color)
                self.update_translation_settings()
        except Exception as e:
            show_error_message(self, "Error", f"Failed to pick color: {str(e)}")

    def pick_background_color(self):
        """Pick background color."""
        try:
            color = QColorDialog.getColor(QColor(self.bg_color_value), self, "Choose Background Color")
            if color.isValid():
                self.bg_color_value = color.name()
                self.bg_color_preview.setStyleSheet(f"background-color: {self.bg_color_value}; border: 1px solid black;")
                self.config_manager.set_background_color(self.bg_color_value)
                self.update_translation_settings()
        except Exception as e:
            show_error_message(self, "Error", f"Failed to pick color: {str(e)}")

    def load_languages_from_config(self):
        """Load languages from configuration."""
        try:
            languages = self.config_manager.get_all_languages()
            if not languages:
                self.config_manager.create_languages_section()
                languages = self.config_manager.get_all_languages()
            self.language_code_to_name = dict(zip(languages.keys(), languages.values()))
            self.language_name_to_code = dict(zip(languages.values(), languages.keys()))
            self.source_lang_combo.addItems(languages.values())
            self.target_lang_combo.addItems(languages.values())
            current_source = self.config_manager.get_language_name(
                self.config_manager.get_global_setting('source_language', 'en'))
            current_target = self.config_manager.get_language_name(
                self.config_manager.get_global_setting('target_language', 'vi'))
            self.source_lang_combo.setCurrentText(current_source)
            self.target_lang_combo.setCurrentText(current_target)
            self.source_lang_combo.currentTextChanged.connect(self.update_translation_settings)
            self.target_lang_combo.currentTextChanged.connect(self.update_translation_settings)
        except Exception as e:
            logger.error(f"Error loading languages: {str(e)}", exc_info=True)
            self.source_lang_combo.addItems(list(languages.values()))
            self.target_lang_combo.addItems(list(languages.values()))
            self.source_lang_combo.setCurrentText(languages['en'])
            self.target_lang_combo.setCurrentText(languages['vi'])
            self.config_manager.create_languages_section()
            self.config_manager.save_config()

    def update_translation_settings(self):
        """Update translation settings for all windows."""
        try:
            source_lang = self.language_name_to_code.get(self.source_lang_combo.currentText(), 'en')
            target_lang = self.language_name_to_code.get(self.target_lang_combo.currentText(), 'vi')
            if source_lang == target_lang:
                QMessageBox.warning(self, "Warning", "Source and target languages cannot be the same. Please select different languages.")
                self.target_lang_combo.setCurrentText(self.config_manager.get_language_name(
                    self.config_manager.get_global_setting('target_language', 'vi')))
                return

            settings = {
                'font_family': self.font_combo.currentText(),
                'font_size': self.font_size_edit.text(),
                'font_style': self.font_style_combo.currentText(),
                'name_color': self.name_color_value,
                'dialogue_color': self.dialogue_color_value,
                'target_language': target_lang,
                'source_language': source_lang,
                'background_color': self.bg_color_value,
                'opacity': self.opacity_edit.text(),
                'toggle_hotkey': self.hotkey_input.text() or 'Ctrl+1',
                'auto_pause_enabled': self.auto_pause_checkbox.isChecked(),
                'auto_pause_threshold': self.auto_pause_threshold_spinbox.value()
            }
            self.config_manager.set_global_setting('font_family', settings['font_family'])
            self.config_manager.set_global_setting('font_size', settings['font_size'])
            self.config_manager.set_global_setting('font_style', settings['font_style'])
            self.config_manager.set_global_setting('name_color', settings['name_color'])
            self.config_manager.set_global_setting('dialogue_color', settings['dialogue_color'])
            self.config_manager.set_source_language(settings['source_language'])
            self.config_manager.set_target_language(settings['target_language'])
            for translation_window in self.translation_windows.values():
                if translation_window.isVisible():
                    translation_window.apply_settings(settings)
                    if translation_window.last_text:
                        translation_window.continuous_translate()
        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}", exc_info=True)

    def update_opacity(self):
        """Update window opacity."""
        try:
            opacity = float(self.opacity_edit.text())
            if 0.01 <= opacity <= 1.0:
                settings = {
                    'font_family': self.font_combo.currentText(),
                    'font_size': self.font_size_edit.text(),
                    'font_style': self.font_style_combo.currentText(),
                    'name_color': self.name_color_value,
                    'dialogue_color': self.dialogue_color_value,
                    'target_language': self.language_name_to_code.get(self.target_lang_combo.currentText(), 'vi'),
                    'source_language': self.language_name_to_code.get(self.source_lang_combo.currentText(), 'en'),
                    'background_color': self.bg_color_value,
                    'opacity': str(opacity),
                    'toggle_hotkey': self.hotkey_input.text() or 'Ctrl+1',
                    'auto_pause_enabled': self.auto_pause_checkbox.isChecked(),
                    'auto_pause_threshold': self.auto_pause_threshold_spinbox.value()
                }
                for window in self.translation_windows.values():
                    if window.isVisible():
                        window.apply_settings(settings)
            else:
                self.opacity_edit.setText('0.85')
        except ValueError:
            self.opacity_edit.setText('0.85')

    def browse_credentials(self):
        """Browse for Google Cloud credentials file."""
        app = QApplication.instance()
        if not app:
            app = QApplication([])
            
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Google Cloud Credentials File",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if file_name:
            self.credentials_edit.setText(file_name)
            self.config_manager.set_credentials_path(file_name)
            if QMessageBox.question(self, "Restart Required",
                                   "Restart now to apply new credentials?") == QMessageBox.Yes:
                QApplication.quit()
                os.execv(sys.executable, ['python'] + sys.argv)

    def on_hotkey_changed(self):
        """Handle hotkey input changes."""
        try:
            current_hotkey = self.hotkey_input.text()
            # Enable apply button only if hotkey has changed and is not empty
            if hasattr(self, 'hotkey_apply_button'):
                self.hotkey_apply_button.setEnabled(
                    bool(current_hotkey) and current_hotkey != self.original_hotkey
                )
        except Exception as e:
            logger.error(f"Error handling hotkey change: {str(e)}", exc_info=True)
    
    def update_hotkey_setting(self):
        """Update hotkey setting when Apply button is clicked."""
        try:
            hotkey = self.hotkey_input.text()
            if not hotkey:
                QMessageBox.warning(self, "Invalid Hotkey", "Please enter a valid hotkey combination.")
                return
            
            # Validate hotkey format
            if not self.validate_hotkey(hotkey):
                QMessageBox.warning(self, "Invalid Hotkey", 
                                   "Invalid hotkey format. Please use a combination like:\n"
                                   "- Ctrl+1, Ctrl+Shift+T, Alt+F1, etc.")
                return
            
            self.config_manager.set_toggle_hotkey(hotkey)
            self.original_hotkey = hotkey
            self.hotkey_apply_button.setEnabled(False)
            
            # Update all active translation windows
            for translation_window in self.translation_windows.values():
                if translation_window.isVisible():
                    settings = {
                        'font_family': self.font_combo.currentText(),
                        'font_size': self.font_size_edit.text(),
                        'font_style': self.font_style_combo.currentText(),
                        'name_color': self.name_color_value,
                        'dialogue_color': self.dialogue_color_value,
                        'target_language': self.language_name_to_code.get(self.target_lang_combo.currentText(), 'vi'),
                        'source_language': self.language_name_to_code.get(self.source_lang_combo.currentText(), 'en'),
                        'background_color': self.bg_color_value,
                        'opacity': self.opacity_edit.text(),
                        'toggle_hotkey': hotkey
                    }
                    translation_window.apply_settings(settings)
            
            QMessageBox.information(self, "Hotkey Updated", 
                                   f"Hotkey changed to {hotkey}\n\n"
                                   "The new hotkey is now active for all translation windows.")
        except Exception as e:
            logger.error(f"Error updating hotkey: {str(e)}", exc_info=True)
            show_error_message(self, "Error", f"Failed to update hotkey: {str(e)}")
    
    def validate_hotkey(self, hotkey: str) -> bool:
        """Validate hotkey format."""
        if not hotkey or '+' not in hotkey:
            return False
        
        parts = hotkey.split('+')
        if len(parts) < 2:
            return False
        
        # Check if at least one modifier is present
        modifiers = {'Ctrl', 'Shift', 'Alt'}
        has_modifier = any(mod in parts for mod in modifiers)
        
        return has_modifier
    
    def parse_hotkey(self, hotkey: str):
        """Parse hotkey string and return (modifier, virtual_key) tuple."""
        if not IS_WINDOWS:
            return (0, 0)
        
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
                if part_upper in VK_CODES:
                    key = VK_CODES[part_upper]
                elif part in VK_CODES:
                    key = VK_CODES[part]
                else:
                    logger.warning(f"Unknown key in hotkey: {part}")
        
        # Default to VK_2 if no key was found
        if key is None:
            logger.warning(f"No valid key found in hotkey '{hotkey}', defaulting to '2'")
            key = VK_CODES.get('2', 0x32)
        
        return (modifier, key)
    
    def register_add_area_hotkey(self):
        """Register a system-wide hotkey for adding translation areas."""
        if not IS_WINDOWS:
            logger.info("Global hotkey registration is only supported on Windows")
            return
        
        if self.add_area_hotkey_id is not None:
            logger.info("Add area hotkey already registered")
            return
        
        app = QCoreApplication.instance()
        if app is None:
            logger.warning("No QCoreApplication instance; cannot register global hotkey")
            return
        
        if self.add_area_hotkey_filter is None:
            self.add_area_hotkey_filter = WindowsHotkeyFilterMain(self.on_add_area_hotkey_triggered)
            app.installNativeEventFilter(self.add_area_hotkey_filter)
        
        # Use a unique ID for the add area hotkey
        self.add_area_hotkey_id = HOTKEY_ID_BASE_MAIN + 1
        user32 = ctypes.windll.user32
        
        # Parse the hotkey from settings
        hotkey = self.config_manager.get_add_area_hotkey()
        modifier, vk_key = self.parse_hotkey(hotkey)
        
        if not user32.RegisterHotKey(None, self.add_area_hotkey_id, modifier, vk_key):
            error_code = ctypes.windll.kernel32.GetLastError()
            logger.error(f"Failed to register add area hotkey {hotkey} (error {error_code})")
            self.add_area_hotkey_id = None
            return
        
        if self.add_area_hotkey_filter:
            self.add_area_hotkey_filter.set_hotkey_id(self.add_area_hotkey_id)
        
        logger.info(f"Add area hotkey {hotkey} registered")
    
    def unregister_add_area_hotkey(self):
        """Remove the system-wide add area hotkey."""
        if not IS_WINDOWS:
            return
        
        if self.add_area_hotkey_id is not None:
            user32 = ctypes.windll.user32
            user32.UnregisterHotKey(None, self.add_area_hotkey_id)
            self.add_area_hotkey_id = None
        
        if self.add_area_hotkey_filter is not None:
            app = QCoreApplication.instance()
            if app:
                app.removeNativeEventFilter(self.add_area_hotkey_filter)
            self.add_area_hotkey_filter = None
            logger.info("Add area hotkey listener removed")
    
    def on_add_area_hotkey_triggered(self):
        """Handle add area hotkey events."""
        hotkey = self.config_manager.get_add_area_hotkey()
        logger.info(f"Add area hotkey {hotkey} triggered")
        self.add_area()
    
    def on_add_area_hotkey_changed(self):
        """Handle add area hotkey input changes."""
        try:
            current_hotkey = self.add_area_hotkey_input.text()
            # Enable apply button only if hotkey has changed and is not empty
            if hasattr(self, 'add_area_hotkey_apply_button'):
                self.add_area_hotkey_apply_button.setEnabled(
                    bool(current_hotkey) and current_hotkey != self.original_add_area_hotkey
                )
        except Exception as e:
            logger.error(f"Error handling add area hotkey change: {str(e)}", exc_info=True)
    
    def update_add_area_hotkey_setting(self):
        """Update add area hotkey setting when Apply button is clicked."""
        try:
            hotkey = self.add_area_hotkey_input.text()
            if not hotkey:
                QMessageBox.warning(self, "Invalid Hotkey", "Please enter a valid hotkey combination.")
                return
            
            # Validate hotkey format
            if not self.validate_hotkey(hotkey):
                QMessageBox.warning(self, "Invalid Hotkey", 
                                   "Invalid hotkey format. Please use a combination like:\n"
                                   "- Ctrl+2, Ctrl+Shift+A, Alt+F1, etc.")
                return
            
            # Unregister old hotkey
            self.unregister_add_area_hotkey()
            
            # Update config
            self.config_manager.set_add_area_hotkey(hotkey)
            self.original_add_area_hotkey = hotkey
            self.add_area_hotkey_apply_button.setEnabled(False)
            
            # Register new hotkey
            if IS_WINDOWS:
                QTimer.singleShot(100, self.register_add_area_hotkey)
            
            QMessageBox.information(self, "Hotkey Updated", 
                                   f"Add area hotkey changed to {hotkey}\n\n"
                                   "The new hotkey is now active.")
        except Exception as e:
            logger.error(f"Error updating add area hotkey: {str(e)}", exc_info=True)
            show_error_message(self, "Error", f"Failed to update hotkey: {str(e)}")
    
    def update_auto_pause_settings(self):
        """Update auto-pause settings for all translation windows."""
        try:
            enabled = self.auto_pause_checkbox.isChecked()
            threshold = self.auto_pause_threshold_spinbox.value()
            
            # Save to config
            self.config_manager.set_auto_pause_enabled(enabled)
            self.config_manager.set_auto_pause_threshold(threshold)
            
            # Update all active translation windows
            for translation_window in self.translation_windows.values():
                if translation_window.isVisible():
                    settings = {
                        'font_family': self.font_combo.currentText(),
                        'font_size': self.font_size_edit.text(),
                        'font_style': self.font_style_combo.currentText(),
                        'name_color': self.name_color_value,
                        'dialogue_color': self.dialogue_color_value,
                        'target_language': self.language_name_to_code.get(self.target_lang_combo.currentText(), 'vi'),
                        'source_language': self.language_name_to_code.get(self.source_lang_combo.currentText(), 'en'),
                        'background_color': self.bg_color_value,
                        'opacity': self.opacity_edit.text(),
                        'toggle_hotkey': self.hotkey_input.text() or 'Ctrl+1',
                        'auto_pause_enabled': enabled,
                        'auto_pause_threshold': threshold
                    }
                    translation_window.apply_settings(settings)
            
            logger.info(f"Auto-pause settings updated: enabled={enabled}, threshold={threshold}")
        except Exception as e:
            logger.error(f"Error updating auto-pause settings: {str(e)}", exc_info=True)

    def check_for_updates(self):
        """Check for application updates."""
        try:
            # Get the last update check time from config
            last_check = self.config_manager.get_global_setting('last_update_check', '0')
            current_time = int(time.time())
            
            # Ensure last_check is a valid integer
            try:
                last_check_time = int(last_check)
            except (ValueError, TypeError):
                # If invalid, reset to 0 and save
                last_check_time = 0
                self.config_manager.set_global_setting('last_update_check', '0')
            
            # Only check if it's been at least 6 hours since the last check
            if current_time - last_check_time >= 21600:  # 6 hours in seconds
                self.version_checker.check_for_updates(self)
                # Update the last check time
                self.config_manager.set_global_setting('last_update_check', str(current_time))
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            # Reset the last check time on error
            try:
                self.config_manager.set_global_setting('last_update_check', '0')
            except:
                pass
    
    def on_translation_mode_changed(self):
        """Handle translation mode change."""
        try:
            mode_index = self.mode_combo.currentIndex()
            if mode_index == 0:
                mode = 'google'
            elif mode_index == 1:
                mode = 'local'
            else:  # mode_index == 2
                mode = 'libretranslate'
            self.config_manager.set_translation_mode(mode)
            self.update_translation_mode_ui()
            logger.info(f"Translation mode changed to: {mode}")
        except Exception as e:
            logger.error(f"Error changing translation mode: {str(e)}", exc_info=True)
    
    def update_translation_mode_ui(self):
        """Update UI based on selected translation mode."""
        try:
            mode = self.config_manager.get_translation_mode()
            is_local_mode = (mode == 'local')
            is_libretranslate_mode = (mode == 'libretranslate')
            
            # Show/hide LLM Studio settings (if it exists)
            if hasattr(self, 'llm_studio_group'):
                self.llm_studio_group.setVisible(is_local_mode)
            
            # Show/hide LibreTranslate settings (if it exists)
            if hasattr(self, 'libretranslate_group'):
                self.libretranslate_group.setVisible(is_libretranslate_mode)
            
            # Show/hide Google Cloud credentials (if it exists)
            if hasattr(self, 'credentials_group'):
                self.credentials_group.setVisible(not is_local_mode and not is_libretranslate_mode)
            
            # Update Tesseract path field visibility based on OCR mode
            if is_local_mode or is_libretranslate_mode:
                ocr_mode = self.config_manager.get_ocr_mode()
                is_tesseract_mode = (ocr_mode == 'tesseract')
                if hasattr(self, 'tesseract_path_layout'):
                    for i in range(self.tesseract_path_layout.count()):
                        widget = self.tesseract_path_layout.itemAt(i).widget()
                        if widget:
                            widget.setVisible(is_tesseract_mode)
                if hasattr(self, 'libretranslate_tesseract_path_layout'):
                    for i in range(self.libretranslate_tesseract_path_layout.count()):
                        widget = self.libretranslate_tesseract_path_layout.itemAt(i).widget()
                        if widget:
                            widget.setVisible(is_tesseract_mode)
        except Exception as e:
            logger.error(f"Error updating translation mode UI: {str(e)}", exc_info=True)
    
    def on_llm_studio_url_changed(self):
        """Handle LLM Studio URL change."""
        try:
            url = self.llm_studio_edit.text()
            if url:
                self.config_manager.set_llm_studio_url(url)
                logger.info(f"LLM Studio URL changed to: {url}")
        except Exception as e:
            logger.error(f"Error changing LLM Studio URL: {str(e)}", exc_info=True)
    
    def on_llm_studio_model_changed(self):
        """Handle LLM Studio model name change."""
        try:
            model = self.llm_studio_model_edit.text()
            self.config_manager.set_llm_studio_model(model)
            logger.info(f"LLM Studio model changed to: {model if model else 'auto-detect'}")
        except Exception as e:
            logger.error(f"Error changing LLM Studio model: {str(e)}", exc_info=True)
    
    def on_ocr_mode_changed(self):
        """Handle OCR mode change."""
        try:
            # Get the sender widget to determine which combo changed
            sender = self.sender()
            mode_index = None
            
            if hasattr(self, 'ocr_mode_combo') and sender == self.ocr_mode_combo:
                mode_index = self.ocr_mode_combo.currentIndex()
            elif hasattr(self, 'libretranslate_ocr_mode_combo') and sender == self.libretranslate_ocr_mode_combo:
                mode_index = self.libretranslate_ocr_mode_combo.currentIndex()
            else:
                # Fallback to current config value (used during initialization)
                current_mode = self.config_manager.get_ocr_mode()
                mode_index = 0 if current_mode == 'tesseract' else 1
            
            mode = 'tesseract' if mode_index == 0 else 'paddleocr'
            
            # Only update config if sender is not None (i.e., user changed it)
            if sender is not None:
                self.config_manager.set_ocr_mode(mode)
            
            # Sync both OCR mode combos if they exist
            if hasattr(self, 'ocr_mode_combo') and sender != self.ocr_mode_combo:
                self.ocr_mode_combo.blockSignals(True)
                self.ocr_mode_combo.setCurrentIndex(mode_index)
                self.ocr_mode_combo.blockSignals(False)
            if hasattr(self, 'libretranslate_ocr_mode_combo') and sender != self.libretranslate_ocr_mode_combo:
                self.libretranslate_ocr_mode_combo.blockSignals(True)
                self.libretranslate_ocr_mode_combo.setCurrentIndex(mode_index)
                self.libretranslate_ocr_mode_combo.blockSignals(False)
            
            # Update Tesseract path field visibility based on OCR mode
            is_tesseract_mode = (mode == 'tesseract')
            if hasattr(self, 'tesseract_path_layout'):
                for i in range(self.tesseract_path_layout.count()):
                    widget = self.tesseract_path_layout.itemAt(i).widget()
                    if widget:
                        widget.setVisible(is_tesseract_mode)
            if hasattr(self, 'libretranslate_tesseract_path_layout'):
                for i in range(self.libretranslate_tesseract_path_layout.count()):
                    widget = self.libretranslate_tesseract_path_layout.itemAt(i).widget()
                    if widget:
                        widget.setVisible(is_tesseract_mode)
            
            logger.info(f"OCR mode changed to: {mode}")
        except Exception as e:
            logger.error(f"Error changing OCR mode: {str(e)}", exc_info=True)
    
    def on_tesseract_path_changed(self):
        """Handle Tesseract path change."""
        try:
            # Get the sender widget to determine which field changed
            sender = self.sender()
            if sender == self.tesseract_path_edit:
                path = self.tesseract_path_edit.text().strip()
            elif hasattr(self, 'libretranslate_tesseract_path_edit') and sender == self.libretranslate_tesseract_path_edit:
                path = self.libretranslate_tesseract_path_edit.text().strip()
            else:
                # Fallback: try to get from whichever is visible
                if hasattr(self, 'tesseract_path_edit') and self.tesseract_path_edit.isVisible():
                    path = self.tesseract_path_edit.text().strip()
                elif hasattr(self, 'libretranslate_tesseract_path_edit') and self.libretranslate_tesseract_path_edit.isVisible():
                    path = self.libretranslate_tesseract_path_edit.text().strip()
                else:
                    path = self.config_manager.get_tesseract_path()
            
            if path:
                # Validate path if provided
                if not os.path.exists(path):
                    logger.warning(f"Tesseract path does not exist: {path}")
                elif not os.path.isfile(path):
                    logger.warning(f"Tesseract path is not a file: {path}")
                elif os.name == 'nt' and not path.lower().endswith('.exe'):
                    logger.warning(f"Tesseract path should point to .exe file: {path}")
            
            self.config_manager.set_tesseract_path(path)
            
            # Sync both fields if they exist (to keep them in sync)
            if hasattr(self, 'tesseract_path_edit') and sender != self.tesseract_path_edit:
                self.tesseract_path_edit.blockSignals(True)
                self.tesseract_path_edit.setText(path)
                self.tesseract_path_edit.blockSignals(False)
            if hasattr(self, 'libretranslate_tesseract_path_edit') and sender != self.libretranslate_tesseract_path_edit:
                self.libretranslate_tesseract_path_edit.blockSignals(True)
                self.libretranslate_tesseract_path_edit.setText(path)
                self.libretranslate_tesseract_path_edit.blockSignals(False)
            
            logger.info(f"Tesseract path changed to: {path if path else 'system PATH'}")
        except Exception as e:
            logger.error(f"Error changing Tesseract path: {str(e)}", exc_info=True)
    
    def browse_tesseract_path(self):
        """Browse for Tesseract executable."""
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        
        # On Windows, Tesseract is typically tesseract.exe
        # Default to common installation locations
        default_paths = [
            r"C:\Program Files\Tesseract-OCR",
            r"C:\Program Files (x86)\Tesseract-OCR",
            os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR")
        ]
        
        start_dir = ""
        for path in default_paths:
            if os.path.exists(path):
                start_dir = path
                break
        
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Tesseract Executable (tesseract.exe)",
            start_dir,
            "Executable Files (*.exe);;All Files (*)"
        )
        if file_name:
            # Validate that it's actually tesseract.exe
            if not file_name.lower().endswith('.exe'):
                QMessageBox.warning(
                    self,
                    "Invalid File",
                    "Please select the tesseract.exe executable file."
                )
                return
            
            # Check if file exists and is accessible
            if not os.path.exists(file_name):
                QMessageBox.warning(
                    self,
                    "File Not Found",
                    f"The selected file does not exist:\n{file_name}"
                )
                return
            
            if not os.path.isfile(file_name):
                QMessageBox.warning(
                    self,
                    "Invalid Selection",
                    f"The selected path is not a file:\n{file_name}\n\nPlease select tesseract.exe"
                )
                return
            
            # Check if file is accessible
            if not os.access(file_name, os.R_OK):
                QMessageBox.warning(
                    self,
                    "Access Warning",
                    f"Cannot read the selected file:\n{file_name}\n\n"
                    "You may need to run the application as Administrator."
                )
            
            # Check if file is executable (on Windows, .exe files should be executable)
            if os.name == 'nt' and not os.access(file_name, os.X_OK):
                reply = QMessageBox.question(
                    self,
                    "Permission Warning",
                    f"The file may not be executable:\n{file_name}\n\n"
                    "This might cause permission errors.\n"
                    "Do you want to continue anyway?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
            
            # Update both Tesseract path fields if they exist
            if hasattr(self, 'tesseract_path_edit'):
                self.tesseract_path_edit.blockSignals(True)
                self.tesseract_path_edit.setText(file_name)
                self.tesseract_path_edit.blockSignals(False)
            if hasattr(self, 'libretranslate_tesseract_path_edit'):
                self.libretranslate_tesseract_path_edit.blockSignals(True)
                self.libretranslate_tesseract_path_edit.setText(file_name)
                self.libretranslate_tesseract_path_edit.blockSignals(False)
            
            self.config_manager.set_tesseract_path(file_name)
            logger.info(f"Tesseract path configured: {file_name}")
            
            # Show success message
            QMessageBox.information(
                self,
                "Path Configured",
                f"Tesseract path has been set to:\n{file_name}\n\n"
                "The path will be used for text detection in Local LM and LibreTranslate modes.\n"
                "Click 'Test' to verify Tesseract is working."
            )
    
    def test_tesseract(self):
        """Test if Tesseract is working correctly."""
        try:
            from src.text_processing import TextProcessor
            import numpy as np
            from PIL import Image
            
            # Get the configured path
            tesseract_path = self.config_manager.get_tesseract_path()
            
            # Try to import pytesseract
            try:
                import pytesseract
            except ImportError:
                QMessageBox.warning(
                    self,
                    "Test Failed",
                    "pytesseract is not installed.\n\n"
                    "Please install it using:\npip install pytesseract"
                )
                return
            
            # Configure path if set
            if tesseract_path:
                if not os.path.exists(tesseract_path):
                    QMessageBox.warning(
                        self,
                        "Test Failed",
                        f"Tesseract path does not exist:\n{tesseract_path}\n\n"
                        "Please check the path and try again."
                    )
                    return
                
                # Check file permissions before attempting to use it
                if not os.access(tesseract_path, os.X_OK):
                    QMessageBox.warning(
                        self,
                        "Permission Warning",
                        f"The Tesseract executable may not be accessible:\n{tesseract_path}\n\n"
                        "The file exists but may have permission restrictions.\n"
                        "Try running the application as Administrator."
                    )
                
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            
            # Create a simple test image with text
            test_image = Image.new('RGB', (200, 50), color='white')
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(test_image)
            try:
                # Try to use a default font
                font = ImageFont.load_default()
            except:
                font = None
            draw.text((10, 10), "Test 123", fill='black', font=font)
            
            # Convert to numpy array
            test_array = np.array(test_image)
            
            # Try to extract text
            try:
                text = pytesseract.image_to_string(test_array, lang='eng')
                if text.strip():
                    QMessageBox.information(
                        self,
                        "Test Successful",
                        f"Tesseract is working correctly!\n\n"
                        f"Path: {tesseract_path if tesseract_path else 'System PATH'}\n"
                        f"Detected text: '{text.strip()}'"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Test Warning",
                        "Tesseract executed but did not detect text.\n\n"
                        "This might be normal for simple test images.\n"
                        "Try using it with actual screen captures."
                    )
            except Exception as e:
                error_msg = str(e)
                if 'not found' in error_msg.lower() or 'tesseract' in error_msg.lower():
                    QMessageBox.critical(
                        self,
                        "Test Failed",
                        f"Tesseract not found:\n{error_msg}\n\n"
                        "Please:\n"
                        "1. Install Tesseract OCR\n"
                        "2. Configure the correct path\n"
                        "3. Ensure it's in your system PATH"
                    )
                elif 'access' in error_msg.lower() or 'permission' in error_msg.lower() or 'winerror 5' in error_msg.lower():
                    detailed_msg = (
                        f"Permission denied:\n{error_msg}\n\n"
                        "This error usually occurs when:\n"
                        "• Windows Defender or antivirus blocks Tesseract\n"
                        "• The file is in a protected location (Program Files)\n"
                        "• User Account Control (UAC) restrictions\n\n"
                        "Solutions (try in order):\n\n"
                        "1. Run as Administrator:\n"
                        "   Right-click the application → 'Run as administrator'\n\n"
                        "2. Add Tesseract to antivirus exclusions:\n"
                        "   Windows Security → Virus & threat protection →\n"
                        "   Manage settings → Exclusions → Add folder\n\n"
                        "3. Reinstall Tesseract to a user folder:\n"
                        "   Install to: C:\\Tesseract-OCR (instead of Program Files)\n\n"
                        "4. Check file permissions:\n"
                        "   Right-click tesseract.exe → Properties → Security\n"
                        "   Ensure your user has 'Execute' permission"
                    )
                    QMessageBox.critical(
                        self,
                        "Test Failed - Permission Denied",
                        detailed_msg
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Test Failed",
                        f"Error testing Tesseract:\n{error_msg}"
                    )
        except Exception as e:
            logger.error(f"Error testing Tesseract: {str(e)}", exc_info=True)
            QMessageBox.critical(
                self,
                "Test Error",
                f"An error occurred while testing Tesseract:\n{str(e)}"
            )
    
    def on_libretranslate_url_changed(self):
        """Handle LibreTranslate URL change."""
        try:
            url = self.libretranslate_edit.text()
            if url:
                self.config_manager.set_libretranslate_url(url)
                logger.info(f"LibreTranslate URL changed to: {url}")
        except Exception as e:
            logger.error(f"Error changing LibreTranslate URL: {str(e)}", exc_info=True)
    
    def test_libretranslate(self):
        """Test if LibreTranslate API is accessible."""
        try:
            from src.translator.libretranslate_translator import LibreTranslateTranslator
            from PyQt5.QtWidgets import QMessageBox
            
            url = self.libretranslate_edit.text() or self.config_manager.get_libretranslate_url()
            if not url:
                QMessageBox.warning(
                    self,
                    "Test Failed",
                    "Please enter a LibreTranslate API URL."
                )
                return
            
            translator = LibreTranslateTranslator(url)
            if translator.test_connection():
                QMessageBox.information(
                    self,
                    "Test Successful",
                    f"LibreTranslate connection successful!\n\n"
                    f"API URL: {url}\n\n"
                    "The API is ready to use."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Test Failed",
                    f"Could not connect to LibreTranslate API.\n\n"
                    f"API URL: {url}\n\n"
                    "Please check:\n"
                    "1. The LibreTranslate server is running\n"
                    "2. The URL is correct\n"
                    "3. The server is accessible from this computer"
                )
        except Exception as e:
            logger.error(f"Error testing LibreTranslate: {str(e)}", exc_info=True)
            QMessageBox.critical(
                self,
                "Test Error",
                f"An error occurred while testing LibreTranslate:\n{str(e)}"
            )