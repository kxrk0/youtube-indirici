#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU-optimized widgets for smooth scrolling and rendering.
Supports high refresh rate monitors (60Hz - 240Hz+).
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QScrollArea, QWidget, QScroller, QScrollerProperties, QApplication, QFrame
from PyQt6.QtGui import QPainter
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

from src.utils.helpers import get_monitor_refresh_rate, get_optimal_timer_interval


def setup_smooth_scroll(scroll_area, enable_kinetic: bool = True):
    """Scroll area optimizasyonları — tık gecikmesi olmadan akıcı kaydırma."""
    scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    # NOT: LeftMouseButtonGesture kullanmıyoruz — tüm fare tıklamalarını
    # ~300ms geciktirir (QScroller drag/click ayırt etmeye çalışır).
    # TouchGesture sadece dokunmatik ekranları etkiler, masaüstünde sorun yok.
    if enable_kinetic:
        try:
            scroller = QScroller.scroller(scroll_area.viewport())
            props = scroller.scrollerProperties()
            props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.85)
            props.setScrollMetric(QScrollerProperties.ScrollMetric.MinimumVelocity, 0.05)
            props.setScrollMetric(QScrollerProperties.ScrollMetric.MaximumVelocity, 2.5)
            props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragResistanceFactor, 1.0)
            props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.0)
            scroller.setScrollerProperties(props)
            # TouchGesture: dokunmatik ekranlarda kinetic, fareye dokunmaz
            QScroller.grabGesture(
                scroll_area.viewport(),
                QScroller.ScrollerGestureType.TouchGesture
            )
        except Exception as e:
            print(f"Kinetic scroll error: {e}")

    return scroll_area


class GPUAcceleratedViewport(QOpenGLWidget):
    """
    OpenGL-based viewport for hardware-accelerated rendering.
    Uses GPU for all paint operations instead of CPU software rendering.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Enable partial updates for better performance
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        
    def paintEvent(self, event):
        # Let OpenGL handle the painting
        super().paintEvent(event)


class SmoothScrollArea(QScrollArea):
    """
    High-performance scroll area with:
    - GPU-accelerated viewport (optional)
    - Kinetic (momentum) scrolling
    - Optimized for high refresh rate monitors
    - Reduced CPU usage during scroll
    """
    
    def __init__(self, parent=None, use_gpu_viewport: bool = False):
        super().__init__(parent)
        
        self._refresh_rate = get_monitor_refresh_rate()
        self._use_gpu = use_gpu_viewport
        
        # Setup GPU viewport if requested
        if use_gpu_viewport:
            try:
                self.setViewport(GPUAcceleratedViewport(self))
            except Exception as e:
                print(f"GPU viewport failed, falling back to CPU: {e}")
        
        # Optimize widget attributes for smooth rendering
        self._setup_widget_attributes()
        
        # Setup kinetic scrolling (touch-like momentum)
        self._setup_kinetic_scrolling()
        
        # Optimize scroll behavior
        self._setup_scroll_optimization()
        
    def _setup_widget_attributes(self):
        """Configure widget attributes for optimal rendering."""
        # WA_StaticContents KULLANMA — dinamik içerikte (progress bar, animasyon)
        # Qt gerekli repaintları atlıyor, visual glitch oluşuyor.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        
    def _setup_kinetic_scrolling(self):
        """Dokunmatik kinetic kaydırma — fareye müdahale etmez."""
        try:
            scroller = QScroller.scroller(self.viewport())
            props = scroller.scrollerProperties()
            props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.85)
            props.setScrollMetric(QScrollerProperties.ScrollMetric.MinimumVelocity, 0.05)
            props.setScrollMetric(QScrollerProperties.ScrollMetric.MaximumVelocity, 2.5)
            props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragResistanceFactor, 1.0)
            props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.0)
            scroller.setScrollerProperties(props)
            # TouchGesture — LeftMouseButtonGesture değil (tık gecikmesi yaratır)
            QScroller.grabGesture(
                self.viewport(),
                QScroller.ScrollerGestureType.TouchGesture
            )
        except Exception as e:
            print(f"Kinetic scrolling setup failed: {e}")
    
    def _setup_scroll_optimization(self):
        """Scroll adım boyutu optimizasyonu."""
        vbar = self.verticalScrollBar()
        if vbar:
            vbar.setSingleStep(40)
            vbar.setPageStep(300)


class OptimizedScrollArea(QScrollArea):
    """
    Optimized scroll area without OpenGL dependency.
    Uses Qt's built-in optimizations for smooth scrolling.
    Better compatibility but slightly less performant than SmoothScrollArea.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._refresh_rate = get_monitor_refresh_rate()
        
        # Basic optimizations
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Enable kinetic scrolling
        try:
            scroller = QScroller.scroller(self.viewport())
            props = scroller.scrollerProperties()
            
            # Smooth deceleration
            props.setScrollMetric(
                QScrollerProperties.ScrollMetric.DecelerationFactor,
                0.98
            )
            
            scroller.setScrollerProperties(props)
            QScroller.grabGesture(
                self.viewport(),
                QScroller.ScrollerGestureType.LeftMouseButtonGesture
            )
        except Exception:
            pass
    
    def wheelEvent(self, event):
        """Standart tekerlek kaydırma — Qt default davranışını kullan."""
        super().wheelEvent(event)
