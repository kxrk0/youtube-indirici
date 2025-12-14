#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU-optimized widgets for smooth scrolling and rendering.
Supports high refresh rate monitors (60Hz - 240Hz+).
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QScrollArea, QWidget, QScroller, QScrollerProperties, QApplication
from PyQt6.QtGui import QPainter
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

from src.utils.helpers import get_monitor_refresh_rate, get_optimal_timer_interval


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
        # Reduce unnecessary repaints
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        
        # Enable static contents optimization (content doesn't change during scroll)
        self.setAttribute(Qt.WidgetAttribute.WA_StaticContents, True)
        
        # Scroll optimization
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Faster updates
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        
    def _setup_kinetic_scrolling(self):
        """Enable smooth kinetic (momentum) scrolling like mobile devices."""
        try:
            # Grab gesture for touch-like scrolling
            scroller = QScroller.scroller(self.viewport())
            
            # Configure scroller properties for smooth experience
            props = scroller.scrollerProperties()
            
            # Adjust deceleration based on refresh rate
            # Higher refresh rate = smoother deceleration = can be longer
            decel_factor = 0.985 if self._refresh_rate >= 120 else 0.975
            props.setScrollMetric(
                QScrollerProperties.ScrollMetric.DecelerationFactor,
                decel_factor
            )
            
            # Minimum velocity to start scrolling (lower = more responsive)
            props.setScrollMetric(
                QScrollerProperties.ScrollMetric.MinimumVelocity,
                0.1
            )
            
            # Maximum velocity cap
            props.setScrollMetric(
                QScrollerProperties.ScrollMetric.MaximumVelocity,
                1.0
            )
            
            # Frame rate for scroll animation
            fps = min(self._refresh_rate, 240)  # Cap at 240
            frame_rate = 1000.0 / fps
            props.setScrollMetric(
                QScrollerProperties.ScrollMetric.FrameRate,
                frame_rate
            )
            
            # Overshoot (bounce effect at edges)
            props.setScrollMetric(
                QScrollerProperties.ScrollMetric.OvershootDragResistanceFactor,
                0.5
            )
            props.setScrollMetric(
                QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor,
                0.2
            )
            
            # Apply properties
            scroller.setScrollerProperties(props)
            
            # Enable touch gesture (works with mouse wheel too)
            QScroller.grabGesture(
                self.viewport(),
                QScroller.ScrollerGestureType.LeftMouseButtonGesture
            )
            
        except Exception as e:
            print(f"Kinetic scrolling setup failed: {e}")
    
    def _setup_scroll_optimization(self):
        """Additional scroll optimizations."""
        # Smooth scroll step size based on refresh rate
        # Higher Hz = smaller steps = smoother
        scroll_step = max(20, int(120 / (self._refresh_rate / 60)))
        
        vbar = self.verticalScrollBar()
        if vbar:
            vbar.setSingleStep(scroll_step)
            
    def wheelEvent(self, event):
        """Override wheel event for smoother scrolling."""
        # Get scroll delta
        delta = event.angleDelta().y()
        
        # Calculate smooth scroll amount based on refresh rate
        # Higher refresh rate = can handle more granular scrolling
        if self._refresh_rate >= 144:
            multiplier = 0.8  # Smoother scrolling for high Hz
        elif self._refresh_rate >= 120:
            multiplier = 1.0
        else:
            multiplier = 1.2  # Faster response for 60Hz
            
        # Apply scroll
        vbar = self.verticalScrollBar()
        if vbar:
            current = vbar.value()
            # Negative delta = scroll down, positive = scroll up
            new_value = current - int(delta * multiplier * 0.5)
            vbar.setValue(new_value)
            
        event.accept()


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
        """Smoother mouse wheel scrolling."""
        delta = event.angleDelta().y()
        vbar = self.verticalScrollBar()
        
        if vbar:
            # Smoother scroll step
            step = int(delta * 0.4)
            vbar.setValue(vbar.value() - step)
            
        event.accept()
