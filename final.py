# === Standard Library ===
import ctypes
from ctypes import wintypes
import json
import logging
import os
import random
import subprocess
import sys
import re
import threading
import time
from datetime import datetime
import types
import logging
import logging.handlers
import platform
import subprocess
from PyQt6 import QtCore, QtWidgets
# === Third-party Modules ===
import keyboard
import numpy as np
import psutil
import requests
import sounddevice as sd
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QMetaObject, Q_ARG
# === PyQt6 Core ===
from PyQt6.QtCore import (
    QCoreApplication,
    QEvent,
    QPropertyAnimation,
    QRect,
    QRegularExpression,
    QSize,
    QTimer,
    Qt,
    QUrl,
    QUrlQuery,
    QBuffer,QObject,
)

# === PyQt6 GUI ===
from PyQt6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QPainter,
    QPixmap,
    QTextCharFormat,
    QTextFormat,
    QSyntaxHighlighter,QAction,QKeySequence,QGuiApplication
)

# === PyQt6 Widgets ===
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,QGroupBox,
)

# === PyQt6 Multimedia ===
from PyQt6.QtMultimedia import (
    QCamera,
    QCameraDevice,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaRecorder,QVideoSink
)

from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QEventLoop
# === PyQt6 Network ===
from PyQt6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)

# === PyQt6 Web Engine ===
from PyQt6.QtWebEngineWidgets import QWebEngineView
# -----------------------------------------------------------------------------
# Logging Setup
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Global flag for manual control
SUPPRESS_FOCUS_CHECKS = False

class DialogMonitor(QObject):
    """Enhanced dialog monitor that hooks into application events"""
    
    def __init__(self):
        super().__init__()
        self.active_dialogs = []
        
        # Install event filter on the application
        QApplication.instance().installEventFilter(self)
        
        # Backup periodic check with moderate frequency
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.scan_for_dialogs)
        self.check_timer.start(250)  # Check every 250ms
        
        # Track dialog stability to reduce flicker
        self.dialog_stable_timer = QTimer()
        self.dialog_stable_timer.setSingleShot(True)
        self.dialog_stable_timer.timeout.connect(self.dialog_stabilized)
        
        # Add debouncing for dialog state changes
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.update_suppression_with_delay)
        
        self.pending_suppression_state = None
        self.suppression_active = False
        
        logging.info("Dialog monitor initialized")
    
    def eventFilter(self, obj, event):
        """Qt-specific event filter with enhanced emergency exit detection and dialog awareness"""
        # Declare global variable at the beginning of the function
        global SUPPRESS_FOCUS_CHECKS
    # Special detection for QComboBox popup
        if (event.type() in [QEvent.Type.Show, QEvent.Type.WindowActivate] and 
            (obj.inherits("QComboBox") or obj.objectName() == "qt_combo_popup" or 
            (hasattr(obj, 'metaObject') and obj.metaObject().className() == "QComboBoxPrivateContainer"))):
            
            # When dropdown shows, activate suppression
            logging.debug(f"QComboBox popup detected - suppressing focus checks")
            self.request_suppression_change(True)
            return super().eventFilter(obj, event)
        
        # Special handling for combobox popup closing
        if (event.type() in [QEvent.Type.Hide, QEvent.Type.WindowDeactivate] and 
            (obj.inherits("QComboBox") or obj.objectName() == "qt_combo_popup" or 
            (hasattr(obj, 'metaObject') and obj.metaObject().className() == "QComboBoxPrivateContainer"))):
            
            # When dropdown hides, maintain suppression briefly to allow selection
            logging.debug(f"QComboBox popup hiding - maintaining suppression briefly")
            QTimer.singleShot(300, lambda: self.check_for_active_combos())
            return super().eventFilter(obj, event)        
        # Special handling for dialog-related events
        if event.type() in [QEvent.Type.WindowActivate, QEvent.Type.WindowDeactivate,
                            QEvent.Type.Show, QEvent.Type.Hide]:
            # Check if this is a dialog or dialog component
            if (isinstance(obj, QDialog) or isinstance(obj, QMessageBox) or 
                obj.inherits("QDialog") or self.is_dialog_child(obj)):
                
                # Handle dialog activation/deactivation with debouncing
                if event.type() == QEvent.Type.Show:
                    logging.debug(f"Dialog show event detected for {obj.__class__.__name__}")
                    if obj not in self.active_dialogs:
                        self.active_dialogs.append(obj)
                        self.request_suppression_change(True)
                        
                elif event.type() == QEvent.Type.Hide:
                    logging.debug(f"Dialog hide event detected for {obj.__class__.__name__}")
                    if obj in self.active_dialogs:
                        self.active_dialogs.remove(obj)
                        if not self.active_dialogs:
                            self.request_suppression_change(False)
                
                # Let dialog events pass through without interference
                return super().eventFilter(obj, event)
        
        # Handle key press events with emergency exit detection
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            
            # Enhanced detection for emergency exit
            is_ctrl = modifiers & Qt.KeyboardModifier.ControlModifier
            is_shift = modifiers & Qt.KeyboardModifier.ShiftModifier
            is_e_key = key == Qt.Key.Key_E
            
            # Check for emergency exit combination
            if is_ctrl and is_shift and is_e_key:
                logging.info("EMERGENCY EXIT combination detected in filter!")
                # Try triggering the emergency submit function
                self.trigger_emergency_submit()
                # If we somehow get here, force exit
                import os
                os._exit(0)
                return True  # Handled
                
            # Allow Ctrl+Shift+E for emergency submit
            if (key == Qt.Key.Key_E and 
                modifiers & Qt.KeyboardModifier.ControlModifier and 
                modifiers & Qt.KeyboardModifier.ShiftModifier):
                logging.info("Emergency submit key combination detected in Qt event filter")
                # Don't block this event
                return False
            
            # Check if we're in a dialog - don't block keys if so
            if SUPPRESS_FOCUS_CHECKS:
                # Let dialog handle its own keyboard events
                return super().eventFilter(obj, event)
            
            # Allow regular keys needed for form input and UI interaction
            if ((key >= Qt.Key.Key_A and key <= Qt.Key.Key_Z) or  # Letters
                (key >= Qt.Key.Key_0 and key <= Qt.Key.Key_9) or  # Numbers
                key == Qt.Key.Key_Space or                        # Space
                key == Qt.Key.Key_Return or                      # Enter/Return
                key == Qt.Key.Key_Backspace or                   # Backspace
                key == Qt.Key.Key_Delete or                      # Delete
                (key >= Qt.Key.Key_Left and key <= Qt.Key.Key_Down)):  # Arrow keys
                return False  # Don't block these keys
                
            # Comprehensive blocking of problematic keys
            # Block function keys
            if key >= Qt.Key.Key_F1 and key <= Qt.Key.Key_F12:
                logging.info(f"Blocked function key {key - Qt.Key.Key_F1 + 1} through Qt event filter")
                return True  # Block the event
                
            # Block Escape only outside of dialogs
            if key == Qt.Key.Key_Escape:
                logging.info("Blocked Escape through Qt event filter")
                return True
                
            # Block Tab
            if key == Qt.Key.Key_Tab:
                logging.info("Blocked Tab through Qt event filter")
                return True
                
            # Block Alt modifiers
            if modifiers & Qt.KeyboardModifier.AltModifier:
                logging.info("Blocked Alt combination through Qt event filter")
                return True
                
            # Block Windows key combinations
            if modifiers & Qt.KeyboardModifier.MetaModifier:
                logging.info("Blocked Windows key combination through Qt event filter")
                return True
                
        # Handle window deactivate events with dialog awareness
        elif event.type() == QEvent.Type.WindowDeactivate:
            # Only handle window deactivation for the main window
            if isinstance(obj, MainWindow):
                # Don't immediately reactivate if a dialog is opening
                if SUPPRESS_FOCUS_CHECKS:
                    logging.debug("Window deactivate during dialog interaction - allowing")
                    return super().eventFilter(obj, event)
                    
                # Check if deactivation is due to a dialog that might be opening
                # This requires scanning for dialogs that are becoming active
                for widget in QApplication.topLevelWidgets():
                    if ((isinstance(widget, QDialog) or isinstance(widget, QMessageBox)) and 
                        widget.isVisible()):
                        # Add this dialog to our tracking
                        if widget not in self.active_dialogs:
                            self.active_dialogs.append(widget)
                            self.request_suppression_change(True)
                        logging.debug("Window deactivated due to visible dialog - allowing")
                        return super().eventFilter(obj, event)
                
                # No dialog detected, schedule focus restore with a delay
                # The delay helps avoid conflict if a dialog is about to appear
                logging.debug("Window deactivate event - scheduling delayed re-activation")
                QTimer.singleShot(250, lambda: self.delayed_focus_restore(obj))
        
        return super().eventFilter(obj, event)
    
    def check_for_active_combos(self):
        """Check if any QComboBox is still showing its popup"""
        combo_active = False
        
        # Look for active combo box popups
        for widget in QApplication.topLevelWidgets():
            if (widget.objectName() == "qt_combo_popup" or 
                (hasattr(widget, 'metaObject') and widget.metaObject().className() == "QComboBoxPrivateContainer")):
                if widget.isVisible():
                    combo_active = True
                    break
        
        # Only deactivate suppression if no combo box is active
        if not combo_active and not self.active_dialogs:
            self.request_suppression_change(False)
            logging.debug("No active QComboBox popups - releasing suppression")   

    def request_suppression_change(self, suppress):
        """Request a change in suppression state with debouncing to prevent flicker"""
        # Save the requested state
        self.pending_suppression_state = suppress
        
        # If timer is not active, start it
        if not self.debounce_timer.isActive():
            self.debounce_timer.start(200)  # 200ms debounce
    
    def update_suppression_with_delay(self):
        """Apply the suppression state change after debounce period"""
        if self.pending_suppression_state is not None:
            self.update_focus_suppression(self.pending_suppression_state)
            self.pending_suppression_state = None
    
    def dialog_stabilized(self):
        """Called when dialog is considered stable - ensures dialog has focus"""
        if self.active_dialogs:
            # Ensure the most recent dialog has focus
            dialog = self.active_dialogs[-1]
            if not dialog.hasFocus() and dialog.isVisible():
                logging.debug("Ensuring dialog has focus after stabilization")
                dialog.activateWindow()
                dialog.raise_()
    
    def is_dialog_child(self, obj):
        """
        Enhanced check if object is a dialog component or dropdown popup
        Recognizes both standard dialogs and QComboBox popup windows
        """
        # Check if this is a QComboBox popup or similar widget
        if obj.inherits("QComboBox") or obj.objectName() == "qt_scrollarea_viewport":
            return True
            
        # Check for dropdown popup - QComboBox creates a popup that needs to be recognized
        if obj.objectName() == "qt_combo_popup" or (hasattr(obj, 'metaObject') and 
                                                obj.metaObject().className() == "QComboBoxPrivateContainer"):
            return True
        
        # Standard dialog hierarchy check
        if hasattr(obj, 'parent'):
            parent = obj.parent()
            while parent:
                if (isinstance(parent, QDialog) or isinstance(parent, QMessageBox) or
                    parent.inherits("QDialog") or parent.inherits("QComboBox") or 
                    parent.objectName() == "qt_combo_popup"):
                    return True
                parent = parent.parent() if hasattr(parent, 'parent') else None
        return False
    
    def scan_for_dialogs(self):
        """Backup method to scan for dialogs with improved stability"""
        found_dialogs = []
        for widget in QApplication.topLevelWidgets():
            if (isinstance(widget, QDialog) or isinstance(widget, QMessageBox)) and widget.isVisible():
                found_dialogs.append(widget)
        
        # Update our list and state
        if found_dialogs and not self.active_dialogs:
            self.active_dialogs = found_dialogs
            self.request_suppression_change(True)
            # Reset dialog stability timer
            self.dialog_stable_timer.start(300)
            logging.info(f"Dialog scan found active dialogs: {len(found_dialogs)}")
        elif self.suppression_active and not found_dialogs:
            # No visible dialogs but suppression is active - wait to confirm
            if not self.active_dialogs:
                # Double-check for any visible dialogs
                for widget in QApplication.topLevelWidgets():
                    if ((isinstance(widget, QDialog) or isinstance(widget, QMessageBox)) and 
                        widget.isVisible()):
                        found_dialogs.append(widget)
                
                if not found_dialogs:
                    # Dialogs really are gone - release suppression after delay
                    QTimer.singleShot(500, lambda: self.update_focus_suppression(False))
                    logging.info("Dialog scan confirmed no active dialogs")
    
    def update_focus_suppression(self, suppress):
        """Update the global focus suppression flag with state tracking"""
        global SUPPRESS_FOCUS_CHECKS
        
        # Track our internal state to avoid redundant operations
        if self.suppression_active == suppress:
            return
            
        self.suppression_active = suppress
        SUPPRESS_FOCUS_CHECKS = suppress
        
        logging.info(f"Focus checks {'SUPPRESSED' if suppress else 'ENABLED'}")
        
        # If suppressing, immediately pause all focus timers
        if suppress:
            self.pause_all_focus_timers()
        else:
            # If enabling, wait a moment before restarting timers
            QTimer.singleShot(400, self.resume_all_focus_timers)
    
    def pause_all_focus_timers(self):
        """Pause all focus checking timers"""
        # Find all timers connected to focus checking
        for window in QApplication.topLevelWidgets():
            if hasattr(window, 'focus_timer') and window.focus_timer.isActive():
                window.focus_timer.stop()
                # Mark it as temporarily stopped
                window.focus_timer.setProperty("temp_stopped", True)
                logging.debug(f"Paused focus timer for {window.__class__.__name__}")
    
    def resume_all_focus_timers(self):
        """Resume all previously paused focus timers with additional checks"""
        # Only restart timers if dialogs are really gone
        if self.active_dialogs:
            logging.debug("Not resuming timers - dialogs still active")
            return
            
        # Double-check for any visible dialogs before resuming
        for widget in QApplication.topLevelWidgets():
            if ((isinstance(widget, QDialog) or isinstance(widget, QMessageBox)) and 
                widget.isVisible()):
                logging.debug("Not resuming timers - dialog still visible")
                return
                
        for window in QApplication.topLevelWidgets():
            if hasattr(window, 'focus_timer') and window.focus_timer.property("temp_stopped"):
                window.focus_timer.setProperty("temp_stopped", False)
                window.focus_timer.start()
                logging.debug(f"Resumed focus timer for {window.__class__.__name__}")
                
    def delayed_focus_restore(self, window):
        """Safely restore focus to window with dialog awareness"""
        # Double-check for dialogs before actually restoring focus
        global SUPPRESS_FOCUS_CHECKS
        if SUPPRESS_FOCUS_CHECKS:
            logging.debug("Not restoring focus - suppression active")
            return
            
        # Check again for any visible dialogs
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) or isinstance(widget, QMessageBox) or widget.inherits("QDialog"):
                if widget.isVisible():
                    if widget not in self.active_dialogs:
                        self.active_dialogs.append(widget)
                        self.request_suppression_change(True)
                    logging.debug("Not restoring focus - dialog visible")
                    return
        
        # Also check for modal dialogs
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, 'isModal') and widget.isModal() and widget.isVisible():
                logging.debug("Not restoring focus - modal dialog active")
                return
        
        # Safe to restore focus
        logging.debug("Delayed focus restore - activating window")
        window.activateWindow()
        window.raise_()

class ComboBoxHandler:
    @staticmethod
    def install():
        """Install the combo box focus handling patches"""
        # Find all combo boxes in the application
        for widget in QApplication.allWidgets():
            if isinstance(widget, QComboBox):
                ComboBoxHandler.patch_combo_box(widget)
                
        logging.info("Installed QComboBox focus handling patches")
    
    @staticmethod
    def patch_combo_box(combo):
        """Patch a single QComboBox to handle focus properly"""
        # Store original showPopup method
        original_show_popup = combo.showPopup
        
        def patched_show_popup():
            """Patched showPopup that suppresses focus checks"""
            global SUPPRESS_FOCUS_CHECKS
            
            # Suppress focus checks while popup is visible
            old_suppress = SUPPRESS_FOCUS_CHECKS
            global_suppress_focus_checks(True)
            
            # Call original method
            original_show_popup()
            
            # Ensure suppression stays active
            global_suppress_focus_checks(True)
            
        # Replace the method
        combo.showPopup = patched_show_popup
        
        # Add event filter to handle popup hide
        class ComboEventFilter(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Hide and obj.objectName() == "qt_combo_popup":
                    # Delay releasing suppression to allow for item selection
                    QTimer.singleShot(300, lambda: global_suppress_focus_checks(False))
                return False
        
        # Install filter on combo box
        combo_filter = ComboEventFilter()
        combo.installEventFilter(combo_filter)
        
        # Store filter as property to prevent garbage collection
        combo.setProperty("combo_filter", combo_filter)

# Add the setup function here
def setup_combo_box_handling():
    """Set up specific handling for QComboBox widgets"""
    # Install combo box patches
    ComboBoxHandler.install()
    
    # Create a timer to monitor for new combo boxes
    combo_monitor = QTimer()
    combo_monitor.timeout.connect(ComboBoxHandler.install)
    combo_monitor.start(2000)  # Check every 2 seconds for new combo boxes
    
    # Store timer as app property to prevent garbage collection
    QApplication.instance().setProperty("combo_monitor", combo_monitor)
    
    logging.info("QComboBox focus handling configured")
# Improved patched check focus method
def patched_check_focus(self):
    """Patched version of check_focus that respects the global suppression flag
    and adds additional safeguards against dialog blinking"""
    global SUPPRESS_FOCUS_CHECKS
    
    # Don't try to restore focus if an exam is already submitted
    if hasattr(self, 'exam_page') and hasattr(self.exam_page, 'exam_submitted') and self.exam_page.exam_submitted:
        # Stop checking focus if exam is submitted
        if hasattr(self, 'focus_timer') and self.focus_timer.isActive():
            self.focus_timer.stop()
            logging.info("Stopped focus checking - exam already submitted")
        return
    
    # Check the global suppression flag first
    if SUPPRESS_FOCUS_CHECKS:
        # Skip focus check while dialogs are active
        return
    
    # Additional safety check for any visible dialogs - more thorough
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog) or isinstance(widget, QMessageBox) or widget.inherits("QDialog"):
            if widget.isVisible():
                # Dialog found - don't restore focus
                # Set suppression flag to prevent focus war
                global_suppress_focus_checks(True)
                return
                
        # Also check for modal dialogs that might be opening
        if hasattr(widget, 'isModal') and widget.isModal() and widget.isVisible():
            # Modal dialog found - don't restore focus
            global_suppress_focus_checks(True)
            return
    
    # Now safe to check and restore focus
    active_window = QGuiApplication.focusWindow()
    if active_window is not self:
        # Make sure we're not stealing focus from a dialog
        focused_widget = QApplication.focusWidget()
        if focused_widget:
            # Check if the focused widget is part of a dialog
            parent = focused_widget
            while parent:
                if isinstance(parent, QDialog) or isinstance(parent, QMessageBox):
                    # Dialog found - don't restore focus
                    global_suppress_focus_checks(True)
                    return
                if hasattr(parent, 'parent'):
                    parent = parent.parent()
                else:
                    break
        
        logging.info("Window lost focus - restoring")
        # Add a small delay before restoring focus
        QTimer.singleShot(100, lambda: self.delayed_focus_restore())
        
def delayed_focus_restore(window):
    """Delayed focus restoration with additional dialog checking"""
    global SUPPRESS_FOCUS_CHECKS
    
    # Double-check for dialogs before actually restoring focus
    if SUPPRESS_FOCUS_CHECKS:
        logging.debug("Not restoring focus - suppression active")
        return
        
    # Check again for any visible dialogs
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog) or isinstance(widget, QMessageBox) or widget.inherits("QDialog"):
            if widget.isVisible():
                # Dialog found - don't restore focus
                global_suppress_focus_checks(True)
                logging.debug("Not restoring focus - dialog visible")
                return
    
    # Also check for modal dialogs
    for widget in QApplication.topLevelWidgets():
        if hasattr(widget, 'isModal') and widget.isModal() and widget.isVisible():
            global_suppress_focus_checks(True)
            logging.debug("Not restoring focus - modal dialog active")
            return
    
    logging.debug("Delayed focus restore - activating window")
    window.activateWindow()
    window.raise_()

def patched_check_app_focus(window):
    """Patched app-level focus checker that respects the global suppression flag
    and has improved dialog detection"""
    global SUPPRESS_FOCUS_CHECKS
    
    # Check the global suppression flag first
    if SUPPRESS_FOCUS_CHECKS:
        # Skip app focus check while dialogs are active
        return
    
    # Additional safety check for any visible dialogs with improved detection
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog) or isinstance(widget, QMessageBox) or widget.inherits("QDialog"):
            if widget.isVisible():
                # Dialog found - don't restore focus and ensure suppression is active
                global_suppress_focus_checks(True)
                return
                
        # Also check for modal dialogs
        if hasattr(widget, 'isModal') and widget.isModal() and widget.isVisible():
            global_suppress_focus_checks(True)
            return
    
    if window and not window.isActiveWindow():
        # Make sure we're not stealing focus from a dialog
        focused_widget = QApplication.focusWidget()
        if focused_widget:
            # Check if the focused widget is part of a dialog
            parent = focused_widget
            while parent:
                if isinstance(parent, QDialog) or isinstance(parent, QMessageBox):
                    # Don't restore focus if a dialog has focus
                    global_suppress_focus_checks(True)
                    return
                if hasattr(parent, 'parent'):
                    parent = parent.parent()
                else:
                    break
                    
        # Only restore focus if no dialogs are active
        logging.info("Application focus check - restoring focus")
        # Add a longer delay before restoring focus
        QTimer.singleShot(250, lambda: delayed_focus_restore(window))

def global_suppress_focus_checks(suppress):
    """Helper function to update global suppression flag and handle side effects"""
    global SUPPRESS_FOCUS_CHECKS
    
    # Only update if value is changing
    if SUPPRESS_FOCUS_CHECKS != suppress:
        SUPPRESS_FOCUS_CHECKS = suppress
        logging.info(f"Global focus suppression set to {suppress}")
        
        # If suppressing, pause all focus timers
        if suppress:
            # Find all focus timers and pause them
            for window in QApplication.topLevelWidgets():
                if hasattr(window, 'focus_timer') and window.focus_timer.isActive():
                    window.focus_timer.stop()
                    window.focus_timer.setProperty("temp_stopped", True)
                    logging.debug(f"Paused focus timer for {window.__class__.__name__}")
        else:
            # Give a delay before resuming timers
            QTimer.singleShot(400, resume_focus_timers) 
def resume_focus_timers():
    """Helper function to resume focus timers after dialog closes"""
    # Check again that no dialogs are visible before resuming
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog) or isinstance(widget, QMessageBox) or widget.inherits("QDialog"):
            if widget.isVisible():
                logging.debug("Not resuming timers - dialog still visible")
                return
    
    # Safe to resume timers
    for window in QApplication.topLevelWidgets():
        if hasattr(window, 'focus_timer') and window.focus_timer.property("temp_stopped"):
            window.focus_timer.setProperty("temp_stopped", False)
            window.focus_timer.start()
            logging.debug(f"Resumed focus timer for {window.__class__.__name__}")
    
    logging.info("Focus timers resumed")    

def patched_check_app_focus(window):
    """Patched app-level focus checker that respects the global suppression flag
    and has improved dialog detection"""
    global SUPPRESS_FOCUS_CHECKS
    
    # Check the global suppression flag first
    if SUPPRESS_FOCUS_CHECKS:
        # Skip app focus check while dialogs are active
        return
    
    # Additional safety check for any visible dialogs with improved detection
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog) or isinstance(widget, QMessageBox) or widget.inherits("QDialog"):
            if widget.isVisible():
                # Dialog found - don't restore focus and ensure suppression is active
                global_suppress_focus_checks(True)
                return
                
        # Also check for modal dialogs
        if hasattr(widget, 'isModal') and widget.isModal() and widget.isVisible():
            global_suppress_focus_checks(True)
            return
    
    if window and not window.isActiveWindow():
        # Make sure we're not stealing focus from a dialog
        focused_widget = QApplication.focusWidget()
        if focused_widget:
            # Check if the focused widget is part of a dialog
            parent = focused_widget
            while parent:
                if isinstance(parent, QDialog) or isinstance(parent, QMessageBox):
                    # Don't restore focus if a dialog has focus
                    global_suppress_focus_checks(True)
                    return
                if hasattr(parent, 'parent'):
                    parent = parent.parent()
                else:
                    break
                    
        # Only restore focus if no dialogs are active
        logging.info("Application focus check - restoring focus")
        # Add a longer delay before restoring focus
        QTimer.singleShot(250, lambda: delayed_focus_restore(window))

