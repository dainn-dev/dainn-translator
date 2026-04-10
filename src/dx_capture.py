"""
DX capture module — DXGI Desktop Duplication (mss) + Windows Graphics Capture API.

Provides two backends:
  - capture_screen_mss(x, y, w, h)  -> BGR ndarray  (primary, works with DX11/12)
  - capture_window_wgc(hwnd)        -> BGR ndarray  (window-specific, optional)
"""
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

# -- mss (DXGI Desktop Duplication) ------------------------------------------
try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False
    logger.warning("mss not available. Install with: pip install mss")

# -- Windows Graphics Capture API ---------------------------------------------
try:
    import windows_capture
    WGC_AVAILABLE = True
except ImportError:
    WGC_AVAILABLE = False
    logger.warning("windows-capture not available. Install with: pip install windows-capture")


def capture_screen_mss(x: int, y: int, w: int, h: int) -> Optional[np.ndarray]:
    """
    Capture a screen region using DXGI Desktop Duplication via mss.
    Works with DX11/12 games in both windowed and fullscreen exclusive modes.

    Args:
        x, y: top-left corner in screen coordinates
        w, h: width and height in pixels

    Returns:
        BGR numpy array (H, W, 3) or None on failure
    """
    if not MSS_AVAILABLE:
        logger.error("mss not installed — cannot capture screen region")
        return None
    if w <= 0 or h <= 0:
        return None
    try:
        with mss.mss() as sct:
            monitor = {"top": y, "left": x, "width": w, "height": h}
            frame = sct.grab(monitor)
            # mss returns BGRA — drop alpha channel
            img = np.array(frame)[:, :, :3]
            return img
    except Exception as e:
        logger.error(f"mss capture failed: {e}", exc_info=True)
        return None


def capture_window_wgc(hwnd: int) -> Optional[np.ndarray]:
    """
    Capture a window's client area using Windows Graphics Capture API.
    Works with DX11/12 games. Returns None if WGC is unavailable or fails.

    Args:
        hwnd: Windows window handle

    Returns:
        BGR numpy array or None on failure
    """
    if not WGC_AVAILABLE:
        return None
    if not hwnd:
        return None
    try:
        capture = windows_capture.WindowsCapture(hwnd=hwnd)
        frame = capture.capture_frame()
        if frame is None:
            return None
        img = np.array(frame)
        # windows-capture returns BGRA
        if img.ndim == 3 and img.shape[2] == 4:
            img = img[:, :, :3]
        return img
    except Exception as e:
        logger.debug(f"WGC capture failed for hwnd {hwnd}: {e}")
        return None
