# Real-time Screen Translator

A powerful real-time screen translation application that can detect and translate text from any region of your screen. Perfect for translating games, videos, documents, and any on-screen text in real-time.

## Features

- **Three Translation Modes:**
  - **Google Cloud Mode**: Cloud-based translation using Google Cloud Vision API for text detection and Google Cloud Translation API for translation
  - **Local LLM Mode**: Offline translation using Tesseract/PaddleOCR for text detection and LLM Studio for translation
  - **LibreTranslate Mode**: Self-hosted or public LibreTranslate server with local OCR (Tesseract/PaddleOCR)

- **Dual OCR Options:**
  - **Tesseract OCR**: Traditional OCR engine with multi-language support
  - **PaddleOCR**: Modern deep learning-based OCR with PP-OCRv4 model for improved accuracy

- **Advanced Features:**
  - Multiple customizable translation regions
  - Global hotkeys for quick access (toggle translation, add new area)
  - Smart frame change detection to optimize performance
  - Translation caching to reduce API calls
  - Auto-pause feature to pause translation when screen content is stable
  - Adjustable UI settings (font, colors, opacity, position)
  - Multiple language support
  - Translation history logging

## Table of Contents

- [Installation](#installation)
- [Quick Start Guide](#quick-start-guide)
- [Detailed Setup Guides](#detailed-setup-guides)
- [Usage Guide](#usage-guide)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Advanced Features](#advanced-features)

## Installation

### 1. Prerequisites

#### Python Installation

1. **Download Python 3.11.0:**
   - Visit https://www.python.org/downloads/
   - Download Python 3.11.0 installer for Windows
   - Run the installer

2. **Important Installation Options:**
   - ✅ Check **"Add Python to PATH"** (critical!)
   - ✅ Check **"Install launcher for all users"**
   - Choose "Install Now" or "Customize installation"

3. **Verify Installation:**
   ```bash
   python --version
   ```
   Should display: `Python 3.11.0`
   
   If `python` doesn't work, try:
   ```bash
   py --version
   ```

#### Additional Requirements by Mode

**For Google Cloud Mode:**
- Google Cloud Platform account
- Google Cloud Vision API enabled
- Google Cloud Translation API enabled
- Service account JSON credentials file

**For Local LLM Mode:**
- Tesseract OCR or PaddleOCR installed
- LLM Studio application (or compatible local LLM server)

**For LibreTranslate Mode:**
- Tesseract OCR or PaddleOCR installed
- LibreTranslate server (local or remote)

### 2. Install Dependencies

You have two options for installation:

#### Option A: Automatic Installation (Recommended for Beginners)

The easiest way to run the application is using the provided auto-install scripts. These scripts will automatically install missing dependencies when you run the application.

**Windows:**
```cmd
run.bat
```

**Linux/Mac:**
```bash
./run.sh
# or
bash run.sh
```

**Direct Python wrapper (all platforms):**
```bash
python run_with_deps.py
# or
python3 run_with_deps.py
```

The scripts will:
- ✅ Check if Python and pip are installed
- ✅ Install all dependencies from `requirements.txt`
- ✅ Automatically install any missing packages during runtime
- ✅ Run the application seamlessly

**Note:** On first run, the scripts will install all dependencies which may take a few minutes.

#### Option B: Manual Installation

1. **Clone or download the repository:**
   ```bash
   cd dainn-translator
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # On Windows
   source venv/bin/activate  # On Linux/Mac
   ```

3. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   ```

   This will install:
   - PyQt5 (GUI framework)
   - OpenCV (image processing)
   - NumPy (array operations)
   - PyAutoGUI (screen capture)
   - Google Cloud libraries (for Google Cloud mode)
   - pytesseract (for Tesseract OCR)
   - paddlepaddle & paddleocr (for PaddleOCR)
   - scikit-image (for frame comparison)
   - requests (for API calls)
   - And other dependencies

## Quick Start Guide

### Method 1: Using Auto-Install Scripts (Easiest)

**Windows:**
```cmd
run.bat
```

**Linux/Mac:**
```bash
./run.sh
```

The scripts will automatically:
- Install all required dependencies
- Install any missing packages during runtime
- Launch the application

### Method 2: Manual Run (If dependencies already installed)

1. **Activate virtual environment (if using one):**
   ```bash
   .\venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```

2. **Run the application:**
   ```bash
   python main.py
   ```

### First-Time Setup

After launching the application:
   - Click the **Settings** button (gear icon) in the main window
   - Select your translation mode (Google Cloud, Local LLM, or LibreTranslate)
   - Configure the required settings for your chosen mode (see [Detailed Setup Guides](#detailed-setup-guides))
   - Click **Save** to apply settings

4. **Start translating:**
   - Click **"Add Area"** button or press the **Add Area Hotkey** (default: `Ctrl+2`)
   - Click and drag on your screen to select a region
   - The translation window will appear showing translated text in real-time
   - Use the **Toggle Hotkey** (default: `Ctrl+1`) to show/hide translation windows

## Detailed Setup Guides

### Option A: Google Cloud Mode Setup

Google Cloud Mode provides the highest accuracy for both text detection and translation, but requires internet connection and Google Cloud API access.

#### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select a project"** → **"New Project"**
3. Enter a project name (e.g., "Screen Translator")
4. Click **"Create"**

#### Step 2: Enable Required APIs

1. In the Google Cloud Console, go to **"APIs & Services"** → **"Library"**
2. Search for and enable:
   - **Cloud Vision API**
   - **Cloud Translation API**

#### Step 3: Create Service Account

1. Go to **"IAM & Admin"** → **"Service Accounts"**
2. Click **"Create Service Account"**
3. Enter a name (e.g., "screen-translator")
4. Click **"Create and Continue"**
5. Grant roles:
   - **Cloud Vision API User**
   - **Cloud Translation API User**
6. Click **"Continue"** → **"Done"**

#### Step 4: Download Credentials

1. Click on the created service account
2. Go to **"Keys"** tab
3. Click **"Add Key"** → **"Create new key"**
4. Select **JSON** format
5. Click **"Create"** - the JSON file will download
6. **Save this file securely** (e.g., `C:\Users\YourName\credentials.json`)

#### Step 5: Configure in Application

1. Open the application
2. Click **Settings** (gear icon)
3. Select **"Google Cloud"** from the **"Translation Mode"** dropdown
4. Click **"Browse"** next to **"Credentials Path"**
5. Select your downloaded JSON credentials file
6. Click **"Save"**

**Note:** The application will validate your credentials on save. If there's an error, check:
- The JSON file is valid
- APIs are enabled in your project
- Service account has correct permissions

### Option B: Local LLM Mode Setup

Local LLM Mode works completely offline after initial setup. It uses local OCR and a local LLM server for translation.

#### Step 1: Install OCR Engine

Choose one of the following OCR options:

##### Option 1: Tesseract OCR (Recommended for beginners)

1. **Download Tesseract:**
   - Visit: https://github.com/UB-Mannheim/tesseract/wiki
   - Download the latest Windows installer (e.g., `tesseract-ocr-w64-setup-5.x.x.exe`)

2. **Install Tesseract:**
   - Run the installer
   - **Important:** Note the installation path (usually `C:\Program Files\Tesseract-OCR`)
   - During installation, you can optionally add Tesseract to PATH
   - Install language data for your target languages (English, Japanese, Korean, Chinese, etc.)

3. **Verify Installation:**
   - Open Command Prompt
   - Run: `tesseract --version`
   - If not found, you'll need to configure the path in the application

##### Option 2: PaddleOCR (Better accuracy, larger download)

1. **Install PaddleOCR:**
   ```bash
   pip install paddlepaddle paddleocr
   ```
   Note: This will download model files on first use (~100MB+)

2. **No additional configuration needed** - PaddleOCR works out of the box
   - The application automatically uses **PP-OCRv4** model for improved accuracy
   - PP-OCRv4 provides better text detection accuracy compared to older PP-OCR versions

#### Step 2: Set Up LLM Studio

1. **Download LLM Studio:**
   - Visit: https://lmstudio.ai/
   - Download and install LLM Studio

2. **Load a Language Model:**
   - Open LLM Studio
   - Go to **"Search"** tab
   - Search for a translation-capable model (e.g., "gemma", "llama", "mistral")
   - Download a model (recommended: 3-7B parameters for balance of speed/quality)
   - Go to **"Chat"** tab and load the model

3. **Enable Local Server:**
   - In LLM Studio, go to **"Local Server"** tab
   - Click **"Start Server"**
   - Note the API URL (usually `http://localhost:1234`)
   - The server should show "Status: Active"

4. **Test the Server:**
   - The server should be accessible at `http://localhost:1234/v1`
   - You can test with: `curl http://localhost:1234/v1/models`

#### Step 3: Configure in Application

1. Open the application
2. Click **Settings** (gear icon)
3. Select **"Local(Tesseract + LM Studio)"** from the **"Translation Mode"** dropdown

4. **Configure LLM Studio:**
   - **API URL:** Enter your LLM Studio server URL (default: `http://localhost:1234/v1`)
   - **Model Name:** Leave empty for auto-detect, or enter the exact model name
   - Click **"Test Connection"** to verify

5. **Configure OCR:**
   - **OCR Mode:** Select "Tesseract OCR" or "PaddleOCR"
   - **Tesseract Path:** 
     - If Tesseract is in PATH, leave empty
     - Otherwise, click **"Browse"** and select `tesseract.exe`
     - Click **"Test"** to verify Tesseract works

6. Click **"Save"**

### Option C: LibreTranslate Mode Setup

LibreTranslate Mode uses a self-hosted or public LibreTranslate server for translation, combined with local OCR.

#### Step 1: Set Up LibreTranslate Server

You have two options:

##### Option 1: Use Public LibreTranslate Server

- No installation needed
- Default URL: `https://libretranslate.com` (may have rate limits)
- Or find other public instances

##### Option 2: Self-Host LibreTranslate (Recommended)

1. **Using Docker (Easiest):**
   ```bash
   docker run -ti --rm -p 5000:5000 libretranslate/libretranslate
   ```

2. **Using Python:**
   ```bash
   pip install libretranslate
   libretranslate --host 0.0.0.0 --port 5000
   ```

3. **Verify Server:**
   - Open browser: `http://localhost:5000`
   - Should see LibreTranslate interface

#### Step 2: Install OCR Engine

Follow the same OCR installation steps as in [Local LLM Mode - Step 1](#option-1-tesseract-ocr-recommended-for-beginners)

#### Step 3: Configure in Application

1. Open the application
2. Click **Settings** (gear icon)
3. Select **"LibreTranslate(Tesseract + LibreTranslate)"** from the **"Translation Mode"** dropdown

4. **Configure LibreTranslate:**
   - **API URL:** Enter your LibreTranslate server URL (default: `http://localhost:5000`)
   - Click **"Test Connection"** to verify

5. **Configure OCR:**
   - **OCR Mode:** Select "Tesseract OCR" or "PaddleOCR"
   - **Tesseract Path:** Configure if needed (same as Local LLM mode)

6. Click **"Save"**

## Usage Guide

### Basic Usage

1. **Start the Application:**
   
   **Option 1: Using auto-install script (recommended):**
   ```bash
   # Windows
   run.bat
   
   # Linux/Mac
   ./run.sh
   
   # Or directly
   python run_with_deps.py
   ```
   
   **Option 2: Manual start (if dependencies installed):**
   ```bash
   python main.py
   ```

2. **Add a Translation Area:**
   - Click **"Add Area"** button in the main window, OR
   - Press the **Add Area Hotkey** (default: `Ctrl+2`)
   - A screen selection window will appear
   - Click and drag to select the region you want to translate
   - Press `ESC` to cancel

3. **View Translation:**
   - A translation window will appear showing the translated text
   - The window overlays on top of your selected region
   - Translation updates automatically when screen content changes

4. **Toggle Translation Windows:**
   - Press the **Toggle Hotkey** (default: `Ctrl+1`) to show/hide all translation windows
   - Useful when you need to see the original text

5. **Remove Translation Area:**
   - Click the **"X"** button on the translation window, OR
   - Close the translation window

### Advanced Usage

#### Managing Multiple Translation Areas

- You can add multiple translation areas for different parts of the screen
- Each area has its own translation window
- All areas are controlled by the same toggle hotkey

#### Changing Translation Language

1. Click **Settings** (gear icon)
2. In **"General Settings"**:
   - **Source Language:** Language of the text on screen
   - **Target Language:** Language to translate to
3. Click **"Save"**
4. Translation windows will update with new language

#### Customizing Translation Window Appearance

1. Click **Settings** (gear icon)
2. In **"General Settings"**:
   - **Font Family:** Choose font (e.g., Consolas, Arial)
   - **Font Size:** Adjust text size (recommended: 14-20)
   - **Font Style:** Normal, Bold, or Italic
   - **Name Color:** Color for character names (if detected)
   - **Dialogue Color:** Color for dialogue text
   - **Background Color:** Window background color
   - **Opacity:** Window transparency (0.0 = transparent, 1.0 = opaque)
3. Click **"Save"**
4. Changes apply immediately to all translation windows

#### Using Hotkeys

The application supports global hotkeys that work even when the application is in the background:

- **Toggle Hotkey** (default: `Ctrl+1`):
  - Shows/hides all translation windows
  - Works system-wide

- **Add Area Hotkey** (default: `Ctrl+2`):
  - Opens screen region selector
  - Works system-wide

**To Change Hotkeys:**

1. Click **Settings** (gear icon)
2. Scroll to **"Hotkey Settings"**
3. Click in the hotkey input field
4. Press the key combination you want (e.g., `Ctrl+Shift+T`)
5. Click **"Apply"** next to the hotkey field
6. Click **"Save"** to save all settings

**Hotkey Format:**
- Modifiers: `Ctrl`, `Alt`, `Shift` (can combine)
- Key: Any letter, number, or function key
- Examples: `Ctrl+1`, `Alt+Shift+T`, `Ctrl+F5`

#### Auto-Pause Feature

The auto-pause feature automatically pauses translation when screen content is stable (useful for static text):

1. Click **Settings** (gear icon)
2. Enable **"Auto Pause"** checkbox
3. Set **"Auto Pause Threshold"** (default: 5-10)
   - Lower value = more sensitive (pauses faster)
   - Higher value = less sensitive (pauses slower)
4. Click **"Save"**

When enabled, translation pauses when the screen content doesn't change for the threshold number of frames.

## Configuration

### Configuration File Location

The configuration file is located at: `config/config.ini`

You can edit this file directly, but it's recommended to use the Settings UI in the application.

### Configuration Sections

#### [Global] Section

Main application settings:

- `translation_mode`: `google`, `local`, or `libretranslate`
- `source_language`: Source language code (e.g., `en`, `ja`, `ko`)
- `target_language`: Target language code (e.g., `vi`, `en`, `zh-cn`)
- `font_family`: Font name (e.g., `Consolas`, `Arial`)
- `font_size`: Font size in pixels
- `font_style`: `normal`, `bold`, or `italic`
- `name_color`: Hex color for names (e.g., `#00ffff`)
- `dialogue_color`: Hex color for dialogue (e.g., `#00ff00`)
- `background_color`: Hex color for background (e.g., `#000000`)
- `opacity`: Window opacity (0.0 to 1.0)
- `toggle_hotkey`: Toggle hotkey (e.g., `Ctrl+1`)
- `add_area_hotkey`: Add area hotkey (e.g., `Ctrl+2`)
- `auto_pause_enabled`: `True` or `False`
- `auto_pause_threshold`: Number of frames (integer)

**Google Cloud Mode:**
- `credentials_path`: Path to Google Cloud JSON credentials file

**Local LLM Mode:**
- `llm_studio_url`: LLM Studio API URL
- `llm_studio_model`: Model name (empty for auto-detect)
- `tesseract_path`: Path to tesseract.exe (empty for system PATH)
- `ocr_mode`: `tesseract` or `paddleocr`

**LibreTranslate Mode:**
- `libretranslate_url`: LibreTranslate server URL
- `tesseract_path`: Path to tesseract.exe (empty for system PATH)
- `ocr_mode`: `tesseract` or `paddleocr`

#### [Languages] Section

Language code to display name mapping (for UI display).

#### [Areas] Section

Saved translation area positions (automatically managed by the application).

## Troubleshooting

### General Issues

#### Application Won't Start

1. **Try using auto-install script (easiest solution):**
   ```bash
   # Windows
   run.bat
   
   # Linux/Mac
   ./run.sh
   
   # Or directly
   python run_with_deps.py
   ```
   The auto-install scripts will automatically install all missing dependencies.

2. **Check Python version:**
   ```bash
   python --version
   ```
   Should be Python 3.11.0 or compatible

3. **Check dependencies:**
   ```bash
   pip list
   ```
   Verify all packages from `requirements.txt` are installed

4. **Check logs:**
   - Logs are saved to: `%APPDATA%\DainnScreenTranslator\logs\trans.log`
   - Check for error messages

5. **Reinstall dependencies:**
   ```bash
   pip install -r requirements.txt --force-reinstall
   ```

6. **If auto-install script fails:**
   - Check that Python and pip are installed correctly
   - Verify internet connection (needed to download packages)
   - Try running as Administrator (Windows) or with sudo (Linux/Mac)
   - Check if pip has permission to install packages

#### Translation Window Not Appearing

1. Check if translation mode is properly configured
2. Verify OCR/API credentials are correct
3. Check if the selected region contains text
4. Try increasing the region size
5. Check logs for errors

#### Poor Translation Quality

1. **For OCR issues:**
   - Ensure good image quality (high contrast, clear text)
   - Try different OCR mode (Tesseract vs PaddleOCR)
   - For Tesseract: Install language data for your source language
   - Increase region size to capture more context

2. **For translation issues:**
   - Try a different translation mode
   - For LLM Studio: Use a larger/better model
   - Check if source/target languages are correctly set

### Google Cloud Mode Issues

#### "Credentials not found" or "Invalid credentials"

1. **Verify credentials file:**
   - Check that the JSON file exists at the specified path
   - Open the JSON file and verify it's valid JSON
   - Ensure the file hasn't been corrupted

2. **Check API enablement:**
   - Go to Google Cloud Console
   - Verify Cloud Vision API and Cloud Translation API are enabled
   - Check billing is enabled (required for APIs)

3. **Verify service account permissions:**
   - Service account needs "Cloud Vision API User" role
   - Service account needs "Cloud Translation API User" role

4. **Test credentials:**
   ```bash
   set GOOGLE_APPLICATION_CREDENTIALS=path\to\credentials.json
   python -c "from google.cloud import vision; print('OK')"
   ```

#### "API quota exceeded" or "Quota limit"

1. Check your Google Cloud project quotas
2. Verify billing is enabled
3. Check if you've exceeded free tier limits
4. Wait for quota reset (usually daily)

#### Slow Response Times

1. Check your internet connection
2. Verify you're using the correct region for APIs
3. Check Google Cloud status page for outages

### Local LLM Mode Issues

#### Tesseract OCR Problems

**"Tesseract not found" error:**

1. **Verify installation:**
   ```bash
   tesseract --version
   ```
   If not found, Tesseract is not in PATH

2. **Configure path in application:**
   - Go to Settings → LLM Studio Settings
   - Click "Browse" next to Tesseract Path
   - Select `tesseract.exe` (usually in `C:\Program Files\Tesseract-OCR\`)
   - Click "Test" to verify

3. **Add to system PATH (alternative):**
   - Add `C:\Program Files\Tesseract-OCR` to Windows PATH
   - Restart the application

**"Permission denied" error:**

1. Run the application as Administrator
2. Check Windows Defender/antivirus isn't blocking Tesseract
3. Verify file permissions on `tesseract.exe`
4. Try reinstalling Tesseract to a user folder

**Poor OCR accuracy:**

1. **Install language data:**
   - Re-run Tesseract installer
   - Select additional language data during installation
   - Or download from: https://github.com/tesseract-ocr/tessdata

2. **Improve image quality:**
   - Select larger regions
   - Ensure good contrast
   - Avoid blurry or low-resolution text

3. **Try PaddleOCR:**
   - Switch OCR mode to PaddleOCR in settings
   - PaddleOCR often has better accuracy for certain languages

#### PaddleOCR Problems

**"PaddleOCR not available" error:**

1. Install PaddleOCR:
   ```bash
   pip install paddlepaddle paddleocr
   ```

2. First run will download models (may take time)

**Slow OCR performance:**

1. PaddleOCR is slower than Tesseract but more accurate
2. Consider using Tesseract for faster performance
3. Ensure sufficient RAM (PaddleOCR uses more memory)

#### LLM Studio Connection Problems

**"Connection failed" or "Unexpected endpoint" error:**

1. **Verify LLM Studio is running:**
   - Open LLM Studio
   - Go to "Local Server" tab
   - Ensure server status is "Active"
   - Note the exact URL and port

2. **Check API URL:**
   - Default: `http://localhost:1234/v1`
   - If using different port, update in settings
   - For remote server, use full URL: `http://IP_ADDRESS:PORT/v1`

3. **Test connection manually:**
   ```bash
   curl http://localhost:1234/v1/models
   ```
   Should return JSON with model list

4. **Check firewall:**
   - Windows Firewall may block connections
   - Add exception for Python or LLM Studio

**"Model not found" error:**

1. **Load model in LLM Studio:**
   - Go to "Chat" tab in LLM Studio
   - Load a model (click "Load" button)
   - Wait for model to fully load

2. **Configure model name:**
   - In application settings, enter exact model name
   - Or leave empty for auto-detect
   - Model name is case-sensitive

3. **Verify model supports translation:**
   - Not all models are good for translation
   - Recommended: Gemma, Llama, Mistral models

**Slow translation:**

1. **Use smaller model:**
   - Smaller models (3B-7B) are faster
   - Larger models (13B+) are slower but better quality

2. **Check system resources:**
   - Ensure sufficient RAM
   - GPU acceleration helps significantly
   - Close other resource-intensive applications

3. **Reduce max_tokens:**
   - Lower max_tokens in translator settings (if available)
   - Shorter responses = faster translation

### LibreTranslate Mode Issues

#### "Connection failed" error

1. **Verify server is running:**
   - If self-hosted: Check Docker container or process
   - If public: Check if server is online

2. **Test server URL:**
   ```bash
   curl http://localhost:5000
   ```
   Should return HTML or JSON

3. **Check URL format:**
   - Correct: `http://localhost:5000` or `https://libretranslate.com`
   - Don't include `/translate` or `/v1` in URL

4. **For public servers:**
   - Some public servers have rate limits
   - Try a different public instance
   - Consider self-hosting for better reliability

#### "Language not supported" error

1. Check LibreTranslate server supports your language pair
2. Some servers have limited language support
3. Try a different language or server

### Hotkey Issues

#### Hotkeys Not Working

1. **Check hotkey format:**
   - Must include modifier (Ctrl, Alt, or Shift)
   - Format: `Ctrl+1`, `Alt+Shift+T`, etc.

2. **Check for conflicts:**
   - Another application may be using the same hotkey
   - Try a different hotkey combination

3. **Restart application:**
   - Hotkeys are registered on startup
   - Restart after changing hotkeys

4. **Run as Administrator:**
   - Some hotkeys require admin privileges
   - Try running as Administrator

#### Hotkey Only Works When Application is Focused

- This is expected for some hotkey types
- Global hotkeys (system-wide) should work in background
- If not working globally, check Windows permissions

### Performance Issues

#### High CPU Usage

1. **Reduce update frequency:**
   - Enable auto-pause feature
   - Increase auto-pause threshold

2. **Use faster OCR:**
   - Tesseract is faster than PaddleOCR
   - Switch to Tesseract if using PaddleOCR

3. **Reduce number of areas:**
   - Each area processes independently
   - Remove unused translation areas

#### High Memory Usage

1. **Close unused translation areas**
2. **Restart application periodically**
3. **Use smaller LLM models** (if using Local LLM mode)

#### Slow Translation Updates

1. **Check internet connection** (for cloud modes)
2. **Use faster translation mode:**
   - Google Cloud is usually fastest
   - LibreTranslate depends on server
   - Local LLM depends on model size

3. **Optimize OCR settings:**
   - Smaller regions = faster processing
   - Better image quality = fewer retries

## Advanced Features

### Auto-Install Scripts

The application includes helper scripts that automatically install missing dependencies:

- **`run.sh`** (Linux/Mac): Bash script that checks dependencies and runs the application
- **`run.bat`** (Windows): Batch script for Windows users
- **`run_with_deps.py`** (Cross-platform): Python wrapper that handles runtime dependency installation

**How it works:**
1. First, installs all dependencies from `requirements.txt`
2. Runs `main.py` as a subprocess
3. Catches `ModuleNotFoundError` exceptions automatically
4. Installs missing packages on-the-fly
5. Retries running the application (up to 10 attempts)
6. Maps common module names to their pip package names (e.g., `cv2` → `opencv-python`)

**Benefits:**
- ✅ No manual dependency management needed
- ✅ Automatic installation of missing packages
- ✅ Smart package name mapping
- ✅ Seamless user experience
- ✅ Works on all platforms

**Note:** The scripts will install packages silently by default. Check the output for any installation messages.

### Translation History

The application automatically saves translation history to:
`%APPDATA%\DainnScreenTranslator\translation_history.json`

This file contains:
- Original text
- Translated text
- Language pair
- Translation service used
- Timestamp

### Logging

Application logs are saved to:
`%APPDATA%\DainnScreenTranslator\logs\trans.log`

Logs include:
- Application startup/shutdown
- Translation requests and responses
- OCR operations
- API calls
- Errors and warnings

**To enable debug logging:**
Edit `main.py` and change:
```python
level=logging.INFO,
```
to:
```python
level=logging.DEBUG,
```

### Multiple Translation Areas

You can add multiple translation areas for different parts of the screen:

1. Each area is independent
2. All areas use the same translation settings
3. Toggle hotkey affects all areas
4. Each area can be closed individually

**Use cases:**
- Translate multiple dialogue boxes simultaneously
- Translate UI elements and subtitles separately
- Translate different language sources on the same screen

### Frame Change Detection

The application uses structural similarity (SSIM) to detect when screen content changes:

- Only processes new frames when content changes
- Reduces CPU usage significantly
- Auto-pause feature uses this to pause on static content

**Adjusting sensitivity:**
- Auto-pause threshold controls sensitivity
- Lower threshold = more sensitive (pauses faster)
- Higher threshold = less sensitive (pauses slower)

### Translation Caching

The application caches translations to reduce API calls:

- Same text + language pair = cached result
- Reduces costs for cloud APIs
- Improves response time for repeated text
- Cache persists during application session

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or contributions:
- Check the [Troubleshooting](#troubleshooting) section
- Review application logs in `%APPDATA%\DainnScreenTranslator\logs\trans.log`
- Open an issue on the project repository

## Acknowledgments

- Built with PyQt5 for the GUI
- Uses Google Cloud APIs for cloud translation
- Supports Tesseract OCR and PaddleOCR for text detection
- Compatible with LLM Studio and LibreTranslate for local/self-hosted translation