def improved_delayed_focus_restore(window):
    """Improved version of delayed focus restoration with additional dialog checking"""
    global SUPPRESS_FOCUS_CHECKS
    
    # Double-check for dialogs before actually restoring focus
    if SUPPRESS_FOCUS_CHECKS:
        logging.debug("Not restoring focus - suppression active")
        return
        
    # Check again for any visible dialogs
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog) or isinstance(widget, QMessageBox) or widget.inherits("QDialog"):
            if widget.isVisible():
                # Dialog found - don't restore focus
                global_suppress_focus_checks(True)
                logging.debug("Not restoring focus - dialog visible")
                return
    
    # Also check for modal dialogs
    for widget in QApplication.topLevelWidgets():
        if hasattr(widget, 'isModal') and widget.isModal() and widget.isVisible():
            global_suppress_focus_checks(True)
            logging.debug("Not restoring focus - modal dialog active")
            return
    
    # Additional safety check for focus - ensure we're not stealing focus from a legitimate app
    focused_widget = QApplication.focusWidget()
    if focused_widget and not window.isAncestorOf(focused_widget):
        # Check if the focused widget is part of a dialog
        parent = focused_widget
        while parent:
            if isinstance(parent, QDialog) or isinstance(parent, QMessageBox):
                # Dialog found - don't restore focus
                global_suppress_focus_checks(True)
                logging.debug("Not restoring focus - dialog has focus")
                return
            if hasattr(parent, 'parent'):
                parent = parent.parent()
            else:
                break
    
    logging.debug("Improved delayed focus restore - activating window")
    window.activateWindow()
    window.raise_()  
         
def setup_global_emergency_exit():
    """Set up a global keyboard hook specifically for emergency exit"""
    try:
        # Register a direct keyboard hook for Ctrl+Shift+E
        keyboard.add_hotkey('ctrl+shift+e', force_emergency_exit, suppress=False)
        logging.info("Global emergency exit hotkey registered successfully")
    except Exception as e:
        logging.error(f"Failed to register global emergency exit hotkey: {e}")

def force_emergency_exit():
    """Force exit the application from global keyboard hook"""
    logging.info("GLOBAL EMERGENCY EXIT triggered via keyboard hook")
    
    # Write to emergency log
    try:
        with open("emergency_exit.log", "w") as f:
            import datetime
            f.write(f"Global emergency exit triggered at {datetime.datetime.now()}")
    except:
        pass
    
    # Force immediate termination
    import os
    os._exit(0)

# -----------------------------------------------------------------------------
# Key Blocking
# -----------------------------------------------------------------------------
def block_system_keys():
    """Block system keys using multiple methods to ensure effectiveness"""
    try:
        logging.info("Initializing enhanced key blocking system")
        
        # Create a global whitelist for allowed keyboard actions
        global ALLOWED_KEYS
        ALLOWED_KEYS = {
            'enter',          # Allow enter key for form submission
            'return',         # Some systems detect return key differently
            'space',          # Allow space for UI interactions
            'up', 'down', 'left', 'right',  # Allow arrow keys for navigation
            'backspace',      # Allow editing in form fields
            'delete',         # Allow editing in form fields
            'shift',          # Allow shift for text input
        }
        
        # Allow common alphanumeric keys for text entry
        for char in 'abcdefghijklmnopqrstuvwxyz0123456789':
            ALLOWED_KEYS.add(char)
        
        # Method 1: Using direct key blocking for specific system keys
        for key in ['f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12']:
            keyboard.block_key(key)
            # Also create an explicit suppressed hotkey for each function key
            keyboard.add_hotkey(key, lambda k=key: logging.info(f"Blocked {k} via hotkey"), suppress=True)
            logging.info(f"Blocking {key}")
        
        # Block Windows keys
        keyboard.block_key('left windows')
        keyboard.block_key('right windows')
        logging.info("Blocking Windows keys")
        
        # Block escape key
        keyboard.block_key('esc')
        logging.info("Blocking 'esc' key")
        
        # Block alt key to prevent alt+tab
        keyboard.block_key('alt')
        logging.info("Blocking 'alt' key")
        
        # Block tab key to prevent tab switching
        keyboard.block_key('tab')
        logging.info("Blocking 'tab' key")
        
        # Block additional keys that might be problematic
        keyboard.block_key('print screen')
        logging.info("Blocking 'print screen' key")
        
        # Method 2: Using hotkeys for more complex combinations
        combinations = [
            'alt+tab', 'alt+f4', 'ctrl+alt+del', 'ctrl+shift+esc',  # System combinations
            'ctrl+f1', 'ctrl+f2', 'ctrl+f3', 'ctrl+f4', 'ctrl+f5',  # Ctrl + function keys
            'ctrl+f6', 'ctrl+f7', 'ctrl+f8', 'ctrl+f9', 'ctrl+f10', 'ctrl+f11', 'ctrl+f12',
            'alt+f1', 'alt+f2', 'alt+f3', 'alt+f4', 'alt+f5',       # Alt + function keys
            'alt+f6', 'alt+f7', 'alt+f8', 'alt+f9', 'alt+f10', 'alt+f11', 'alt+f12',
            'ctrl+tab', 'ctrl+w', 'ctrl+q',                         # Browser/application controls
            'ctrl+esc', 'win+d', 'win+e', 'win+r',                  # System shortcuts
        ]
        
        for combo in combinations:
            # Using a more robust approach for hotkeys
            keyboard.add_hotkey(combo, lambda c=combo: logging.info(f"Blocked combination {c}"), suppress=True)
            logging.info(f"Blocking combination {combo}")
        
        # Method 3: Global keyboard hook as a failsafe
        # This is the most comprehensive approach as it intercepts ALL keyboard events
        def keyboard_hook_handler(event):
            """Handle keyboard events from the global hook"""
            # For key down events, check if it's a key we want to block
            if event.event_type == keyboard.KEY_DOWN:
                key_name = event.name.lower() if event.name else ""
                
                # Emergency override for exam submission (Ctrl+Shift+E)
                if keyboard.is_pressed('ctrl') and keyboard.is_pressed('shift') and key_name == 'e':
                    logging.info("Emergency submit key combination detected - allowing")
                    return True  # Allow the event to pass through
                
                # Check if the key is in our whitelist - if so, allow it
                if key_name in ALLOWED_KEYS:
                    return True  # Allow the event
                
                # Comprehensive list of keys to block
                blocked_keys = [
                    'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
                    'esc', 'tab', 'win', 'print screen', 'menu',
                    # Include the actual scan codes for function keys as some systems report them differently
                    '112', '113', '114', '115', '116', '117', '118', '119', '120', '121', '122', '123',
                ]
                
                # Check if our key is in the blocked list
                for blocked_key in blocked_keys:
                    if blocked_key in key_name or blocked_key == str(event.scan_code):
                        logging.info(f"Blocked key {key_name} (scan code: {event.scan_code}) via global hook")
                        return False  # Block the event
                
                # Also block if any modifiers are held with certain keys
                if keyboard.is_pressed('alt') or keyboard.is_pressed('win'):
                    sensitive_keys = ['tab', 'esc', 'd', 'e', 'r', 'q', 'w']
                    for sensitive_key in sensitive_keys:
                        if sensitive_key in key_name:
                            logging.info(f"Blocked modifier+{key_name} via global hook")
                            return False  # Block the event
                
                # Allow Ctrl key combinations that are not explicitly blocked
                # This enables common interactions like Ctrl+A (select all), Ctrl+C (copy), etc.
                if keyboard.is_pressed('ctrl') and key_name not in ['tab', 'esc', 'w', 'q']:
                    return True
            
            # For all other events, allow them to pass through
            return True
        
        # Register our global hook with suppression enabled
        keyboard.hook(keyboard_hook_handler, suppress=True)
        logging.info("Global keyboard hook established with whitelist and emergency override")
            
    except Exception as e:
        logging.error(f"Error in key blocking system: {e}")
        raise

def prevent_window_minimization():
    """Additional measures to prevent window minimization"""
    try:
        # Block Win+D (show desktop)
        keyboard.add_hotkey('win+d', lambda: None, suppress=True)
        
        # Block Win+M (minimize all)
        keyboard.add_hotkey('win+m', lambda: None, suppress=True)
        
        logging.info("Added minimization prevention measures")
    except Exception as e:
        logging.error(f"Error setting up minimization prevention: {e}")

def start_key_blocking():
    """Start key blocking in a separate thread with robust error handling"""
    logging.info("Starting key blocking system")
    
    def blocking_worker():
        try:
            block_system_keys()
            prevent_window_minimization()
            logging.info("Key blocking system successfully initialized")
            
            # Keep the thread alive and checking
            while True:
                # Periodically check if our hooks are still active
                # This helps catch and fix any hooks that might have been bypassed
                import time
                time.sleep(5)
                
        except Exception as e:
            logging.error(f"Critical error in key blocking thread: {e}")
            # Try to recover
            try:
                logging.info("Attempting to recover key blocking...")
                block_system_keys()
            except:
                logging.error("Recovery attempt failed")
    
    # Start in a daemon thread so it automatically terminates when the main program exits
    blocking_thread = threading.Thread(target=blocking_worker, daemon=True)
    blocking_thread.start()
    return blocking_thread
def patched_eventFilter(self, obj, event):
    """Fixed event filter that prevents focus wars with dialogs"""
    global SUPPRESS_FOCUS_CHECKS
    
    # Ignore WindowDeactivate events during dialog interaction
    if event.type() == QEvent.Type.WindowDeactivate:
        # Check if this is our main window being deactivated
        if obj is self:
            # If we're in a dialog interaction, don't try to reactivate
            if SUPPRESS_FOCUS_CHECKS:
                logging.debug("Window deactivate during dialog - allowing")
                return super(MainWindow, self).eventFilter(obj, event)
                
            # Check if deactivation is due to a dialog opening
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QDialog) or isinstance(widget, QMessageBox) or widget.inherits("QDialog"):
                    if widget.isVisible():
                        global_suppress_focus_checks(True)
                        logging.debug("Window deactivate due to dialog - allowing")
                        return super(MainWindow, self).eventFilter(obj, event)
                
                # Also check for modal dialogs
                if hasattr(widget, 'isModal') and widget.isModal() and widget.isVisible():
                    global_suppress_focus_checks(True)
                    logging.debug("Window deactivate due to modal dialog - allowing")
                    return super(MainWindow, self).eventFilter(obj, event)
            
            # No dialog detected, schedule focus restore with a delay
            logging.debug("Window deactivate event - scheduling delayed re-activation")
            QTimer.singleShot(300, self.delayed_focus_restore)
    
    # Handle key events as before
    elif event.type() == QEvent.Type.KeyPress:
        key = event.key()
        modifiers = event.modifiers()
        
        # Enhanced detection for emergency exit
        is_ctrl = modifiers & Qt.KeyboardModifier.ControlModifier
        is_shift = modifiers & Qt.KeyboardModifier.ShiftModifier
        is_e_key = key == Qt.Key.Key_E
        
        # Check for emergency exit combination
        if is_ctrl and is_shift and is_e_key:
            logging.info("EMERGENCY EXIT combination detected in filter!")
            # Try triggering the emergency submit function
            self.trigger_emergency_submit()
            # If we somehow get here, force exit
            import os
            os._exit(0)
            return True  # Handled
            
        # Allow Ctrl+Shift+E for emergency submit
        if (key == Qt.Key.Key_E and 
            modifiers & Qt.KeyboardModifier.ControlModifier and 
            modifiers & Qt.KeyboardModifier.ShiftModifier):
            logging.info("Emergency submit key combination detected in Qt event filter")
            # Don't block this event
            return False
        
        # Allow regular keys needed for form input and UI interaction
        if ((key >= Qt.Key.Key_A and key <= Qt.Key.Key_Z) or  # Letters
            (key >= Qt.Key.Key_0 and key <= Qt.Key.Key_9) or  # Numbers
            key == Qt.Key.Key_Space or                        # Space
            key == Qt.Key.Key_Return or                      # Enter/Return
            key == Qt.Key.Key_Backspace or                   # Backspace
            key == Qt.Key.Key_Delete or                      # Delete
            (key >= Qt.Key.Key_Left and key <= Qt.Key.Key_Down)):  # Arrow keys
            return False  # Don't block these keys
            
        # Allow Escape key in dialogs
        if key == Qt.Key.Key_Escape and SUPPRESS_FOCUS_CHECKS:
            return False  # Don't block Escape in dialogs
            
        # Comprehensive blocking of problematic keys
        # Block function keys
        if key >= Qt.Key.Key_F1 and key <= Qt.Key.Key_F12:
            logging.info(f"Blocked function key {key - Qt.Key.Key_F1 + 1} through Qt event filter")
            return True  # Block the event
            
        # Block Escape outside of dialogs
        if key == Qt.Key.Key_Escape and not SUPPRESS_FOCUS_CHECKS:
            logging.info("Blocked Escape through Qt event filter")
            return True
            
        # Block Tab
        if key == Qt.Key.Key_Tab:
            logging.info("Blocked Tab through Qt event filter")
            return True
            
        # Block Alt modifiers
        if modifiers & Qt.KeyboardModifier.AltModifier:
            logging.info("Blocked Alt combination through Qt event filter")
            return True
            
        # Block Windows key combinations
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            logging.info("Blocked Windows key combination through Qt event filter")
            return True
            
    return super(MainWindow, self).eventFilter(obj, event)
# -----------------------------------------------------------------------------
# API Integration: Login API
# -----------------------------------------------------------------------------
SESSION_TOKEN = None

def login_api(exam_code):
    url = "https://stageevaluate.sentientgeeks.us/wp-json/api/v1/login"
    payload = {"exam_link": exam_code}
    headers = {"Content-Type": "application/json"}

    try:
        logging.debug(f"🔹 Sending POST request to {url} with payload: {payload}")
        response = requests.post(url, json=payload, headers=headers)
        logging.debug(f"📡 Response Status Code: {response.status_code}")
        logging.debug(f"📜 Response Content: {response.text}")

        if response.status_code == 200:
            global SESSION_TOKEN
            SESSION_TOKEN = response.json().get("token", "")
            if SESSION_TOKEN.startswith("Bearer "):
                SESSION_TOKEN = SESSION_TOKEN.replace("Bearer ", "")
            if SESSION_TOKEN:
                print(f"\n✅ Token Generated: {SESSION_TOKEN}")
                return SESSION_TOKEN
            else:
                print("\n❌ Token not found in response")
        else:
            print(f"\n❌ Login failed with status code {response.status_code}")
    except requests.exceptions.RequestException as e:
        logging.error(f"⚠️ Error hitting the API: {e}")
    return None

def get_exam_details(token, exam_code=None):
    url = "https://stageevaluate.sentientgeeks.us/wp-json/api/v1/get-exam-details"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {"exam_link": exam_code} if exam_code else {}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        logging.debug(f"Response Status Code: {response.status_code}")
        logging.debug(f"Response Content: {response.text}")
        response_json = response.json()
        if response.status_code == 200 or ('message' in response_json and 'remaining_time' in response_json):
            print("\n✅ Exam Details:", response_json)
            return response_json
        else:
            print(f"\n❌ Failed to fetch exam details. Status Code: {response.status_code}")
            print("Response JSON:", response_json)
            return response_json
    except requests.exceptions.RequestException as e:
        logging.error(f"API Request Exception: {e}")
        print("\n⚠️ Error calling exam details API:", e)
        return None

def fetch_question(question_id, exam_id, user_id, idx, first_request=False):
    url = "https://stageevaluate.sentientgeeks.us/wp-json/api/v1/get-question-from-id"
    payload = {
        "question_id": str(question_id),
        "exam_id": str(exam_id),
        "user_id": str(user_id),
        "idx": idx,
        "first_request": first_request
    }
    headers = {
        "Authorization": f"Bearer {SESSION_TOKEN}",  # <-- Check if SESSION_TOKEN is VALID and not expired
        "Content-Type": "application/json"
    }

    try:
        logging.info(f"[fetch_question] Sending request: {payload}")
        response = requests.post(url, json=payload, headers=headers)
        logging.info(f"[fetch_question] Status Code: {response.status_code}")

        if response.status_code != 200:
            logging.error(f"[fetch_question] Failed with status: {response.status_code}")
            return None

        data = response.json()
        logging.debug(f"[fetch_question] Full JSON Response: {data}")

        if data.get("status") is True and data.get("question_id"):
            logging.info(f"[fetch_question] Successfully fetched question ID {data['question_id']}")
            return data
        else:
            logging.warning(f"[fetch_question] No valid question returned for ID {question_id}")
            return None

    except Exception as e:
        logging.exception(f"[fetch_question] Exception: {e}")
        return None



