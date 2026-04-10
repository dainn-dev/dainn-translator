# DainnScreenTranslator — Memory

**Stack:** Python 3.x + PyQt5 + OpenCV | **OCR:** Tesseract / PaddleOCR | **Users:** Gamer

**Luôn nhớ:**
- Windows-centric: dùng `ctypes` + `WM_HOTKEY` cho hotkeys, Windows API cho window capture
- Config tại `config/config.ini` — LUÔN access qua `ConfigManager`, không đọc trực tiếp
- 4 translation modes: `google` · `local` (LLM Studio) · `libretranslate` · `gemini`
- Area coords có 2 format: absolute (legacy) và pct-based (mới, ưu tiên dùng)
- Translation windows: `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WA_TranslucentBackground`

**Mode:** DEV AGENT

---

## Current State

- Status: freshly initialized by Blueberry Sensei
- Active branch: feat/enhance
- Last task: thêm Gemini translation support + window capture + CSV dictionary

## Key Components

- `main.py` — Entry point, routing theo translation mode
- `src/text_processing.py` — Core processor: OCR + translate + dict lookup + cache
- `src/config_manager.py` — Single source of truth cho tất cả settings
- `src/ui/main_window.py` — Main control window (settings, hotkeys, area management)
- `src/ui/translation_window.py` — Overlay hiển thị bản dịch trên màn hình game

## In Progress

(none)

## Recent Decisions

Xem `.claude/memory/decisions.md`

---

_Keep this file under 200 lines. Archive old context with compress-context skill._
