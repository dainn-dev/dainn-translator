import pyautogui
import cv2
import numpy as np
from typing import Tuple, Optional

def capture_screen_region() -> Tuple[Optional[np.ndarray], Optional[Tuple[int, int, int, int]]]:
    """Capture a region of the screen selected by the user."""
    region = pyautogui.screenshot()
    region = cv2.cvtColor(np.array(region), cv2.COLOR_RGB2BGR)
    cv2.namedWindow("Chọn vùng", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Chọn vùng", cv2.WND_PROP_TOPMOST, 1)
    drawing = region.copy()
    rect_start = None
    rect_end = None
    is_drawing = False

    def draw_rectangle(event, x, y, flags, param):
        nonlocal rect_start, rect_end, is_drawing, drawing
        if event == cv2.EVENT_LBUTTONDOWN:
            rect_start = (x, y)
            is_drawing = True
            drawing = region.copy()
        elif event == cv2.EVENT_MOUSEMOVE:
            if is_drawing:
                drawing = region.copy()
                for i in range(0, abs(rect_start[0] - x), 10):
                    cv2.line(drawing, (rect_start[0] + i, rect_start[1]), (rect_start[0] + i + 5, rect_start[1]), (0, 255, 0), 2)
                    cv2.line(drawing, (rect_start[0] + i, y), (rect_start[0] + i + 5, y), (0, 255, 0), 2)
                for i in range(0, abs(rect_start[1] - y), 10):
                    cv2.line(drawing, (rect_start[0], rect_start[1] + i), (rect_start[0], rect_start[1] + i + 5), (0, 255, 0), 2)
                    cv2.line(drawing, (x, rect_start[1] + i), (x, rect_start[1] + i + 5), (0, 255, 0), 2)
        elif event == cv2.EVENT_LBUTTONUP:
            is_drawing = False
            rect_end = (x, y)
            drawing = region.copy()
            for i in range(0, abs(rect_start[0] - x), 10):
                cv2.line(drawing, (rect_start[0] + i, rect_start[1]), (rect_start[0] + i + 5, rect_start[1]), (0, 255, 0), 2)
                cv2.line(drawing, (rect_start[0] + i, y), (rect_start[0] + i + 5, y), (0, 255, 0), 2)
            for i in range(0, abs(rect_start[1] - y), 10):
                cv2.line(drawing, (rect_start[0], rect_start[1] + i), (rect_start[0], rect_start[1] + i + 5), (0, 255, 0), 2)
                cv2.line(drawing, (x, rect_start[1] + i), (x, rect_start[1] + i + 5), (0, 255, 0), 2)

    cv2.setMouseCallback("Chọn vùng", draw_rectangle)
    while True:
        cv2.imshow("Chọn vùng", drawing)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC key
            cv2.destroyAllWindows()
            return None, None
        elif not is_drawing and rect_start is not None and rect_end is not None:
            break
    cv2.destroyAllWindows()
    x = min(rect_start[0], rect_end[0])
    y = min(rect_start[1], rect_end[1])
    w = abs(rect_end[0] - rect_start[0])
    h = abs(rect_end[1] - rect_start[1])
    if w == 0 or h == 0:
        return None, None
    screenshot = pyautogui.screenshot(region=(x, y, w, h))
    screenshot = np.array(screenshot)
    return screenshot, (x, y, w, h)