# Architectural Decisions

_Thêm decisions vào đây khi chúng được đưa ra._

---

## Decision: Dùng PyQt5 thay vì tkinter/customtkinter

**Date:** 2026-03-26
**Decision:** UI framework là PyQt5
**Reason:** PyQt5 hỗ trợ tốt hơn cho overlay windows (`WA_TranslucentBackground`, `WindowStaysOnTopHint`), native event filter cho Windows hotkeys (`QAbstractNativeEventFilter`), và multi-threading (`QThread`, `pyqtSignal`)
**Alternatives considered:** customtkinter (có trong requirements.txt nhưng không được dùng trong code hiện tại)

---

## Decision: 4 Translation Modes pluggable

**Date:** 2026-03-26
**Decision:** Hỗ trợ `google`, `local`, `libretranslate`, `gemini` — chọn qua `config.ini`
**Reason:** Gamer có nhu cầu khác nhau — người có Google Cloud credentials, người muốn free/offline với LLM local, người muốn dùng Gemini API
**Alternatives considered:** Chỉ support Google Cloud (quá hạn chế)

---

## Decision: 2 OCR Modes (Tesseract vs PaddleOCR)

**Date:** 2026-03-26
**Decision:** Hỗ trợ cả Tesseract và PaddleOCR (PP-OCRv4), chọn qua `ocr_mode` trong config
**Reason:** PaddleOCR cho accuracy tốt hơn với text trong game, Tesseract nhẹ hơn và dễ cài hơn
**Alternatives considered:** Chỉ Tesseract (accuracy thấp hơn)

---

## Decision: CSV Dictionary với Hash Lookup + Fuzzy Match

**Date:** 2026-03-26
**Decision:** CSV dictionary EN→VI dùng MD5 + SHA1 hash cho exact match, SequenceMatcher cho fuzzy fallback (threshold 80%)
**Reason:** Gamer có thể cung cấp từ điển custom cho game cụ thể (tên nhân vật, skill...), tra cứu dict trước khi gọi API để tiết kiệm quota và tăng tốc độ
**Alternatives considered:** Chỉ exact match (miss các trường hợp OCR không hoàn hảo)

---

## Decision: Area coords hỗ trợ cả absolute và pct-based

**Date:** 2026-03-26
**Decision:** Format mới dùng `x_pct/y_pct/w_pct/h_pct` (phần trăm relative to window client area), giữ backward compat với format cũ absolute `x/y/width/height`
**Reason:** Window capture cần coords relative to cửa sổ game, không phải tọa độ màn hình tuyệt đối — giúp area vẫn đúng khi cửa sổ game di chuyển
**Alternatives considered:** Chỉ absolute coords (break khi window di chuyển)

---

## Decision: Config lưu tại config/config.ini (không phải .env)

**Date:** 2026-03-26
**Decision:** Tất cả settings (API keys, credentials path, hotkeys, colors, areas) lưu tại `config/config.ini`
**Reason:** Desktop app không cần env vars, config file dễ đọc/sửa tay, `configparser` là stdlib không cần dependency thêm
**Alternatives considered:** .env file với python-dotenv

---

## Decision: Logs và history lưu tại %APPDATA%

**Date:** 2026-03-26
**Decision:** `%APPDATA%/DainnScreenTranslator/logs/` và `translation_history.json`
**Reason:** Windows convention cho user data của desktop apps, tránh write vào thư mục install (có thể readonly nếu build thành exe)
**Alternatives considered:** Lưu cùng thư mục source (vấn đề khi đóng gói thành exe)