def save_question_answer(exam_id, user_id, question_id, question_type, answer, SESSION_TOKEN):
    """
    Save a question answer to the API.
    
    Args:
        exam_id (str): The ID of the exam
        user_id (str): The ID of the user
        question_id (str): The ID of the question
        question_type (str): The type of question (1, 2, 3, or 4)
        answer: The user's answer (format depends on question type)
        session_token (str): The authentication token
        
    Returns:
        dict: The API response as a dictionary, or None if the request failed
    """
    try:
        import json  # Make sure to import json
        import requests  # Make sure requests is imported
        
        # Debug information
        print(f"DEBUG - Saving answer with parameters:")
        print(f"  exam_id: {exam_id}")
        print(f"  user_id: {user_id}")
        print(f"  question_id: {question_id}")
        print(f"  question_type: {question_type}")
        print(f"  raw answer: {answer}")
        
        # Validation check - ensure question_id is not empty
        if not question_id:
            print("ERROR: question_id is empty or None")
            return None
            
        # Format the answer based on question type
        formatted_answer = format_answer_for_api(question_type, answer)
        print(f"  formatted answer: {formatted_answer}")
        
        # Prepare the payload - simplified to use consistent naming
        payload = {
            "exam_id": exam_id,
            "user_id": user_id,
            "question_id": question_id,
            "question_type": question_type,
            "provided_answer": formatted_answer
        }
        
        headers = {
            "Authorization": f"Bearer {SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
        
        print(f"DEBUG - API Payload: {payload}")
        
        # Make the API request
        response = requests.post(
            "https://stageevaluate.sentientgeeks.us/wp-json/api/v1/save-question-answer",
            json=payload,
            headers=headers
        )
        
        # Check if request was successful
        if response.status_code in (200, 201):
            print(f"Successfully saved answer for question {question_id}")
            print(f"Response: {response.json()}")
            return response.json()
        else:
            print(f"Failed to save answer for question {question_id}")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error saving answer for question {question_id}: {str(e)}")
        print(f"Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()  # Print full stack trace for debugging
        return None
        

def format_answer_for_api(question_type, answer):
    """
    Format the answer based on question type for API submission.
    
    Args:
        question_type (str): The type of question ("1", "2", "3", or "4")
        answer: The user's answer in the internal format
        
    Returns:
        The formatted answer ready for API submission
    """
    if answer is None:
        print("WARNING: Answer is None, returning empty string")
        return ""
        
    if question_type == "1":  # Descriptive
        # Just send the text as is
        return answer
        
    elif question_type == "2":  # MCQ
        # Send the selected option index
        # Ensure the answer is a string as some APIs expect string values
        return str(answer)
        
    elif question_type == "3":  # MSQ
        # Convert to comma-separated string of selected indices
        if isinstance(answer, list) and len(answer) > 0:
            return ",".join(str(idx) for idx in answer)
        return ""
        
    elif question_type == "4":  # Coding
        # Handle coding questions - answer is a tuple of (code, language)
        if answer is not None:
            code, language = answer
            # Format as: language>code
            return f"{language}>{code}"
        return ""
    
    # Default case
    return str(answer) if answer is not None else ""

# -----------------------------------------------------------------------------
# System Check Functions
# -----------------------------------------------------------------------------
def check_audio():
    duration = 0.5
    fs = 44100
    try:
        default_output = sd.default.device[1]
        device_info = sd.query_devices(default_output)
        hostapi_info = sd.query_hostapis()[device_info['hostapi']]
        print(f"Using device: {device_info['name']} ({device_info['hostapi']})")
        if "WASAPI" in hostapi_info['name']:
            print("Using WASAPI Loopback for audio check.")
            recording = sd.rec(
                int(duration * fs),
                samplerate=fs,
                channels=1,
                dtype='float32',
                device=default_output,
                blocking=True,
                extra_settings=sd.WasapiSettings(loopback=True)
            )
        else:
            print("WASAPI Loopback not available, using microphone instead.")
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float32')
            sd.wait()
        amplitude = np.max(np.abs(recording))
        print(f"Detected audio amplitude: {amplitude}")
        result = "Failed" if amplitude > 0.05 else "OK"
        logging.info(f"Audio check result: {result} (amplitude={amplitude})")
        return result
    except Exception as e:
        logging.error(f"Audio check error: {e}")
        print(f"Audio check failed: {e}")
        return "Failed"

def check_video():
    """
    Enhanced version of check_video that also verifies a face is visible.
    """
    # First check if camera exists
    available = QMediaDevices.videoInputs()
    if not available:
        logging.info("Video check failed: No cameras detected")
        return "Failed (No camera detected)"
        
    # Then check if a face is visible
    face_result = check_face_visible()
    if face_result != "OK":
        return face_result
        
    # All checks passed
    return "OK"

def check_face_visible():
    """
    Checks if a face is visible in the camera feed.
    Returns "OK" if a face is detected, otherwise returns a failure message.
    
    Requirements:
    - OpenCV (cv2) library
    - A working camera
    """
    try:
        import cv2
        import numpy as np
        import logging
        import os
        import sys
        
        logging.info("Starting face detection check...")
        
        # Initialize the camera (default camera index 0)
        cap = cv2.VideoCapture(0)
        
        # Check if camera opened successfully
        if not cap.isOpened():
            logging.error("Failed to open camera for face detection")
            return "Failed (Cannot access camera)"
        
        # Set a timeout for face detection (3 seconds)
        max_attempts = 30  # At 10 FPS = 3 seconds
        attempts = 0
        face_detected = False
        
        # Load the face detector - determine correct path for both dev and packaged environments
        try:
            # Get the base directory for resources
            if getattr(sys, 'frozen', False):
                # If the application is running as a bundled executable
                base_dir = sys._MEIPASS
            else:
                # If running in a normal Python environment
                base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Try multiple possible cascade file locations
            cascade_paths = [
                os.path.join(base_dir, 'haarcascade_frontalface_default.xml'),  # Bundled with executable
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'   # Standard OpenCV location
            ]
            
            face_cascade = None
            for cascade_path in cascade_paths:
                logging.info(f"Trying cascade file at: {cascade_path}")
                if os.path.exists(cascade_path):
                    logging.info(f"Found cascade file at: {cascade_path}")
                    face_cascade = cv2.CascadeClassifier(cascade_path)
                    if not face_cascade.empty():
                        logging.info("Face cascade classifier loaded successfully")
                        break
            
            if face_cascade is None or face_cascade.empty():
                logging.error("Failed to load face cascade classifier from any location")
                cap.release()
                return "Failed (Face detection model not found)"
                
        except Exception as e:
            logging.error(f"Failed to load face cascade classifier: {str(e)}")
            cap.release()
            return f"Failed (Cannot load face detection model: {str(e)})"
        
        # Try to detect a face with multiple attempts
        while attempts < max_attempts and not face_detected:
            # Capture frame
            ret, frame = cap.read()
            if not ret:
                logging.error("Failed to capture frame from camera")
                break
                
            # Convert to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            # Check if any faces are detected
            if len(faces) > 0:
                face_detected = True
                logging.info(f"Face detected! Found {len(faces)} face(s)")
                
                # Log face dimensions and position for debugging
                for (x, y, w, h) in faces:
                    logging.info(f"Face at position: x={x}, y={y}, width={w}, height={h}")
                break
                
            attempts += 1
            
        # Release the camera
        cap.release()
        
        # Return result based on face detection
        if face_detected:
            return "OK"
        else:
            logging.warning("No face detected in camera feed")
            return "Failed (No face detected in camera feed)"
            
    except ImportError:
        logging.error("OpenCV (cv2) library not installed")
        return "Failed (OpenCV library not installed)"
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Face detection error: {error_msg}")
        return f"Failed (Face detection error: {error_msg})"

def check_screen_sharing():
    """
    Comprehensively checks for screen sharing and remote access applications.
    Returns "OK" if none found, otherwise returns a list of detected applications.
    """
    # Extensive list of screen sharing, remote access, and meeting applications
    known_apps = {
        # Video conferencing apps
        "zoom": ["zoom.exe", "zoomingapp.exe", "zoomus.exe", "zoomoutlookplugin.exe"],
        "skype": ["skype.exe", "skypeapp.exe", "skypehost.exe"],
        "webex": ["webex.exe", "webexmta.exe", "webexstart.exe"],
        # "teams": ["teams.exe", "microsoft teams.exe"],
        "meet": ["googlemeet.exe", "meet.google.exe"],
        "gotomeeting": ["gotomeeting.exe", "g2m.exe", "g2mcomm.exe", "g2mlauncher.exe"],
        "bluejeans": ["bluejeans.exe", "bluejeans-v2.exe"],
        "slack": ["slack.exe"],
        "discord": ["discord.exe", "discordptb.exe", "discordcanary.exe"],
        
        # Remote access apps
        "anydesk": ["anydesk.exe"],
        "teamviewer": ["teamviewer.exe", "tv_w32.exe", "tv_x64.exe"],
        "vnc": ["vncserver.exe", "vncviewer.exe", "vncagent.exe", "vncserverui.exe", "uvnc_service.exe", "winvnc.exe"],
        "remotedesktop": ["mstsc.exe", "rdpclip.exe", "rdpshell.exe"],
        "logmein": ["logmein.exe", "lmiignition.exe"],
        "splashtop": ["splashtop.exe", "splashtopremotemirror.exe", "splashtopservice.exe"],
        "parsec": ["parsec.exe", "parsecd.exe"],
        "ammyy": ["ammyy.exe", "ammyyadmin.exe"],
        "supremo": ["supremo.exe"],
        "aeroadmin": ["aeroadmin.exe"],
        "chromerdp": ["chromeremotedesktophost.exe"],
        "screenconnect": ["screenconnect.windowsclient.exe", "connectwisecontrol.exe"],
        "showmypc": ["showmypc.exe"],
        "zoho": ["zohoassist.exe", "zohoassistservice.exe"],
        "ultraviewer": ["ultraviewer.exe", "ultraviewerservice.exe"],
        "rustdesk": ["rustdesk.exe"],
        "dwservice": ["dwagent.exe", "dwagsvc.exe"],
        "remotepc": ["remotepc.exe"],
        "litemanager": ["litemanager.exe"]
    }
    
    # For non-Windows platforms
    if platform.system().lower() != "windows":
        # Convert to lowercase strings without .exe extension for other platforms
        non_windows_apps = {}
        for app_name, app_list in known_apps.items():
            non_windows_apps[app_name] = [app.replace('.exe', '').lower() for app in app_list]
            # Add some additional Unix/Mac variants
            if app_name == "zoom":
                non_windows_apps[app_name].extend(["zoom", "zoomus", "zoomingapp"])
            elif app_name == "vnc":
                non_windows_apps[app_name].extend(["vnc", "x11vnc", "tigervnc", "tightvnc", "realvnc"])
        known_apps = non_windows_apps
    
    detected_apps = []
    
    # Check running processes
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            proc_name = proc.info['name'].lower() if proc.info['name'] else ""
            proc_cmdline = " ".join(proc.info['cmdline']).lower() if proc.info['cmdline'] else ""
            
            # Check against our known apps dictionary with exact matching
            for app_name, app_identifiers in known_apps.items():
                # Exact process name matching
                if proc_name in app_identifiers:
                    full_name = f"{proc_name} ({app_name})"
                    if full_name not in detected_apps:
                        detected_apps.append(full_name)
                    continue
                
                # For Windows, check if proc_name matches exactly any of the identifiers
                if platform.system().lower() == "windows":
                    if any(proc_name == identifier.lower() for identifier in app_identifiers):
                        full_name = f"{proc_name} ({app_name})"
                        if full_name not in detected_apps:
                            detected_apps.append(full_name)
                        continue
                
                # Only do substring matching on command line, not on process name
                # This prevents false positives like code.exe matching "zoom"
                if any(f"{identifier.lower()} " in f" {proc_cmdline} " for identifier in app_identifiers):
                    full_name = f"{proc_name} ({app_name})"
                    if full_name not in detected_apps:
                        detected_apps.append(full_name)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    # No installation directory checks - only looking for active processes
    
    # Additional OS-specific checks
    system = platform.system().lower()
    
    if system == "windows":
        # Check Windows services related to remote access
        try:
            # Get list of running services
            service_output = subprocess.check_output("sc query state= running", shell=True).decode('utf-8', errors='ignore')
            remote_services = [
                "TermService",  # Windows Remote Desktop
                "uvnc_service", # UltraVNC
                "winvnc",       # TightVNC service
                "vncserver",    # RealVNC service
                "TeamViewer",   # TeamViewer
                "AnyDesk",      # AnyDesk
                "LogMeIn",      # LogMeIn
                "Splashtop"     # Splashtop
            ]
            
            for service in remote_services:
                if re.search(fr"SERVICE_NAME:\s+{service}", service_output, re.IGNORECASE):
                    service_name = f"{service} (service)"
                    if service_name not in detected_apps:
                        detected_apps.append(service_name)
        except (subprocess.SubprocessError, FileNotFoundError):
            logging.warning("Failed to check Windows services")
    
    elif system == "darwin":  # macOS
        try:
            # Check for macOS-specific screen sharing
            apple_services = [
                ("ScreensharingAgent", "Apple Screen Sharing"),
                ("screensharing", "Apple Screen Sharing"),
                ("AppleVNCServer", "Apple VNC Server"),
                ("RemoteManagement", "Apple Remote Management")
            ]
            
            ps_output = subprocess.check_output("ps -ax", shell=True).decode('utf-8', errors='ignore').lower()
            
            for process_name, display_name in apple_services:
                if process_name.lower() in ps_output:
                    if display_name not in detected_apps:
                        detected_apps.append(display_name)
        except (subprocess.SubprocessError, FileNotFoundError):
            logging.warning("Failed to check macOS screen sharing processes")
    
    elif system == "linux":
        try:
            # Check for X11 forwarding and VNC
            x11_output = subprocess.check_output("ps -ef | grep -E 'x11vnc|x11forwarding|vino-server'", 
                                               shell=True).decode('utf-8', errors='ignore')
            
            if "x11vnc" in x11_output and "grep" not in x11_output:
                detected_apps.append("X11VNC")
            if "vino-server" in x11_output and "grep" not in x11_output:
                detected_apps.append("Vino VNC Server")
        except (subprocess.SubprocessError, FileNotFoundError):
            logging.warning("Failed to check Linux screen sharing processes")
    
    # Check for active network connections to common remote access ports
    try:
        if system == "windows":
            netstat_cmd = "netstat -ano"
        else:
            netstat_cmd = "netstat -tunap"
            
        netstat_output = subprocess.check_output(netstat_cmd, shell=True).decode('utf-8', errors='ignore')
        
        # Common remote access ports
        remote_ports = {
            "3389": "RDP",
            "5900-5910": "VNC",
            "5931": "TeamViewer",
            "7070": "AnyDesk",
            "8834": "LogMeIn",
            "5938": "TeamViewer",
            "5950": "Splashtop"
        }
        
        for port_range, app_name in remote_ports.items():
            # Handle port ranges like 5900-5910
            if "-" in port_range:
                start, end = port_range.split("-")
                port_pattern = "|".join([str(p) for p in range(int(start), int(end)+1)])
            else:
                port_pattern = port_range
                
            pattern = rf"[:.]({port_pattern})\b"
            if re.search(pattern, netstat_output):
                connection_info = f"{app_name} (port {port_range})"
                if connection_info not in detected_apps:
                    detected_apps.append(connection_info)
    except (subprocess.SubprocessError, FileNotFoundError):
        logging.warning("Failed to check network ports")
    
    # Log and return results
    if detected_apps:
        app_names = ", ".join(detected_apps)
        logging.warning(f"Screen sharing check failed: {app_names} detected")
        return f"Failed (Found: {app_names})"
    else:
        logging.info("Screen sharing check: OK")
        return "OK"


def check_monitor():
    screens = len(QApplication.screens())
    if screens == 1:
        return "OK"
    else:
        logging.info(f"Monitor check failed: {screens} monitors detected")
        return f"Failed ({screens} monitors detected)"

# -----------------------------------------------------------------------------
# Dialogs & Pages
# -----------------------------------------------------------------------------

# 1. Exam Code Page
class ExamCodePage(QWidget):
    def __init__(self, switch_to_system_check_callback):
        super().__init__()
        self.switch_to_system_check_callback = switch_to_system_check_callback
        self.setup_ui()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main

        # ------------------ Left Form Column ------------------ #
        form_widget = QWidget()
        form_widget.setStyleSheet("background-color: white;")
        form_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        form_layout = QVBoxLayout(form_widget)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.setContentsMargins(40, 40, 40, 40) 
        form_layout.setSpacing(10)

        # Welcome label
        welcome_label = QLabel("Welcome to Evaluate")
        welcome_label.setStyleSheet("color: #00205b;")
        welcome_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        form_layout.addWidget(welcome_label)

        # Title label
        title_label = QLabel("Enter Exam Code")
        title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Medium))
        title_label.setStyleSheet("color: #444; margin-top: 0px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        form_layout.addWidget(title_label)

        # Exam code input
        self.exam_code_edit = QLineEdit()
        self.exam_code_edit.setPlaceholderText("Enter Code Here...")
        self.exam_code_edit.setFont(QFont("Segoe UI", 16, QFont.Weight.Medium))
        self.exam_code_edit.setMinimumHeight(45)
        self.exam_code_edit.setStyleSheet("""
            QLineEdit {
                padding: 7px 15px;
                border: 1px solid #ccc;
                border-radius: 10px;
                background-color: #f9f9f9;
            }
            QLineEdit:focus {
                border-color: #00205b;
                background-color: #ffffff;
            }
        """)
        form_layout.addWidget(self.exam_code_edit)

        # Submit button
        submit_button = QPushButton("Submit")
        submit_button.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        submit_button.setMinimumHeight(40)
        submit_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        submit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        submit_button.setStyleSheet("""
            QPushButton {
                background-color: #00205b;
                color: white;
                border-radius: 12px;
                padding: 11px 0px;
            }
            QPushButton:hover {
                background-color: #001a4f;
            }
        """)

        # Optional: Add a drop shadow to button
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 120))
        submit_button.setGraphicsEffect(shadow)

        submit_button.clicked.connect(self.handle_exam_code)
        form_layout.addWidget(submit_button)
        main_layout.addWidget(form_widget, stretch=1)  # Left column takes 1 part of space

        logo_widget = QWidget()
        logo_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        logo_layout = QVBoxLayout(logo_widget)
        logo_layout.setContentsMargins(0, 0, 0, 0)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        screen = QApplication.primaryScreen()
        screen_size = screen.size()
        logo_width = int(screen_size.width() * 0.6)
        logo_height = int(screen_size.height() * 1)
        pixmap = QPixmap(resource_path("login.jpg"))
        if not pixmap.isNull():
            # Calculate aspect ratio preserving scale and crop center (object-fit: cover)
            label_ratio = logo_width / logo_height
            pixmap_ratio = pixmap.width() / pixmap.height()

            if pixmap_ratio > label_ratio:
                # Pixmap is wider, scale by height and crop width
                scaled_pixmap = pixmap.scaledToHeight(logo_height, Qt.TransformationMode.SmoothTransformation)
                x_offset = int((scaled_pixmap.width() - logo_width) / 2)
                cropped_pixmap = scaled_pixmap.copy(x_offset, 0, logo_width, logo_height)
            else:
                # Pixmap is taller, scale by width and crop height
                scaled_pixmap = pixmap.scaledToWidth(logo_width, Qt.TransformationMode.SmoothTransformation)
                y_offset = int((scaled_pixmap.height() - logo_height) / 2)
                cropped_pixmap = scaled_pixmap.copy(0, y_offset, logo_width, logo_height)

            logo_label.setPixmap(cropped_pixmap)
        else:
            logo_label.setText("Logo")
            logo_label.setFont(QFont("Cinzel", 20, QFont.Weight.Bold))
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_layout.addWidget(logo_label)

        main_layout.addWidget(logo_widget, stretch=1)  

    def handle_exam_code(self):
        exam_code = self.exam_code_edit.text().strip()
        if exam_code:
            token = login_api(exam_code)
            if token:
                print("\n✅ Token generated:", token)
                logging.info(f"Exam code entered and login successful: {exam_code}")
                exam_details = get_exam_details(token, exam_code)
                if exam_details:
                    print("\n✅ Exam Details received in ExamCodePage:", exam_details)
                    self.switch_to_system_check_callback(exam_code, token, exam_details)
                else:
                    print("\n❌ Exam details API call failed.")
            else:
                logging.warning("❌ Login failed. Please check your exam code or your network connection.")
        else:
            logging.warning("⚠️ Exam code cannot be empty.")

# 2. System Check Page
class SystemCheckPage(QWidget):
    def __init__(self, switch_to_instructions_callback):
        super().__init__()
        self.switch_to_instructions_callback = switch_to_instructions_callback
        self.exam_details = None
        self.check_counter = 0
        self.checks_completed = False
        self.setup_ui()
        
    def set_exam_details(self, exam_details):
        self.exam_details = exam_details
        print("\n✅ Exam Details in SystemCheckPage:", self.exam_details)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(20, 20, 20, 20)

        # Outer container
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 30, 20, 20) 
        container_layout.setSpacing(8)
        container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 15px;
            }
        """)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(container)

        # Header
        header = QLabel("System & Device Checks")
        header.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        header.setFixedHeight(65)
        header.setStyleSheet("QLabel { text-decoration: underline; margin: 0; color: #00205b;  }")
        header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        container_layout.addWidget(header)

        # 2-column grid layout for status boxes
        grid_layout = QGridLayout()
        grid_layout.setSpacing(15)
        container_layout.addLayout(grid_layout)

        label_style = """
        QLabel {
            background-color: #f0f4ff;
            color: #0d1b57;
            border: 1px solid #c5cae9;
            border-radius: 10px;
            padding: 10px 16px;
            font-family: 'Segoe UI';
            font-size: 20px;
        }
        """

        def create_label(text):
            label = QLabel(text)
            label.setStyleSheet(label_style)
            label.setFont(QFont("Arial", 18))
            label.setFixedHeight(80)
            return label

        self.video_label = create_label("Video Check: Pending")
        self.audio_label = create_label("Audio Check: Pending")
        self.machine_label = create_label("Machine Requirement: Pending")
        self.screen_label = create_label("Screen Sharing App: Pending")
        self.funkey_label = create_label("Function Key Block: Pending")
        self.monitor_label = create_label("Monitor Check: Pending")

        # Add to grid (2 columns, 3 rows)
        grid_layout.addWidget(self.video_label, 0, 0)
        grid_layout.addWidget(self.audio_label, 0, 1)
        grid_layout.addWidget(self.machine_label, 1, 0)
        grid_layout.addWidget(self.screen_label, 1, 1)
        grid_layout.addWidget(self.funkey_label, 2, 0)
        grid_layout.addWidget(self.monitor_label, 2, 1)

        # Select Devices Button
        self.select_devices_button = QPushButton("Select Devices")
        self.select_devices_button.setFont(QFont("Arial", 18))
        self.select_devices_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #00205b;
                border: 1px solid #00205b;
                padding: 10px 20px;
                font-size: 18px;
                border-radius: 8px;
                margin-top: 20px;
            }
            QPushButton:hover {
                background-color: #00205b;
                color: white;  
                border: 1px solid #001b4f;
            }
        """)
        self.select_devices_button.clicked.connect(self.handle_select_devices)
        container_layout.addWidget(self.select_devices_button, alignment=Qt.AlignmentFlag.AlignLeft)

        # Status Message
        self.status_message = QLabel("")
        self.status_message.setFont(QFont("Arial", 18))
        self.status_message.setFixedHeight(40)
        self.status_message.setContentsMargins(0,5,0,0)
        self.status_message.setStyleSheet("QLabel { text-decoration: underline; padding-bottom: 4px; color: #00205b;  }")
        self.status_message.setAlignment(Qt.AlignmentFlag.AlignLeft)
        container_layout.addWidget(self.status_message)

        # Continue Button
        self.continue_button = QPushButton("Continue")
        self.continue_button.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.continue_button.setStyleSheet("""
            QPushButton {
                background-color: #00205b;
                color: white;
                border: 1px solid #00205b;
                padding: 10px 20px;
                font-size: 18px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #001b4f;
                color: white;
                border: 1px solid #001b4f;
            }
        """)
        self.continue_button.setEnabled(False)
        self.continue_button.clicked.connect(self.on_continue)
        container_layout.addWidget(self.continue_button, alignment=Qt.AlignmentFlag.AlignLeft)

    def start_checks(self):
        # Reset labels to "Checking..." state
        for lbl in [self.video_label, self.audio_label, self.machine_label,
                    self.screen_label, self.funkey_label, self.monitor_label]:
            lbl.setText(f"{lbl.text().split(':')[0]}: Checking...")
            
        self.status_message.setText("Running system checks...")
        self.check_counter = 0
        self.checks_completed = False
        
        # Start the check timer
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.update_checks)
        self.check_timer.start(1000)

    def update_checks(self):
        self.check_counter += 1
        if self.check_counter >= 3:
            # Only perform checks if they haven't been completed yet
            if not self.checks_completed:
                # Run all checks
                video_result = check_video()
                audio_result = check_audio()
                logging.info(f"Video check result: {video_result}")
                logging.info(f"Audio check result: {audio_result}")

                # Other checks
                machine_result = "OK"  # Always OK for this check
                screen_result = check_screen_sharing()
                funkey_result = "OK"   # Always OK for this check
                monitor_result = check_monitor()
                
                # Update the labels with results
                self.video_label.setText("Video Check: " + video_result)
                self.audio_label.setText("Audio Check: " + audio_result)
                self.machine_label.setText("Machine Requirement: " + machine_result)
                self.screen_label.setText("Screen Sharing App: " + screen_result)
                self.funkey_label.setText("Function Key Block: " + funkey_result)
                self.monitor_label.setText("Monitor Check: " + monitor_result)
                
                # Format labels for better visibility of failures
                for lbl in [self.video_label, self.audio_label, self.machine_label,
                           self.screen_label, self.funkey_label, self.monitor_label]:
                    if "Failed" in lbl.text():
                        lbl.setStyleSheet("background-color: #fef2f2;color: #dc2626;border: 1px solid #fecaca;border-radius: 10px;padding: 10px 16px;font-family: 'Segoe UI';font-size: 20px; font-weight: 500;")
                    else:
                        lbl.setStyleSheet("background-color: #f6fff9;color: #16a34a;border: 1px solid #bbf7d0;border-radius: 10px;padding: 10px 16px;font-family: 'Segoe UI';font-size: 20px; font-weight: 500;")
                
                self.checks_completed = True
                
            self.check_timer.stop()
            
            # Check if all tests passed
            failed_checks = []
            for lbl in [self.video_label, self.audio_label, self.machine_label,
                        self.screen_label, self.funkey_label, self.monitor_label]:
                if "Failed" in lbl.text():
                    failed_checks.append(lbl.text().split(':')[0])
            
            if not failed_checks:
                self.status_message.setText("All checks passed!")
                self.status_message.setStyleSheet("color: green; font-weight: bold;")
                self.continue_button.setEnabled(True)
            else:
                # Create a detailed failure message
                failed_items = ", ".join(failed_checks)
                self.status_message.setText(f"Failed checks: {failed_items}. Please fix issues and try again.")
                self.status_message.setStyleSheet("color: red;")
                self.select_devices_button.setEnabled(True)

    def handle_select_devices(self):
        # Disable the select devices button while dialog is open
        self.select_devices_button.setEnabled(False)
        
        dialog = DeviceSelectionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logging.info("Devices confirmed. Starting system checks...")
            # Start checks after device selection is confirmed
            self.start_checks()
        else:
            logging.info("Device selection cancelled.")
            self.select_devices_button.setEnabled(True)

    def on_continue(self):
        self.switch_to_instructions_callback()
        
class SharedCameraSession:
    def __init__(self):
        self.camera = None
        self.capture_session = None
        self.is_initialized = False
        
    def initialize(self, camera_device):
        if self.is_initialized:
            return True

        self.camera = QCamera(camera_device)
        self.capture_session = QMediaCaptureSession()
        self.capture_session.setCamera(self.camera)
        self.is_initialized = True
        return True
        
    def get_session(self):
        return self.capture_session
        
    def start_camera(self):
        if self.camera and self.is_initialized:
            self.camera.start()
            return True
        return False
            
    def stop_camera(self):
        if self.camera and self.is_initialized:
            self.camera.stop()
            return True
        return False

# Global shared session instance
shared_camera = SharedCameraSession()


class BackgroundWebcamRecorder:
    def __init__(self, token=None, exam_code=None, user_id=None, exam_id=None):
        self.token = token
        self.exam_code = exam_code
        self.user_id = user_id if user_id is not None else "default_user"
        self.exam_id = exam_id if exam_id is not None else "default_exam"
        self.recorder = None
        self.recording_dir = "exam_recordings"
        self.ensure_recording_dir()
        self.chunk_timer = QTimer()
        self.chunk_timer.timeout.connect(self.handle_chunk_timer)
        self.chunk_interval = 10000  # 10 seconds in milliseconds
        self.current_chunk_file = None
        self.chunk_counter = 0
        self.api_endpoint = "https://stageevaluate.sentientgeeks.us/wp-json/api/v1/save-exam-recorded-video"


    
    def ensure_recording_dir(self):
        try:
            if not os.path.exists(self.recording_dir):
                os.makedirs(self.recording_dir)

            # Test writability
            test_file = os.path.join(self.recording_dir, "test_write.txt")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            logging.info(f"Recording directory {self.recording_dir} is writable")
        except Exception as e:
            logging.error(f"Error with recording directory: {str(e)}")

    def setup_recorder(self, capture_session):
        self.recorder = QMediaRecorder()
        capture_session.setRecorder(self.recorder)
        
        # Connect error signal
        self.recorder.errorOccurred.connect(self.handle_error)
        
        # Set up the media format
        fmt = QMediaFormat()
        fmt.setFileFormat(QMediaFormat.FileFormat.MPEG4)
        fmt.setVideoCodec(QMediaFormat.VideoCodec.H264)
        
        # Add more specific settings
        self.recorder.setMediaFormat(fmt)
        self.recorder.setQuality(QMediaRecorder.Quality.HighQuality)
        self.recorder.setVideoResolution(QSize(640, 480))
        self.recorder.setVideoFrameRate(30.0)
        
        # Set up initial chunk file
        self.update_chunk_file()
        
        logging.info(f"Recorder configured with absolute path: {self.current_chunk_file}")
        return True
    
    def update_chunk_file(self):
        # Ensure we have valid user_id and exam_id values to avoid "None" in filenames
        user_id = str(self.user_id) if self.user_id is not None else "unknown"
        exam_id = str(self.exam_id) if self.exam_id is not None else "unknown"
        
        # Create the simplified filename in the format "user_id-exam_id.mp4"
        # We'll append the chunk number internally to avoid overwriting files locally
        filename = f"{user_id}-{exam_id}_{self.chunk_counter}.mp4"
        
        # Create the full path
        chunk_filepath = os.path.join(self.recording_dir, filename)
        self.current_chunk_file = os.path.abspath(chunk_filepath)
        
        # Set the output location for the recorder
        self.recorder.setOutputLocation(QUrl.fromLocalFile(self.current_chunk_file))
        
        # Log the new file path
        logging.info(f"New recording chunk will be saved as: {self.current_chunk_file}")
        
        # Increment chunk counter for next file
        self.chunk_counter += 1
    
    def handle_error(self, error, error_string):
        logging.error(f"Recorder error ({error}): {error_string}")

    def is_ready(self):
        return self.recorder is not None

    def start_recording(self):
        if self.is_ready() and self.recorder.recorderState() != QMediaRecorder.RecorderState.RecordingState:
            logging.info(f"Starting recording to: {self.recorder.outputLocation().toLocalFile()}")
            self.recorder.record()
            # Start the chunk timer
            self.chunk_timer.start(self.chunk_interval)
            logging.info(f"Recorder state after starting: {self.recorder.recorderState()}")
            logging.info(f"Recording duration: {self.recorder.duration()} ms")
            return True
        return False

    def stop_recording(self):
        if self.is_ready() and self.recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            logging.info("Stopping recording...")
            self.recorder.stop()
            # Stop the chunk timer
            self.chunk_timer.stop()
            # Upload the final chunk
            self.upload_current_chunk()
            logging.info(f"Recorder state after stopping: {self.recorder.recorderState()}")
            logging.info(f"Final recording duration: {self.recorder.duration()} ms")
            logging.info(f"Output file should be at: {self.recorder.outputLocation().toLocalFile()}")
            return True
        return False
    
    def handle_chunk_timer(self):
        # This function is called every 10 seconds
        if self.recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            # Stop current recording
            logging.info("Stopping current chunk recording...")
            self.recorder.stop()
            
            # Add a small delay to ensure file is properly finalized
            QTimer.singleShot(500, self.process_and_start_new_chunk)

    def process_and_start_new_chunk(self):
        # Upload the current chunk
        success = self.upload_current_chunk()
        logging.info(f"Upload of chunk {self.chunk_counter-1} {'succeeded' if success else 'failed'}")
        
        # Start a new chunk
        self.update_chunk_file()
        logging.info(f"Starting new chunk recording to: {self.current_chunk_file}")
        self.recorder.record()
    
    def upload_current_chunk(self):
        if not self.current_chunk_file or not os.path.exists(self.current_chunk_file):
            logging.error(f"Chunk file doesn't exist: {self.current_chunk_file}")
            return False
        
        try:
            # Log file info before upload attempt
            file_size = os.path.getsize(self.current_chunk_file)
            logging.info(f"Preparing to upload chunk: {self.current_chunk_file} (Size: {file_size} bytes)")
            
            if file_size == 0:
                logging.error("File size is 0 bytes, cannot upload empty file")
                return False
                
            # Format chunk counter with leading zeros
            chunk_number = f"chunk{(self.chunk_counter - 1):04d}"
            
            # Create file_name for the API request
            file_id = f"{self.user_id}-{self.exam_id}"
            
            # Prepare multipart form data exactly matching Postman
            with open(self.current_chunk_file, 'rb') as file_data:
                files = {
                    'exam_id': (None, str(self.exam_id)),
                    'user_id': (None, str(self.user_id)),
                    'chunk': (f"{file_id}.mp4", file_data, 'video/mp4'),  # Use proper MIME type
                    'type': (None, 'ondataavailable'),
                    'file_name': (None, file_id),
                    'chunk_number': (None, chunk_number)
                }
                
                # Set headers with token
                headers = {
                    'Authorization': f'Bearer {self.token}'
                }
                
                # Log the request details
                logging.info(f"Sending request to: {self.api_endpoint}")
                logging.info(f"Headers: {headers}")
                logging.info(f"Form data keys: {list(files.keys())}")
                
                # Send POST request
                response = requests.post(
                    self.api_endpoint,
                    files=files,
                    headers=headers
                )
            
            # Check response
            logging.info(f"Response status code: {response.status_code}")
            logging.info(f"Response content: {response.text}")
            
            if response.status_code == 200:
                try:
                    json_response = response.json()
                    if json_response.get('status') is True and "successful" in json_response.get('message', ''):
                        logging.info(f"Successfully uploaded chunk {chunk_number}")
                        # Delete the file after successful upload
                        os.remove(self.current_chunk_file)
                        return True
                    else:
                        logging.warning(f"Upload response not as expected: {json_response}")
                        return False
                except ValueError:
                    logging.error("Could not parse response as JSON")
                    return False
            else:
                logging.error(f"Failed to upload chunk. Status code: {response.status_code}")
                logging.error(f"Response text: {response.text}")
                return False
                    
        except requests.RequestException as req_err:
            logging.error(f"Request error uploading chunk: {str(req_err)}")
            return False
        except IOError as io_err:
            logging.error(f"I/O error handling chunk file: {str(io_err)}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error uploading chunk: {str(e)}")
            logging.exception("Stack trace:")
            return False
        
