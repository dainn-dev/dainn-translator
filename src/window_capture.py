"""
Window enumeration and capture module for Windows.
Uses Win32 API via ctypes to list visible windows and capture their client area
using PrintWindow, so overlapping windows (including our own overlay) are excluded.
"""

import os
import logging
import numpy as np
from typing import List, Optional, Tuple, NamedTuple

logger = logging.getLogger(__name__)

IS_WINDOWS = os.name == 'nt'

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32

    # --- Constants ---
    PW_CLIENTONLY = 0x00000001
    SRCCOPY = 0x00CC0020
    DIB_RGB_COLORS = 0
    BI_RGB = 0
    GA_ROOTOWNER = 3

    # --- Structures ---
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ("bmiHeader", BITMAPINFOHEADER),
            ("bmiColors", wintypes.DWORD * 3),
        ]

    # Function prototypes
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    IsWindowVisible = user32.IsWindowVisible
    GetWindowTextW = user32.GetWindowTextW
    GetWindowTextLengthW = user32.GetWindowTextLengthW
    GetClassNameW = user32.GetClassNameW
    GetWindowThreadProcessId = user32.GetWindowThreadProcessId
    GetClientRect = user32.GetClientRect
    ClientToScreen = user32.ClientToScreen
    PrintWindow = user32.PrintWindow
    GetWindowLongW = user32.GetWindowLongW
    GetAncestor = user32.GetAncestor
    GetLastActivePopup = user32.GetLastActivePopup
    IsIconic = user32.IsIconic
    GetDC = user32.GetDC
    ReleaseDC = user32.ReleaseDC

    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW = 0x00040000
    WS_EX_NOACTIVATE = 0x08000000


class WindowInfo(NamedTuple):
    """Information about a visible window."""
    hwnd: int
    title: str
    class_name: str
    pid: int


def list_visible_windows(exclude_own_pid: bool = True) -> List[WindowInfo]:
    """
    Enumerate all visible top-level windows suitable for capture.
    Filters out tool windows, zero-size windows, and (optionally) our own process.
    """
    if not IS_WINDOWS:
        return []

    own_pid = os.getpid() if exclude_own_pid else -1
    results: List[WindowInfo] = []

    def _enum_callback(hwnd, _lparam):
        # Must be visible and not minimised
        if not IsWindowVisible(hwnd):
            return True
        if IsIconic(hwnd):
            return True

        # Filter: the window must be an "alt-tab" window (top-level app window)
        # Heuristic: GetAncestor(GA_ROOTOWNER) == hwnd, not a tool window, etc.
        ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE)
        if ex_style & WS_EX_TOOLWINDOW and not (ex_style & WS_EX_APPWINDOW):
            return True

        root_owner = GetAncestor(hwnd, GA_ROOTOWNER)
        if root_owner != hwnd:
            # Not the root owner - skip child/owned windows
            return True

        # Get title
        length = GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if not title.strip():
            return True

        # Get class name
        cls_buf = ctypes.create_unicode_buffer(256)
        GetClassNameW(hwnd, cls_buf, 256)
        class_name = cls_buf.value

        # Get PID
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        window_pid = pid.value

        # Optionally exclude our own process
        if exclude_own_pid and window_pid == own_pid:
            return True

        # Check window has non-zero client area
        rect = wintypes.RECT()
        GetClientRect(hwnd, ctypes.byref(rect))
        if rect.right - rect.left <= 0 or rect.bottom - rect.top <= 0:
            return True

        results.append(WindowInfo(hwnd=hwnd, title=title, class_name=class_name, pid=window_pid))
        return True

    EnumWindows(EnumWindowsProc(_enum_callback), 0)
    # Sort by title for stable ordering
    results.sort(key=lambda w: w.title.lower())
    return results


def get_client_origin_and_size(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    """
    Return (origin_x, origin_y, client_w, client_h) in screen coordinates
    for the given window handle. Returns None if the window is invalid.
    """
    if not IS_WINDOWS:
        return None
    try:
        rect = wintypes.RECT()
        if not GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        client_w = rect.right - rect.left
        client_h = rect.bottom - rect.top
        if client_w <= 0 or client_h <= 0:
            return None

        # Map (0,0) of client area to screen coordinates
        pt = wintypes.POINT(0, 0)
        ClientToScreen(hwnd, ctypes.byref(pt))
        return (pt.x, pt.y, client_w, client_h)
    except Exception as e:
        logger.error(f"Error getting client rect for hwnd {hwnd}: {e}")
        return None


def capture_window_client(hwnd: int) -> Optional[np.ndarray]:
    """
    Capture the client area of a window using PrintWindow (PW_CLIENTONLY).
    Returns a BGR numpy array (compatible with OpenCV) or None on failure.
    This captures the window content even if it is partially or fully occluded.
    """
    if not IS_WINDOWS:
        return None

    try:
        info = get_client_origin_and_size(hwnd)
        if info is None:
            return None
        _, _, width, height = info

        # Get device context
        hwnd_dc = GetDC(hwnd)
        if not hwnd_dc:
            return None

        # Create compatible DC and bitmap
        mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
        if not mem_dc:
            ReleaseDC(hwnd, hwnd_dc)
            return None

        bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
        if not bmp:
            gdi32.DeleteDC(mem_dc)
            ReleaseDC(hwnd, hwnd_dc)
            return None

        old_bmp = gdi32.SelectObject(mem_dc, bmp)

        # Use PrintWindow with PW_CLIENTONLY to render the client area into our DC
        result = PrintWindow(hwnd, mem_dc, PW_CLIENTONLY)
        if not result:
            # Fallback: try BitBlt (may include overlapping windows)
            gdi32.BitBlt(mem_dc, 0, 0, width, height, hwnd_dc, 0, 0, SRCCOPY)

        # Prepare BITMAPINFO for GetDIBits
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height  # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32  # BGRA
        bmi.bmiHeader.biCompression = BI_RGB

        # Allocate buffer
        buffer_size = width * height * 4
        buffer = ctypes.create_string_buffer(buffer_size)

        gdi32.GetDIBits(mem_dc, bmp, 0, height, buffer, ctypes.byref(bmi), DIB_RGB_COLORS)

        # Cleanup GDI objects
        gdi32.SelectObject(mem_dc, old_bmp)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem_dc)
        ReleaseDC(hwnd, hwnd_dc)

        # Convert to numpy array (BGRA -> BGR)
        img = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)
        img_bgr = img[:, :, :3].copy()  # Drop alpha channel

        return img_bgr

    except Exception as e:
        logger.error(f"Error capturing window client for hwnd {hwnd}: {e}", exc_info=True)
        return None


def is_window_valid(hwnd: int) -> bool:
    """Check if a window handle is still valid and visible."""
    if not IS_WINDOWS:
        return False
    try:
        return bool(user32.IsWindow(hwnd)) and bool(IsWindowVisible(hwnd))
    except Exception:
        return False
