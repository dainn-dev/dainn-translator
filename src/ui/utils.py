import os
import json
from PyQt5.QtWidgets import QMessageBox
import logging

logger = logging.getLogger(__name__)

def validate_credentials(file_path: str) -> bool:
    """
    Validate the Google Cloud credentials file.
    
    Args:
        file_path: Path to the credentials JSON file
        
    Returns:
        bool: True if credentials are valid, False otherwise
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"Credentials file does not exist: {file_path}")
            return False

        with open(file_path, 'r') as f:
            credentials = json.load(f)

        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if field not in credentials]

        if missing_fields:
            logger.error(f"Credentials file is missing required fields: {missing_fields}")
            return False

        logger.info("Credentials file is valid")
        return True

    except json.JSONDecodeError:
        logger.error(f"Credentials file is not a valid JSON file: {file_path}")
        return False

    except Exception as e:
        logger.error(f"Error validating credentials file: {str(e)}", exc_info=True)
        return False

def show_error_message(parent, title: str, message: str) -> None:
    """Show an error message dialog."""
    QMessageBox.critical(parent, title, message)