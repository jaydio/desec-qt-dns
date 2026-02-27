#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Log Widget for deSEC Qt DNS Manager.
Displays application logs with timestamps and different message levels.
"""

import logging
import time
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from qfluentwidgets import TextEdit, PushButton, StrongBodyLabel, CaptionLabel, isDarkTheme

logger = logging.getLogger(__name__)

class LogWidget(QtWidgets.QWidget):
    """Widget for displaying application logs with collapsibility support."""

    # Colors per theme: (light, dark)
    _LEVEL_COLORS = {
        'info':    ('#1a1a1a', '#e4e4e4'),
        'debug':   ('#607D8B', '#90A4AE'),
        'warning': ('#E65100', '#FFB74D'),
        'error':   ('#C62828', '#FF6B6B'),
        'success': ('#2E7D32', '#66BB6A'),
    }

    def __init__(self, parent=None):
        """
        Initialize the log widget.

        Args:
            parent: Parent widget, if any
        """
        super(LogWidget, self).__init__(parent)

        # Set up the UI
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with title and buttons
        header_layout = QtWidgets.QHBoxLayout()

        title = StrongBodyLabel("Log Console")
        header_layout.addWidget(title)

        # Add message count label
        self.count_label = CaptionLabel("0 messages")
        header_layout.addWidget(self.count_label)

        header_layout.addStretch()

        # Clear log button
        clear_btn = PushButton("Clear")
        clear_btn.setFixedSize(60, 28)
        clear_btn.clicked.connect(self.clear_log)
        header_layout.addWidget(clear_btn)

        layout.addLayout(header_layout)

        # Log text area
        self.log_text = TextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(100)
        self.log_text.document().setMaximumBlockCount(500)  # Limit to 500 lines
        # Monospace font set directly (no stylesheet)
        mono_font = QFont()
        mono_font.setFamily("monospace")
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.log_text.setFont(mono_font)
        layout.addWidget(self.log_text)

    def add_message(self, message, level='info'):
        """
        Add a message to the log.

        Args:
            message (str): Message text
            level (str): Message level (info, warning, error, success)
        """
        # Theme-aware color per level
        pair = self._LEVEL_COLORS.get(level, self._LEVEL_COLORS['info'])
        color = pair[1] if isDarkTheme() else pair[0]

        timestamp = time.strftime("%H:%M:%S")

        # Dim the timestamp relative to the current text colour
        dim = self.palette().color(QtGui.QPalette.ColorRole.PlaceholderText).name()

        # Format the log entry
        html = f'<div style="margin: 2px 0;">'
        html += f'<span style="color: {dim};">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'
        html += '</div>'

        # Add to log
        self.log_text.append(html)

        # Ensure the latest entry is visible
        scroll_bar = self.log_text.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

        # Update message count
        count = self.log_text.document().blockCount()
        self.count_label.setText(f"{count} {'messages' if count != 1 else 'message'}")



    def clear_log(self):
        """Clear the log contents."""
        self.log_text.clear()
        self.add_message("Log cleared", "info")
        self.count_label.setText("1 message")
