# Real-time Screen Translator

A real-time screen translation application that can detect and translate text from any region of your screen.

## Features

- Real-time text detection and translation
- Customizable translation regions
- Multiple language support
- Adjustable UI settings
- Local OCR pre-filtering (optional)

## Installation

### 1. Prerequisites

#### Python Installation

1. Download and install Python 3.11.0 from the official website:
   - Visit https://www.python.org/downloads/
   - Download Python 3.11.0 installer
   - During installation, make sure to check "Add Python to PATH"
   - Also check "Install launcher for all users"

2. Verify Python installation:
   ```bash
   python --version
   ```
   If Python is not found, try:
   ```bash
   py --version
   ```

#### Additional Requirements

- Google Cloud Vision API credentials
- Google Cloud Translation API credentials

### 2. Set up Google Cloud Credentials

1. Create a Google Cloud project if you don't have one
2. Enable the following APIs:
   - Cloud Vision API
   - Cloud Translation API
3. Create a service account and download the JSON key file
4. Set the environment variable:
   ```bash
   set GOOGLE_APPLICATION_CREDENTIALS="path/to/your/credentials.json"
   ```

### 3. Install Dependencies

1. Create a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # On Windows
   ```

2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

### 4. Optional: Install EasyOCR

The application uses EasyOCR for local text detection pre-filtering. This is optional but recommended for better performance.

#### Installation

EasyOCR is installed automatically with the other dependencies (see "Install Dependencies" section above). No additional installation is required.

#### Supported Languages

EasyOCR supports multiple languages including:
- English
- Chinese
- Japanese
- Korean
- French
- German
- Spanish
- And many more...

The application will automatically use EasyOCR for text detection when available.

## Usage

1. Ensure your virtual environment is activated:
   ```bash
   .\venv\Scripts\activate  # On Windows
   ```

2. Run the application:
   ```bash
   python main.py
   ```

3. Application Interface:
   - Click and drag to select a region of your screen
   - Use the dropdown menu to select your target language
   - Adjust settings through the settings menu (gear icon)
   - Use the "Exit" button or press Ctrl+C in the terminal to quit

4. Features:
   - Real-time text detection and translation
   - Customizable translation regions
   - Multiple language support
   - Adjustable UI settings
   - Optional local OCR pre-filtering (if Tesseract is installed)

## Configuration

The application can be configured through the settings menu:
- Font size and style
- Window opacity
- Colors
- Translation languages

## Troubleshooting

### EasyOCR Issues

If you see any issues with text detection:
1. Ensure all dependencies are installed correctly
2. Check if your GPU is being utilized (if available)
3. Try adjusting the text detection settings in the application's configuration menu

### API Quota Issues

The application includes built-in quota management:
- Daily API call limits
- Automatic retry with exponential backoff
- Caching to reduce API calls

## License

This project is licensed under the MIT License - see the LICENSE file for details. 