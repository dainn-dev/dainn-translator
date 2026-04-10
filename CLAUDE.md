# DainnScreenTranslator

Ứng dụng desktop dịch màn hình thời gian thực dành cho gamer — chụp vùng màn hình, OCR, và hiển thị bản dịch dạng overlay trong khi chơi game.

---

## Project Context

| | |
|---|---|
| **Stack** | Python 3.x + PyQt5 + OpenCV + numpy |
| **OCR** | Tesseract (pytesseract) hoặc PaddleOCR (PP-OCRv4) |
| **Translation** | Google Cloud Vision/Translate · Gemini API · LLM Studio (local) · LibreTranslate |
| **Kiến trúc** | Desktop app Windows-centric, multi-window overlay |
| **Deployment** | Hiện tại chạy từ source (`python main.py`) |
| **Users** | Gamer — dùng để đọc text trong game |

**Luôn nhớ:**
- App là Windows-centric — dùng Windows API (`ctypes`, `WM_HOTKEY`) cho hotkey system
- Config lưu tại `config/config.ini`, KHÔNG phải `.env`
- 4 translation modes: `google`, `local`, `libretranslate`, `gemini` — mỗi mode khởi tạo khác nhau
- 2 OCR modes: `tesseract`, `paddleocr` — toggle trong settings
- Translation windows là overlay trong suốt `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`
- Area coords có 2 format: legacy absolute `(x, y, width, height)` và mới pct-based `(x_pct, y_pct, w_pct, h_pct)`

---

## Làm việc với Claude (DEV AGENT mode)

### Bước 1 — Hiểu Task
- Đọc CLAUDE.md + `.claude/memory/MEMORY.md` + docs liên quan
- Nếu chưa rõ: hỏi từng câu một, chờ trả lời (max 3 câu)
- Dùng quick options khi có thể: "Option 1: ... Option 2: ... Option 3: Khác"

### Bước 2 — Branch
- Kiểm tra branch hiện tại: `git branch --show-current`
- **Cảnh báo** nếu user đang ở feat/fix branch khác (có thể quên chưa checkout về main/master)
- Hỏi:
  - Option 1: Tạo branch mới `feat/<slug>` hoặc `fix/<slug>`
  - Option 2: Tiếp tục trên branch hiện tại
  - Option 3: Khác

### Bước 3 — Plan & Confirm

**Task nhỏ** (1-3 file, ít impact):
> "Tôi sẽ [mô tả ngắn]. Được chưa?"
Chờ confirm mới làm.

**Task lớn** (nhiều file, nhiều component):
Build plan đầy đủ:
- File nào tạo/sửa
- Test nào viết
- Dependency nào cần
- Plan đủ context để chia cho sub-agent nếu cần
> "Đây là plan: [plan]. Confirm để bắt đầu?"
Chờ confirm mới làm.

### Bước 4 — Implement

Khi code, luôn kiểm tra:
- **Security:** Input đã validate chưa? Có lỗ hổng injection, auth bypass không?
- **Cluster-safe:** Có dùng in-memory state không? Nếu có → chuyển qua Redis
- **Performance:** Có N+1 query không? Cần cache không? Batch được không?
- **Pattern nhất quán:** Có theo đúng module pattern của codebase không?
- **Side effects:** Thay đổi này có break feature/logic khác không?
- **Deploy safety:** Code mới có ảnh hưởng đến rolling deploy (PM2 reload) không?

### Bước 5 — Test & Verify
- Chạy test suite
- Build nếu cần
- Kiểm tra không có lỗi compile/runtime
- Nếu có UI thay đổi → dùng `.claude/skills/ui-review.md`

---

## Project Structure

