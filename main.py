import sys
import os
import logging

# Compatibility fix for Python < 3.10
# packages_distributions was added in Python 3.10
if sys.version_info < (3, 10):
    try:
        import importlib.metadata as metadata
        if not hasattr(metadata, 'packages_distributions'):
            # Add a dummy function for compatibility
            # Some libraries call this as a function, others access it as an attribute
            def _packages_distributions():
                return {}
            # Make it work both as function and attribute access
            metadata.packages_distributions = _packages_distributions
            # Also patch the module dict in case it's accessed differently
            if hasattr(metadata, '__dict__'):
                metadata.__dict__['packages_distributions'] = _packages_distributions
    except (ImportError, AttributeError):
        # If importlib.metadata doesn't exist, importlib-metadata package will provide it
        pass

from PyQt5.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.text_processing import TextProcessor
from src.ui.utils import validate_credentials
from src.config_manager import ConfigManager

# Configure logging
# Create logs directory in AppData if it doesn't exist
appdata_path = os.path.join(os.getenv('APPDATA'), 'DainnScreenTranslator')
logs_path = os.path.join(appdata_path, 'logs')
os.makedirs(logs_path, exist_ok=True)

log_file = os.path.join(logs_path, 'trans.log')

# Fix Unicode encoding issues on Windows by forcing UTF-8
# This prevents 'charmap' codec errors when logging Vietnamese characters
import io
stream_handler = logging.StreamHandler(
    io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        stream_handler,
        logging.FileHandler(log_file, mode='w', encoding='utf-8')
    ]
)

# Set logging level for all loggers
for logger_name in ['src.text_processing', 'src.ui.translation_window', 'src.ui.main_window']:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

def main():
    try:
        # Initialize config manager
        config_manager = ConfigManager()
        translation_mode = config_manager.get_translation_mode()
        
        logger.info(f"Translation mode: {translation_mode}")

        translate_client = None
        vision_client = None
        llm_studio_translator = None
        libretranslate_translator = None

        if translation_mode == 'google':
            # Google Cloud mode
            credentials_path = config_manager.get_credentials_path()

            # Validate credentials
            if not validate_credentials(credentials_path):
                logger.warning("No valid Google Cloud credentials found. Please set up credentials in the settings.")
                # Create main window anyway to allow user to set up credentials
                app = QApplication(sys.argv)
                main_window = MainWindow(None)  # Pass None as text_processor
                main_window.show()
                return app.exec()

            # Set Google Cloud credentials environment variable
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path

            logger.info("Initializing Google Cloud clients...")
            # Initialize Google Cloud clients
            from google.cloud import translate_v2 as translate
            from google.cloud import vision

            translate_client = translate.Client()
            vision_client = vision.ImageAnnotatorClient()
            logger.info("Google Cloud clients initialized successfully")
        elif translation_mode == 'libretranslate':
            # LibreTranslate mode
            logger.info("Initializing LibreTranslate translator...")
            from src.translator.libretranslate_translator import LibreTranslateTranslator
            
            libretranslate_url = config_manager.get_libretranslate_url()
            libretranslate_translator = LibreTranslateTranslator(libretranslate_url)
            
            # Test connection
            if libretranslate_translator.test_connection():
                logger.info("LibreTranslate connection successful")
            else:
                logger.warning("LibreTranslate connection test failed. The API may not be running.")
        else:
            # Local LLM mode - will be initialized in background thread
            llm_studio_translator = None
            logger.info("LLM Studio translator will be initialized in background thread")

        logger.info("Creating TextProcessor...")
        text_processor = TextProcessor(
            translate_client=translate_client,
            vision_client=vision_client,
            llm_studio_translator=llm_studio_translator,
            libretranslate_translator=libretranslate_translator
        )
        logger.info("TextProcessor created successfully")

        logger.info("Creating MainWindow...")
        app = QApplication(sys.argv)
        main_window = MainWindow(text_processor, config_manager)
        main_window.show()
        logger.info("MainWindow created successfully")
        
        # Start LLM initialization in background thread if in local mode
        if translation_mode == 'local':
            main_window.init_llm_in_background()

        return app.exec()

    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())