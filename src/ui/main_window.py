import os
import sys
import json
import logging
import time
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QColorDialog, QMessageBox, QApplication, QSpinBox, QDoubleSpinBox,
    QScrollArea, QFrame, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QColor
from src.config_manager import ConfigManager
from src.screen_capture import capture_screen_region
from src.ui.translation_window import TranslationWindow
from src.ui.utils import get_resource_path, validate_credentials, show_error_message
from src.text_processing import TextProcessor
from src.translator_service import TranslatorService
from src.version_checker import VersionChecker

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Main application window for the real-time screen translator."""
    
    def __init__(self, text_processor: TextProcessor):
        super().__init__()
        self.setWindowTitle("Real-time Screen Translator")
        self.setGeometry(100, 100, 900, 400)
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
        self.config_manager = ConfigManager()

        # Version checker
        self.version_checker = VersionChecker()
        self.version_check_timer = QTimer()
        self.version_check_timer.timeout.connect(self.check_for_updates)
        self.version_check_timer.start(3600000)  # Check every hour

        # Initialize UI
        self.init_ui()
        self.load_languages_from_config()
        self.load_saved_areas()
        self.update_button_states()

        self.text_processor = text_processor
        self.translation_windows = {}

        # Check for updates after a short delay to ensure the window is fully loaded
        QTimer.singleShot(2000, self.check_for_updates)

    def init_ui(self):
        """Initialize the user interface."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # Settings panel
        self.settings_group = QGroupBox("Settings")
        self.settings_group.setStyleSheet(
            f"QGroupBox {{ font: 10pt 'Google Sans'; color: {self.text_color}; background-color: {self.frame_bg}; }}"
        )
        self.main_layout.addWidget(self.settings_group)
        self.settings_layout = QVBoxLayout(self.settings_group)

        # Font settings
        self.font_group = QGroupBox("Font Settings")
        self.font_group.setStyleSheet(f"background-color: {self.frame_bg};")
        self.settings_layout.addWidget(self.font_group)
        self.font_layout = QHBoxLayout(self.font_group)

        self.font_label = QLabel("Font:")
        self.font_layout.addWidget(self.font_label)
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Google Sans", "Segoe UI", "Consolas", "Courier New", "Lucida Console", "Monospace"])
        self.font_combo.setCurrentText(self.config_manager.get_global_setting('font_family', 'Google Sans'))
        self.font_combo.currentTextChanged.connect(self.update_translation_settings)
        self.font_layout.addWidget(self.font_combo)

        self.size_label = QLabel("Size:")
        self.font_layout.addWidget(self.size_label)
        self.font_size_edit = QLineEdit()
        self.font_size_edit.setFixedWidth(40)
        self.font_size_edit.setText(self.config_manager.get_global_setting('font_size', '14'))
        self.font_size_edit.textChanged.connect(self.update_translation_settings)
        self.font_layout.addWidget(self.font_size_edit)

        self.style_label = QLabel("Style:")
        self.font_layout.addWidget(self.style_label)
        self.font_style_combo = QComboBox()
        self.font_style_combo.addItems(["normal", "bold", "italic"])
        self.font_style_combo.setCurrentText(self.config_manager.get_global_setting('font_style', 'normal'))
        self.font_style_combo.currentTextChanged.connect(self.update_translation_settings)
        self.font_layout.addWidget(self.font_style_combo)

        # Color settings
        self.color_group = QGroupBox("Color Settings")
        self.color_group.setStyleSheet(f"background-color: {self.frame_bg};")
        self.settings_layout.addWidget(self.color_group)
        self.color_layout = QHBoxLayout(self.color_group)

        self.name_color_label = QLabel("Name Color:")
        self.color_layout.addWidget(self.name_color_label)
        self.name_color_button = QPushButton("Pick Color")
        self.name_color_button.clicked.connect(lambda: self.pick_color('name_color'))
        self.color_layout.addWidget(self.name_color_button)
        self.name_color_preview = QLabel()
        self.name_color_preview.setFixedSize(20, 20)
        self.name_color_value = self.config_manager.get_global_setting('name_color', '#00ffff')
        self.name_color_preview.setStyleSheet(f"background-color: {self.name_color_value}; border: 1px solid black;")
        self.color_layout.addWidget(self.name_color_preview)

        self.dialogue_color_label = QLabel("Dialogue Color:")
        self.color_layout.addWidget(self.dialogue_color_label)
        self.dialogue_color_button = QPushButton("Pick Color")
        self.dialogue_color_button.clicked.connect(lambda: self.pick_color('dialogue_color'))
        self.color_layout.addWidget(self.dialogue_color_button)
        self.dialogue_color_preview = QLabel()
        self.dialogue_color_preview.setFixedSize(20, 20)
        self.dialogue_color_value = self.config_manager.get_global_setting('dialogue_color', '#00ff00')
        self.dialogue_color_preview.setStyleSheet(f"background-color: {self.dialogue_color_value}; border: 1px solid black;")
        self.color_layout.addWidget(self.dialogue_color_preview)

        # Background settings
        self.bg_group = QGroupBox("Background Settings")
        self.bg_group.setStyleSheet(f"background-color: {self.frame_bg};")
        self.settings_layout.addWidget(self.bg_group)
        self.bg_layout = QHBoxLayout(self.bg_group)

        self.bg_color_label = QLabel("Background Color:")
        self.bg_layout.addWidget(self.bg_color_label)
        self.bg_color_button = QPushButton("Pick Color")
        self.bg_color_button.clicked.connect(self.pick_background_color)
        self.bg_layout.addWidget(self.bg_color_button)
        self.bg_color_preview = QLabel()
        self.bg_color_preview.setFixedSize(20, 20)
        self.bg_color_value = self.config_manager.get_background_color()
        self.bg_color_preview.setStyleSheet(f"background-color: {self.bg_color_value}; border: 1px solid black;")
        self.bg_layout.addWidget(self.bg_color_preview)

        self.opacity_label = QLabel("Opacity:")
        self.bg_layout.addWidget(self.opacity_label)
        self.opacity_edit = QLineEdit()
        self.opacity_edit.setFixedWidth(40)
        self.opacity_edit.setText('0.85')
        self.opacity_edit.textChanged.connect(self.update_opacity)
        self.bg_layout.addWidget(self.opacity_edit)

        # Language settings
        self.language_group = QGroupBox("Language Settings")
        self.language_group.setStyleSheet(f"background-color: {self.frame_bg};")
        self.settings_layout.addWidget(self.language_group)
        self.language_layout = QHBoxLayout(self.language_group)

        self.source_lang_label = QLabel("Source Language:")
        self.language_layout.addWidget(self.source_lang_label)
        self.source_lang_combo = QComboBox()
        self.language_layout.addWidget(self.source_lang_combo)

        self.target_lang_label = QLabel("Target Language:")
        self.language_layout.addWidget(self.target_lang_label)
        self.target_lang_combo = QComboBox()
        self.language_layout.addWidget(self.target_lang_combo)

        # Credentials settings
        self.credentials_group = QGroupBox("Google Cloud Settings")
        self.credentials_group.setStyleSheet(f"background-color: {self.frame_bg};")
        self.settings_layout.addWidget(self.credentials_group)
        self.credentials_layout = QHBoxLayout(self.credentials_group)

        self.credentials_label = QLabel("Credentials Path:")
        self.credentials_layout.addWidget(self.credentials_label)
        self.credentials_edit = QLineEdit()
        self.credentials_edit.setText(self.config_manager.get_credentials_path())
        self.credentials_layout.addWidget(self.credentials_edit)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_credentials)
        self.credentials_layout.addWidget(self.browse_button)

        # Translation areas panel
        self.areas_group = QGroupBox("Translation Areas")
        self.areas_group.setStyleSheet(
            f"QGroupBox {{ font: 10pt 'Google Sans'; color: {self.text_color}; background-color: {self.frame_bg}; }}"
        )
        self.main_layout.addWidget(self.areas_group)
        self.areas_layout = QVBoxLayout(self.areas_group)

        self.areas_tree = QTreeWidget()
        self.areas_tree.setHeaderLabels(["Name", "Position", "Size"])
        self.areas_tree.setStyleSheet(f"background-color: {self.frame_bg};")
        self.areas_layout.addWidget(self.areas_tree)

        self.buttons_layout = QHBoxLayout()
        self.areas_layout.addLayout(self.buttons_layout)

        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_area)
        self.buttons_layout.addWidget(self.add_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_area)
        self.buttons_layout.addWidget(self.delete_button)

        self.start_button = QPushButton("Run")
        self.start_button.clicked.connect(self.start_translation)
        self.buttons_layout.addWidget(self.start_button)

        # Styling buttons
        for btn in [self.add_button, self.delete_button, self.start_button, self.browse_button,
                    self.name_color_button, self.dialogue_color_button, self.bg_color_button]:
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {self.button_bg}; color: {self.button_fg}; padding: 5px; }}"
                f"QPushButton:hover {{ background-color: {self.secondary_color}; }}"
            )

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
                        f"W: {area_data['width']}, H: {area_data['height']}"
                    ])
                    item.setData(0, Qt.UserRole, area_id)
                    self.areas_tree.addTopLevelItem(item)
            self.area_selected = self.areas_tree.topLevelItemCount() > 0
            self.update_button_states()
            logger.info("Areas loaded successfully")
        except Exception as e:
            logger.error(f"Error loading saved areas: {str(e)}", exc_info=True)

    def add_area(self):
        """Add a new translation area."""
        self.hide()
        screenshot, region = capture_screen_region(False)
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
                f"W: {w}, H: {h}"
            ])
            item.setData(0, Qt.UserRole, area_id)
            self.areas_tree.addTopLevelItem(item)
            self.save_area_config(area_id, x, y, w, h)
            self.area_selected = True
            self.update_button_states()
        self.show()

    def delete_area(self):
        """Delete a selected area."""
        selected = self.areas_tree.selectedItems()
        if selected:
            area_id = selected[0].data(0, Qt.UserRole)
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
                
                # Then remove from tree and config
                index = self.areas_tree.indexOfTopLevelItem(selected[0])
                self.areas_tree.takeTopLevelItem(index)
                self.remove_area_from_config(area_id)
                
                # Update area selection state
                self.area_selected = self.areas_tree.topLevelItemCount() > 0
                self.update_button_states()
                
                # If no more translation windows are open, re-enable settings
                if not self.translation_windows:
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
                'opacity': self.opacity_edit.text()
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
            translation_window.timer.start(1000)
            self.translation_windows[area_id] = translation_window
            
            # Connect the closeEvent of the translation window
            translation_window.closeEvent = lambda event: self.handle_translation_window_close(event, area_id)
            
            translation_window.show()
            
            # Disable settings when translation window is opened
            self.update_settings_state(False)
            
            logger.info("Translation window created and shown")
        except Exception as e:
            logger.error(f"Error in start_translation: {str(e)}", exc_info=True)
            show_error_message(self, "Error", f"Failed to start translation: {str(e)}")

    def handle_translation_window_close(self, event, area_id):
        """Handle the closure of a translation window."""
        try:
            if area_id in self.translation_windows:
                window = self.translation_windows[area_id]
                window.running = False
                window.timer.stop()
                del self.translation_windows[area_id]
            
            # If no more translation windows are open, re-enable settings
            if not self.translation_windows:
                self.update_settings_state(enabled=True)  # Explicitly pass True
            
            event.accept()
        except Exception as e:
            logger.error(f"Error handling translation window close: {str(e)}", exc_info=True)
            event.accept()

    def closeEvent(self, event):
        """Handle window close event."""
        # Save window position
        if self.config_manager:
            self.config_manager.set_global_setting('main_window_pos', f"{self.x()},{self.y()}")
        
        # Close all translation windows
        for area_id in list(self.translation_windows.keys()):  # Create a copy of keys to avoid modification during iteration
            try:
                window = self.translation_windows.get(area_id)
                if window and window.isVisible():
                    window.close()
                # Remove from dictionary regardless of whether it was closed or not
                self.translation_windows.pop(area_id, None)
            except Exception as e:
                logger.error(f"Error closing translation window {area_id}: {str(e)}")
                # Continue with other windows even if one fails
                continue
        
        # Stop the translation timer
        if hasattr(self, 'timer') and self.timer:
            self.timer.stop()
        
        # Accept the close event
        event.accept()

    def update_button_states(self):
        """Update button states based on area selection."""
        self.delete_button.setEnabled(self.area_selected)
        self.start_button.setEnabled(self.area_selected)

    def update_settings_state(self, enabled: bool):
        """Enable or disable all settings controls."""
        try:
            # Ensure enabled is a boolean
            enabled = bool(enabled) if enabled is not None else True
            
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
            
            # Credentials settings
            if hasattr(self, 'credentials_edit'):
                self.credentials_edit.setEnabled(enabled)
            if hasattr(self, 'browse_button'):
                self.browse_button.setEnabled(enabled)
            
            # Area management buttons - always enabled
            if hasattr(self, 'add_button'):
                self.add_button.setEnabled(True)
            if hasattr(self, 'delete_button'):
                self.delete_button.setEnabled(self.area_selected)
            if hasattr(self, 'start_button'):
                self.start_button.setEnabled(self.area_selected)

            # Update button styles
            disabled_style = """
                QPushButton {
                    background-color: #cccccc;
                    color: #666666;
                    border: 1px solid #999999;
                    padding: 5px;
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
                    padding: 5px;
                }}
                QPushButton:hover {{
                    background-color: {self.secondary_color};
                }}
            """

            # Apply styles to color and browse buttons
            for btn in [self.name_color_button, self.dialogue_color_button, 
                       self.bg_color_button, self.browse_button]:
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
                'opacity': self.opacity_edit.text()
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
                    'opacity': str(opacity)
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