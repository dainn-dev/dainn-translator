import easyocr
import numpy as np
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class TextProcessor:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.use_local_ocr = True
        self.easyocr_reader = None
        self.initialize_easyocr()

    def initialize_easyocr(self):
        """Initialize EasyOCR reader."""
        try:
            # Initialize EasyOCR with English language
            self.easyocr_reader = easyocr.Reader(['en'])
            logger.info("EasyOCR initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {str(e)}")
            self.easyocr_reader = None
            self.use_local_ocr = False

    def process_image(self, image):
        """Process image and extract text using EasyOCR."""
        if not self.use_local_ocr or not self.easyocr_reader:
            return None

        try:
            # Convert PIL Image to numpy array if needed
            if isinstance(image, Image.Image):
                image = np.array(image)

            # Perform OCR
            results = self.easyocr_reader.readtext(image)
            
            # Extract text from results
            text = ' '.join([result[1] for result in results])
            return text.strip() if text else None

        except Exception as e:
            logger.error(f"Error processing image with EasyOCR: {str(e)}")
            return None

    def set_use_local_ocr(self, value):
        """Set whether to use local OCR."""
        self.use_local_ocr = value
        if value and not self.easyocr_reader:
            self.initialize_easyocr() 