# 3. Device Selection Dialog
class DeviceSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Your Audio & Video Device")
        self.setModal(True)
        self.resize(500, 350)  # Slightly taller to accommodate error messages
        self.setup_ui()
        self.populate_device_lists()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        self.setStyleSheet("""
            QLabel {
                font-family: 'Segoe UI';
                color: #0d1b57;
            }

            QComboBox {
                padding: 8px 12px;
                border-radius: 8px;
                border: 1px solid #c5cae9;
                background-color: #f0f4ff;
                font-family: 'Segoe UI';
                font-size: 14px;
                color: #0d1b57;
                min-height: 20px;
            }

            QPushButton {
                background-color: #00205b;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #001b4f;
            }
            
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }

            QComboBox::down-arrow {
                width: 15px;
                height: 15px;
            }
        """)

        title_label = QLabel("Choose Your Audio & Video Device")
        title_label.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignLeft)

        # Status message for error reporting
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: red; background-color: #ffeeee; padding: 5px; border-radius: 5px;")
        self.status_label.setFont(QFont("Segoe UI", 12))
        self.status_label.setVisible(False)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Audio layout
        audio_layout = QVBoxLayout()
        audio_label = QLabel("Select Audio Device:")
        audio_label.setFont(QFont("Segoe UI", 14))
        self.audio_combo = QComboBox()
        self.audio_combo.setFont(QFont("Segoe UI", 14))
        self.audio_combo.setMaxVisibleItems(10)
        audio_layout.addWidget(audio_label)
        audio_layout.addWidget(self.audio_combo)
        layout.addLayout(audio_layout)

        # Video layout
        video_layout = QVBoxLayout()
        video_label = QLabel("Select Video Device:")
        video_label.setFont(QFont("Segoe UI", 14))
        self.video_combo = QComboBox()
        self.video_combo.setFont(QFont("Segoe UI", 14))
        self.video_combo.setMaxVisibleItems(10)
        video_layout.addWidget(video_label)
        video_layout.addWidget(self.video_combo)
        layout.addLayout(video_layout)

        # Refresh button
        refresh_button = QPushButton("Refresh Devices")
        refresh_button.setFont(QFont("Segoe UI", 12))
        refresh_button.clicked.connect(self.refresh_devices)
        layout.addWidget(refresh_button, alignment=Qt.AlignmentFlag.AlignLeft)

        # Buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.show_demo_button = QPushButton("Show Preview")
        self.show_demo_button.setFont(QFont("Segoe UI", 14))
        self.show_demo_button.clicked.connect(self.on_show_demo_clicked)
        buttons_layout.addWidget(self.show_demo_button)

        self.confirm_button = QPushButton("Confirm and Run Checks")
        self.confirm_button.setFont(QFont("Segoe UI", 14))
        self.confirm_button.clicked.connect(self.accept)
        buttons_layout.addWidget(self.confirm_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.setFont(QFont("Segoe UI", 14))
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)

        layout.addLayout(buttons_layout)

    def populate_device_lists(self):
        """Populate the device lists with available audio and video devices"""
        success = True
        try:
            # Clear existing items
            self.audio_combo.clear()
            self.video_combo.clear()
            
            # Populate audio devices
            audio_devices_found = self.populate_audio_devices()
            if not audio_devices_found:
                self.show_status_error("No audio input devices found. Please connect a microphone.")
                success = False
            
            # Populate video devices
            video_devices_found = self.populate_video_devices()
            if not video_devices_found:
                self.show_status_error("No video devices found. Please connect a webcam.")
                success = False
                
            # Update UI based on device availability
            self.update_ui_state(audio_devices_found, video_devices_found)
            
            return success
            
        except Exception as e:
            logging.error(f"Error populating device lists: {e}")
            self.show_status_error(f"Error loading devices: {str(e)}")
            return False
    
    def populate_audio_devices(self):
        """Populate audio devices list"""
        try:
            devices = sd.query_devices()
            input_devices_found = False
            
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    self.audio_combo.addItem(f"{device['name']}", i)
                    input_devices_found = True
            
            # Set default device if available
            default_in = sd.default.device[0]
            if default_in >= 0:
                # Find the index in the combo box that corresponds to the default device
                for i in range(self.audio_combo.count()):
                    if self.audio_combo.itemData(i) == default_in:
                        self.audio_combo.setCurrentIndex(i)
                        break
            
            return input_devices_found
            
        except Exception as e:
            logging.error(f"Error populating audio devices: {e}")
            # Add fallback items
            self.audio_combo.addItem("Default System Microphone", -1)
            return True  # Return true to allow operation to continue with fallback
    
    def populate_video_devices(self):
        """Populate video devices list"""
        try:
            available_cameras = QMediaDevices.videoInputs()
            if available_cameras:
                for i, camera in enumerate(available_cameras):
                    self.video_combo.addItem(f"{camera.description()}", i)
                return True
            else:
                return False
        except Exception as e:
            logging.error(f"Error populating video devices: {e}")
            # Add fallback items
            self.video_combo.addItem("Default System Camera", 0)
            return True  # Return true to allow operation to continue with fallback
    
    def update_ui_state(self, audio_devices_found, video_devices_found):
        """Update UI elements based on device availability"""
        # Enable/disable buttons based on device availability
        can_continue = audio_devices_found and video_devices_found
        self.show_demo_button.setEnabled(can_continue)
        self.confirm_button.setEnabled(can_continue)
        
        # Show appropriate status message
        if not can_continue:
            if not audio_devices_found and not video_devices_found:
                self.show_status_error("No audio or video devices found. Please connect required hardware.")
            elif not audio_devices_found:
                self.show_status_error("No audio input devices found. Please connect a microphone.")
            elif not video_devices_found:
                self.show_status_error("No video devices found. Please connect a webcam.")
    
    def show_status_error(self, message):
        """Show an error message in the status label"""
        self.status_label.setText(message)
        self.status_label.setVisible(True)
    
    def hide_status_error(self):
        """Hide the status error message"""
        self.status_label.setVisible(False)
    
    def refresh_devices(self):
        """Refresh the device lists"""
        self.hide_status_error()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        success = self.populate_device_lists()
        
        QApplication.restoreOverrideCursor()
        
        if success:
            QMessageBox.information(self, "Device Refresh", "Device lists refreshed successfully.")
        else:
            QMessageBox.warning(self, "Device Refresh", "Some devices could not be detected. Check your hardware connections.")

    def get_selected_devices(self):
        """Return the selected audio and video devices"""
        audio_device = self.audio_combo.currentText()
        video_device = self.video_combo.currentText()
        audio_device_id = self.audio_combo.currentData()
        video_device_id = self.video_combo.currentData()
        
        return {
            'audio_device': audio_device,
            'video_device': video_device,
            'audio_device_id': audio_device_id,
            'video_device_id': video_device_id
        }

    def on_show_demo_clicked(self):
        """Show the demo preview dialog"""
        try:
            # Get selected devices
            audio_device = self.audio_combo.currentText()
            video_device = self.video_combo.currentText()
            
            if not audio_device or not video_device:
                QMessageBox.warning(self, "Device Selection", "Please select both audio and video devices.")
                return
            
            # Show a waiting cursor
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            
            # Create and show the demo preview dialog
            demo_dialog = DemoPreviewDialog(audio_device, video_device, parent=self)
            
            # Restore cursor
            QApplication.restoreOverrideCursor()
            
            demo_result = demo_dialog.exec()
            if demo_result == QDialog.DialogCode.Accepted:
                logging.info("Devices confirmed via demo.")
                # Option to proceed immediately
                proceed = QMessageBox.question(
                    self,
                    "Device Confirmation",
                    "Devices look good! Do you want to proceed with these devices?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if proceed == QMessageBox.StandardButton.Yes:
                    self.accept()
            else:
                logging.info("Device demo cancelled.")
                
        except Exception as e:
            QApplication.restoreOverrideCursor()
            error_msg = f"Error previewing devices: {str(e)}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Device Preview Error", error_msg)
            
    def closeEvent(self, event):
        """Handle dialog close event"""
        # Clean up any resources if needed
        super().closeEvent(event)
        
    def accept(self):
        """Override accept to validate selections before closing"""
        # Validate that devices are selected
        audio_device = self.audio_combo.currentText()
        video_device = self.video_combo.currentText()
        
        if not audio_device or not video_device:
            QMessageBox.warning(self, "Device Selection", "Please select both audio and video devices.")
            return
            
        # All good, accept the dialog
        super().accept()

