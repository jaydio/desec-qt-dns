#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration dialog for deSEC Qt DNS Manager.
Allows users to modify application settings.
"""

import logging
from typing import Dict, Any, Optional
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)

class ConfigDialog(QtWidgets.QDialog):
    """Dialog for editing application configuration."""
    
    def __init__(self, config_manager, theme_manager=None, parent=None):
        """
        Initialize the configuration dialog.
        
        Args:
            config_manager: Configuration manager instance
            theme_manager: Optional theme manager instance
            parent: Parent widget, if any
        """
        super(ConfigDialog, self).__init__(parent)
        
        self.config_manager = config_manager
        self.theme_manager = theme_manager
        
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
        
        # API Rate Limit
        self.api_rate_limit_input = QtWidgets.QDoubleSpinBox()
        self.api_rate_limit_input.setRange(0.1, 10.0)  # 0.1 to 10 requests per second
        self.api_rate_limit_input.setSingleStep(0.5)
        self.api_rate_limit_input.setDecimals(1)
        self.api_rate_limit_input.setSuffix(" req/sec")
        self.api_rate_limit_input.setSpecialValueText("No limit")
        self.api_rate_limit_input.setMinimum(0.0)  # Allow 0 for no limit
        form_layout.addRow("API Rate Limit:", self.api_rate_limit_input)
        
        # Add help text for rate limit
        rate_limit_help = QtWidgets.QLabel("Lower values prevent API timeouts during bulk operations")
        rate_limit_help.setStyleSheet("color: #666; font-size: 11px;")
        rate_limit_help.setWordWrap(True)
        form_layout.addRow("", rate_limit_help)
        
        # Debug mode
        self.debug_mode_checkbox = QtWidgets.QCheckBox("Enable debug mode")
        form_layout.addRow("", self.debug_mode_checkbox)
        
        # Themes section
        if self.theme_manager:
            # Add a separator
            layout.addSpacing(10)
            layout.addWidget(QtWidgets.QLabel("<b>Theme Settings</b>"))
            
            theme_layout = QtWidgets.QVBoxLayout()
            
            # Theme type selection (Light, Dark, System)
            theme_type_group = QtWidgets.QGroupBox("Theme Mode")
            theme_type_layout = QtWidgets.QVBoxLayout(theme_type_group)
            self.theme_type_group = QtWidgets.QButtonGroup(self)
            
            theme_types = self.theme_manager.get_theme_types()
            self.theme_type_radios = {}
            
            for theme_type, display_name in theme_types.items():
                radio = QtWidgets.QRadioButton(display_name)
                theme_type_layout.addWidget(radio)
                self.theme_type_group.addButton(radio)
                self.theme_type_radios[theme_type] = radio
                
                # Connect to enable/disable theme selection
                radio.toggled.connect(self.on_theme_type_changed)
            
            theme_layout.addWidget(theme_type_group)
            
            # Light theme selection
            self.light_theme_group = QtWidgets.QGroupBox("Light Theme")
            light_theme_layout = QtWidgets.QVBoxLayout(self.light_theme_group)
            self.light_theme_combo = QtWidgets.QComboBox()
            light_themes = self.theme_manager.get_theme_names(theme_type="light")
            for theme_id, theme_name in light_themes.items():
                self.light_theme_combo.addItem(theme_name, theme_id)
            light_theme_layout.addWidget(self.light_theme_combo)
            theme_layout.addWidget(self.light_theme_group)
            
            # Dark theme selection
            self.dark_theme_group = QtWidgets.QGroupBox("Dark Theme")
            dark_theme_layout = QtWidgets.QVBoxLayout(self.dark_theme_group)
            self.dark_theme_combo = QtWidgets.QComboBox()
            dark_themes = self.theme_manager.get_theme_names(theme_type="dark")
            for theme_id, theme_name in dark_themes.items():
                self.dark_theme_combo.addItem(theme_name, theme_id)
            dark_theme_layout.addWidget(self.dark_theme_combo)
            theme_layout.addWidget(self.dark_theme_group)
            
            layout.addLayout(theme_layout)
        
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
        self.api_rate_limit_input.setValue(self.config_manager.get_setting('api_rate_limit', 2.0))
        self.debug_mode_checkbox.setChecked(self.config_manager.get_debug_mode())
        
        # Initialize theme settings
        if self.theme_manager:
            # Set theme type
            theme_type = self.config_manager.get_theme_type()
            if theme_type in self.theme_type_radios:
                self.theme_type_radios[theme_type].setChecked(True)
            
            # Set light theme - need to find the current light theme
            if theme_type == "light":
                # If in light mode, use the current theme
                light_theme_id = self.config_manager.get_theme_id()
            else:
                # If in dark/system mode, find what the light theme would be
                light_theme_id = self.config_manager.get_light_theme_id()
                if not light_theme_id:  # Fallback if not set
                    light_theme_id = "light_plus"
                    
            light_index = self.light_theme_combo.findData(light_theme_id)
            if light_index >= 0:
                self.light_theme_combo.setCurrentIndex(light_index)
            
            # Set dark theme - need to find the current dark theme
            if theme_type == "dark":
                # If in dark mode, use the current theme
                dark_theme_id = self.config_manager.get_theme_id()
            else:
                # If in light/system mode, find what the dark theme would be
                dark_theme_id = self.config_manager.get_dark_theme_id()
                if not dark_theme_id:  # Fallback if not set
                    dark_theme_id = "dark_plus"
                    
            dark_index = self.dark_theme_combo.findData(dark_theme_id)
            if dark_index >= 0:
                self.dark_theme_combo.setCurrentIndex(dark_index)
                
            # Update enabled state
            self.on_theme_type_changed()
    
    def on_theme_type_changed(self):
        """Enable/disable theme selection based on selected theme type."""
        if not self.theme_manager:
            return
            
        # Check which theme type is selected
        is_light = self.theme_type_radios.get("light", QtWidgets.QRadioButton()).isChecked()
        is_dark = self.theme_type_radios.get("dark", QtWidgets.QRadioButton()).isChecked()
        is_system = self.theme_type_radios.get("system", QtWidgets.QRadioButton()).isChecked()
        
        # Enable/disable theme selection
        self.light_theme_group.setEnabled(is_light)
        self.dark_theme_group.setEnabled(is_dark)
        
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
        self.config_manager.set_setting('api_rate_limit', self.api_rate_limit_input.value())
        self.config_manager.set_debug_mode(self.debug_mode_checkbox.isChecked())
        
        # Save theme settings
        if self.theme_manager:
            # Save theme type
            theme_type = None
            for type_id, radio in self.theme_type_radios.items():
                if radio.isChecked():
                    theme_type = type_id
                    break
            
            if theme_type:
                self.config_manager.set_theme_type(theme_type)
            
            # Always save both light and dark theme selections regardless of current mode
            # This way we remember preferences for each mode
            
            # Save light theme selection
            light_theme_id = self.light_theme_combo.currentData()
            if light_theme_id:
                self.config_manager.set_light_theme_id(light_theme_id)
                
            # Save dark theme selection
            dark_theme_id = self.dark_theme_combo.currentData()
            if dark_theme_id:
                self.config_manager.set_dark_theme_id(dark_theme_id)
                
            # Also set the current theme based on selected mode
            if theme_type == "light":
                self.config_manager.set_theme_id(light_theme_id)
            elif theme_type == "dark":
                self.config_manager.set_theme_id(dark_theme_id)
        
        self.config_manager.save_config()
        
        logger.info("Configuration settings updated")
        super(ConfigDialog, self).accept()
