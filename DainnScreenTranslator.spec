# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for Dainn Screen Translator
# This spec file is configured for directory distribution (onedir mode)
# which is optimized for Inno Setup installer creation.
# Output will be in dist/DainnScreenTranslator/ directory.
#

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config/config.ini', 'config'),
        ('resources/logo.ico', 'resources'),
        ('resources/logo.png', 'resources'),
    ],
    hiddenimports=[
        # Core dependencies
        'numpy',
        'PIL',
        'PIL._tkinter_finder',
        'PIL._imaging',
        'cv2',
        
        # Google Cloud APIs
        'google.cloud.vision',
        'google.cloud.translate',
        'pkg_resources',
        'setuptools',
        
        # PyQt5 GUI
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        'PyQt5.QtCore',
        
        # Screen capture
        'pyautogui',
        'pyscreeze',
        
        # UI components
        'customtkinter',
        
        # Standard library modules
        'configparser',
        'logging',
        'json',
        'threading',
        'concurrent.futures',
        'collections',
        'typing',
        'datetime',
        'hashlib',
        'requests',
        'html',
        'ctypes',
        'ctypes.wintypes'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Testing and debugging
        'sqlite3', 'test', '__main__', 'unittest', 'pydoc', 'pydoc_data',
        
        # Network protocols not needed
        'ftplib', 'netrc', 'xmlrpc', 'curses', '_pyrepl',
        
        # Unused PyQt5 modules
        'PyQt5.QtPrintSupport', 'PyQt5.QtBluetooth', 'PyQt5.QtDesigner', 
        'PyQt5.QtMultimedia', 'PyQt5.QtNetwork', 'PyQt5.QtOpenGL', 
        'PyQt5.QtSql', 'PyQt5.QtTest', 'PyQt5.QtWebEngine',
        
        # Unused ML/AI frameworks
        'torch', 'torchvision', 'tensorflow', 'keras',
        
        # Unused OCR libraries
        'easyocr', 'pytesseract', 'tesseract',
        
        # Unused Google Cloud services
        'google.cloud.storage', 'google.cloud.bigquery', 'google.cloud.pubsub',
        'google.cloud.datastore', 'google.cloud.firestore', 'google.cloud.spanner',
        'google.cloud.bigtable', 'google.cloud.redis', 'google.cloud.memcache',
        'google.cloud.tasks', 'google.cloud.scheduler', 'google.cloud.monitoring',
        'google.cloud.logging', 'google.cloud.error_reporting', 'google.cloud.trace',
        'google.cloud.profiler', 'google.cloud.debugger', 'google.cloud.testing',
        'google.cloud.resource_manager', 'google.cloud.iam', 'google.cloud.kms',
        'google.cloud.secret_manager', 'google.cloud.security_center',
        'google.cloud.websecurityscanner', 'google.cloud.recaptcha_enterprise',
        'google.cloud.dlp', 'google.cloud.asset', 'google.cloud.orgpolicy',
        'google.cloud.access_approval', 'google.cloud.access_context_manager',
        'google.cloud.osconfig', 'google.cloud.oslogin', 'google.cloud.compute',
        'google.cloud.appengine', 'google.cloud.cloudfunctions', 'google.cloud.run',
        'google.cloud.workflows', 'google.cloud.iot'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Directory mode - required for Inno Setup packaging
    name='DainnScreenTranslator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['Qt5Core.dll', 'Qt5Gui.dll', 'Qt5Widgets.dll', 'python3*.dll'],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources\\logo.ico',
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['Qt5Core.dll', 'Qt5Gui.dll', 'Qt5Widgets.dll', 'python3*.dll'],
    name='DainnScreenTranslator',  # Output directory: dist/DainnScreenTranslator/
)