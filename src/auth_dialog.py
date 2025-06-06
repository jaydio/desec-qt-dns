#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Authentication dialog for deSEC Qt DNS Manager.
Prompts the user for their deSEC API authentication token.
"""

import logging
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)

class AuthDialog(QtWidgets.QDialog):
    """Dialog for prompting and setting API authentication token."""
    
    def __init__(self, config_manager, parent=None):
        """
        Initialize the authentication dialog.
        
        Args:
            config_manager: Configuration manager instance
            parent: Parent widget, if any
        """
        super(AuthDialog, self).__init__(parent)
        
        self.config_manager = config_manager
        
        # Set up the UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("deSEC API Authentication")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        # Create layout
        layout = QtWidgets.QVBoxLayout(self)
        
        # Add explanation label
        explanation = QtWidgets.QLabel(
            "Please enter your deSEC API token.\n\n"
            "You can obtain this token by logging into your deSEC account at "
            "https://desec.io and generating a token with permissions to "
            "manage DNS records."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        
        # Add separator
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        layout.addWidget(line)
        
        # Add form layout for inputs
        form_layout = QtWidgets.QFormLayout()
        
        # Token input field
        self.token_input = QtWidgets.QLineEdit()
        self.token_input.setPlaceholderText("Enter your API token here")
        self.token_input.setText(self.config_manager.get_auth_token())
        self.token_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)  # Hide the token by default
        form_layout.addRow("API Token:", self.token_input)
        
        # Show/hide token checkbox
        self.show_token_checkbox = QtWidgets.QCheckBox("Show token")
        self.show_token_checkbox.stateChanged.connect(self.toggle_token_visibility)
        form_layout.addRow("", self.show_token_checkbox)
        
        layout.addLayout(form_layout)
        
        # Add spacing
        layout.addSpacing(10)
        
        # Add buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def toggle_token_visibility(self, state):
        """
        Toggle visibility of the API token.
        
        Args:
            state: Checkbox state
        """
        # Check the actual checked state of the checkbox directly
        if self.show_token_checkbox.isChecked():
            self.token_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Normal)
        else:
            self.token_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
    
    def accept(self):
        """Handle dialog acceptance."""
        token = self.token_input.text().strip()
        
        if not token:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing Token",
                "Please enter a valid API token."
            )
            return
        
        # Save the token to the configuration
        self.config_manager.set_auth_token(token)
        self.config_manager.save_config()
        
        logger.info("API token set successfully")
        super(AuthDialog, self).accept()
