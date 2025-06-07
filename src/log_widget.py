#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Log Widget for deSEC Qt DNS Manager.
Displays application logs with timestamps and different message levels.
"""

import logging
import time
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)

class LogWidget(QtWidgets.QWidget):
    """Widget for displaying application logs with collapsibility support."""
    
    # Define colors for different log levels
    LOG_COLORS = {
        'info': '#000000',    # Black
        'warning': '#FF9900',  # Orange
        'error': '#FF0000',    # Red
        'success': '#008800'   # Green
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
        
        title = QtWidgets.QLabel("Log Console")
        title.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(title)
        
        # Add message count label
        self.count_label = QtWidgets.QLabel("0 messages")
        self.count_label.setStyleSheet("color: #666; font-size: 11px;")
        header_layout.addWidget(self.count_label)
        
        header_layout.addStretch()
        
        # Clear log button
        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.setFixedSize(50, 25)
        clear_btn.clicked.connect(self.clear_log)
        header_layout.addWidget(clear_btn)
        
        layout.addLayout(header_layout)
        
        # Log text area
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(100)
        self.log_text.setMaximumHeight(200)
        self.log_text.document().setMaximumBlockCount(500)  # Limit to 500 lines
        layout.addWidget(self.log_text)
        
        # Apply initial styling
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                font-family: monospace;
            }
        """)
    
    def add_message(self, message, level='info'):
        """
        Add a message to the log.
        
        Args:
            message (str): Message text
            level (str): Message level (info, warning, error, success)
        """
        if level not in self.LOG_COLORS:
            level = 'info'
            
        color = self.LOG_COLORS[level]
        timestamp = time.strftime("%H:%M:%S")
        
        # Format the log entry
        html = f'<div style="margin: 2px 0;">'
        html += f'<span style="color: #666;">[{timestamp}]</span> '
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
