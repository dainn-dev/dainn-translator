import pyautogui
import numpy as np
import time
import sys
from typing import Tuple, Optional
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QPainter, QColor, QPen, QScreen

class RegionSelector(QWidget):
    """A transparent overlay widget for selecting screen regions."""
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Get screen geometry
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        self.setGeometry(screen_geometry)
        
        self.start_point = None
        self.end_point = None
        self.is_selecting = False
        self.selection_result = None
    
    def _get_selection_rect(self) -> Optional[QRect]:
        """Calculate and return the selection rectangle."""
        if not self.start_point or not self.end_point:
            return None
        
        x1 = min(self.start_point.x(), self.end_point.x())
        y1 = min(self.start_point.y(), self.end_point.y())
        x2 = max(self.start_point.x(), self.end_point.x())
        y2 = max(self.start_point.y(), self.end_point.y())
        
        return QRect(x1, y1, x2 - x1, y2 - y1)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.is_selecting = True
            self.end_point = self.start_point
            self.update()
            
    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.end_point = event.pos()
            self.update()
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.end_point = event.pos()
            self.is_selecting = False
            
            selection_rect = self._get_selection_rect()
            if selection_rect and selection_rect.width() > 0 and selection_rect.height() > 0:
                # Convert to global coordinates
                global_pos = self.mapToGlobal(QPoint(selection_rect.x(), selection_rect.y()))
                self.selection_result = (global_pos.x(), global_pos.y(), 
                                       selection_rect.width(), selection_rect.height())
            
            self.close()
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.selection_result = None
            self.close()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw semi-transparent overlay
        overlay_color = QColor(0, 0, 0, 100)
        painter.fillRect(self.rect(), overlay_color)
        
        selection_rect = self._get_selection_rect()
        if selection_rect:
            # Clear the selected region
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(selection_rect, Qt.transparent)
            
            # Draw selection border
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            pen = QPen(QColor(0, 255, 0), 2)
            painter.setPen(pen)
            painter.drawRect(selection_rect)
        
    def get_selection(self) -> Optional[Tuple[int, int, int, int]]:
        """Get the selected region as (x, y, width, height)."""
        return self.selection_result


def capture_screen_region() -> Tuple[Optional[np.ndarray], Optional[Tuple[int, int, int, int]]]:
    """Capture a region of the screen selected by the user using PyQt5."""
    # Ensure QApplication exists
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Create region selector
    selector = RegionSelector()
    selector.show()
    selector.raise_()
    selector.activateWindow()
    
    # Process events to show the window
    app.processEvents()
    
    # Wait for selection (use event loop)
    while selector.isVisible():
        app.processEvents()
        time.sleep(0.01)  # Small delay to prevent CPU spinning
    
    # Get selection
    region = selector.get_selection()
    
    if region is None:
        return None, None
    
    x, y, w, h = region
    
    # Capture the selected region
    screenshot = pyautogui.screenshot(region=(x, y, w, h))
    screenshot = np.array(screenshot)
    return screenshot, (x, y, w, h)