```
dainn-translator/
├── main.py                        # Entry point — khởi tạo translator theo mode, launch PyQt5
├── requirements.txt               # Dependencies
├── config/
│   └── config.ini                 # Tất cả settings (translation mode, OCR, hotkeys, areas, colors)
├── src/
│   ├── config_manager.py          # Đọc/ghi config.ini — nguồn sự thật duy nhất cho settings
│   ├── text_processing.py         # Core: OCR detect + translate + CSV dict lookup + cache
│   ├── screen_capture.py          # Vẽ overlay chọn vùng màn hình (drag), chụp bằng pyautogui
│   ├── window_capture.py          # Capture từ cửa sổ cụ thể bằng Windows API (hwnd)
│   ├── dictionary_utils.py        # CSV dictionary EN→VI: parse, normalize, MD5/SHA1 hash lookup
│   ├── version_checker.py         # Check GitHub releases cho app version update
│   ├── translator/
│   │   ├── gemini_translator.py   # Google Gemini API (google-generativeai)
│   │   ├── llm_studio_translator.py  # LLM Studio local API (OpenAI-compatible endpoint)
│   │   └── libretranslate_translator.py  # LibreTranslate self-hosted API
│   └── ui/
│       ├── main_window.py         # Cửa sổ điều khiển chính — settings, area list, hotkeys
│       ├── translation_window.py  # Overlay window hiển thị text dịch (frameless, always-on-top)
│       └── utils.py               # Validate Google credentials, show error messages
├── resources/
│   ├── logo.ico
│   └── logo.png
├── docs/
│   └── architecture.md            # Tài liệu kiến trúc chi tiết
└── .claude/
    ├── memory/                    # Project memory cho Claude
    └── skills/                    # Skill files
```

---

## Key Commands

| Command | Mô tả |
|---|---|
| `python main.py` | Chạy app |
| `pip install -r requirements.txt` | Cài dependencies |
| `python run_with_deps.py` | Chạy với auto-install dependencies |

---

## Skills

| Skill | Khi nào dùng |
|---|---|
| `.claude/skills/testing.md` | Chạy tests, viết tests |
| `.claude/skills/ui-review.md` | Sau khi thay đổi UI |
| `.claude/skills/parallel-agents.md` | Task lớn có nhiều phần độc lập |
| `.claude/skills/compress-context.md` | Context quá dài |
| `.claude/skills/build-distribution.md` | Build exe / package phân phối |

---

## Memory System

Đọc trước khi bắt đầu task:
- `.claude/memory/MEMORY.md` — project state hiện tại (< 200 lines)
- `.claude/memory/project.md` — stable facts về project
- `.claude/memory/decisions.md` — architectural decisions đã được đưa ra

Cập nhật sau khi hoàn thành task:
- Update `MEMORY.md` nếu project state thay đổi
- Thêm vào `decisions.md` nếu có architectural decision mới

---

## Testing

- Framework: Chưa có test framework setup
- Khi thêm tests: dùng `pytest`
- Pattern: đặt tests trong `tests/` hoặc `test_*.py` ở root

---

## Git & GitHub

- Branches: `feat/<task>`, `fix/<task>`, `chore/<task>` (kebab-case, max 4 từ)
- Commits: nhỏ, thường xuyên, descriptive
- PR: tạo khi task xong, bao gồm change summary + test results

---

## Code Conventions

- Class names: PascalCase (`TextProcessor`, `GeminiTranslator`, `ConfigManager`)
- Method names: snake_case (`translate_text`, `detect_text`, `get_area`)
- Private methods: prefix `_` (`_detect_text_tesseract`, `_translate_text_gemini`)
- Logging: mỗi module có `logger = logging.getLogger(__name__)`, dùng `logger.info/debug/error`
- Optional imports: wrap trong `try/except ImportError`, set flag `XXX_AVAILABLE = True/False`
- Config access: LUÔN qua `ConfigManager`, không đọc `config.ini` trực tiếp
- Translation modes: string literal `'google'`, `'local'`, `'libretranslate'`, `'gemini'`

---

## Context Management

Khi context quá dài (nhiều messages, conversation cũ):
Run compress-context skill → summarize → archive → rewrite MEMORY.md
