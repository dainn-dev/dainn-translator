import numpy as np
import pytest
from unittest.mock import patch, MagicMock


def test_capture_screen_mss_returns_ndarray():
    """mss capture returns BGR numpy array for valid region."""
    from src.dx_capture import capture_screen_mss
    result = capture_screen_mss(0, 0, 100, 100)
    assert result is not None
    assert isinstance(result, np.ndarray)
    assert result.shape == (100, 100, 3)


def test_capture_screen_mss_invalid_region_returns_none():
    """mss capture returns None when region is zero-size."""
    from src.dx_capture import capture_screen_mss
    result = capture_screen_mss(0, 0, 0, 0)
    assert result is None


def test_wgc_available_flag_is_bool():
    """WGC_AVAILABLE flag is a boolean."""
    from src.dx_capture import WGC_AVAILABLE
    assert isinstance(WGC_AVAILABLE, bool)


def test_capture_window_wgc_returns_none_for_invalid_hwnd():
    """WGC capture returns None for invalid hwnd."""
    from src.dx_capture import capture_window_wgc
    result = capture_window_wgc(0)
    assert result is None
