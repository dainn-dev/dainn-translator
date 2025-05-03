def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Settings")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setFixedSize(400, 600)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #2a2a2a;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #4a4a4a;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #5a5a5a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(15)
        
        # Create settings groups
        self.create_general_group(content_layout)
        self.create_appearance_group(content_layout)
        self.create_ocr_group(content_layout)
        self.create_translation_group(content_layout)
        self.create_shortcuts_group(content_layout)
        
        # Add content to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Add stretch to push buttons to bottom
        main_layout.addStretch()
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.setFixedHeight(40)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.save_button.clicked.connect(self.save_settings)
        buttons_layout.addWidget(self.save_button)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedHeight(40)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #ba000d;
            }
        """)
        self.cancel_button.clicked.connect(self.close)
        buttons_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(buttons_layout)
        self.setLayout(main_layout)
        
        # Set window style
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 5px 10px;
                min-height: 25px;
                color: #ffffff;
                selection-background-color: #4a4a4a;
                selection-color: #ffffff;
            }
            QComboBox:hover {
                border: 1px solid #4a4a4a;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #3a3a3a;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: #2a2a2a;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                width: 0;
                height: 0;
                margin-right: 3px;
            }
            QComboBox::down-arrow:on {
                border-top: 5px solid #4a4a4a;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                selection-background-color: #4a4a4a;
                selection-color: #ffffff;
                outline: none;
                padding: 5px;
            }
            QComboBox QAbstractItemView::item {
                padding: 5px 10px;
                border-radius: 4px;
                margin: 2px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #3a3a3a;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #4a4a4a;
            }
            QComboBox:on {
                border: 1px solid #4a4a4a;
                background-color: #2a2a2a;
            }
            QComboBox:!on {
                border: 1px solid #3a3a3a;
                background-color: #2a2a2a;
            }
            QComboBox::item {
                padding: 5px 10px;
            }
            QComboBox::item:selected {
                background-color: #4a4a4a;
            }
            QLineEdit {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 5px 10px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #4a4a4a;
            }
            QSpinBox {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 5px 10px;
                color: #ffffff;
            }
            QSpinBox:hover {
                border: 1px solid #4a4a4a;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                border: none;
                background-color: #3a3a3a;
                border-radius: 3px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #4a4a4a;
            }
            QSpinBox::up-arrow, QSpinBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
            }
            QSpinBox::up-arrow {
                border-bottom: 5px solid #ffffff;
            }
            QSpinBox::down-arrow {
                border-top: 5px solid #ffffff;
            }
            QCheckBox {
                color: #ffffff;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #3a3a3a;
                border-radius: 4px;
                background-color: #2a2a2a;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #4a4a4a;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 2px solid #4CAF50;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #45a049;
                border: 2px solid #45a049;
            }
        """) 