# DX11/12 Capture Support Design

**Date:** 2026-04-10  
**Branch:** feat/enhance  
**Status:** Approved

---

## Problem

Hiện tại app dùng `pyautogui.screenshot()` (GDI BitBlt) và `PrintWindow` để capture màn hình. Cả hai đều **không hoạt động** với game DirectX 11/12 fullscreen exclusive — trả về ảnh đen.

## Goal

Hỗ trợ capture game DX11/12 ở cả 2 chế độ:
- Windowed / Borderless Windowed
- Fullscreen Exclusive

---

## Architecture

### Backend 1 — `mss` (primary screen capture)

- Thay thế toàn bộ `pyautogui.screenshot()` bằng `mss`
- `mss` dùng **DXGI Desktop Duplication API** trên Windows → hoạt động với DX11/12
- Drop-in replacement: cùng input `(x, y, w, h)`, cùng output `np.ndarray` BGR

**Áp dụng tại:**
- `src/screen_capture.py` — `capture_screen_region()`
- `src/ui/translation_window.py` — `_capture_roi_screen()`

### Backend 2 — Windows Graphics Capture API / WGC (window-specific capture)

- Dùng `windows-capture` Python package (wraps WGC)
- Capture theo hwnd cụ thể → không bị overlay contamination
- Thay thế `PrintWindow` + `BitBlt` trong `window_capture.py`
- **Fallback chain:** WGC → mss screen region → error

**Áp dụng tại:**
- `src/window_capture.py` — `capture_window_client(hwnd)`

---

## Data Flow

```
_capture_roi() [translation_window.py]
  ├─ Có capture_hwnd và area_pct
  │     └─ capture_window_client(hwnd)  [window_capture.py]
  │           ├─ WGC available → windows-capture
  │           └─ WGC failed   → mss region (origin + pct coords)
  └─ Không có hwnd
        └─ _capture_roi_screen()
              └─ mss.grab(region)
```

---

## Files Changed

| File | Action | Chi tiết |
|---|---|---|
| `src/dx_capture.py` | **Tạo mới** | Wrapper module: `capture_screen_mss(x,y,w,h)` + `capture_window_wgc(hwnd)` |
| `src/window_capture.py` | Sửa | `capture_window_client()` thử WGC trước, fallback mss |
| `src/ui/translation_window.py` | Sửa | `_capture_roi_screen()` dùng mss |
| `src/screen_capture.py` | Sửa | `capture_screen_region()` dùng mss |
| `requirements.txt` | Sửa | Thêm `mss>=9.0`, `windows-capture>=1.0` |

---

## Error Handling

- WGC không available (Windows < 10 1803) → log warning, fallback mss
- `windows-capture` không install → `WGC_AVAILABLE = False`, skip silently
- `mss` grab lỗi → log error, return `None` (behavior giống hiện tại)

---

## Dependencies

```
mss>=9.0                  # DXGI Desktop Duplication
windows-capture>=1.0      # Windows Graphics Capture API (optional)
```

`windows-capture` là optional — wrap trong `try/except ImportError`, consistent với pattern hiện tại của codebase.

---

## Out of Scope

- Capture game fullscreen exclusive qua Vulkan/OpenGL (không phổ biến với game JP)
- Hardware-accelerated OCR
- Anti-cheat bypass
