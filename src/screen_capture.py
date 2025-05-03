import cv2
import numpy as np
import sys
import platform
from typing import Tuple, Optional
import subprocess
import tempfile
import os
import re

def capture_screen_region(show_instructions: bool = True) -> Tuple[Optional[np.ndarray], Optional[Tuple[int, int, int, int]]]:
    """Capture a region of the screen selected by the user."""
    if platform.system() == 'Darwin':
        # On macOS, use screencapture command
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        temp_file.close()
        
        try:
            # Take a screenshot using screencapture command
            result = subprocess.run(['screencapture', '-x', temp_file.name], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Failed to capture screen: {result.stderr}")
                os.unlink(temp_file.name)
                return None, None
            
            # Read the screenshot
            screen = cv2.imread(temp_file.name)
            if screen is None:
                print("Failed to read captured screenshot")
                os.unlink(temp_file.name)
                return None, None
                
            # Get screen dimensions
            screen_info = subprocess.run(['system_profiler', 'SPDisplaysDataType'], capture_output=True, text=True)
            if screen_info.returncode == 0:
                # Parse screen resolution from output
                resolution_match = re.search(r'Resolution: (\d+) x (\d+)', screen_info.stdout)
                if resolution_match:
                    screen_width = int(resolution_match.group(1))
                    screen_height = int(resolution_match.group(2))
                    
                    # Validate region coordinates
                    def validate_coordinates(x, y, w, h):
                        x = max(0, min(x, screen_width - 1))
                        y = max(0, min(y, screen_height - 1))
                        w = max(1, min(w, screen_width - x))
                        h = max(1, min(h, screen_height - y))
                        return x, y, w, h
                    
                    # Show the screenshot and let user select region
                    cv2.namedWindow("Select Region", cv2.WINDOW_NORMAL)
                    cv2.setWindowProperty("Select Region", cv2.WND_PROP_TOPMOST, 1)
                    drawing = screen.copy()
                    rect_start = None
                    rect_end = None
                    is_drawing = False

                    def draw_rectangle(event, x, y, flags, param):
                        nonlocal rect_start, rect_end, is_drawing, drawing
                        if event == cv2.EVENT_LBUTTONDOWN:
                            rect_start = (x, y)
                            is_drawing = True
                            drawing = screen.copy()
                        elif event == cv2.EVENT_MOUSEMOVE:
                            if is_drawing:
                                drawing = screen.copy()
                                cv2.rectangle(drawing, rect_start, (x, y), (0, 255, 0), 2)
                        elif event == cv2.EVENT_LBUTTONUP:
                            is_drawing = False
                            rect_end = (x, y)
                            drawing = screen.copy()
                            cv2.rectangle(drawing, rect_start, rect_end, (0, 255, 0), 2)

                    cv2.setMouseCallback("Select Region", draw_rectangle)
                    while True:
                        cv2.imshow("Select Region", drawing)
                        key = cv2.waitKey(1) & 0xFF
                        if key == 27:  # ESC key
                            cv2.destroyAllWindows()
                            os.unlink(temp_file.name)
                            return None, None
                        elif not is_drawing and rect_start is not None and rect_end is not None:
                            break
                    cv2.destroyAllWindows()

                    # Calculate region coordinates
                    x = min(rect_start[0], rect_end[0])
                    y = min(rect_start[1], rect_end[1])
                    w = abs(rect_end[0] - rect_start[0])
                    h = abs(rect_end[1] - rect_start[1])

                    if w == 0 or h == 0:
                        os.unlink(temp_file.name)
                        return None, None

                    # Validate and adjust coordinates
                    x, y, w, h = validate_coordinates(x, y, w, h)
                    
                    # Crop the selected region
                    screenshot = screen[y:y+h, x:x+w]
                    os.unlink(temp_file.name)
                    return screenshot, (x, y, w, h)
            
        except Exception as e:
            print(f"Error during screen capture: {str(e)}")
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            return None, None
            
    else:
        # For other platforms, use pyautogui
        import pyautogui
        screen = pyautogui.screenshot()
        screen = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)

        cv2.namedWindow("Select Region", cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("Select Region", cv2.WND_PROP_TOPMOST, 1)
        drawing = screen.copy()
        rect_start = None
        rect_end = None
        is_drawing = False

        def draw_rectangle(event, x, y, flags, param):
            nonlocal rect_start, rect_end, is_drawing, drawing
            if event == cv2.EVENT_LBUTTONDOWN:
                rect_start = (x, y)
                is_drawing = True
                drawing = screen.copy()
            elif event == cv2.EVENT_MOUSEMOVE:
                if is_drawing:
                    drawing = screen.copy()
                    cv2.rectangle(drawing, rect_start, (x, y), (0, 255, 0), 2)
            elif event == cv2.EVENT_LBUTTONUP:
                is_drawing = False
                rect_end = (x, y)
                drawing = screen.copy()
                cv2.rectangle(drawing, rect_start, rect_end, (0, 255, 0), 2)

        cv2.setMouseCallback("Select Region", draw_rectangle)
        while True:
            cv2.imshow("Select Region", drawing)
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

        # Crop the selected region
        screenshot = screen[y:y+h, x:x+w]
        return screenshot, (x, y, w, h)