# Project Facts — DainnScreenTranslator

_Stable facts. Chỉ update khi project thay đổi căn bản._

## Description

Desktop app dịch màn hình thời gian thực cho gamer. Người dùng chọn vùng màn hình (hoặc cửa sổ game cụ thể), app chụp ảnh định kỳ, OCR để đọc text, dịch sang tiếng Việt, và hiển thị kết quả dạng overlay trong suốt luôn nằm trên cùng màn hình.

## Tech Stack

| Thư viện | Vai trò |
|---|---|
| PyQt5 | UI framework — main window + overlay windows |
| OpenCV (cv2) | Xử lý ảnh trước khi OCR |
| numpy | Array operations cho ảnh |
| pyautogui | Chụp màn hình (screenshot) |
| Pillow | Xử lý ảnh bổ sung |
| pytesseract | OCR engine (Tesseract wrapper) |
| paddleocr + paddlepaddle | OCR engine thay thế (PP-OCRv4) |
| google-cloud-vision | OCR qua Google Cloud |
| google-cloud-translate | Dịch qua Google Cloud |
| google-generativeai | Dịch qua Gemini API |
| requests | HTTP client cho LLM Studio + LibreTranslate |
| scikit-image | Xử lý ảnh bổ sung |
| configparser (stdlib) | Đọc/ghi config.ini |
| ctypes (stdlib) | Windows API cho hotkeys + window capture |

## Architecture

```
User chọn area (drag hoặc pick window)
    → ConfigManager lưu area coords vào config.ini
    → TranslationWindow timer trigger mỗi N giây
    → screen_capture / window_capture chụp ảnh vùng đó
    → TextProcessor.detect_text() → OCR (Google Vision / Tesseract / PaddleOCR)
    → TextProcessor.translate_text() → check CSV dict → check cache → gọi API
    → TranslationWindow cập nhật overlay text
```

**Layers:**
- **UI layer:** `src/ui/main_window.py` (control panel) + `src/ui/translation_window.py` (overlay)
- **Processing layer:** `src/text_processing.py` (OCR + translate + cache + dict)
- **Translator layer:** `src/translator/` (gemini, llm_studio, libretranslate)
- **Config layer:** `src/config_manager.py` + `config/config.ini`
- **Capture layer:** `src/screen_capture.py` (toàn màn hình) + `src/window_capture.py` (theo hwnd)
- **Utilities:** `src/dictionary_utils.py` (CSV dict), `src/version_checker.py`

## Translation Modes

| Mode | OCR | Translator | Cần gì |
|---|---|---|---|
| `google` | Google Cloud Vision | Google Cloud Translate | credentials JSON |
| `local` | Tesseract / PaddleOCR | LLM Studio (local API) | LLM Studio chạy local |
| `libretranslate` | Tesseract / PaddleOCR | LibreTranslate API | LibreTranslate server |
| `gemini` | Tesseract / PaddleOCR | Gemini API | Gemini API key |

## Key Features

- **Multi-area:** Hỗ trợ nhiều vùng dịch cùng lúc (area 1, 2, 3...)
- **CSV Dictionary:** Load file CSV EN→VI, tra cứu exact hash + fuzzy match trước khi gọi API
- **Translation cache:** OrderedDict cache, tránh gọi API trùng lặp
- **Window capture:** Chọn cửa sổ game cụ thể, capture theo hwnd (không phụ thuộc vị trí màn hình)
- **Hotkeys:** Windows native hotkey (`WM_HOTKEY`) — toggle dịch + add area
- **Auto-pause:** Tự dừng dịch nếu không có text mới sau N lần
- **Overlay customization:** Font, màu text (name/dialogue), background, opacity

## Infrastructure

- **Deployment:** Chạy từ source `python main.py` hoặc `run.bat` / `run.sh`
- **Config:** `config/config.ini` (persisted locally)
- **Logs:** `%APPDATA%/DainnScreenTranslator/logs/trans.log`
- **Translation history:** `%APPDATA%/DainnScreenTranslator/translation_history.json`
- **Packaging:** `DainnScreenTranslator.spec` (PyInstaller config có sẵn), `installer.iss` (Inno Setup)
- **CI/CD:** Không có

## Conventions

- Mỗi module có `logger = logging.getLogger(__name__)`
- Optional deps: wrap `try/except ImportError`, flag `XXX_AVAILABLE`
- Private methods: prefix `_` (e.g., `_detect_text_tesseract`)
- Config access: luôn qua `ConfigManager`, không đọc file trực tiếp
- Area format mới: pct-based (`x_pct`, `y_pct`, `w_pct`, `h_pct`) — tương thích với legacy absolute
