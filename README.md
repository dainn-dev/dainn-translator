# Real-time Screen Translator

A real-time screen translation application that can detect and translate text from any region of your screen.

## Features

- Real-time text detection using Google Cloud Vision API
- Automatic translation using Google Cloud Translation API
- Customizable translation regions
- Multiple language support
- Adjustable UI settings (font, colors, opacity)
- Smart caching to reduce API calls
- Frame change detection to optimize performance

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
   - Real-time text detection using Google Cloud Vision API
   - Automatic translation using Google Cloud Translation API
   - Customizable translation regions
   - Multiple language support
   - Adjustable UI settings (font, colors, opacity)

## Configuration

The application can be configured through the settings menu:
- Font size and style
- Window opacity
- Colors
- Translation languages

## Troubleshooting

### Google Cloud Vision API Issues

If you experience issues with text detection:
1. Verify your Google Cloud credentials are properly configured
2. Ensure the Cloud Vision API is enabled in your Google Cloud project
3. Check that your service account has the necessary permissions
4. Verify your API key file path is correct in the application settings

### API Quota Issues

The application includes built-in quota management:
- Daily API call limits
- Automatic retry with exponential backoff
- Caching to reduce API calls

## License

This project is licensed under the MIT License - see the LICENSE file for details. 