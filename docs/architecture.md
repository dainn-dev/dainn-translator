# Architecture — DainnScreenTranslator

## Overview

DainnScreenTranslator là desktop app dành cho Windows, giúp gamer dịch text trên màn hình game theo thời gian thực. App chụp ảnh từ các vùng màn hình được định nghĩa trước (hoặc từ cửa sổ game cụ thể), nhận dạng text bằng OCR, dịch sang tiếng Việt, và hiển thị kết quả dạng overlay trong suốt luôn nằm trên cùng màn hình game.

App hỗ trợ nhiều translation backend (Google Cloud, Gemini, LLM local, LibreTranslate) và nhiều OCR engine (Google Vision, Tesseract, PaddleOCR), cho phép user chọn phương án phù hợp với nhu cầu và điều kiện kết nối.

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        MainWindow                           │
│  (control panel: settings, area list, mode selection)       │
└──────────────┬──────────────────────────────────────────────┘
               │ manages N windows
               ▼
┌─────────────────────────────────────────────────────────────┐
│               TranslationWindow (x N areas)                 │
│  frameless · always-on-top · transparent overlay            │
│  QTimer → trigger capture + translate every N seconds       │
└──────┬───────────────────────────────────────────┬──────────┘
       │                                           │
       ▼                                           ▼
┌──────────────────┐                  ┌────────────────────────┐
│  screen_capture  │                  │   window_capture        │
│  (pyautogui +    │                  │   (Windows API hwnd)    │
│   RegionSelector)│                  │                         │
└──────────────────┘                  └────────────────────────┘
       │                                           │
       └─────────────────┬─────────────────────────┘
                         │ numpy array (BGR image)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    TextProcessor                             │
│                                                             │
│  detect_text() ──► Google Vision API                        │
│                 ──► Tesseract (pytesseract)                  │
│                 ──► PaddleOCR (PP-OCRv4)                     │
│                                                             │
│  translate_text()                                           │
│    1. CSV Dictionary lookup (MD5/SHA1 + fuzzy)              │
│    2. Translation cache (OrderedDict)                       │
│    3. API call:                                             │
│       ──► Google Cloud Translate                            │
│       ──► Gemini API (google-generativeai)                  │
│       ──► LLM Studio (OpenAI-compatible local)              │
│       ──► LibreTranslate (self-hosted)                      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
                    Translated text → TranslationWindow renders overlay
```

## Components

### main.py
- **Role:** Entry point — đọc translation_mode từ config, khởi tạo đúng translator, launch PyQt5 app
- **Key logic:** Routing theo mode, graceful fallback nếu credentials/API key thiếu

### src/config_manager.py
- **Role:** Single source of truth — tất cả settings đọc/ghi qua đây
- **Backend:** `configparser` → `config/config.ini`
- **Key settings:** translation_mode, ocr_mode, areas, hotkeys, colors, API keys/URLs

### src/text_processing.py — TextProcessor
- **Role:** Core processing pipeline
- **OCR:** `detect_text()` routing sang đúng engine theo mode
- **Translation:** `translate_text()` với CSV dict → cache → API
- **CSV Dictionary:** `set_dictionary()` / `lookup_dictionary()` — MD5+SHA1 hash exact, SequenceMatcher fuzzy (80% threshold)
- **Cache:** `OrderedDict` (unlimited hoặc bounded)

### src/ui/main_window.py — MainWindow
- **Role:** Control panel chính
- **Features:** Area management, settings tabs (colors, fonts, API config), hotkey registration, version check, CSV dict import
- **Hotkeys:** Windows native `RegisterHotKey` / `WM_HOTKEY` via `QAbstractNativeEventFilter`

### src/ui/translation_window.py — TranslationWindow
- **Role:** Overlay window hiển thị bản dịch
- **Properties:** `FramelessWindowHint | WindowStaysOnTopHint | WA_TranslucentBackground | WA_TransparentForMouseEvents`
- **Timer:** QTimer trigger capture + translate định kỳ
- **Multi-threading:** `ThreadPoolExecutor` cho translation calls (không block UI)

### src/translator/
- `gemini_translator.py` — `google-generativeai` SDK, model configurable (default: `gemini-1.5-flash`)
- `llm_studio_translator.py` — OpenAI-compatible REST API, auto-detect model + endpoint
- `libretranslate_translator.py` — LibreTranslate REST API (`/translate`, `/languages`)

### src/screen_capture.py
- `RegionSelector` — QWidget overlay để drag-select vùng màn hình
- `capture_screen_region()` — Show selector, chụp bằng `pyautogui.screenshot()`

### src/window_capture.py
- Dùng Windows API (`ctypes`, `win32gui` concepts) để lấy window handle (hwnd)
- Capture client area của cửa sổ cụ thể (không phụ thuộc vị trí màn hình)
- `list_visible_windows()`, `get_client_origin_and_size()`, `capture_window_client()`

### src/dictionary_utils.py
- `parse_csv_dictionary()` — Parse CSV file với cột EN/VI (auto-detect header)
- `normalize_en()` — NFKC + lowercase + strip whitespace
- `hash_md5()`, `hash_sha1()` — Fast lookup keys

## Data Flow (chi tiết)

```
1. User chọn area:
   MainWindow → RegionSelector / WindowPicker
   → ConfigManager.save_area_pct() → config.ini

2. TranslationWindow timer tick (mỗi N giây):
   → capture_window_client(hwnd) hoặc pyautogui.screenshot(region)
   → TextProcessor.detect_text(image)
   → TextProcessor.translate_text(text, target_lang, source_lang)
   → overlay.setText(translated_text)

3. translate_text() pipeline:
   [EN→VI + dict_entry_count > 0]
   → lookup_dictionary(text)
      → normalize_en() → hash_md5() → dict_md5.get()  [O(1)]
      → fallback: SequenceMatcher fuzzy scan            [O(n)]
   → [miss] check translation_cache                     [O(1)]
   → [miss] call API (Gemini / Google / LLM / Libre)
   → cache result → save to translation_history.json
```

## External Services

| Service | Mode | Cần gì |
|---|---|---|
| Google Cloud Vision | `google` | Service account JSON key |
| Google Cloud Translate | `google` | Service account JSON key |
| Gemini API | `gemini` | API key (`GEMINI_API_KEY`) |
| LLM Studio | `local` | Server chạy tại `localhost:1234` |
| LibreTranslate | `libretranslate` | Server chạy tại `localhost:5000` |

## Environment Variables

Không dùng env vars. Tất cả config tại `config/config.ini`.

## Files Quan Trọng

| File | Mô tả |
|---|---|
| `config/config.ini` | Tất cả settings người dùng |
| `%APPDATA%/DainnScreenTranslator/logs/trans.log` | Log file |
| `%APPDATA%/DainnScreenTranslator/translation_history.json` | Lịch sử dịch |
| `DainnScreenTranslator.spec` | PyInstaller config |
| `installer.iss` | Inno Setup installer config |
