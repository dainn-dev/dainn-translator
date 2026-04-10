"""
Shared Windows hotkey utilities for MainWindow and TranslationWindow.
Centralises VK_CODES, modifier constants, the native event filter, and hotkey parsing.
"""
import logging
import os
from typing import Optional, Callable, Tuple

logger = logging.getLogger(__name__)

IS_WINDOWS = os.name == 'nt'

WM_HOTKEY = 0x0312
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_ALT = 0x0001

VK_CODES = {
    # Numbers
    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
    # Letters
    'A': 0x41, 'B': 0x42, 'C': 0x43, 'D': 0x44, 'E': 0x45,
    'F': 0x46, 'G': 0x47, 'H': 0x48, 'I': 0x49, 'J': 0x4A,
    'K': 0x4B, 'L': 0x4C, 'M': 0x4D, 'N': 0x4E, 'O': 0x4F,
    'P': 0x50, 'Q': 0x51, 'R': 0x52, 'S': 0x53, 'T': 0x54,
    'U': 0x55, 'V': 0x56, 'W': 0x57, 'X': 0x58, 'Y': 0x59, 'Z': 0x5A,
    # Function keys
    'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73, 'F5': 0x74, 'F6': 0x75,
    'F7': 0x76, 'F8': 0x77, 'F9': 0x78, 'F10': 0x79, 'F11': 0x7A, 'F12': 0x7B,
    # Special keys
    'SPACE': 0x20, 'PAGEUP': 0x21, 'PAGEDOWN': 0x22, 'END': 0x23, 'HOME': 0x24,
    'LEFT': 0x25, 'UP': 0x26, 'RIGHT': 0x27, 'DOWN': 0x28,
    'INSERT': 0x2D, 'DELETE': 0x2E,
    # Symbol keys
    '`': 0xC0, '-': 0xBD, '=': 0xBB, '[': 0xDB, ']': 0xDD,
    '\\': 0xDC, ';': 0xBA, "'": 0xDE, ',': 0xBC, '.': 0xBE, '/': 0xBF,
}

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes
    from PyQt5.QtCore import QTimer
    from PyQt5.QtCore import QAbstractNativeEventFilter

    class WindowsHotkeyFilter(QAbstractNativeEventFilter):
        """Native event filter that captures WM_HOTKEY messages for a single hotkey ID."""

        def __init__(self, callback: Callable):
            super().__init__()
            self.callback = callback
            self.hotkey_id: Optional[int] = None

        def set_hotkey_id(self, hotkey_id: Optional[int]):
            self.hotkey_id = hotkey_id

        def nativeEventFilter(self, event_type, message):
            if self.hotkey_id is None:
                return False, 0
            if event_type == "windows_generic_MSG":
                try:
                    msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
                except (ValueError, TypeError):
                    return False, 0
                if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                    QTimer.singleShot(0, self.callback)
                    return True, 0
            return False, 0


def parse_hotkey(hotkey: str, default_key: str = '1') -> Tuple[int, int]:
    """
    Parse a hotkey string like 'Ctrl+1' or 'F5' into (modifier, vk_code).

    Args:
        hotkey: String like 'Ctrl+Shift+F5', 'Ctrl+1', or bare 'F5'
        default_key: Key name to fall back to if no valid key is found

    Returns:
        (modifier_flags, virtual_key_code) tuple
    """
    if not IS_WINDOWS:
        return (0, 0)

    parts = hotkey.split('+')
    modifier = 0
    key = None

    for part in parts:
        part_upper = part.strip().upper()
        if part_upper == 'CTRL':
            modifier |= MOD_CONTROL
        elif part_upper == 'SHIFT':
            modifier |= MOD_SHIFT
        elif part_upper == 'ALT':
            modifier |= MOD_ALT
        else:
            if part_upper in VK_CODES:
                key = VK_CODES[part_upper]
            elif part in VK_CODES:
                key = VK_CODES[part]
            else:
                logger.warning(f"Unknown key in hotkey: {part}")

    if key is None:
        logger.warning(f"No valid key found in hotkey '{hotkey}', defaulting to '{default_key}'")
        key = VK_CODES.get(default_key, 0x31)

    return (modifier, key)
