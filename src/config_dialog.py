#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration dialog for deSEC Qt DNS Manager.
Allows users to modify application settings.
"""

import logging
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)

class ConfigDialog(QtWidgets.QDialog):
    """Dialog for editing application configuration."""
    
    def __init__(self, config_manager, parent=None):
        """
        Initialize the configuration dialog.
        
        Args:
            config_manager: Configuration manager instance
            parent: Parent widget, if any
        """
        super(ConfigDialog, self).__init__(parent)
        
        self.config_manager = config_manager
        
        # Set up the UI
        self.setup_ui()
        
        # Initialize values from config
        self.initialize_values()
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Configuration")
        self.setModal(True)
        self.setMinimumWidth(450)
        
        # Create layout
        layout = QtWidgets.QVBoxLayout(self)
        
        # Create form layout for inputs
        form_layout = QtWidgets.QFormLayout()
        
        # API URL
        self.api_url_input = QtWidgets.QLineEdit()
        self.api_url_input.setPlaceholderText("https://desec.io/api/v1")
        form_layout.addRow("API URL:", self.api_url_input)
        
        # API Token
        self.token_input = QtWidgets.QLineEdit()
        self.token_input.setPlaceholderText("Enter your API token here")
        self.token_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)  # Hide the token by default
        form_layout.addRow("API Token:", self.token_input)
        
        # Show/hide token checkbox
        self.show_token_checkbox = QtWidgets.QCheckBox("Show token")
        self.show_token_checkbox.stateChanged.connect(self.toggle_token_visibility)
        form_layout.addRow("", self.show_token_checkbox)
        
        # Sync interval
        self.sync_interval_input = QtWidgets.QSpinBox()
        self.sync_interval_input.setRange(1, 60)  # 1 to 60 minutes
        self.sync_interval_input.setSuffix(" minutes")
        form_layout.addRow("Sync Interval:", self.sync_interval_input)
        
        # Debug mode
        self.debug_mode_checkbox = QtWidgets.QCheckBox("Enable debug mode")
        form_layout.addRow("", self.debug_mode_checkbox)
        
        layout.addLayout(form_layout)
        
        # Add spacing
        layout.addSpacing(10)
        
        # Add tip
        tip = QtWidgets.QLabel(
            "Note: Changes to the API URL or token will take effect immediately and "
            "will trigger a re-synchronization."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #777; font-style: italic;")
        layout.addWidget(tip)
        
        # Add buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def initialize_values(self):
        """Initialize form values from configuration."""
        self.api_url_input.setText(self.config_manager.get_api_url())
        self.token_input.setText(self.config_manager.get_auth_token())
        self.sync_interval_input.setValue(self.config_manager.get_sync_interval())
        self.debug_mode_checkbox.setChecked(self.config_manager.get_debug_mode())
    
    def toggle_token_visibility(self, state):
        """
        Toggle visibility of the API token.
        
        Args:
            state: Checkbox state
        """
        logger.debug(f"Toggle token visibility called with state: {state}")
        
        # In PyQt6, the CheckState enum values are different
        # Let's explicitly check if the checkbox is checked
        if self.show_token_checkbox.isChecked():
            logger.debug("Setting echo mode to Normal")
            self.token_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Normal)
        else:
            logger.debug("Setting echo mode to Password")
            self.token_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
    
    def accept(self):
        """Handle dialog acceptance."""
        # Validate API URL
        api_url = self.api_url_input.text().strip()
        if not api_url:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid API URL",
                "Please enter a valid API URL."
            )
            return
        
        # Save the values to configuration
        self.config_manager.set_api_url(api_url)
        self.config_manager.set_auth_token(self.token_input.text().strip())
        self.config_manager.set_sync_interval(self.sync_interval_input.value())
        self.config_manager.set_debug_mode(self.debug_mode_checkbox.isChecked())
        self.config_manager.save_config()
        
        logger.info("Configuration settings updated")
        super(ConfigDialog, self).accept()
