import pyautogui
import numpy as np
import logging
from typing import Tuple, Optional
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen

logger = logging.getLogger(__name__)


class RegionSelector(QWidget):
    """A transparent overlay window for selecting screen regions."""
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        
        # Get all screens and create overlay for primary screen
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication instance not found")
        
        primary_screen = app.primaryScreen()
        screen_geometry = primary_screen.geometry()
        
        # Set window to cover entire primary screen
        self.setGeometry(screen_geometry)
        
        # Selection state
        self.start_point = None
        self.end_point = None
        self.is_selecting = False
        self.selection_complete = False
        self.cancelled = False
        
    def paintEvent(self, event):
        """Draw the overlay with selection rectangle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw semi-transparent overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        # Draw selection rectangle if selecting
        if self.start_point and self.end_point:
            rect = QRect(self.start_point, self.end_point).normalized()
            
            # Clear the selection area (make it brighter)
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            
            # Draw border
            pen = QPen(QColor(0, 255, 0), 2)
            painter.setPen(pen)
            painter.drawRect(rect)
            
            # Draw corner indicators
            corner_size = 10
            pen.setWidth(3)
            painter.setPen(pen)
            
            # Top-left
            painter.drawLine(rect.topLeft(), rect.topLeft() + QPoint(corner_size, 0))
            painter.drawLine(rect.topLeft(), rect.topLeft() + QPoint(0, corner_size))
            
            # Top-right
            painter.drawLine(rect.topRight(), rect.topRight() + QPoint(-corner_size, 0))
            painter.drawLine(rect.topRight(), rect.topRight() + QPoint(0, corner_size))
            
            # Bottom-left
            painter.drawLine(rect.bottomLeft(), rect.bottomLeft() + QPoint(corner_size, 0))
            painter.drawLine(rect.bottomLeft(), rect.bottomLeft() + QPoint(0, -corner_size))
            
            # Bottom-right
            painter.drawLine(rect.bottomRight(), rect.bottomRight() + QPoint(-corner_size, 0))
            painter.drawLine(rect.bottomRight(), rect.bottomRight() + QPoint(0, -corner_size))
    
    def mousePressEvent(self, event):
        """Start selection."""
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.is_selecting = True
            self.selection_complete = False
            self.update()
    
    def mouseMoveEvent(self, event):
        """Update selection rectangle."""
        if self.is_selecting and self.start_point:
            self.end_point = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Complete selection."""
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.end_point = event.pos()
            self.is_selecting = False
            # Only complete if we have a valid selection
            if self.start_point and self.end_point:
                rect = QRect(self.start_point, self.end_point).normalized()
                if rect.width() > 10 and rect.height() > 10:  # Minimum size
                    self.selection_complete = True
                    self.close()
            self.update()
    
    def keyPressEvent(self, event):
        """Handle ESC key to cancel."""
        if event.key() == Qt.Key_Escape:
            self.cancelled = True
            self.selection_complete = False
            self.close()
    
    def get_selection(self) -> Optional[Tuple[int, int, int, int]]:
        """Get the selected region in screen coordinates."""
        if not self.start_point or not self.end_point:
            return None
        
        # Convert widget coordinates to screen coordinates
        screen_pos_start = self.mapToGlobal(self.start_point)
        screen_pos_end = self.mapToGlobal(self.end_point)
        
        x = min(screen_pos_start.x(), screen_pos_end.x())
        y = min(screen_pos_start.y(), screen_pos_end.y())
        w = abs(screen_pos_end.x() - screen_pos_start.x())
        h = abs(screen_pos_end.y() - screen_pos_start.y())
        
        if w == 0 or h == 0:
            return None
        
        return (x, y, w, h)


def capture_screen_region() -> Tuple[Optional[np.ndarray], Optional[Tuple[int, int, int, int]]]:
    """Capture a region of the screen selected by the user using PyQt5."""
    try:
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication instance not found")
        
        # Create region selector
        selector = RegionSelector()
        selector.show()
        selector.raise_()
        selector.activateWindow()
        
        # Force window to front on Windows
        try:
            import platform
            if platform.system() == 'Windows':
                import ctypes
                hwnd = int(selector.winId())
                if hwnd:
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        except Exception:
            pass  # Ignore errors in window management
        
        # Process events to ensure window is shown
        app.processEvents()
        
        # Use QEventLoop to wait for selection
        from PyQt5.QtCore import QEventLoop
        loop = QEventLoop()
        
        # Check if window is closed (selection complete or cancelled)
        def check_selection():
            if not selector.isVisible():
                loop.quit()
        
        timer = QTimer()
        timer.timeout.connect(check_selection)
        timer.start(50)  # Check every 50ms
        
        # Run event loop until window closes
        loop.exec_()
        timer.stop()
        
        # Get selection
        if selector.selection_complete and not selector.cancelled:
            region = selector.get_selection()
            selector.close()
            
            if region:
                x, y, w, h = region
                screenshot = pyautogui.screenshot(region=(x, y, w, h))
                screenshot = np.array(screenshot)
                return screenshot, (x, y, w, h)
        
        selector.close()
        return None, None
        
    except Exception as e:
        logger.error(f"Error capturing screen region: {str(e)}", exc_info=True)
        return None, None