class DemoPreviewDialog(QDialog):
    def __init__(self, audio_device, video_device, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Device Preview")
        self.setModal(True)
        screen = QApplication.primaryScreen().availableGeometry()
        screen_height = screen.height()
        dialog_height = int(screen_height * 0.9)  # Set dialog height to 90% of screen height
        self.resize(750, dialog_height)
        self.audio_device = audio_device
        self.video_device = video_device
        self.audio_device_id = None
        self.video_device_id = None
        
        # Flag to track if dialog is active
        self.is_active = True
        
        # Find the device IDs based on names
        self.find_device_ids()
        
        self.setup_ui()
        self.start_camera()
        self.start_audio_monitoring()
        
    def find_device_ids(self):
        """Find the device IDs corresponding to the selected device names"""
        try:
            # Find audio device ID
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if device['name'] == self.audio_device or self.audio_device in device['name']:
                    if device['max_input_channels'] > 0:
                        self.audio_device_id = i
                        logging.info(f"Found audio device ID {i} for {self.audio_device}")
                        break
            
            if self.audio_device_id is None:
                logging.warning(f"Could not find audio device ID for {self.audio_device}, using default")
                self.audio_device_id = sd.default.device[0]
            
            # Find video device ID
            available_cameras = QMediaDevices.videoInputs()
            for i, camera in enumerate(available_cameras):
                if camera.description() == self.video_device or self.video_device in camera.description():
                    self.video_device_id = i
                    logging.info(f"Found video device ID {i} for {self.video_device}")
                    break
            
            if self.video_device_id is None:
                logging.warning(f"Could not find video device ID for {self.video_device}, using default")
                self.video_device_id = 0
                
        except Exception as e:
            logging.error(f"Error finding device IDs: {e}")
            self.audio_device_id = sd.default.device[0] if hasattr(sd, 'default') else 0
            self.video_device_id = 0
            
    def setup_ui(self):
        # Create the main content widget and layout
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #00205b;
                min-height: 30px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #1976D2;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        # Set the scroll area as the main layout widget
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.setStyleSheet("""
            QLabel {
                font-family: 'Segoe UI';
                color: #0d1b57;
            }
            
            QPushButton {
                background-color: #00205b;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #001b4f;
            }
            
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            
            QProgressBar {
                border: 1px solid #c5cae9;
                border-radius: 5px;
                text-align: center;
                background-color: #f0f4ff;
            }
            
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 20px;
            }
        """)

        # Title
        title_label = QLabel("Device Preview")
        title_label.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Video section
        video_section = QGroupBox("Video Preview")
        video_section.setFont(QFont("Segoe UI", 12))
        video_layout = QVBoxLayout(video_section)
        
        # Video display area
        self.video_preview = QLabel("Camera initializing...")
        self.video_preview.setMinimumSize(400, 300)
        self.video_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_preview.setStyleSheet("background-color: #e0e0e0; border: 1px solid #ccc;")
        video_layout.addWidget(self.video_preview)
        
        # Camera status
        self.camera_status = QLabel("Camera: Initializing...")
        self.camera_status.setFont(QFont("Segoe UI", 10))
        video_layout.addWidget(self.camera_status)
        
        layout.addWidget(video_section)

        # Audio section
        audio_section = QGroupBox("Audio Test")
        audio_section.setFont(QFont("Segoe UI", 12))
        audio_layout = QVBoxLayout(audio_section)
        
        # Audio level meter
        audio_level_label = QLabel("Microphone Level:")
        audio_level_label.setFont(QFont("Segoe UI", 10))
        audio_layout.addWidget(audio_level_label)
        
        self.audio_levels = QProgressBar()
        self.audio_levels.setRange(0, 100)
        self.audio_levels.setValue(0)
        self.audio_levels.setFixedHeight(20)
        self.audio_levels.setTextVisible(True)
        self.audio_levels.setFormat("%v%")
        audio_layout.addWidget(self.audio_levels)
        
        # Audio status
        self.audio_status = QLabel("Audio: Initializing...")
        self.audio_status.setFont(QFont("Segoe UI", 10))
        audio_layout.addWidget(self.audio_status)
        
        # Test sound button
        self.test_sound_button = QPushButton("Play Test Sound")
        self.test_sound_button.clicked.connect(self.play_test_sound)
        audio_layout.addWidget(self.test_sound_button, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addWidget(audio_section)

        # Help button
        help_button = QPushButton("Troubleshooting Help")
        help_button.clicked.connect(self.show_help)
        layout.addWidget(help_button, alignment=Qt.AlignmentFlag.AlignLeft)

        # Buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        # Cancel and confirm buttons
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        confirm_button = QPushButton("Confirm Devices")
        confirm_button.clicked.connect(self.accept)
        
        buttons_layout.addWidget(cancel_button)
        buttons_layout.addWidget(confirm_button)
        
        layout.addLayout(buttons_layout)

    def start_camera(self):
        """Start the camera and display the live feed"""
        try:
            # Create a QCamera instance
            available_cameras = QMediaDevices.videoInputs()
            if not available_cameras:
                self.handle_camera_error("No cameras available")
                return
                
            # Use the selected camera or fall back to default
            camera_info = available_cameras[self.video_device_id] if self.video_device_id < len(available_cameras) else available_cameras[0]
            
            # Set up the camera
            self.camera = QCamera(camera_info)
            self.camera_captureSession = QMediaCaptureSession()
            self.camera_captureSession.setCamera(self.camera)
            
            # Create a video sink to receive frames
            self.videoSink = QVideoSink()
            self.camera_captureSession.setVideoSink(self.videoSink)
            
            # Connect the video frame signal to update the preview
            self.videoSink.videoFrameChanged.connect(self.update_video_frame)
            
            # Start the camera
            self.camera.start()
            self.camera_status.setText("Camera started successfully")
            self.camera_status.setStyleSheet("color: green;")
            
        except Exception as e:
            self.handle_camera_error(f"Camera error: {str(e)}")
    
    def update_video_frame(self, frame):
        """Update the video preview with the latest frame"""
        # Check if dialog is still active before processing the frame
        if not self.is_active:
            return
            
        if frame.isValid():
            # Convert QVideoFrame to QImage
            image = frame.toImage()
            if not image.isNull():
                # Scale image to fit the label while maintaining aspect ratio
                pixmap = QPixmap.fromImage(image)
                scaled_pixmap = pixmap.scaled(
                    self.video_preview.width(), 
                    self.video_preview.height(),
                    Qt.AspectRatioMode.KeepAspectRatio
                )
                self.video_preview.setPixmap(scaled_pixmap)
            else:
                self.handle_camera_error("Invalid image from camera")
        else:
            self.handle_camera_error("Invalid frame from camera")
    
    def handle_camera_error(self, message):
        """Handle camera errors by showing an error message"""
        if not self.is_active:
            return
            
        logging.error(message)
        self.video_preview.setText(message)
        self.video_preview.setStyleSheet("background-color: #ffcccc; color: red;")
        self.camera_status.setText("Camera error")
        self.camera_status.setStyleSheet("color: red;")
    
    def start_audio_monitoring(self):
        """Start monitoring audio levels from the actual microphone"""
        try:
            # Set up the audio stream parameters
            self.audio_buffer_size = 1024
            self.sample_rate = 44100
            self.channels = 1
            
            # Create the audio stream
            self.audio_stream = sd.InputStream(
                device=self.audio_device_id,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.audio_buffer_size,
                callback=self.audio_callback
            )
            
            # Start the audio stream
            self.audio_stream.start()
            self.audio_status.setText("Audio monitoring started")
            
        except Exception as e:
            self.handle_audio_error(f"Audio error: {str(e)}")
    
    def audio_callback(self, indata, frames, time, status):
        """Callback function for the audio stream"""
        # First check if dialog is still active before processing audio
        if not self.is_active:
            return
            
        if status:
            logging.warning(f"Audio stream status: {status}")
            
        # Calculate the audio level (RMS value)
        if indata is not None and len(indata) > 0:
            rms = np.sqrt(np.mean(indata**2)) * 100
            level = min(100, int(rms * 500))  # Scale to 0-100%
            
            # Update UI from the main thread
            try:
                QMetaObject.invokeMethod(self, "update_audio_level_ui", 
                                        Qt.ConnectionType.QueuedConnection,
                                        Q_ARG(int, level))
            except RuntimeError:
                # If we get here, the object is likely already deleted
                logging.debug("Dialog already deleted during audio callback")
                pass
    
    @pyqtSlot(int)
    def update_audio_level_ui(self, level):
        """Update the audio level UI (called from main thread)"""
        if not self.is_active:
            return
            
        self.audio_levels.setValue(level)
        
        # Update status based on level
        if level > 70:
            self.audio_status.setText("Audio level excellent!")
            self.audio_status.setStyleSheet("color: green;")
        elif level > 30:
            self.audio_status.setText("Audio level good")
            self.audio_status.setStyleSheet("color: green;")
        elif level > 10:
            self.audio_status.setText("Audio detected")
            self.audio_status.setStyleSheet("color: black;")
        else:
            self.audio_status.setText("Speak to test your microphone")
            self.audio_status.setStyleSheet("color: black;")
    
    def handle_audio_error(self, message):
        """Handle audio errors by showing an error message"""
        if not self.is_active:
            return
            
        logging.error(message)
        self.audio_status.setText(message)
        self.audio_status.setStyleSheet("color: red;")
        self.audio_levels.setValue(0)
    
    def play_test_sound(self):
        """Play a test sound through the selected output device"""
        if not self.is_active:
            return
            
        try:
            self.test_sound_button.setText("Playing...")
            self.test_sound_button.setEnabled(False)
            
            # Get default output device
            output_device = sd.default.device[1]
            
            # Generate a test tone (440 Hz A note)
            duration = 1.0  # seconds
            sample_rate = 44100
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            # Generate a more pleasant tone with fade in/out
            tone = 0.5 * np.sin(2 * np.pi * 440 * t)
            fade = 0.1  # seconds
            fade_samples = int(fade * sample_rate)
            # Apply fade in
            fade_in = np.linspace(0, 1, fade_samples)
            tone[:fade_samples] *= fade_in
            # Apply fade out
            fade_out = np.linspace(1, 0, fade_samples)
            tone[-fade_samples:] *= fade_out
            
            # Play the sound asynchronously
            sd.play(tone, sample_rate, device=output_device)
            
            # Re-enable button after playing
            QTimer.singleShot(int(duration * 1000) + 200, self.reset_test_button)
            
        except Exception as e:
            logging.error(f"Error playing test sound: {e}")
            self.test_sound_button.setText("Error Playing Sound")
            self.test_sound_button.setStyleSheet("color: red;")
            QTimer.singleShot(2000, self.reset_test_button)
    
    def reset_test_button(self):
        """Reset the test sound button"""
        if not self.is_active:
            return
            
        self.test_sound_button.setText("Play Test Sound")
        self.test_sound_button.setEnabled(True)
        self.test_sound_button.setStyleSheet("")
    
    def show_help(self):
        """Show help dialog with troubleshooting tips"""
        help_dialog = QMessageBox(self)
        help_dialog.setWindowTitle("Device Setup Help")
        help_dialog.setIcon(QMessageBox.Icon.Information)
        help_dialog.setText("Device Setup Troubleshooting")
        
        help_text = (
            "<b>Camera Issues:</b><br>"
            "• Make sure your camera is connected properly<br>"
            "• Check if other applications are using your camera<br>"
            "• Try selecting a different camera if available<br>"
            "• Ensure you have given permission to use the camera<br><br>"
            
            "<b>Audio Issues:</b><br>"
            "• Make sure your microphone is not muted<br>"
            "• Check if the correct audio device is selected<br>"
            "• Try adjusting your system's audio input volume<br>"
            "• Ensure you have given permission to use the microphone<br><br>"
            
            "If problems persist, contact technical support."
        )
        
        help_dialog.setInformativeText(help_text)
        help_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        help_dialog.exec()
    
    def closeEvent(self, event):
        """Clean up resources when the dialog is closed"""
        # Set the active flag to False first
        self.is_active = False
        
        # Stop the camera
        if hasattr(self, 'camera') and self.camera:
            self.camera.stop()
        
        # Stop the audio stream
        if hasattr(self, 'audio_stream') and self.audio_stream:
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
            except Exception as e:
                logging.error(f"Error closing audio stream: {e}")
        
        # Process the close event
        super().closeEvent(event)
    
    def done(self, result):
        """Override done to clean up resources before closing dialog"""
        # Set the active flag to False first
        self.is_active = False
        
        # Stop the camera
        if hasattr(self, 'camera') and self.camera:
            self.camera.stop()
        
        # Stop the audio stream
        if hasattr(self, 'audio_stream') and self.audio_stream:
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
            except Exception as e:
                logging.error(f"Error closing audio stream: {e}")
        
        # Process the done event
        super().done(result)

# 5. Exam Instructions Page
class ExamInstructionsPage(QWidget):
    def __init__(self, switch_to_exam_callback):
        super().__init__()
        self.switch_to_exam_callback = switch_to_exam_callback
        self.exam_details = None
        self.remaining_time = 0
        self.setup_ui()

    def set_exam_details(self, exam_details):
        self.exam_details = exam_details
        print("\n✅ Exam Details in ExamInstructionsPage:", self.exam_details)
        # Ensure remaining_time is an integer
        self.remaining_time = int(self.exam_details.get("remaining_time", 0))
        self.message_label.setText(self.exam_details.get("message", ""))
        self.start_countdown()

    def setup_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(20,20, 20, 20)
            layout.setSpacing(0)
            
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(20, 30, 20, 20) 
            container_layout.setSpacing(8)
            container.setStyleSheet("""
                QWidget {
                    background-color: white;
                    border-radius: 15px;
                }
            """)
            container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            layout.addWidget(container)

            title = QLabel("Welcome To SentientGeeks Assessment Exam")
            title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
            title.setStyleSheet("color: #00205b;")
            title.setAlignment(Qt.AlignmentFlag.AlignLeft)
            container_layout.addWidget(title)

            banner = QLabel("Please read the following instructions carefully before starting the exam:")
            banner.setFont(QFont("Arial", 18, QFont.Weight.Medium))
            banner.setStyleSheet("background-color: #ff0000; color: #fff; padding: 10px; border-radius: 4px;")
            banner.setFixedWidth(800)
            banner.setWordWrap(True)
            banner.setAlignment(Qt.AlignmentFlag.AlignLeft)
            container_layout.addWidget(banner)    

            instructions_html = """
            <ol style="font-size:16px; font-family:sans-serif; line-height:2; color:#121212; padding-left: 0px; margin-left: 0px;">
                <li style="margin-bottom: 15px; margin-left: 0px; padding-left: 0px;">Exam can only be started on desktop or laptop devices.</li>
                <li style="margin-bottom: 15px; margin-left: 0px; padding-left: 0px;">Ensure that your camera and microphone are connected and grant the necessary permissions before starting the exam.</li>
                <li style="margin-bottom: 15px; margin-left: 0px; padding-left: 0px;">Close all other programs before starting your exam.</li>
                <li style="margin-bottom: 15px; margin-left: 0px; padding-left: 0px;">Do not use any browser extensions (e.g., Grammarly), as they may cause exam termination.</li>
                <li style="margin-bottom: 15px; margin-left: 0px; padding-left: 0px;">Ensure you have a stable internet and power connection.</li>
                <li style="margin-bottom: 15px; margin-left: 0px; padding-left: 0px;">Do not press the <b>Esc</b>, <b>Windows</b>, or any other shortcut button.</li>
                <li style="margin-bottom: 15px; margin-left: 0px; padding-left: 0px;">Do not exit full-screen mode.</li>
                <li style="margin-bottom: 15px; margin-left: 0px; padding-left: 0px;">Do not refresh the page during the exam.</li>
                <li style="margin-bottom: 15px; margin-left: 0px; padding-left: 0px;">Avoid clicking on any pop-ups during the exam.</li>
                <li style="margin-bottom: 15px; margin-left: 0px; padding-left: 0px;">If you do not submit your exam within the provided time, your answers will be automatically saved.</li>
                <li style="margin-bottom: 15px; margin-left: 0px; padding-left: 0px;">Close your browser only after the "Thank You" page is visible.</li>
            </ol>
                """
            self.instructions_label = QLabel(instructions_html)
            self.instructions_label.setWordWrap(True)
            self.instructions_label.setFont(QFont("Arial", 16))
            self.instructions_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.instructions_label.setContentsMargins(0, 15, 0, 0)
            container_layout.addWidget(self.instructions_label)

            self.message_label = QLabel("")
            self.message_label.setFont(QFont("Arial", 18))
            self.message_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.message_label.setStyleSheet("color: #00205b;")
            self.message_label.setContentsMargins(0, 15, 0, 0)
            container_layout.addWidget(self.message_label)

            self.countdown_label = QLabel("")
            self.countdown_label.setFont(QFont("Arial", 22, QFont.Weight.Bold))
            self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            container_layout.addWidget(self.countdown_label)
            self.countdown_label.setStyleSheet("color: #418b69;")

    def start_countdown(self):
        # Create a QTimer and connect its timeout to update_countdown
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.update_countdown()  # Call immediately to update the label
        self.timer.start(1000)

    def update_countdown(self):
        if self.remaining_time > 0:
            hours, rem = divmod(self.remaining_time, 3600)
            mins, secs = divmod(rem, 60)
            time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
            self.countdown_label.setText(f"Exam starts in: {time_str}")
            self.remaining_time -= 1
        else:
            self.timer.stop()
            self.countdown_label.setText("Starting Exam...")

            # Refresh exam details using a valid exam identifier (e.g., exam code)
            exam_link = self.exam_details.get("exam_link") or ""  # Adjust as needed
            print("🔹 Calling get_exam_details after countdown ends with exam_link:", exam_link)
            updated_details = get_exam_details(SESSION_TOKEN, exam_link)
            print("🔹 Updated Exam Details received:", updated_details)
            logging.info("Updated Exam Details received after countdown: " + str(updated_details))
            
            if updated_details and updated_details.get("status"):
                self.exam_details = updated_details
                question_ids = updated_details.get("questionsIds", [])
                print("🔹 Question IDs after update:", question_ids)
                logging.info("Question IDs after update: " + str(question_ids))
                
                if question_ids:
                    question_data = fetch_question(
                        question_ids[0],
                        updated_details.get("examId") or updated_details.get("exam_id"),
                        updated_details.get("userId") or updated_details.get("user_id") or "default_user",
                        idx=0,
                        first_request=True
                    )
                    print("🔹 Fetched first question:", question_data)
                    logging.info("Fetched first question: " + str(question_data))
                else:
                    print("⚠️ No question IDs returned in exam details.")
                    logging.warning("No question IDs returned in exam details.")
            else:
                print("❌ Failed to refresh exam details.")
                logging.error("Failed to refresh exam details after countdown.")

            # Call the callback to switch to the exam page with updated details
            self.switch_to_exam_callback(self.exam_details)
    


class ExamPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.questions = []
        self.current_question_index = 0
        self.user_answers = []
        self.exam_code = ""
        self.exam_details = None
        self.exam_id = None
        self.user_id = None
        self.exam_submitted = False
        self.webcam_recorder = None

        self.timer = QTimer(self)
        self.remaining_seconds = 0
        self.timer.timeout.connect(self.update_timer)

        self.setup_ui()



    def setup_ui(self):
        # Import network related modules at the top of the class

        # Set the overall background color to match the screenshot
        self.setStyleSheet("background-color: #f5f9ff;")
    
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Left Container (Question & Options)
        self.left_container = QWidget()
        self.left_container.setStyleSheet("background-color: #FFFFFF; border-radius: 6px;")
        self.left_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(self.left_container)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(8)

        # Question indicator with bullet point (•)
        question_header_layout = QHBoxLayout()
        self.question_number_pill = QLabel("• Question 1")
        self.question_number_pill.setStyleSheet("""
            background-color: #EBF1F9;
            color: #0D2144;
            border-radius: 15px;
            padding: 5px 15px;
            font-weight: bold;
        """)
        question_header_layout.addWidget(self.question_number_pill)
        question_header_layout.addStretch()
    
        # Marks indicator
        self.marks_label = QLabel("[Marks: 2]")
        self.marks_label.setStyleSheet("color: #333333; font-weight: bold;")
        question_header_layout.addWidget(self.marks_label)
    
        # Question type indicator
        self.question_type_label = QLabel("[Type: MCQ]")
        self.question_type_label.setStyleSheet("color: #333333;")
        question_header_layout.addWidget(self.question_type_label)
    
        left_layout.addLayout(question_header_layout)

        # Question text
        self.question_label = QLabel("Question text will appear here")
        self.question_label.setFont(QFont("Arial", 16))
        self.question_label.setWordWrap(True)
        self.question_label.setContentsMargins(0, 5, 0, 0)
        self.question_label.setTextFormat(Qt.TextFormat.RichText)
        self.question_label.setStyleSheet("""
            color: #02205b;
            background-color: #FFFFFF;
        """)
        self.question_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # self.question_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        left_layout.addWidget(self.question_label)
        
        # Question content (for additional content like images)
        self.question_content_label = QLabel()
        self.question_content_label.setWordWrap(True)
        self.question_content_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.question_content_label.setTextFormat(Qt.TextFormat.RichText)
        self.question_content_label.setStyleSheet("""
            color: #02205b;
            background-color: #FFFFFF;
        """)
        # self.question_content_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.question_content_label.setOpenExternalLinks(True)  # Allow opening links if any
        left_layout.addWidget(self.question_content_label)

        self.question_content_label = QLabel()

        self.question_content_label.setWordWrap(True)
        self.question_content_label.setTextFormat(Qt.TextFormat.RichText)
        self.question_content_label.setStyleSheet("""
            color: #02205b;
            background-color: #FFFFFF;
            border-radius: 4px;
        """)
        self.question_content_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.question_content_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.question_content_label.setOpenExternalLinks(True)  # Allow opening links if any
        left_layout.addWidget(self.question_content_label)

        # Add WebEngineView for better HTML content rendering
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        self.question_content_web = QWebEngineView()
        self.question_content_web.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.question_content_web.setStyleSheet("""
            background-color: #FFFFFF;
            border: 1px solid #D0D0D0;
            color: #02205b;
        """)
        left_layout.addWidget(self.question_content_web)
        self.question_content_web.hide()  # Hide initially
    
        # Horizontal separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("background-color: #E0E0E0;")
        left_layout.addWidget(separator)

        # Options container for MCQ/MSQ - MODIFIED
        options_container = QWidget()
        options_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.options_layout = QGridLayout(options_container)
        self.options_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.options_layout.setSpacing(15)
        self.options_layout.setContentsMargins(0, 10, 0, 10)
        left_layout.addWidget(options_container, 1)  # Add stretch factor of 1
        
        # Description answer container - MODIFIED
        self.description_container = QWidget()
        self.description_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        description_layout = QVBoxLayout(self.description_container)
        description_layout.setContentsMargins(0, 0, 0, 0)
    
        # Description answer container - MODIFIED
        self.description_editor = QTextEdit()
        screen = QApplication.primaryScreen()
        screen_size = screen.size()
        screen_height = screen_size.height()
        calculated_height = int(screen_height * 0.65)
        self.description_editor.setFixedHeight(calculated_height)
        self.description_editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.description_editor.setStyleSheet("""
            QTextEdit {
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                padding: 8px;
                background-color: #FFFFFF;
                font-size: 14px;
                color: #333;
            }
            QScrollBar:vertical {
                background: #F0F0F0;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #A0A0A0;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        description_layout.addWidget(self.description_editor, 1)  # Add stretch factor of 1
    
        # Word count display
        word_count_layout = QHBoxLayout()
        self.word_count_label = QLabel("Word count: 0")
        self.word_count_label.setStyleSheet("color: #666666;")
        word_count_layout.addStretch()
        word_count_layout.addWidget(self.word_count_label)
        description_layout.addLayout(word_count_layout)
    
        # Connect text change signal to word counter
        self.description_editor.textChanged.connect(self.update_word_count)
    
        # Initially hide the description editor
        self.description_container.hide()
        left_layout.addWidget(self.description_container, 1)  # Add stretch factor of 1
    
        # Coding answer container - MODIFIED
        self.coding_container = QWidget()
        self.coding_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        coding_layout = QVBoxLayout(self.coding_container)
        coding_layout.setContentsMargins(0, 0, 0, 0)
        coding_layout.setSpacing(10)
    
        # Language selector and run button in the same row
        lang_row_layout = QHBoxLayout()
    
        # Language selector for coding questions
        lang_label = QLabel("Language:")
        lang_label.setStyleSheet("color: #333333; font-weight: bold;")
        self.language_selector = QComboBox()
        self.language_selector.addItems(["Python", "Java", "JavaScript", "C++", "C", "HTML"])
        self.language_selector.setStyleSheet("""
            border: 1px solid #D0D0D0;
            border-radius: 4px;
            padding: 5px;
            background-color: white;
            color: black;
        """)
    
        # Add Run button
        self.run_code_button = QPushButton("Run")
        self.run_code_button.setStyleSheet("""
            QPushButton {
                background-color: #0D2144;
                color: white;
                border-radius: 4px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0A1A36;
            }
        """)
        self.run_code_button.clicked.connect(self.run_code)
    
        lang_row_layout.addWidget(lang_label)
        lang_row_layout.addWidget(self.language_selector)
        lang_row_layout.addStretch()
        lang_row_layout.addWidget(self.run_code_button)
        coding_layout.addLayout(lang_row_layout)
        
        code_output_container = QWidget()
        code_output_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        code_output_layout = QVBoxLayout(code_output_container)
        code_output_layout.setContentsMargins(0, 0, 0, 0)
        code_output_layout.setSpacing(10)
        
        # Code editor - 70% of height
        self.code_editor = QTextEdit()
        self.code_editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.code_editor.setStyleSheet("""
            border: 1px solid #D0D0D0;
            border-radius: 4px;
            padding: 8px;
            background-color: #1E1E1E;
            color: #FFFFFF;
            font-family: Consolas, Monaco, 'Courier New', monospace;
            font-size: 14px;
        """)
        
        # Set a monospace font for code
        code_font = QFont("Consolas")
        code_font.setStyleHint(QFont.StyleHint.Monospace)
        self.code_editor.setFont(code_font)
        
        output_container = QWidget()
        output_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        output_layout = QVBoxLayout(output_container)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(5)
        
        # Add output area with header - 30% of height
        output_header = QLabel("Output:")
        output_header.setStyleSheet("color: #333333; font-weight: bold;")
        output_layout.addWidget(output_header)
        
        self.code_output = QTextEdit()
        self.code_output.setReadOnly(True)
        self.code_output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.code_output.setStyleSheet("""
            border: 1px solid #D0D0D0;
            border-radius: 4px;
            padding: 8px;
            background-color: #1E1E1E;
            color: #FFFFFF;
            font-family: Consolas, Monaco, 'Courier New', monospace;
            font-size: 14px;
        """)
        output_layout.addWidget(self.code_output)
        
        # Add components to code_output_layout with specific proportions (70/30)
        code_output_layout.addWidget(self.code_editor, 3)  # 70% of space
        code_output_layout.addWidget(output_header)
        code_output_layout.addWidget(self.code_output, 5)  # 30% of space
        
        # Add the code_output_container to coding_layout
        coding_layout.addWidget(code_output_container)  # stretch factor of 
        
        self.setup_modern_code_editor()
        # Initially hide the coding editor
        self.coding_container.hide()
        left_layout.addWidget(self.coding_container, 1)  # Add stretch factor of 1

        # Right Container (Timer, Navigation, Question Panel) - keep as is
        self.right_container = QWidget()
        self.right_container.setFixedWidth(320)  # Fixed width for right panel
        self.right_container.setStyleSheet("background-color: #FFFFFF; border-radius: 6px;")
        self.right_container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(self.right_container)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(20)

        # Logo at the top
        logo_layout = QHBoxLayout()
        logo_label = QLabel("KEvaluate")
        logo_label.setStyleSheet("""
            color: #0D2144;
            font-size: 20px;
            font-weight: bold;
        """)
        logo_layout.addWidget(logo_label)
        logo_layout.addStretch()
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_layout.addLayout(logo_layout)

        # Timer container with circular design
        timer_container = QWidget()
        timer_container.setStyleSheet("""
            background-color: white;
            border-radius: 10px;
        """)
        timer_layout = QVBoxLayout(timer_container)
        
        time_label_title = QLabel("Remaining Time")
        time_label_title.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)
        time_label_title.setStyleSheet("color: #0D2144; font-size: 16px; font-weight: bold;")
        timer_layout.addWidget(time_label_title)
        
        # Custom circular timer
        self.time_container = QLabel("00:00:00")
        self.time_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_container.setFixedSize(150, 150)
        self.time_container.setStyleSheet("""
            background-color: white;
            color: #0D2144;
            font-size: 24px;
            font-weight: bold;
            border: 3px solid #0D2144;
            border-radius: 75px;
        """)
        timer_layout.addWidget(self.time_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Hours, Min, Sec labels
        time_units_layout = QHBoxLayout()
        time_units = ["Hours", "Min", "Sec"]
        for unit in time_units:
            unit_label = QLabel(unit)
            unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            unit_label.setStyleSheet("color: #666; font-size: 12px;")
            time_units_layout.addWidget(unit_label)
        
        timer_layout.addLayout(time_units_layout)
        right_layout.addWidget(timer_container)

        # Question Panel section
        question_panel_container = QWidget()
        question_panel_container.setStyleSheet("""
            background-color: white;
            border-radius: 10px;
        """)
        question_panel_layout = QVBoxLayout(question_panel_container)
        question_panel_layout.setContentsMargins(0,0,0,0)  # Add margins around the entire panel
        question_panel_title = QLabel("Question Panel")
        question_panel_title.setStyleSheet("color: #0D2144; font-size: 16px; font-weight: bold;")
        question_panel_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        question_panel_layout.addWidget(question_panel_title)
        question_panel_layout.addSpacing(7)  # Add space after the title
        
        # Legend for question status
        legend_layout = QVBoxLayout()
        legend_layout.setSpacing(5)  # Increase spacing between legend items

        status_items = [
            ("Answer Given", "#8BC34A"),
            ("Answer Not Given", "#F44336"),
            ("Current", "#0D2144"),
            ("Not Visited", "#D0D0D0")
        ]

        for status, color in status_items:
            item_layout = QHBoxLayout()
            item_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            item_layout.setSpacing(6)  # Increase horizontal spacing between indicator and text
            
            status_indicator = QLabel()
            status_indicator.setFixedSize(15, 15)
            status_indicator.setStyleSheet(f"background-color: {color}; border-radius: 7px;")
            
            status_label = QLabel(status)
            status_label.setStyleSheet("color: #333; font-size: 12px;")
            
            item_layout.addWidget(status_indicator)
            item_layout.addWidget(status_label)
            item_layout.addStretch()
            
            # Create a container widget for each item to better control spacing
            item_container = QWidget()
            item_container.setLayout(item_layout)
            legend_layout.addWidget(item_container)
        question_panel_layout.addLayout(legend_layout)
        
        # Question number buttons grid
        self.question_panel = QGridLayout()
        self.question_panel.setSpacing(10)
        question_panel_layout.addLayout(self.question_panel)
        right_layout.addWidget(question_panel_container)

        # Navigation Buttons
        nav_layout = QHBoxLayout()
        
        self.prev_button = QPushButton("◀ Previous")
        self.prev_button.setStyleSheet("""
            QPushButton {
                background-color: #E1E8F5;
                color: #0D2144;
                border-radius: 4px;
                padding: 10px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D0DBEB;
            }
        """)
        
        self.next_button = QPushButton("Next ▶")
        self.next_button.setStyleSheet("""
            QPushButton {
                background-color: #0D2144;
                color: white;
                border-radius: 4px;
                padding: 10px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0A1A36;
            }
        """)
        
        nav_layout.addWidget(self.prev_button)
        nav_layout.addStretch()
        nav_layout.addWidget(self.next_button)
        right_layout.addLayout(nav_layout)
        
        # Submit button
        self.submit_button = QPushButton("Submit")
        self.submit_button.setStyleSheet("""
            QPushButton {
                background-color: #0D2144;
                color: white;
                border-radius: 4px;
                padding: 12px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #0A1A36;
            }
        """)
        right_layout.addWidget(self.submit_button)
        
        # Add containers to main layout with proper proportions
        main_layout.addWidget(self.left_container, 3)  # Increased left container proportion
        main_layout.addWidget(self.right_container, 0)  # Right container has fixed width
        
        # Connect button signals
        self.prev_button.clicked.connect(self.go_previous)
        self.next_button.clicked.connect(self.go_next)
        self.submit_button.clicked.connect(self.submit_exam)
        
        # Initialize button group for options
        self.options_button_group = QButtonGroup(self)
        self.options_button_group.setExclusive(True)
        
        # Initialize checkbox list for MSQ questions
        self.checkbox_list = []

    def display_html_content(self, html_content):
        """Display HTML content including images in the web view with improved stability"""
        # We need to wrap the HTML content in a complete HTML document structure
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #FFFFFF;
                    color: #000000;
                    margin: 0;
                    padding: 5px;
                }}
                h1,h2,h3,h4,h5,h6,p,ul,li {{
                    margin: 0;
                    padding: 0;
                }}
                img {{
                    max-width: 100%;
                    height: auto;
                    display: block;
                    margin: 10px auto;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 10px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        # Hide the web view first to prevent flashing during content update
        if hasattr(self, 'question_content_web'):
            self.question_content_web.hide()
            
            # Clear any previous content
            self.question_content_web.setHtml("")
            
            # Set a default height before content loads
            self.question_content_web.setMinimumHeight(50)
            self.question_content_web.setMaximumHeight(300)  # Maximum height
            
            # Set the new content
            self.question_content_web.setHtml(full_html)
            
            # Show the web view after content is loaded with a short delay
            QTimer.singleShot(100, lambda: self.question_content_web.show())
        
        # Adjust the web view height after a longer delay
        QTimer.singleShot(300, lambda: self.delayed_adjust_web_view_height())

    def delayed_adjust_web_view_height(self):
        """Run the height adjustment after a brief delay to ensure content is properly loaded"""
        if not hasattr(self, 'question_content_web') or self.question_content_web.isHidden():
            return
            
        # First set a reasonable default height
        self.question_content_web.setMinimumHeight(50)
        
        # Try to get the actual height using JavaScript with proper error handling
        try:
            self.question_content_web.page().runJavaScript(
                "document.body ? document.body.scrollHeight : 50;", 
                self.adjust_web_view_height
            )
        except Exception as e:
            print(f"Error getting web content height: {e}")
            # Use a default height as fallback
            self.adjust_web_view_height(50)
            
        # Schedule another check to make sure content has fully loaded
        QTimer.singleShot(500, self.final_height_check)
        
    def final_height_check(self):
        """Final check for web content height after all content should be loaded"""
        if not hasattr(self, 'question_content_web') or self.question_content_web.isHidden():
            return
            
        try:
            self.question_content_web.page().runJavaScript(
                "document.body ? document.body.scrollHeight : 50;",
                self.adjust_web_view_height
            )
        except Exception:
            pass  # Silently ignore errors in final height check

    def adjust_web_view_height(self, height):
        """Adjust the height of the web view based on content with improved stability"""
        if not hasattr(self, 'question_content_web'):
            return
            
        # Handle the case where height is None
        if height is None:
            height = 30  # Default height when JavaScript returns None
        
        # Set a minimum height but allow it to grow with content
        # Limit to a maximum height to prevent excessive scrolling
        min_height = 30
        max_height = 300  # Increased from 100 to allow more content visibility
        content_height = max(min_height, min(int(height) + 20, max_height))
        
        # Block signals temporarily to prevent cascading events
        self.question_content_web.blockSignals(True)
        try:
            self.question_content_web.setMinimumHeight(content_height)
            self.question_content_web.setMaximumHeight(content_height)
        finally:
            self.question_content_web.blockSignals(False)
              
    def setup_modern_code_editor(self):
        
        # Create syntax highlighter for different languages
        class VSCodeSyntaxHighlighter(QSyntaxHighlighter):
            def __init__(self, parent=None, language="python"):
                super().__init__(parent)
                self.language = language.lower()
                self.highlighting_rules = []
                
                # VS Code color scheme
                self.colors = {
                    "keyword": QColor("#569CD6"),       # blue
                    "class": QColor("#4EC9B0"),         # teal
                    "function": QColor("#DCDCAA"),      # yellow
                    "string": QColor("#CE9178"),        # orange-brown
                    "comment": QColor("#6A9955"),       # green
                    "number": QColor("#B5CEA8"),        # light green
                    "operator": QColor("#D4D4D4"),      # light gray
                    "constant": QColor("#4FC1FF"),      # light blue
                    "preprocessor": QColor("#C586C0"),  # purple
                    "identifier": QColor("#9CDCFE"),    # light blue
                    "bracket": QColor("#D4D4D4"),       # light gray
                    "default": QColor("#D4D4D4")        # light gray
                }
                
                self.setup_highlighting_rules()
            
            def setup_highlighting_rules(self):
                # Clear rules first
                self.highlighting_rules = []
                
                # Common formatting for different code elements
                keyword_format = QTextCharFormat()
                keyword_format.setForeground(self.colors["keyword"])
                keyword_format.setFontWeight(QFont.Weight.Bold)
                
                class_format = QTextCharFormat()
                class_format.setForeground(self.colors["class"])
                
                function_format = QTextCharFormat()
                function_format.setForeground(self.colors["function"])
                
                string_format = QTextCharFormat()
                string_format.setForeground(self.colors["string"])
                
                comment_format = QTextCharFormat()
                comment_format.setForeground(self.colors["comment"])
                
                number_format = QTextCharFormat()
                number_format.setForeground(self.colors["number"])
                
                operator_format = QTextCharFormat()
                operator_format.setForeground(self.colors["operator"])
                
                # Set language-specific rules
                if self.language == "python":
                    # Python keywords
                    keywords = [
                        "and", "as", "assert", "async", "await", "break", "class", "continue", 
                        "def", "del", "elif", "else", "except", "False", "finally", "for", 
                        "from", "global", "if", "import", "in", "is", "lambda", "None", 
                        "nonlocal", "not", "or", "pass", "raise", "return", "True", 
                        "try", "while", "with", "yield"
                    ]
                    
                    # Add keyword rules
                    for keyword in keywords:
                        pattern = QRegularExpression(r'\b' + keyword + r'\b')
                        self.highlighting_rules.append((pattern, keyword_format))
                    
                    # Function calls pattern
                    function_pattern = QRegularExpression(r'\b[A-Za-z0-9_]+(?=\()')
                    self.highlighting_rules.append((function_pattern, function_format))
                    
                    # Class name pattern
                    class_pattern = QRegularExpression(r'\bclass\s+([A-Za-z_][A-Za-z0-9_]*)')
                    self.highlighting_rules.append((class_pattern, class_format))
                    
                    # String patterns - single and double quotes
                    self.highlighting_rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format))
                    self.highlighting_rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format))
                    
                    # Triple-quoted strings patterns
                    self.highlighting_rules.append((QRegularExpression(r'""".*?"""', QRegularExpression.PatternOption.DotMatchesEverythingOption), string_format))
                    self.highlighting_rules.append((QRegularExpression(r"'''.*?'''", QRegularExpression.PatternOption.DotMatchesEverythingOption), string_format))
                    
                    # Comment pattern
                    self.highlighting_rules.append((QRegularExpression(r'#[^\n]*'), comment_format))
                    
                    # Number pattern
                    self.highlighting_rules.append((QRegularExpression(r'\b\d+\b'), number_format))
                    
                    # Operators pattern
                    self.highlighting_rules.append((QRegularExpression(r'[\+\-\*/=<>%&\|\^~!]'), operator_format))
                
                elif self.language == "javascript":
                    # JavaScript keywords
                    keywords = [
                        "break", "case", "catch", "class", "const", "continue", "debugger", 
                        "default", "delete", "do", "else", "export", "extends", "false", 
                        "finally", "for", "function", "if", "import", "in", "instanceof", 
                        "new", "null", "return", "super", "switch", "this", "throw", "true", 
                        "try", "typeof", "var", "void", "while", "with", "yield", "let", "async", "await"
                    ]
                    
                    # Add keyword rules
                    for keyword in keywords:
                        pattern = QRegularExpression(r'\b' + keyword + r'\b')
                        self.highlighting_rules.append((pattern, keyword_format))
                    
                    # Function declarations and calls
                    function_pattern = QRegularExpression(r'\b[A-Za-z0-9_]+(?=\()')
                    self.highlighting_rules.append((function_pattern, function_format))
                    
                    # Class name pattern
                    class_pattern = QRegularExpression(r'\bclass\s+([A-Za-z_][A-Za-z0-9_]*)')
                    self.highlighting_rules.append((class_pattern, class_format))
                    
                    # String patterns - single and double quotes
                    self.highlighting_rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format))
                    self.highlighting_rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format))
                    self.highlighting_rules.append((QRegularExpression(r"`[^`\\]*(\\.[^`\\]*)*`"), string_format))
                    
                    # Comment patterns
                    self.highlighting_rules.append((QRegularExpression(r'//[^\n]*'), comment_format))
                    self.highlighting_rules.append((QRegularExpression(r'/\*.*?\*/', QRegularExpression.PatternOption.DotMatchesEverythingOption), comment_format))
                    
                    # Number pattern
                    self.highlighting_rules.append((QRegularExpression(r'\b\d+(\.\d+)?\b'), number_format))
                    
                    # Operators pattern
                    self.highlighting_rules.append((QRegularExpression(r'[\+\-\*/=<>%&\|\^~!]'), operator_format))
                
                elif self.language == "java" or self.language == "c++" or self.language == "c":
                    # C-like language keywords
                    if self.language == "java":
                        keywords = [
                            "abstract", "assert", "boolean", "break", "byte", "case", "catch", 
                            "char", "class", "const", "continue", "default", "do", "double", 
                            "else", "enum", "extends", "final", "finally", "float", "for", 
                            "goto", "if", "implements", "import", "instanceof", "int", 
                            "interface", "long", "native", "new", "package", "private", 
                            "protected", "public", "return", "short", "static", "strictfp", 
                            "super", "switch", "synchronized", "this", "throw", "throws", 
                            "transient", "try", "void", "volatile", "while", "true", "false", "null"
                        ]
                    elif self.language == "c++":
                        keywords = [
                            "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", 
                            "bitor", "bool", "break", "case", "catch", "char", "char16_t", 
                            "char32_t", "class", "compl", "const", "constexpr", "const_cast", 
                            "continue", "decltype", "default", "delete", "do", "double", 
                            "dynamic_cast", "else", "enum", "explicit", "export", "extern", 
                            "false", "float", "for", "friend", "goto", "if", "inline", "int", 
                            "long", "mutable", "namespace", "new", "noexcept", "not", "not_eq", 
                            "nullptr", "operator", "or", "or_eq", "private", "protected", 
                            "public", "register", "reinterpret_cast", "return", "short", 
                            "signed", "sizeof", "static", "static_assert", "static_cast", 
                            "struct", "switch", "template", "this", "thread_local", "throw", 
                            "true", "try", "typedef", "typeid", "typename", "union", "unsigned", 
                            "using", "virtual", "void", "volatile", "wchar_t", "while", "xor", "xor_eq"
                        ]
                    else:  # C language
                        keywords = [
                            "auto", "break", "case", "char", "const", "continue", "default", 
                            "do", "double", "else", "enum", "extern", "float", "for", "goto", 
                            "if", "inline", "int", "long", "register", "restrict", "return", 
                            "short", "signed", "sizeof", "static", "struct", "switch", 
                            "typedef", "union", "unsigned", "void", "volatile", "while", 
                            "_Alignas", "_Alignof", "_Atomic", "_Bool", "_Complex", 
                            "_Generic", "_Imaginary", "_Noreturn", "_Static_assert", "_Thread_local"
                        ]
                    
                    # Add keyword rules
                    for keyword in keywords:
                        pattern = QRegularExpression(r'\b' + keyword + r'\b')
                        self.highlighting_rules.append((pattern, keyword_format))
                    
                    # Function declarations and calls
                    function_pattern = QRegularExpression(r'\b[A-Za-z0-9_]+(?=\()')
                    self.highlighting_rules.append((function_pattern, function_format))
                    
                    # Class/struct name pattern
                    class_pattern = QRegularExpression(r'\b(?:class|struct|enum)\s+([A-Za-z_][A-Za-z0-9_]*)')
                    self.highlighting_rules.append((class_pattern, class_format))
                    
                    # String patterns
                    self.highlighting_rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format))
                    self.highlighting_rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format))
                    
                    # Comment patterns
                    self.highlighting_rules.append((QRegularExpression(r'//[^\n]*'), comment_format))
                    self.highlighting_rules.append((QRegularExpression(r'/\*.*?\*/', QRegularExpression.PatternOption.DotMatchesEverythingOption), comment_format))
                    
                    # Preprocessor directives
                    preprocessor_format = QTextCharFormat()
                    preprocessor_format.setForeground(self.colors["preprocessor"])
                    self.highlighting_rules.append((QRegularExpression(r'#\s*[a-zA-Z]+'), preprocessor_format))
                    
                    # Number pattern
                    self.highlighting_rules.append((QRegularExpression(r'\b\d+(\.\d+)?[fFlL]?\b'), number_format))
                    
                    # Operators pattern
                    self.highlighting_rules.append((QRegularExpression(r'[\+\-\*/=<>%&\|\^~!]'), operator_format))
                
                elif self.language == "html":
                    # HTML tags
                    tag_format = QTextCharFormat()
                    tag_format.setForeground(self.colors["keyword"])
                    self.highlighting_rules.append((QRegularExpression(r'<[/]?[a-zA-Z0-9]+'), tag_format))
                    self.highlighting_rules.append((QRegularExpression(r'[/]?>'), tag_format))
                    
                    # HTML attributes
                    attribute_format = QTextCharFormat()
                    attribute_format.setForeground(self.colors["identifier"])
                    self.highlighting_rules.append((QRegularExpression(r'\s[a-zA-Z0-9-]+='), attribute_format))
                    
                    # HTML strings
                    self.highlighting_rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format))
                    self.highlighting_rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format))
                    
                    # HTML comments
                    self.highlighting_rules.append((QRegularExpression(r'<!--.*?-->', QRegularExpression.PatternOption.DotMatchesEverythingOption), comment_format))
            
            def set_language(self, language):
                """Change the language for syntax highlighting"""
                self.language = language.lower()
                self.setup_highlighting_rules()
                self.rehighlight()
            
            def highlightBlock(self, text):
                """Apply syntax highlighting to the given block of text"""
                # Apply the highlighting rules
                for pattern, format in self.highlighting_rules:
                    expression = pattern
                    match = expression.match(text)
                    index = match.capturedStart()
                    
                    while index >= 0:
                        length = match.capturedLength()
                        self.setFormat(index, length, format)
                        match = expression.match(text, index + length)
                        index = match.capturedStart()
        
        # Create a custom QPlainTextEdit subclass for code editing with line numbers
        class CodeEditor(QPlainTextEdit):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.line_number_area = LineNumberArea(self)
                
                # Connect signals
                self.blockCountChanged.connect(self.update_line_number_area_width)
                self.updateRequest.connect(self.update_line_number_area)
                self.cursorPositionChanged.connect(self.highlight_current_line)
                
                # Initial setup
                self.update_line_number_area_width(0)
                self.highlight_current_line()
                
                # Set monospace font for code
                font = QFont("Consolas")
                font.setStyleHint(QFont.StyleHint.Monospace)
                self.setFont(font)
                
                # Set tab size to 4 spaces
                self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
                
                # Modern style for the editor (VS Code-like dark theme)
                self.setStyleSheet("""
                    QPlainTextEdit {
                        background-color: #1E1E1E;
                        color: #D4D4D4;
                        border: 1px solid #2D2D2D;
                        border-radius: 4px;
                        selection-background-color: #264F78;
                        selection-color: #FFFFFF;
                        font-family: Consolas, Monaco, 'Courier New', monospace;
                        font-size: 14px;
                    }
                """)
                
                # Create syntax highlighter
                self.highlighter = VSCodeSyntaxHighlighter(self.document(), "python")
            
            def set_language(self, language):
                """Set language for syntax highlighting"""
                self.highlighter.set_language(language)
            
            # Add setText method for compatibility with QTextEdit
            def setText(self, text):
                """Compatibility method to match QTextEdit's setText"""
                self.setPlainText(text)
                
            def text(self):
                """Compatibility method to match QTextEdit's text()"""
                return self.toPlainText()
                
            def line_number_area_width(self):
                """Calculate the width of the line number area"""
                digits = 1
                max_value = max(1, self.blockCount())
                while max_value >= 10:
                    max_value //= 10
                    digits += 1
                
                space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
                return space
            
            def update_line_number_area_width(self, _):
                """Update the margin reserved for the line number area"""
                self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
            
            def update_line_number_area(self, rect, dy):
                """Update the line number area when the viewport is scrolled"""
                if dy:
                    self.line_number_area.scroll(0, dy)
                else:
                    self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
                
                if rect.contains(self.viewport().rect()):
                    self.update_line_number_area_width(0)
            
            def resizeEvent(self, event):
                """Handle resize events"""
                super().resizeEvent(event)
                
                cr = self.contentsRect()
                self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))     

            def highlight_current_line(self):
                """Highlight the line where the cursor is positioned"""
                extra_selections = []
                
                if not self.isReadOnly():
                    selection = QTextEdit.ExtraSelection()
                    line_color = QColor("#2A2A2A")  # Dark subtle highlight for current line
                    
                    selection.format.setBackground(line_color)
                    selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                    selection.cursor = self.textCursor()
                    selection.cursor.clearSelection()
                    extra_selections.append(selection)
                
                self.setExtraSelections(extra_selections)
            
            def line_number_area_paint_event(self, event):
                """Paint the line numbers"""
                painter = QPainter(self.line_number_area)
                painter.fillRect(event.rect(), QColor("#1A1A1A"))  # VS Code-like line number background
                
                block = self.firstVisibleBlock()
                block_number = block.blockNumber()
                top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
                bottom = top + round(self.blockBoundingRect(block).height())
                
                while block.isValid() and top <= event.rect().bottom():
                    if block.isVisible() and bottom >= event.rect().top():
                        number = str(block_number + 1)
                        painter.setPen(QColor("#6D6D6D"))  # VS Code-like line number color
                        painter.drawText(0, top, self.line_number_area.width() - 5, self.fontMetrics().height(),
                                        Qt.AlignmentFlag.AlignRight, number)
                    
                    block = block.next()
                    top = bottom
                    bottom = top + round(self.blockBoundingRect(block).height())
                    block_number += 1
        
        # Line number area widget
        class LineNumberArea(QWidget):
            def __init__(self, editor):
                super().__init__(editor)
                self.code_editor = editor
            
            def sizeHint(self):
                return QSize(self.code_editor.line_number_area_width(), 0)
            
            def paintEvent(self, event):
                self.code_editor.line_number_area_paint_event(event)
        
        # Replace the existing code editor with our enhanced version
        new_editor = CodeEditor()
        new_editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Copy any existing code
        if hasattr(self, 'code_editor') and self.code_editor is not None:
            # Get text from the old editor - could be QTextEdit or QPlainTextEdit
            if hasattr(self.code_editor, 'toPlainText'):
                text = self.code_editor.toPlainText()
            elif hasattr(self.code_editor, 'text'):
                text = self.code_editor.text()
            else:
                text = ""
            new_editor.setPlainText(text)
        
        # Replace the old editor in the layout
        code_output_layout = self.code_editor.parent().layout()
        old_editor_index = code_output_layout.indexOf(self.code_editor)
        code_output_layout.removeWidget(self.code_editor)
        self.code_editor.deleteLater()
        
        # Add new editor to layout at same position
        code_output_layout.insertWidget(old_editor_index, new_editor, 7)
        self.code_editor = new_editor
        
        # Define methods for the main class (self)
        def set_code_text(text):
            """Set the code text in the editor"""
            self.code_editor.setPlainText(text)
        
        def get_code_text():
            """Get the code text from the editor"""
            return self.code_editor.toPlainText()
        
        def set_language_template():
            """Set code template based on the selected language"""
            language = self.language_selector.currentText().lower()
            
            # Also update syntax highlighting
            self.code_editor.set_language(language)
            
            templates = {
                "python": '# Python code\n\ndef main():\n    print("Hello, World!")\n\nif __name__ == "__main__":\n    main()',
                "java": '// Java code\n\npublic class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, World!");\n    }\n}',
                "javascript": '// JavaScript code\n\nfunction main() {\n    console.log("Hello, World!");\n}\n\nmain();',
                "c++": '// C++ code\n\n#include <iostream>\n\nint main() {\n    std::cout << "Hello, World!" << std::endl;\n    return 0;\n}',
                "c": '// C code\n\n#include <stdio.h>\n\nint main() {\n    printf("Hello, World!\\n");\n    return 0;\n}',
                "html": '<!-- HTML code -->\n\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Hello World</title>\n</head>\n<body>\n    <h1>Hello, World!</h1>\n</body>\n</html>'
            }
            
            if language in templates:
                set_code_text(templates[language])
        
        # Properly bind methods to self
        self.set_code_text = set_code_text
        self.get_code_text = get_code_text
        self.set_language_template = set_language_template
        
        # Connect language selector to template setter
        self.language_selector.currentTextChanged.connect(self.set_language_template)

    def start_recording(self):
        if not hasattr(self, 'webcam_recorder') or self.webcam_recorder is None:
            self.webcam_recorder = BackgroundWebcamRecorder(
                token=self.session_token,
                exam_code=self.exam_code,
                user_id=self.user_id,
                exam_id=self.exam_id
            )
            self.webcam_recorder.setup_recorder(shared_camera.get_session())

        if self.webcam_recorder.start_recording():
            logging.info("Exam recording started successfully")
        else:
            logging.error("Failed to start exam recording")


    def showEvent(self, event):
        super().showEvent(event)

        available_cameras = QMediaDevices.videoInputs()
        if not available_cameras:
            logging.error("No camera devices found")
            return

        if not shared_camera.is_initialized:
            camera_device = available_cameras[0]
            if not shared_camera.initialize(camera_device):
                logging.error("Failed to initialize shared camera")
                return

        if shared_camera.start_camera():
            logging.info("Camera started successfully")
            QTimer.singleShot(1000, self.start_recording)
        else:
            logging.error("Failed to start camera")

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.webcam_recorder and self.webcam_recorder.is_ready():
            self.webcam_recorder.stop_recording()

    def update_word_count(self):
        """Update the word count for descriptive answers"""
        text = self.description_editor.toPlainText()
        word_count = len(text.split()) if text else 0
        self.word_count_label.setText(f"Word count: {word_count}")

    def set_exam_code(self, code):
        self.exam_code = code

    def set_exam_details(self, exam_details):
        self.exam_details = exam_details
        self.exam_id = exam_details.get("exam_id") or exam_details.get("examId")
        self.user_id = exam_details.get("user_id") or exam_details.get("userId") or "default_user"
        
        self.session_token = SESSION_TOKEN
        
        # Initialize timer with default values
        try:
            # Extract total time from exam details - it's in minutes
            total_time_str = exam_details.get("totalTime", "30").strip()
            total_minutes = int(total_time_str) if total_time_str else 30  # Default 30 minutes
            
            # Convert minutes to seconds for internal countdown
            self.remaining_seconds = total_minutes * 60
            
            # Format time display in hours:minutes:seconds
            self.update_time_display()
            
            # Start the timer - update every second
            self.timer.start(1000)  # 1000 ms = 1 second
        except ValueError:
            # Default to 30 minutes if there's an error parsing the time
            self.remaining_seconds = 30 * 60  # 30 minutes in seconds
            self.time_container.setText("00:30:00")
            self.timer.start(1000)
        
        # Load questions and build question panel
        question_ids = exam_details.get("questionsIds", [])
        
        fetched_questions = []
        for idx, q_id in enumerate(question_ids):
            question_data = fetch_question(q_id, self.exam_id, self.user_id, idx, first_request=False)
            if question_data:
                fetched_questions.append(question_data)
                print(f"Successfully fetched question {q_id}")
                
                # Sync with server time from the first question response
                if idx == 0 and 'remaining_time' in question_data:
                    self.sync_with_server_time(question_data['remaining_time'])
            else:
                print(f"Failed to fetch question {q_id}")
           
        
        self.questions = fetched_questions
        self.user_answers = [None] * len(self.questions)
        self.current_question_index = 0
        
        # Only build and load if we have questions
        if self.questions:
            self.build_question_panel()
            self.load_question(0)
            # Process events to ensure UI updates
            QCoreApplication.processEvents()
        else:
            # Display message if no questions are available
            self.question_label.setText("<b style='color:red'>No questions available. Please contact support.</b>")

    def update_time_display(self):
        """Update the timer display based on remaining_seconds"""
        # Format time in hours:minutes:seconds
        hours = self.remaining_seconds // 3600
        minutes = (self.remaining_seconds % 3600) // 60
        seconds = self.remaining_seconds % 60
        
        # Update the display
        self.time_container.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # Change timer color based on remaining time
        if self.remaining_seconds <= 300:  # Less than 5 minutes
            self.time_container.setStyleSheet("""
                background-color: white;
                color: #FF3333;
                font-size: 24px;
                font-weight: bold;
                border: 3px solid #FF3333;
                border-radius: 75px;
            """)

    def sync_with_server_time(self, server_remaining_time):
        """
        Synchronize the client timer with the server's remaining time
        
        Args:
            server_remaining_time: Remaining time in seconds from server
        """
        if server_remaining_time is None:
            print("Warning: Server did not provide remaining time")
            return
            
        try:
            # Convert to integer (handle string or numeric inputs)
            new_remaining = int(server_remaining_time)
            
            # Only update if the difference is significant (more than 5 seconds)
            if abs(new_remaining - self.remaining_seconds) > 5:
                print(f"Syncing timer: Local time was {self.remaining_seconds}s, server time is {new_remaining}s")
                self.remaining_seconds = new_remaining
                self.update_time_display()
            
        except (ValueError, TypeError) as e:
            print(f"Error syncing with server time: {e}")
            print(f"Received value: {server_remaining_time}, type: {type(server_remaining_time)}")

    def handle_image_timeout(self, reply, fallback_content):
        """Handle timeout for image loading requests"""
        if reply and reply.isRunning():
            reply.abort()
            print("Image loading timed out, using fallback HTML display")
            self.question_content_label.setText(fallback_content)
            self.question_content_label.show()

    def load_question(self, index, store_current=True):
        """
        Load question at the given index with improved stability to prevent window popping
        
        Args:
            index: The index of the question to load
            store_current: Whether to store the current answer before loading new question
        """
        if not self.questions or index >= len(self.questions):
            return

        # Store current window state
        was_active = self.isActiveWindow()

        # Store user answer from current question before loading new one, but only if requested
        if store_current:
            self.store_user_answer()

        self.current_question_index = index
        q_data = self.questions[index]
        
        # Sync with server time if available in the question data
        if 'remaining_time' in q_data:
            self.sync_with_server_time(q_data['remaining_time'])
        
        q_number = index + 1

        # Get question type (default to type 2 if not specified)
        question_type = q_data.get("question_type", "2")  # Default to MCQ

        # Important: Clear previous content FIRST to prevent overlapping
        self.question_content_label.clear()
        if hasattr(self, 'question_content_web'):
            self.question_content_web.setHtml("")
            self.question_content_web.hide()
        
        # Clear existing options
        self.clear_options()

        # HIDE all containers to prevent flickering and overlap
        self.description_container.hide()
        self.coding_container.hide()
        self.options_layout.parentWidget().hide()
        
        # Update question number and marks
        marks = q_data.get("question_mark", 1)
        self.question_number_pill.setText(f"• Question {q_number}")
        self.marks_label.setText(f"[Marks: {marks}]")

        # Set question type label text
        question_type_text = {
            "1": "Descriptive",
            "2": "MCQ",
            "3": "MSQ",
            "4": "Coding"
        }.get(question_type, "Unknown")
        self.question_type_label.setText(f"[Type: {question_type_text}]")

        # Update question text from question_title
        question_text = q_data.get("question_title", "No question text")
        self.question_label.setText(question_text)
        
        # Handle question_content if it exists (images, additional HTML content)
        question_content = q_data.get("question_content", "")
        
        # Handle different question types
        try:
            saved_answer = self.user_answers[index]
        except (IndexError, TypeError):
            saved_answer = None

        if question_type == "1":  # Descriptive
            # Restore saved answer if exists - before showing the container
            if saved_answer is not None:
                self.description_editor.setText(saved_answer)
            else:
                self.description_editor.clear()
            
            # Update word count
            self.update_word_count()
            
        elif question_type in ["2", "3"]:  # MCQ or MSQ
            if question_type == "2":  # MCQ - Single choice
                self.setup_mcq_options(q_data)
            
                # Restore saved answer for MCQ if exists
                if saved_answer is not None and hasattr(self, 'options_button_group'):
                    button = self.options_button_group.button(saved_answer)
                    if button:
                        button.setChecked(True)
                        
            else:  # MSQ - Multiple choice
                self.setup_msq_options(q_data)
            
                # Restore saved answer for MSQ if exists
                if saved_answer is not None:
                    for idx in saved_answer:
                        if 0 <= idx < len(self.checkbox_list):
                            self.checkbox_list[idx].setChecked(True)
        
        elif question_type == "4":  # Coding
            # Clear output area
            self.code_output.clear()
        
            # Restore saved code and language if exists
            if saved_answer is not None:
                code, language = saved_answer
                self.code_editor.setText(code)
            
                # Set language in dropdown
                lang_index = self.language_selector.findText(language)
                if lang_index >= 0:
                    self.language_selector.setCurrentIndex(lang_index)
            else:
                self.code_editor.clear()
                self.language_selector.setCurrentIndex(0)  # Default to first language

        # Update question panel buttons to mark current question
        self.update_question_buttons(index)

        # Enable/disable navigation buttons
        self.prev_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < len(self.questions) - 1)

        # FIRST show the correct container for the question type
        self.show_correct_container(question_type)
        
        # THEN handle any additional content loading after a short delay
        if question_content:
            # Wait until UI has updated before loading content
            QTimer.singleShot(50, lambda: self.display_html_content(question_content))
        
        # Process events in a controlled way to prevent unwanted focus changes
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        
        # Restore window active state if needed using a small delay
        # This prevents window flashing/flickering issues
        if was_active:
            QTimer.singleShot(10, self.activateWindow)

    def show_correct_container(self, question_type):
        """
        Show only the container for the current question type
        """
        # First hide all containers
        self.description_container.hide()
        self.coding_container.hide()
        self.options_layout.parentWidget().hide()
        
        # Then show only the appropriate container for this question type
        if question_type == "1":  # Descriptive
            self.description_container.show()
            # Set focus after a brief delay to prevent focus-related window issues
            QTimer.singleShot(50, lambda: self.description_editor.setFocus())
        elif question_type in ["2", "3"]:  # MCQ or MSQ
            self.options_layout.parentWidget().show()
        elif question_type == "4":  # Coding
            self.coding_container.show()
            # Set focus after a brief delay to prevent focus-related window issues
            QTimer.singleShot(50, lambda: self.code_editor.setFocus())

    def stable_show_containers(self, question_type):
        """
        Show appropriate containers based on question type with improved stability
        """
        # First make all containers invisible without hiding them
        # This approach prevents layout recalculation that causes window flicker
        self.description_container.setVisible(False)
        self.coding_container.setVisible(False)
        self.options_layout.parentWidget().setVisible(False)
        if hasattr(self, 'question_content_web'):
            self.question_content_web.setVisible(False)
        
        # Set the correct container visible
        if question_type == "1":  # Descriptive
            self.description_container.setVisible(True)
        elif question_type in ["2", "3"]:  # MCQ or MSQ
            self.options_layout.parentWidget().setVisible(True)
        elif question_type == "4":  # Coding
            self.coding_container.setVisible(True)
        
        # Show web content if needed
        if hasattr(self, 'question_content_web') and self.question_content_web.page().url().toString() != "about:blank":
            self.question_content_web.setVisible(True)
        
        # Update layout without triggering unnecessary events
        self.left_container.layout().activate()
        
        # Use the QApplication.processEvents with limited flags to prevent window activation
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        
        # Use a delayed focus to avoid focus-related window issues
        QTimer.singleShot(100, lambda: self.delayed_set_focus(question_type))


    def delayed_set_focus(self, question_type):
        """
        Set focus to the appropriate widget after a delay to prevent window flashing
        while maintaining the original window state
        """
        # Store current active window to avoid unwanted focus changes
        active_window = QApplication.activeWindow()
        
        if question_type == "1":  # Descriptive
            # Focus on editor but preserve window state
            self.description_editor.setFocus(Qt.FocusReason.MouseFocusReason)
        elif question_type == "4":  # Coding
            # Focus on code editor but preserve window state
            self.code_editor.setFocus(Qt.FocusReason.MouseFocusReason)
        else:
            # For MCQ/MSQ, focus on the container
            self.left_container.setFocus(Qt.FocusReason.MouseFocusReason)
        
        # If we had an active window before, restore its activation state
        if active_window and active_window != self:
            QTimer.singleShot(50, lambda: active_window.activateWindow()) 

    def resizeEvent(self, event):
        """Handle resize events to adjust the web view if needed"""
        super().resizeEvent(event)
        
        # Re-adjust web view height if it's visible
        if hasattr(self, 'question_content_web') and not self.question_content_web.isHidden():
            self.question_content_web.page().runJavaScript(
                "document.body.scrollHeight",
                self.adjust_web_view_height
            )
    def handle_image_timeout(self, reply, fallback_content):
        """Handle timeout for image loading requests"""
        if reply.isRunning():
            # If the request is still running after timeout, abort it
            reply.abort()
            print("Image loading timed out. Using fallback content.")
            self.question_content_label.setText(fallback_content)
            self.question_content_label.show()

    def update_timer(self):
        """Update the timer display and check if time is up"""
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self.update_time_display()
        else:
            # Time is up, stop the timer
            self.timer.stop()
            self.time_container.setText("00:00:00")
            self.time_container.setStyleSheet("""
                background-color: white;
                color: #FF3333;
                font-size: 24px;
                font-weight: bold;
                border: 3px solid #FF3333;
                border-radius: 75px;
            """)

            # Show time's up message box
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Time's Up!")
            msg_box.setText("Your exam time has ended. Your answers will be submitted automatically.")
            msg_box.setIcon(QMessageBox.Icon.Warning)

            # Use a single-shot timer to show the message box briefly and then submit
            QTimer.singleShot(3000, msg_box.close)  # Close after 3 seconds
            msg_box.exec()

            # Submit the exam automatically
            self.auto_submit_exam()
            

    # New method to ensure proper sizing of panels
    def adjustSizeOfPanels(self, question_type):
        """
        Adjust sizes of panels based on question type with improved stability
        Replaced the problematic resize approach with a more stable method
        """
        # First, hide all containers
        self.description_container.hide()
        self.coding_container.hide()
        self.options_layout.parentWidget().hide()
        
        # Then show only the relevant container with proper sizing
        if question_type == "1":  # Descriptive
            self.description_container.show()
        elif question_type in ["2", "3"]:  # MCQ or MSQ
            self.options_layout.parentWidget().show()
        elif question_type == "4":  # Coding
            self.coding_container.show()
            
        # Update layout properly without forcing resize
        self.left_container.updateGeometry()
        self.left_container.layout().update()
        
        # Make sure the web view remains visible if it has content
        if hasattr(self, 'question_content_web') and not self.question_content_web.isHidden():
            self.question_content_web.show()
      
         
    def setup_mcq_options(self, q_data):
        """Set up radio buttons for MCQ (single choice) questions"""
        # Create options button group (reset it)
        if self.options_button_group:
            self.options_button_group.deleteLater()
        self.options_button_group = QButtonGroup(self)
        self.options_button_group.setExclusive(True)
        
        # Add new options
        options = q_data.get("question_options", [])
        option_letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
        
        for i, option in enumerate(options):
            option_text = option.get("name", f"Option {i+1}")
            letter = option_letters[i] if i < len(option_letters) else str(i+1)
            
            # Create option row layout
            option_row_widget = QWidget()
            option_row = QHBoxLayout(option_row_widget)
            option_row.setContentsMargins(0, 0, 0, 0)
            option_row.setSpacing(15)
            
            # Apply attractive styling to container widget
            option_row_widget.setStyleSheet("""
                QWidget {
                    background-color: #EBF1F9;
                    border-radius: 8px;
                    padding-top: 15px;
                    padding-bottom: 15px;
                    padding-left: 10px;
                    padding-right: 10px;
                    border: 1px solid #EBF1F9;
                }
                QWidget:hover {
                    background-color: #EBF1F9;
                    border: 1px solid #EBF1F9;
                }
            """)
            
            # Radio button with proper styling
            rb = QRadioButton()
            rb.setObjectName(f"option_radio_{i}")
            rb.setMinimumWidth(30)
            rb.setFixedWidth(30)
            rb.setStyleSheet("""
                QRadioButton {
                    background-color: transparent;
                    padding: 0px;
                    margin-left: 10px;
                }
            """)
            
            # Label with option text
            option_label = QLabel(f"{letter}. {option_text}")
            option_label.setStyleSheet("""
                QLabel {
                    font-size: 15px;
                    font-weight: 500;
                    color: #02205b;
                    background-color: transparent;
                }
            """)
            option_label.setWordWrap(True)
            
            # Add to layout
            option_row.addWidget(rb)
            option_row.addWidget(option_label, 1)  # Give label stretch factor
            option_row.addStretch()
            
            # Add to grid layout in 2-column format
            row = i // 2
            col = i % 2
            self.options_layout.addWidget(option_row_widget, row, col)
            self.options_button_group.addButton(rb, i)
        
        # Restore selected answer if any
        if self.user_answers[self.current_question_index] is not None:
            selected_index = self.user_answers[self.current_question_index]
            btns = self.options_button_group.buttons()
            if 0 <= selected_index < len(btns):
                btns[selected_index].setChecked(True)

    def setup_msq_options(self, q_data):
        """Set up checkboxes for MSQ (multiple choice) questions"""
        # Clear previous checkbox list
        self.checkbox_list = []
        
        # Add new options
        options = q_data.get("question_options", [])
        option_letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
        
        for i, option in enumerate(options):
            option_text = option.get("name", f"Option {i+1}")
            letter = option_letters[i] if i < len(option_letters) else str(i+1)
            
            # Create option row layout
            option_row_widget = QWidget()
            option_row = QHBoxLayout(option_row_widget)
            option_row.setContentsMargins(0, 0, 0, 0)
            option_row.setSpacing(15)
            
            # Apply attractive styling to container widget
            option_row_widget.setStyleSheet("""
                QWidget {
                    background-color: #EBF1F9;
                    border-radius: 8px;
                    padding-top: 15px;
                    padding-bottom: 15px;
                    padding-left: 10px;
                    padding-right: 10px;
                    border: 1px solid #EBF1F9;
                }
                QWidget:hover {
                    background-color: #EBF1F9;
                    border: 1px solid #EBF1F9;
                }
            """)
            
            # Checkbox with proper styling
            cb = QCheckBox()
            cb.setObjectName(f"option_checkbox_{i}")
            cb.setMinimumWidth(30)
            cb.setFixedWidth(30)
            cb.setStyleSheet("""
                QCheckBox {
                    background-color: transparent;
                    padding: 0px;
                    margin-left: 10px;
                }
                QCheckBox::indicator {
                    width: 20px;
                    height: 20px;
                }
            """)
            
            # Label with option text
            option_label = QLabel(f"{letter}. {option_text}")
            option_label.setStyleSheet("""
                QLabel {
                    font-size: 15px;
                    font-weight: 500;
                    color: #02205b;
                    background-color: transparent;
                }
            """)
            option_label.setWordWrap(True)
            
            # Add to layout
            option_row.addWidget(cb)
            option_row.addWidget(option_label, 1)  # Give label stretch factor
            option_row.addStretch()
            
            # Add to grid layout in 2-column format (just like MCQ options)
            row = i // 2
            col = i % 2
            self.options_layout.addWidget(option_row_widget, row, col)
            self.checkbox_list.append(cb)
        
        # Restore selected answers if any
        if self.user_answers[self.current_question_index] is not None:
            selected_indices = self.user_answers[self.current_question_index]
            for i, cb in enumerate(self.checkbox_list):
                cb.setChecked(i in selected_indices)

    def clear_options(self):
        # Clear all options layout widgets and layouts
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Clear sub-layouts
                while item.layout().count():
                    sub_item = item.layout().takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()
        
        # Reset button group
        if hasattr(self, 'options_button_group') and self.options_button_group:
            self.options_button_group.deleteLater()
            self.options_button_group = QButtonGroup(self)
            self.options_button_group.setExclusive(True)
    
    # Clear checkbox list
        self.checkbox_list = []

    def update_question_buttons(self, current_index):
        # Update the styling of question buttons to reflect status
        for i in range(self.question_panel.count()):
            item = self.question_panel.itemAt(i)
            if item and item.widget():
                btn = item.widget()
                
                # Get the question number from button text (1-based)
                q_index = int(btn.text()) - 1
                
                if q_index == current_index:
                    # Current question
                    btn.setStyleSheet("""
                        background-color: #0D2144;
                        color: white;
                        border-radius: 20px;
                        font-weight: bold;
                    """)
                elif self.user_answers[q_index] is not None:
                    # Answered question
                    btn.setStyleSheet("""
                        background-color: #8BC34A;
                        color: white;
                        border-radius: 20px;
                    """)
                else:
                    # Not visited or not answered
                    btn.setStyleSheet("""
                        background-color: #E1E8F5;
                        color: #333;
                        border-radius: 20px;
                    """)

    def build_question_panel(self):
        # Clear existing buttons
        for i in reversed(range(self.question_panel.count())):
            widget = self.question_panel.itemAt(i).widget()
            if widget:
                self.question_panel.removeWidget(widget)
                widget.deleteLater()
        
        # Create new buttons
        num_cols = 5
        for i in range(len(self.questions)):
            question_btn = QPushButton(str(i + 1))
            question_btn.setFixedSize(40, 40)
            
            # Default style (not visited)
            question_btn.setStyleSheet("""
                background-color: #E1E8F5;
                color: #333;
                border-radius: 20px;
            """)
            
            # Connect button to jump to question
            question_btn.clicked.connect(lambda checked, idx=i: self.jump_to_question(idx))
            
            row = i // num_cols
            col = i % num_cols
            self.question_panel.addWidget(question_btn, row, col)
        
        # Mark first question as current
        if self.question_panel.count() > 0:
            first_btn = self.question_panel.itemAt(0).widget()
            first_btn.setStyleSheet("""
                background-color: #0D2144;
                color: white;
                border-radius: 20px;
                font-weight: bold;
            """)

    def store_user_answer(self):
        """Store and save the user's answer for the current question"""
        # Don't save if exam is already submitted
        if hasattr(self, 'exam_submitted') and self.exam_submitted:
            return
            
        if not self.questions:
            return
            
        current_question = self.questions[self.current_question_index]
        question_type = current_question.get("question_type", "2")  # Default to MCQ
        
        # Try different possible ID field names
        question_id = current_question.get("id") or current_question.get("question_id") or current_question.get("questionId")
        
        # Ensure we have a valid question ID
        if not question_id:
            print("ERROR: Could not find valid question ID in question data")
            return
        
        # Get previous answer safely with try-except to avoid errors
        try:
            previous_answer = self.user_answers[self.current_question_index]
        except (KeyError, IndexError):
            previous_answer = None
        
        new_answer = None
        if question_type == "1":  # Descriptive
            text = self.description_editor.toPlainText()
            new_answer = text if text.strip() else None
            
        elif question_type == "2":  # MCQ - Single choice
            if hasattr(self, 'options_button_group') and self.options_button_group:
                selected_id = self.options_button_group.checkedId()
                new_answer = selected_id if selected_id != -1 else None
                
        elif question_type == "3":  # MSQ - Multiple choice
            selected_indices = []
            for i, cb in enumerate(self.checkbox_list):
                if cb.isChecked():
                    selected_indices.append(i)
            new_answer = selected_indices if selected_indices else None
            
        elif question_type == "4":  # Coding
            code = self.code_editor.toPlainText()
            language = self.language_selector.currentText()
            if code.strip():
                new_answer = (code, language)
            else:
                new_answer = None
        
        # Update the answer in memory (local storage)
        self.user_answers[self.current_question_index] = new_answer
        
        # Save to API if the answer has changed
        if new_answer != previous_answer:
            print(f"Saving answer for question {question_id}. Previous: {previous_answer}, New: {new_answer}")
            self.save_answer_to_api(question_id, question_type, new_answer)
        
        return new_answer

    def save_answer_to_api(self, question_id, question_type, answer):
        """Save a single answer to the API"""
        if not self.session_token:
            print("Warning: No session token provided. Cannot save answer to API.")
            return False
        
        try:
            # Call the API function
            result = save_question_answer(
                self.exam_id,
                self.user_id,
                question_id,
                question_type,
                answer,
                self.session_token
            )
            
            if result:
                print(f"Successfully saved answer for question {question_id}")
                return True
            else:
                print(f"Failed to save answer for question {question_id}")
                return False
                
        except Exception as e:
            print(f"Error saving answer for question {question_id}: {str(e)}")
            return False
        
    def run_code(self):
        """Execute the code using the remote compiler API with proper error handling"""
        code = self.code_editor.toPlainText()
        language = self.language_selector.currentText().lower()
        
        if not code.strip():
            self.code_output.setPlainText("Error: No code to run.")
            return
        
        # Show loading state
        self.code_output.setPlainText("Running code, please wait...")
        original_button_text = self.run_code_button.text()
        self.run_code_button.setText("Running...")
        self.run_code_button.setEnabled(False)
        
        # Use PyQt's QNetworkAccessManager for non-blocking API calls

        
        # Create network manager if it doesn't exist
        if not hasattr(self, 'network_manager'):
            self.network_manager = QNetworkAccessManager()
        
        # Prepare the request
        url = QUrl("https://stageevaluate.sentientgeeks.us/wp-content/themes/questioner/app/compiler.php")
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, 
                        "application/x-www-form-urlencoded")
        
        # Prepare form data
        query = QUrlQuery()
        query.addQueryItem("language", language)
        query.addQueryItem("code", code)
        post_data = query.toString().encode()
        
        # Send request
        reply = self.network_manager.post(request, post_data)
        
        # Handle response
        def handle_response():
            self.run_code_button.setText(original_button_text)
            self.run_code_button.setEnabled(True)
            
            if reply.error() == QNetworkReply.NetworkError.NoError:
                response_data = reply.readAll().data().decode()
                self.code_output.setPlainText(response_data)
            else:
                error_msg = f"Network Error: {reply.errorString()}"
                self.code_output.setPlainText(error_msg)
            
            reply.deleteLater()
        
        # Connect to the finished signal
        reply.finished.connect(handle_response)

    def go_previous(self):
        """Navigate to previous question with improved stability"""
        if self.current_question_index > 0:
            # Store current answer
            self.store_user_answer()
            
            # Hide all content containers immediately to prevent content overlap
            self.description_container.hide()
            self.coding_container.hide()
            self.options_layout.parentWidget().hide()
            if hasattr(self, 'question_content_web'):
                self.question_content_web.hide()
                self.question_content_web.setHtml("")
            
            # Remember if window was active
            was_active = self.isActiveWindow()
            
            # Move to previous question with a slight delay
            new_index = self.current_question_index - 1
            QTimer.singleShot(50, lambda: self.load_question(new_index, store_current=False))
            
            # Restore window activation state
            if was_active:
                QTimer.singleShot(100, self.activateWindow)

    def go_next(self):
        """Navigate to next question with improved stability"""
        if self.current_question_index < len(self.questions) - 1:
            # Store current answer
            self.store_user_answer()
            
            # Hide all content containers immediately to prevent content overlap
            self.description_container.hide()
            self.coding_container.hide()
            self.options_layout.parentWidget().hide()
            if hasattr(self, 'question_content_web'):
                self.question_content_web.hide()
                self.question_content_web.setHtml("")
            
            # Remember if window was active
            was_active = self.isActiveWindow()
            
            # Move to next question with a slight delay
            new_index = self.current_question_index + 1
            QTimer.singleShot(50, lambda: self.load_question(new_index, store_current=False))
            
            # Restore window activation state
            if was_active:
                QTimer.singleShot(100, self.activateWindow)

    def jump_to_question(self, index):
        """
        Jump to a specific question with improved stability to prevent window popping
        """
        # Only take action if we're changing questions
        if index != self.current_question_index:
            # Store current answer first
            self.store_user_answer()
            
            # Remember if the window is currently active
            was_active = self.isActiveWindow()
            
            # Hide all content containers immediately to prevent content overlap
            self.description_container.hide()
            self.coding_container.hide()
            self.options_layout.parentWidget().hide()
            if hasattr(self, 'question_content_web'):
                self.question_content_web.hide()
            
            # Clear previous web content to prevent overlap
            if hasattr(self, 'question_content_web'):
                self.question_content_web.setHtml("")
            
            # Clear question content label too
            self.question_content_label.clear()
            
            # Use a timer with short delay to load the new question
            # This helps prevent focus issues and flickering
            QTimer.singleShot(50, lambda: self.load_question(index, store_current=False))
            
            # Restore window active state if needed using a small delay
            if was_active:
                QTimer.singleShot(100, self.activateWindow)
        else:
            # Just refresh the current question if jumping to the same one
            # but don't store the answer again (would be redundant)
            self.load_question(index, store_current=False)

    def delayed_jump_to_question(self, index):
        """
        Perform the actual jump to question after a slight delay
        """
        self.current_question_index = index
        self.load_question(index, store_current=False)

    def initialize_user_answers(self):
        """
        Initialize user answers storage - call this during initialization
        """
        # Initialize empty user answers
        if not hasattr(self, 'user_answers'):
            self.user_answers = {}
            
    def emergency_submit(self):
        """Emergency submit function with guaranteed exit"""
        logging.info("EMERGENCY SUBMIT triggered - preparing for forced exit")
        
        # No need to check if already submitted - we're doing an emergency exit regardless
        
        try:
            # Try to store current answers - don't let failure prevent exit
            try:
                self.store_user_answer()
                logging.info("Successfully stored current answers")
            except Exception as e:
                logging.error(f"Failed to store answers during emergency exit: {e}")
            
            # Try to stop the timer
            try:
                if hasattr(self, 'timer') and self.timer.isActive():
                    self.timer.stop()
                    logging.info("Timer stopped")
            except Exception as e:
                logging.error(f"Failed to stop timer during emergency exit: {e}")
            
            # Try to stop webcam recording
            try:
                if self.webcam_recorder:
                    self.webcam_recorder.stop_recording()
                    logging.info("Webcam recording stopped")
            except Exception as e:
                logging.error(f"Failed to stop webcam during emergency exit: {e}")
            
            # Try to send notification
            try:
                submit_reason = "EMERGENCY SUBMIT"
                self.send_onstop_notification(submit_reason)
                logging.info("Successfully sent onstop notification")
            except Exception as e:
                logging.error(f"Failed to send notification during emergency exit: {e}")
                
            # Mark exam as submitted
            self.exam_submitted = True
            logging.info("Exam marked as submitted")
        except Exception as e:
            logging.error(f"Top-level error during emergency submit: {e}")
        
        # Try writing to a special log file to confirm emergency exit was triggered
        try:
            with open("emergency_exit.log", "w") as f:
                import datetime
                f.write(f"Emergency exit triggered at {datetime.datetime.now()}")
        except:
            pass
        
        # Force exit no matter what happened above
        logging.info("EMERGENCY EXIT - Terminating process NOW")
        import os
        os._exit(0) 

    def submit_exam(self):
        """Regular submit function that guarantees exit when requested"""
        if self.check_if_submitted():
            return
            
        # Save the current answer first
        self.store_user_answer()
        
        # Show confirmation dialog
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Submit Exam")
        msg_box.setText("Are you sure you want to submit your exam?")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            # Stop the timer when manually submitting
            if hasattr(self, 'timer') and self.timer.isActive():
                self.timer.stop()
            
            # Stop webcam recording
            if self.webcam_recorder:
                try:
                    self.webcam_recorder.stop_recording()
                    logging.info("Webcam recording stopped after manual exam submission")
                except Exception as e:
                    logging.error(f"Error stopping webcam: {e}")
            
            # Check for any unanswered questions and inform user
            unanswered = sum(1 for answer in self.user_answers if answer is None)
            if unanswered > 0:
                warning_box = QMessageBox()
                warning_box.setWindowTitle("Warning")
                warning_box.setText(f"You have {unanswered} unanswered question(s). Do you still want to submit?")
                warning_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                warning_box.setDefaultButton(QMessageBox.StandardButton.No)
                warning_box.setWindowFlags(warning_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
                
                if warning_box.exec() == QMessageBox.StandardButton.No:
                    # Resume timer if user cancels submission
                    if hasattr(self, 'timer'):
                        self.timer.start(1000)
                    # Resume recording if user cancels submission
                    if self.webcam_recorder:
                        try:
                            self.webcam_recorder.start_recording()
                        except Exception as e:
                            logging.error(f"Error restarting webcam: {e}")
                    return  # Don't submit if user cancels
            
            try:
                # Set submit reason for manual submission
                submit_reason = "user submit"
                
                # Try to send the onstop notification - don't let failures prevent exit
                try:
                    self.send_onstop_notification(submit_reason)
                    logging.info("Successfully sent onstop notification")
                except Exception as e:
                    logging.error(f"Failed to send onstop notification: {e}")
                
                # Mark exam as submitted
                self.exam_submitted = True
                
                # Try to disable all inputs
                try:
                    self.disable_all_inputs()
                    logging.info("Successfully disabled all inputs")
                except Exception as e:
                    logging.error(f"Failed to disable inputs: {e}")
                
                # Show success message
                success_box = QMessageBox()
                success_box.setWindowTitle("Exam Submitted")
                success_box.setText("Your exam has been submitted successfully! Do you want to close the application?")
                success_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                success_box.setDefaultButton(QMessageBox.StandardButton.Yes)
                success_box.setWindowFlags(success_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
                
                result = success_box.exec()
                
                # Most reliable exit method
                if result == QMessageBox.StandardButton.Yes:
                    logging.info("User confirmed exit after submission - force terminating")
                    # Force-terminate the process
                    import os
                    os._exit(0)  # Force immediate termination
                
            except Exception as e:
                # Show error message if submission fails
                error_box = QMessageBox()
                error_box.setWindowTitle("Submission Error")
                error_box.setText(f"Failed to submit exam: {str(e)}")
                error_box.setWindowFlags(error_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
                error_box.exec()
                
                # Resume timer if submission fails
                if hasattr(self, 'timer'):
                    self.timer.start(1000)
                # Resume recording if submission fails
                if self.webcam_recorder:
                    try:
                        self.webcam_recorder.start_recording()
                    except Exception as e:
                        logging.error(f"Error restarting webcam: {e}")
                        
    def auto_submit_exam(self):
        """Automatically submit the exam when time is up"""
        if self.check_if_submitted():
            return
            
        # Store current answers first
        self.store_user_answer()
        
        # Stop webcam recording
        if self.webcam_recorder:
            self.webcam_recorder.stop_recording()
            logging.info("Webcam recording stopped after auto exam submission")
        
        print(f"Time's up! Auto-submitting exam {self.exam_id} with code {self.exam_code} for user {self.user_id}")
        
        try:
            # Set the submit reason for time end
            submit_reason = "Auto Submit Time Ends"
            
            # Send the onstop API call
            self.send_onstop_notification(submit_reason)
            
            # Mark exam as submitted
            self.exam_submitted = True
            
            # We've already saved answers one by one, now disable all inputs
            self.disable_all_inputs()
            
            # Show success message
            success_box = QMessageBox()
            success_box.setWindowTitle("Exam Submitted")
            success_box.setText("Your exam has been submitted automatically as time expired. Do you want to close the application?")
            success_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            success_box.setDefaultButton(QMessageBox.StandardButton.Yes)
            
            result = success_box.exec()
            if result == QMessageBox.StandardButton.Yes:
                # Fix for proper exit
                logging.info("User confirmed exit after auto submission - closing application")
                import sys
                os._exit(0)  # Force exit with success code
            
        except Exception as e:
            # Show error message if submission fails
            error_box = QMessageBox()
            error_box.setWindowTitle("Submission Error")
            error_box.setText(f"Failed to submit exam: {str(e)}")
            error_box.exec()
            
            # Resume recording if submission fails
            if self.webcam_recorder:
                self.webcam_recorder.start_recording()

    def check_if_submitted(self):
        """Check if exam is already submitted and prevent further actions"""
        if hasattr(self, 'exam_submitted') and self.exam_submitted:
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Exam Submitted")
            msg_box.setText("Your exam has already been submitted. No further changes are allowed.")
            msg_box.exec()
            return True
        return False
 

    def send_onstop_notification(self, submit_reason):
        """
        Send the onstop notification to the API endpoint
        """
        try:
            # Check if webcam_recorder exists and has the necessary attributes
            if not hasattr(self, 'webcam_recorder') or not self.webcam_recorder:
                logging.error("Cannot send onstop notification: webcam_recorder not available")
                return False
                
            # Get API endpoint and token from the webcam recorder
            api_endpoint = self.webcam_recorder.api_endpoint
            token = self.webcam_recorder.token
            
            if not token:
                logging.error("Cannot send onstop notification: token not available")
                return False
                
            # Prepare the form data
            form_data = {
                'exam_id': (None, str(self.exam_id)),
                'user_id': (None, str(self.user_id)),
                'type': (None, 'onstop'),
                'file_name': (None, f"{self.user_id}-{self.exam_id}"),
                'exam_submit_reason': (None, submit_reason)
            }
            
            # Set headers with token
            headers = {
                'Authorization': f'Bearer {token}'
            }
            
            # Send POST request
            logging.debug(f"Sending onstop notification to: {api_endpoint}")
            logging.debug(f"Form data: {form_data}")
            
            response = requests.post(
                api_endpoint,
                files=form_data,
                headers=headers
            )
            
            # Log response details
            logging.debug(f"Response status code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    json_response = response.json()
                    if json_response.get('status') is True:
                        logging.info("Successfully sent onstop notification")
                        return True
                    else:
                        logging.warning(f"Onstop notification response not as expected: {json_response}")
                        return False
                except ValueError:
                    logging.error("Could not parse response as JSON")
                    return False
            else:
                # More detailed error logging
                logging.error(f"Failed to send onstop notification. Status code: {response.status_code}")
                logging.error(f"Response text: {response.text}")
                return False
                    
        except requests.RequestException as req_err:
            logging.error(f"Request error sending onstop notification: {str(req_err)}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error sending onstop notification: {str(e)}")
            logging.exception("Stack trace:")
            return False

    # Add new method to disable all inputs after submission
    def disable_all_inputs(self):
        """Disable all input elements after exam submission"""
        # Disable description editor
        self.description_editor.setReadOnly(True)
        self.description_editor.setStyleSheet("""
            border: 1px solid #D0D0D0;
            border-radius: 4px;
            padding: 8px;
            background-color: #F5F5F5;
            font-size: 14px;
            color: #666666;
        """)
        
        # Disable code editor
        self.code_editor.setReadOnly(True)
        self.code_editor.setStyleSheet("""
            border: 1px solid #D0D0D0;
            border-radius: 4px;
            padding: 8px;
            background-color: #2A2A2A;
            color: #AAAAAA;
            font-family: Consolas, Monaco, 'Courier New', monospace;
            font-size: 14px;
        """)
        
        # Disable language selector and run button
        self.language_selector.setEnabled(False)
        self.run_code_button.setEnabled(False)
        
        # Disable all radio buttons and checkboxes
        for i in range(self.options_layout.count()):
            item = self.options_layout.itemAt(i)
            if item and item.layout():
                # Look for widgets in nested layouts
                for j in range(item.layout().count()):
                    widget = item.layout().itemAt(j).widget()
                    if isinstance(widget, (QRadioButton, QCheckBox)):
                        widget.setEnabled(False)
        
        # Disable all navigation buttons
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.submit_button.setEnabled(False)
        
        # Disable question panel buttons
        for i in range(self.question_panel.count()):
            item = self.question_panel.itemAt(i)
            if item and item.widget():
                item.widget().setEnabled(False)
        
        # Set a global flag to indicate exam is submitted
        self.exam_submitted = True
        
    def force_ui_refresh(self):
        # Save current state
        current_index = self.current_question_index
        
        # Make sure we have the current question data
        if self.questions and 0 <= current_index < len(self.questions):
            question_text = self.questions[current_index].get("question_title", "")
            question_type = self.questions[current_index].get("question_type", "2")  # Default to MCQ
            
            # Update with forced styling
            formatted_text = f"""
            <div style='color: black; font-size: 16px; font-weight: bold; padding: 10px; margin: 10px;'>
                {question_text}
            </div>
            """
            
            # Set text with direct styling
            self.question_label.setText(formatted_text)
            
            # Ensure the label is properly sized and visible
            self.question_label.setMinimumSize(400, 200)
            self.question_label.adjustSize()
            
            # Force immediate update
            self.question_label.repaint()
            
            # Handle question type-specific UI elements
            if question_type == "1":  # Descriptive
                print("UI refresh - Ensuring description text editor is visible")
                self.description_container.show()
                self.description_editor.repaint()
                
            elif question_type == "2":  # MCQ
                options = self.questions[current_index].get("question_options", [])
                print(f"UI refresh - Ensuring {len(options)} MCQ options are visible")
                
                # Make sure options are created again if needed
                if not self.options_layout.count() and options:
                    self.setup_mcq_options(self.questions[current_index])
                    
            elif question_type == "3":  # MSQ
                options = self.questions[current_index].get("question_options", [])
                print(f"UI refresh - Ensuring {len(options)} MSQ options are visible")
                
                # Make sure options are created again if needed
                if not self.options_layout.count() and options:
                    self.setup_msq_options(self.questions[current_index])
                    
            elif question_type == "4":  # Coding
                print("UI refresh - Ensuring code editor is visible")
                self.coding_container.show()
                self.code_editor.repaint()
            
            QCoreApplication.processEvents()
            
            print(f"UI refresh - Question text: '{question_text}'")
            print(f"UI refresh - Question type: '{question_type}'")
            print(f"UI refresh - Label size: {self.question_label.size().width()}x{self.question_label.size().height()}")
            
# 7. Main Window with Stacked Pages
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Evaluate App")
        self.resize(1200, 800)
        
        # Set window flags to prevent normal window controls
        # Note: we're using a more comprehensive approach than just FramelessWindowHint
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |  # No frame
            Qt.WindowType.WindowStaysOnTopHint | # Always on top
            Qt.WindowType.NoDropShadowWindowHint  # No shadow
        )
        
        # Prevent minimizing by capturing the window state change event
        self.setWindowState(Qt.WindowState.WindowActive)

        self.exam_code = None
        self.token = None
        self.exam_details = None
        
        # Create an emergency submit action that can be triggered via keyboard
        self.emergency_submit_action = QAction("Emergency Submit", self)
        self.emergency_submit_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.emergency_submit_action.triggered.connect(self.trigger_emergency_submit)
        self.addAction(self.emergency_submit_action)

        # Setup UI components
        self.stack = QStackedWidget(self)
        self.setCentralWidget(self.stack)

        self.exam_code_page = ExamCodePage(self.show_system_check_page)
        self.system_check_page = SystemCheckPage(self.show_instructions_page)
        self.instructions_page = ExamInstructionsPage(self.show_exam_page)
        self.exam_page = ExamPage()

        self.stack.addWidget(self.exam_code_page)
        self.stack.addWidget(self.system_check_page)
        self.stack.addWidget(self.instructions_page)
        self.stack.addWidget(self.exam_page)
        self.stack.setCurrentIndex(0)

        # Install Qt event filter for key blocking - this will catch Qt-specific events
        self.installEventFilter(self)

        logging.info("MainWindow initialized; showing in full screen.")
        self.showFullScreen()
        
        # Additional setup to ensure the window stays in focus and can't be minimized
        self.setup_focus_protection()
    
    def trigger_emergency_submit(self):
        """Emergency submit handler with guaranteed exit"""
        logging.info("Emergency submit action triggered")
        
        try:
            # First, check if we're on the exam page
            current_widget = self.stack.currentWidget()
            
            if current_widget == self.exam_page:
                # Try the exam page's emergency submit
                try:
                    logging.info("Calling exam page emergency submit")
                    self.exam_page.emergency_submit()
                    # If we reach here, the emergency submit didn't exit
                    logging.warning("exam_page.emergency_submit() returned without exiting")
                except Exception as e:
                    logging.error(f"Error in exam_page.emergency_submit(): {e}")
            else:
                logging.info("Emergency exit triggered outside exam page")
        except Exception as e:
            logging.error(f"Error determining current page: {e}")
        
        # If we reach here, the above methods failed to exit
        # Fall back to direct process termination
        logging.info("Fallback emergency exit - terminating process directly")
        import os
        os._exit(0)  # Force immediate termination
        
    def setup_focus_protection(self):
        """Setup additional protections to keep app in focus"""
        # Set focus policy to ensure our window maintains focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Create a timer to periodically check and restore focus if needed
        from PyQt6.QtCore import QTimer
        self.focus_timer = QTimer(self)
        self.focus_timer.timeout.connect(self.check_focus)
        # Reduce check frequency to avoid competing with dialog handling
        self.focus_timer.start(750)  # Check less frequently (increased from 500ms to 750ms)
        
        # Add property to track if we're in a dialog interaction
        self.setProperty("in_dialog_interaction", False)

    def improved_delayed_focus_restore(self):
        """Improved delayed focus restoration that respects dialog states"""
        global SUPPRESS_FOCUS_CHECKS
        
        # Don't restore focus if dialogs are active
        if SUPPRESS_FOCUS_CHECKS:
            logging.debug("Not restoring focus - dialog active")
            return
            
        # Double-check for any visible dialogs
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) or isinstance(widget, QMessageBox) or widget.inherits("QDialog"):
                if widget.isVisible():
                    global_suppress_focus_checks(True)
                    logging.debug("Not restoring focus - dialog detected")
                    return
            
            # Also check for modal dialogs
            if hasattr(widget, 'isModal') and widget.isModal() and widget.isVisible():
                global_suppress_focus_checks(True)
                logging.debug("Not restoring focus - modal dialog detected")
                return
        
        # It's safe to restore focus now
        logging.debug("Delayed focus restore - activating window")
        self.activateWindow()
        self.raise_()

    def stop_focus_checking(self):
        """Stop all focus checking to prevent dialog box loops"""
        if hasattr(self, 'focus_timer') and self.focus_timer.isActive():
            self.focus_timer.stop()
            logging.info("Stopped focus checking timer")
        
        # Also stop the app level timer if it exists
        for timer in self.findChildren(QTimer):
            if timer.isActive():
                timer.stop()
                logging.info("Stopped additional timer")

    def check_focus(self):
        """Check if our window has focus and restore it if not - with improved dialog awareness"""
        # Don't try to restore focus if an exam is already submitted
        if hasattr(self, 'exam_page') and hasattr(self.exam_page, 'exam_submitted') and self.exam_page.exam_submitted:
            # Stop checking focus if exam is submitted
            if hasattr(self, 'focus_timer') and self.focus_timer.isActive():
                self.focus_timer.stop()
                logging.info("Stopped focus checking - exam already submitted")
            return
        
        # Skip focus check if any dialog is active - using the global flag
        global SUPPRESS_FOCUS_CHECKS
        if SUPPRESS_FOCUS_CHECKS:
            logging.debug("Dialog active - skipping focus check")
            return
        
        # Enhanced dialog detection
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) or isinstance(widget, QMessageBox) or widget.inherits("QDialog"):
                if widget.isVisible():
                    # Dialog found - don't restore focus
                    return
                    
            # Also check for modal dialogs
            if hasattr(widget, 'isModal') and widget.isModal() and widget.isVisible():
                return
        
        # Now safe to check and restore focus
        active_window = QGuiApplication.focusWindow()
        if active_window is not self:
            # Make sure we're not stealing focus from a dialog component
            focused_widget = QApplication.focusWidget()
            if focused_widget:
                # Check if the focused widget is part of a dialog
                parent = focused_widget
                while parent:
                    if isinstance(parent, QDialog) or isinstance(parent, QMessageBox):
                        # Don't restore focus if a dialog has focus
                        return
                    if hasattr(parent, 'parent'):
                        parent = parent.parent()
                    else:
                        break
            
            logging.info("Window lost focus - restoring")
            # Add a small delay before restoring focus
            QTimer.singleShot(100, self.delayed_focus_restore)

    def changeEvent(self, event):
        """Override to prevent window state changes like minimizing, with dialog awareness"""
        if event.type() == QEvent.Type.WindowStateChange:
            # Skip if we're in a dialog interaction
            global SUPPRESS_FOCUS_CHECKS
            if SUPPRESS_FOCUS_CHECKS:
                # Let dialog handle its own state
                super().changeEvent(event)
                return
                
            # If the window state is changing to minimized, prevent it
            if self.windowState() & Qt.WindowState.WindowMinimized:
                logging.info("Preventing window minimization")
                # Restore the window state to active
                self.setWindowState(Qt.WindowState.WindowActive)
                event.accept()
                return
        super().changeEvent(event)


    def patched_eventFilter(self, obj, event):
        """Fixed event filter for MainWindow that prevents focus wars with dialogs"""
        global SUPPRESS_FOCUS_CHECKS
        
        # Ignore WindowDeactivate events during dialog interaction
        if event.type() == QEvent.Type.WindowDeactivate:
            # Check if this is our main window being deactivated
            if obj is self:
                # If we're in a dialog interaction, don't try to reactivate
                if SUPPRESS_FOCUS_CHECKS:
                    logging.debug("Window deactivate during dialog - allowing")
                    return super().eventFilter(obj, event)
                    
                # Check if deactivation is due to a dialog opening
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, QDialog) or isinstance(widget, QMessageBox) or widget.inherits("QDialog"):
                        if widget.isVisible():
                            global_suppress_focus_checks(True)
                            logging.debug("Window deactivate due to dialog - allowing")
                            return super().eventFilter(obj, event)
                    
                    # Also check for modal dialogs
                    if hasattr(widget, 'isModal') and widget.isModal() and widget.isVisible():
                        global_suppress_focus_checks(True)
                        logging.debug("Window deactivate due to modal dialog - allowing")
                        return super().eventFilter(obj, event)
                
                # No dialog detected, schedule focus restore with a delay
                logging.debug("Window deactivate event - scheduling delayed re-activation")
                QTimer.singleShot(300, self.delayed_focus_restore)
        
        # Handle key events as before
        elif event.type() == QEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            
            # Enhanced detection for emergency exit
            is_ctrl = modifiers & Qt.KeyboardModifier.ControlModifier
            is_shift = modifiers & Qt.KeyboardModifier.ShiftModifier
            is_e_key = key == Qt.Key.Key_E
            
            # Check for emergency exit combination
            if is_ctrl and is_shift and is_e_key:
                logging.info("EMERGENCY EXIT combination detected in filter!")
                # Try triggering the emergency submit function
                self.trigger_emergency_submit()
                # If we somehow get here, force exit
                import os
                os._exit(0)
                return True  # Handled
                
            # Allow Ctrl+Shift+E for emergency submit
            if (key == Qt.Key.Key_E and 
                modifiers & Qt.KeyboardModifier.ControlModifier and 
                modifiers & Qt.KeyboardModifier.ShiftModifier):
                logging.info("Emergency submit key combination detected in Qt event filter")
                # Don't block this event
                return False
            
            # Allow regular keys needed for form input and UI interaction
            if ((key >= Qt.Key.Key_A and key <= Qt.Key.Key_Z) or  # Letters
                (key >= Qt.Key.Key_0 and key <= Qt.Key.Key_9) or  # Numbers
                key == Qt.Key.Key_Space or                        # Space
                key == Qt.Key.Key_Return or                      # Enter/Return
                key == Qt.Key.Key_Backspace or                   # Backspace
                key == Qt.Key.Key_Delete or                      # Delete
                (key >= Qt.Key.Key_Left and key <= Qt.Key.Key_Down)):  # Arrow keys
                return False  # Don't block these keys
                
            # Allow Escape key in dialogs
            if key == Qt.Key.Key_Escape and SUPPRESS_FOCUS_CHECKS:
                return False  # Don't block Escape in dialogs
                
            # Comprehensive blocking of problematic keys
            # Block function keys
            if key >= Qt.Key.Key_F1 and key <= Qt.Key.Key_F12:
                logging.info(f"Blocked function key {key - Qt.Key.Key_F1 + 1} through Qt event filter")
                return True  # Block the event
                
            # Block Escape outside of dialogs
            if key == Qt.Key.Key_Escape and not SUPPRESS_FOCUS_CHECKS:
                logging.info("Blocked Escape through Qt event filter")
                return True
                
            # Block Tab
            if key == Qt.Key.Key_Tab:
                logging.info("Blocked Tab through Qt event filter")
                return True
                
            # Block Alt modifiers
            if modifiers & Qt.KeyboardModifier.AltModifier:
                logging.info("Blocked Alt combination through Qt event filter")
                return True
                
            # Block Windows key combinations
            if modifiers & Qt.KeyboardModifier.MetaModifier:
                logging.info("Blocked Windows key combination through Qt event filter")
                return True
                
        return super().eventFilter(obj, event)
    
    def is_dialog_child(self, obj):
        """Check if object is a child of a dialog"""
        if hasattr(obj, 'parent'):
            parent = obj.parent()
            while parent:
                if isinstance(parent, QDialog) or isinstance(parent, QMessageBox):
                    return True
                parent = parent.parent() if hasattr(parent, 'parent') else None
        return False    
    
    def apply_focus_patches(main_window):
        """Apply all focus checking patches"""
        # Store the original method
        if not hasattr(main_window, '_original_check_focus'):
            main_window._original_check_focus = main_window.check_focus
        
        # Add the delayed focus restore method
        main_window.delayed_focus_restore = lambda: delayed_focus_restore(main_window)
        
        # Apply the patched method
        main_window.check_focus = lambda: patched_check_focus(main_window)
        
        logging.info("Applied focus check patches to main window")
        
        return main_window
    def animate_transition(self):
        animation = QPropertyAnimation(self.stack, b"geometry")
        animation.setDuration(300)
        start_rect = self.stack.geometry()
        end_rect = QRect(start_rect.x() - 50, start_rect.y(), start_rect.width(), start_rect.height())
        animation.setStartValue(start_rect)
        animation.setEndValue(end_rect)
        animation.start()

    def show_system_check_page(self, exam_code, token, exam_details):
        self.exam_code = exam_code
        self.token = token
        self.exam_details = exam_details
        self.system_check_page.set_exam_details(exam_details)
        self.animate_transition()
        self.stack.setCurrentWidget(self.system_check_page)

    def show_instructions_page(self):
        self.instructions_page.set_exam_details(self.exam_details)
        self.animate_transition()
        self.stack.setCurrentWidget(self.instructions_page)

    def show_exam_page(self, updated_exam_details):
        """
        Show the exam page with improved transition to prevent flickering
        """
        # First, prepare the exam page (do as much as possible before showing it)
        self.exam_details = updated_exam_details
        self.exam_page.set_exam_code(self.exam_code)
        
        # Create a simple semi-transparent overlay on current widget
        overlay = QtWidgets.QFrame(self)
        overlay.setStyleSheet("background-color: rgba(0, 0, 0, 80);")
        overlay.setGeometry(self.rect())
        
        # Add loading text
        loading_text = QtWidgets.QLabel("Loading exam...", overlay)
        loading_text.setStyleSheet("""
            color: white;
            font-size: 16px;
            font-weight: bold;
            background-color: rgba(0, 0, 0, 120);
            padding: 20px;
            border-radius: 10px;
        """)
        # Center the loading text
        loading_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        loading_text.setGeometry(self.width()//2 - 100, self.height()//2 - 40, 200, 80)
        
        # Show overlay
        overlay.raise_()
        overlay.show()
        QtCore.QCoreApplication.processEvents()
        
        # Create a very short timer to allow UI to refresh
        QtCore.QTimer.singleShot(10, lambda: self._switch_to_exam_page(updated_exam_details, overlay))

    def _switch_to_exam_page(self, updated_exam_details, overlay):
        """
        Safe method to switch to the exam page without black screen issues
        """
        try:
            # Set exam details (potentially heavy operation)
            self.exam_page.set_exam_details(updated_exam_details)
            
            # Switch to exam page WITHOUT any visual effects for now
            self.stack.setCurrentWidget(self.exam_page)
            
            # Process events to ensure the widget is properly shown
            QtCore.QCoreApplication.processEvents()
            
            # Remove overlay after a short delay to ensure exam page is visible
            QtCore.QTimer.singleShot(100, lambda: overlay.deleteLater())
            
        except Exception as e:
            print(f"Error during page transition: {e}")
            # Safety fallback - make sure we still show the exam page even if something fails
            self.stack.setCurrentWidget(self.exam_page)
            overlay.deleteLater()

    def _simple_fade_in(self, widget, duration=250):
        """Simple fade-in animation for the widget"""
        effect = QtWidgets.QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        
        anim = QtCore.QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        

    def keyPressEvent(self, event: QKeyEvent):
        """Override keyPressEvent with enhanced emergency exit detection"""
        key = event.key()
        modifiers = event.modifiers()
        
        # Enhanced check for emergency exit key combination
        is_ctrl = modifiers & Qt.KeyboardModifier.ControlModifier
        is_shift = modifiers & Qt.KeyboardModifier.ShiftModifier
        is_e_key = key == Qt.Key.Key_E
        
        # Log all key presses to help with debugging
        logging.info(f"Key press: key={key}, modifiers={modifiers}, "
                    f"ctrl={is_ctrl}, shift={is_shift}, is_e={is_e_key}")
        
        # Check for emergency exit combination
        if is_ctrl and is_shift and is_e_key:
            logging.info("EMERGENCY EXIT key combination detected!")
            # Try triggering emergency submit
            self.trigger_emergency_submit()
            # If we somehow get here, force exit
            import os
            os._exit(0)
        
        # For all other key combinations, use your existing logic
        # Allow regular keys needed for form input and UI interaction
        if ((key >= Qt.Key.Key_A and key <= Qt.Key.Key_Z) or  # Letters
            (key >= Qt.Key.Key_0 and key <= Qt.Key.Key_9) or  # Numbers
            key == Qt.Key.Key_Space or                        # Space
            key == Qt.Key.Key_Return or                      # Enter/Return
            key == Qt.Key.Key_Backspace or                   # Backspace
            key == Qt.Key.Key_Delete or                      # Delete
            (key >= Qt.Key.Key_Left and key <= Qt.Key.Key_Down)):  # Arrow keys
            # Process these keys normally
            super().keyPressEvent(event)
            return
        
        # Block ALL function keys, system keys, and navigation keys
        # This is our final defense against keyboard shortcuts
        if (
            (key >= Qt.Key.Key_F1 and key <= Qt.Key.Key_F35) or  # ALL function keys
            key == Qt.Key.Key_Escape or
            key == Qt.Key.Key_Tab or
            key == Qt.Key.Key_Menu or  # Context menu key
            key == Qt.Key.Key_Print or  # Print screen
            modifiers & Qt.KeyboardModifier.AltModifier or  # Any Alt combo
            modifiers & Qt.KeyboardModifier.MetaModifier    # Any Windows key combo
        ):
            logging.info(f"Blocked key {key} with modifiers {modifiers} in keyPressEvent")
            event.accept()
            return
            
        # For unblocked keys, let the default handler process it
        super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle window close events"""
        # Check if exam is submitted or if emergency exit is triggered
        if hasattr(self, 'exam_page') and hasattr(self.exam_page, 'exam_submitted') and self.exam_page.exam_submitted:
            logging.info("Close event allowed - exam already submitted")
            event.accept()  # Allow window to close
        else:
            # Only prevent closing if exam is in progress and not submitted
            logging.info("Close event intercepted - preventing")
            event.ignore()
# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------
def main():
    """
    Application entry point with enhanced security, error handling, and clean shutdown.
    Sets up logging, key blocking, window management, and dialog monitoring.
    """
    # Set up detailed logging with rotation to prevent large log files
    try:
        # Create log directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, "exam_app.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            handlers=[
                # Rotating file handler to prevent unlimited log growth
                logging.handlers.RotatingFileHandler(
                    log_file, maxBytes=5*1024*1024, backupCount=3
                ),
                logging.StreamHandler()
            ]
        )
        logging.info("="*50)
        logging.info("Starting Evaluate App with enhanced security measures")
    except Exception as e:
        # Fallback logging setup if the enhanced setup fails
        print(f"Failed to configure logging: {e}")
        logging.basicConfig(level=logging.INFO)
        logging.error(f"Failed to configure detailed logging: {e}")
    
    # Initialize global state
    global SUPPRESS_FOCUS_CHECKS
    SUPPRESS_FOCUS_CHECKS = False
    
    # Start the application
    try:
        app = QApplication(sys.argv)
        
        # Set application properties
        app.setApplicationName("Evaluate Exam App")
        app.setQuitOnLastWindowClosed(False)  # Prevent accidental exit
        
        # Set up emergency exit handlers
        setup_global_emergency_exit()
        logging.info("Emergency exit handler configured")
        
        # Start key blocking in a background thread
        blocking_thread = None
        try:
            blocking_thread = start_key_blocking()
            logging.info("Key blocking system started successfully")
        except Exception as e:
            logging.error(f"Failed to start key blocking: {e}", exc_info=True)
            # Show warning but continue - we have other protective layers
            QMessageBox.warning(
                None, 
                "Security Warning", 
                "Enhanced keyboard security could not be activated. Basic security is still in effect."
            )

        # Create and configure main window
        try:
            window = MainWindow()
            setup_combo_box_handling()
            # Apply the patched event filter method to the main window
            # This overrides the default eventFilter with our security-enhanced version
            window.eventFilter = types.MethodType(patched_eventFilter, window)
            
            # Add the delayed_focus_restore method to the window
            window.delayed_focus_restore = types.MethodType(improved_delayed_focus_restore, window)
            
            # Patch the check_focus method if it exists
            if hasattr(window, 'check_focus'):
                window.check_focus = types.MethodType(patched_check_focus, window)
                
            logging.info("Main window created with security patches applied")
        except Exception as e:
            logging.critical(f"Failed to create main window: {e}", exc_info=True)
            QMessageBox.critical(None, "Fatal Error", f"Could not create application window: {e}")
            return 1
            
        # Initialize dialog monitor for enhanced dialog handling
        try:
            dialog_monitor = DialogMonitor()
            logging.info("Dialog monitor initialized")
        except Exception as e:
            logging.error(f"Failed to initialize dialog monitor: {e}", exc_info=True)
            # Continue anyway as this is an enhancement, not core functionality
        
        # Create a timer to periodically check focus at the application level
        focus_timer = QTimer()
        focus_timer.timeout.connect(lambda: patched_check_app_focus(window))
        focus_timer.start(1500)  # Check every 1.5 seconds
        
        # Set up clean shutdown handler
        def clean_shutdown():
            logging.info("Performing clean shutdown...")
            # Stop timers
            focus_timer.stop()
            if hasattr(dialog_monitor, 'check_timer'):
                dialog_monitor.check_timer.stop()
            
            # Stop key blocking thread if running
            if blocking_thread and blocking_thread.is_alive():
                # Signal thread to exit if it has a way to do so
                if hasattr(blocking_thread, 'stop'):
                    blocking_thread.stop()
            
            logging.info("Clean shutdown complete")
            
        app.aboutToQuit.connect(clean_shutdown)
        
        # Show the window and enter event loop
        window.show()
        window.activateWindow()
        window.raise_()
        
        logging.info("Application initialized successfully. Entering event loop.")
        return app.exec()
        
    except Exception as e:
        logging.critical(f"Unhandled exception in main: {e}", exc_info=True)
        # Try to show error dialog if possible
        try:
            QMessageBox.critical(None, "Fatal Error", f"Application failed to start: {e}")
        except:
            print(f"FATAL ERROR: {e}")
        return 1

if __name__ == "__main__":
    # Wrap with sys.exit to return proper exit code
    sys.exit(main())


