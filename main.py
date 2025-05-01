import sys
import os
import logging
from PyQt5.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.text_processing import TextProcessor
from src.ui.utils import validate_credentials
from src.config_manager import ConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('trans.log', mode='w')  # Changed to 'w' mode to clear previous logs
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
        from google.cloud import vision
        from google.cloud import translate_v2 as translate

        vision_client = vision.ImageAnnotatorClient()
        translate_client = translate.Client()
        logger.info("Google Cloud clients initialized successfully")

        logger.info("Creating TextProcessor...")
        text_processor = TextProcessor(vision_client, translate_client)
        logger.info("TextProcessor created successfully")

        logger.info("Creating MainWindow...")
        app = QApplication(sys.argv)
        main_window = MainWindow(text_processor)
        main_window.show()
        logger.info("MainWindow created successfully")

        return app.exec()

    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())