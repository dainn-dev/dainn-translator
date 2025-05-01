# Real-time Screen Translator

A real-time screen translation application that can detect and translate text from any region of your screen.

## Features

- Real-time text detection and translation
- Customizable translation regions
- Multiple language support
- Adjustable UI settings
- Local OCR pre-filtering (optional)

## Installation

### Prerequisites

- Python 3.7 or higher
- Google Cloud Vision API credentials
- Google Cloud Translation API credentials

### Optional: Tesseract OCR Installation

The application can use Tesseract OCR for local text detection pre-filtering. This is optional but recommended for better performance.

#### Windows Installation

1. Download the Tesseract installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run the installer and follow the installation wizard
3. Add Tesseract to your system PATH:
   - Open System Properties > Advanced > Environment Variables
   - Under System Variables, find and select "Path"
   - Click Edit > New
   - Add the Tesseract installation path (typically `C:\Program Files\Tesseract-OCR`)
4. Restart your terminal/IDE

#### macOS Installation

```bash
brew install tesseract
```

#### Linux Installation

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

### Python Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

## Usage

1. Set up your Google Cloud credentials
2. Run the application:
   ```bash
   python main.py
   ```
3. Select a region of your screen to translate
4. Choose your target language
5. The translation will appear in real-time

## Configuration

The application can be configured through the settings menu:
- Font size and style
- Window opacity
- Colors
- Translation languages

## Troubleshooting

### Tesseract OCR Issues

If you see a warning about Tesseract not being installed:
1. Verify that Tesseract is installed correctly
2. Check that Tesseract is in your system PATH
3. Restart the application after installation

### API Quota Issues

The application includes built-in quota management:
- Daily API call limits
- Automatic retry with exponential backoff
- Caching to reduce API calls

## License

This project is licensed under the MIT License - see the LICENSE file for details. 