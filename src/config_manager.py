#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration manager for deSEC Qt DNS Manager.
Handles reading, writing, and verifying configuration settings.
"""

import os
import json
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration including API token storage."""
    
    CONFIG_DIR = os.path.expanduser("~/.config/desecqt")
    CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
    DEFAULT_API_URL = "https://desec.io/api/v1"
    
    def __init__(self):
        """Initialize the configuration manager."""
        self._config = {
            "api_url": self.DEFAULT_API_URL,
            "auth_token": "",
            "sync_interval_minutes": 10,  # Default sync interval in minutes
            "debug_mode": False,
            "show_log_console": True,  # Default to showing log console
            "keepalive_interval": 60,  # Default keepalive check interval in seconds
            "offline_mode": False,  # Default to online mode
            "show_multiline_records": True,  # Default to full display of multiline records
            "api_throttle_seconds": 2,  # Default delay between API requests to avoid rate limiting
            "theme_type": "light",  # Default theme type (light, dark, system)
            "light_theme_id": "light_plus",  # Default light theme ID
            "dark_theme_id": "dark_plus"  # Default dark theme ID
        }
        self._ensure_config_dir_exists()
        self._load_config()
        
    def _ensure_config_dir_exists(self):
        """Create configuration directory if it doesn't exist."""
        if not os.path.exists(self.CONFIG_DIR):
            try:
                os.makedirs(self.CONFIG_DIR)
                logger.info(f"Created configuration directory: {self.CONFIG_DIR}")
            except OSError as e:
                logger.error(f"Failed to create config directory: {e}")
    
    def _get_encryption_key(self):
        """Generate a consistent encryption key based on user-specific data."""
        # Using the username and machine ID as a salt for encryption
        # This is a simple approach - for production use, consider a more secure key management strategy
        salt = (os.path.expanduser("~") + os.name).encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        # Generate key from a fixed passphrase plus the salt (which varies by user/machine)
        key = base64.urlsafe_b64encode(kdf.derive(b"desecqt-fixed-passphrase"))
        return key
    
    def _encrypt_token(self, token):
        """Encrypt the API token before storing it."""
        if not token:
            return ""
        
        key = self._get_encryption_key()
        f = Fernet(key)
        return f.encrypt(token.encode()).decode()
    
    def _decrypt_token(self, encrypted_token):
        """Decrypt the stored API token."""
        if not encrypted_token:
            return ""
        
        try:
            key = self._get_encryption_key()
            f = Fernet(key)
            return f.decrypt(encrypted_token.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt token: {e}")
            return ""
    
    def _load_config(self):
        """Load configuration from file."""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    stored_config = json.load(f)
                    
                # Decrypt the auth token if it exists
                if 'encrypted_auth_token' in stored_config:
                    stored_config['auth_token'] = self._decrypt_token(stored_config['encrypted_auth_token'])
                    del stored_config['encrypted_auth_token']
                    
                # Only update with explicitly set values
                self._config.update(stored_config)
                logger.info("Configuration loaded successfully")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load config: {e}")
        else:
            logger.info("No configuration file found, using defaults")
    
    def save_config(self):
        """Save current configuration to file."""
        try:
            # Create a copy of the config to avoid modifying the original
            config_to_save = self._config.copy()
            
            # Encrypt the auth token for storage
            if 'auth_token' in config_to_save and config_to_save['auth_token']:
                config_to_save['encrypted_auth_token'] = self._encrypt_token(config_to_save['auth_token'])
                del config_to_save['auth_token']  # Don't store the plain token
            
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(config_to_save, f, indent=2)
            logger.info("Configuration saved successfully")
            return True
        except IOError as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def get_api_url(self):
        """Get the API URL."""
        return self._config["api_url"]
    
    def set_api_url(self, url):
        """Set the API URL."""
        self._config["api_url"] = url
    
    def get_auth_token(self):
        """Get the authentication token."""
        return self._config["auth_token"]
    
    def set_auth_token(self, token):
        """Set the authentication token."""
        self._config["auth_token"] = token
    
    def get_sync_interval(self):
        """Get the sync interval in minutes."""
        return self._config["sync_interval_minutes"]
    
    def set_sync_interval(self, minutes):
        """Set the sync interval in minutes."""
        self._config["sync_interval_minutes"] = minutes
    
    def get_debug_mode(self):
        """Get debug mode status."""
        return self._config["debug_mode"]
        
    def get_show_log_console(self):
        """Get log console visibility preference."""
        return self._config.get("show_log_console", False)  # Default to hidden if not set
    
    def set_show_log_console(self, show):
        """Set log console visibility preference.
        
        Args:
            show (bool): Whether to show the log console
        """
        self._config["show_log_console"] = show
    
    def set_debug_mode(self, enabled):
        """Set debug mode status."""
        self._config["debug_mode"] = enabled
        
    def get_keepalive_interval(self):
        """Get the keepalive check interval in seconds."""
        return self._config.get("keepalive_interval", 60)  # Default to 60 seconds
    
    def set_keepalive_interval(self, seconds):
        """Set the keepalive check interval in seconds.
        
        Args:
            seconds (int): Interval in seconds between keepalive checks
        """
        self._config["keepalive_interval"] = seconds
        
    def get_offline_mode(self):
        """Get offline mode status."""
        return self._config.get("offline_mode", False)  # Default to online mode
    
    def set_offline_mode(self, enabled):
        """Set offline mode status.
        
        Args:
            enabled (bool): Whether offline mode is enabled
        """
        if enabled:
            # Only add to config when explicitly enabled
            self._config["offline_mode"] = True
        else:
            # Remove from config when disabled, so default (False) applies
            if "offline_mode" in self._config:
                del self._config["offline_mode"]
        
    def get_show_multiline_records(self):
        """Get multiline records display status."""
        return self._config.get("show_multiline_records", True)  # Default to full display
    
    def set_show_multiline_records(self, enabled):
        """Set multiline records display status.
        
        Args:
            enabled (bool): Whether to show multiline records in full
        """
        self._config["show_multiline_records"] = enabled
        
    def get_api_throttle_seconds(self):
        """Get the API request throttling delay in seconds.
        
        Returns:
            float: The delay between API requests in seconds
        """
        return self._config.get("api_throttle_seconds", 2.0)  # Default to 2 seconds
    
    def set_api_throttle_seconds(self, seconds):
        """Set the API request throttling delay in seconds.
        
        Args:
            seconds (float): Delay between API requests in seconds
        """
        self._config["api_throttle_seconds"] = seconds
        
    def get_theme_type(self):
        """Get the theme type (light, dark, or system).
        
        Returns:
            str: The current theme type
        """
        return self._config.get("theme_type", "light")  # Default to light theme
    
    def set_theme_type(self, theme_type):
        """Set the theme type.
        
        Args:
            theme_type (str): Theme type ('light', 'dark', or 'system')
        """
        self._config["theme_type"] = theme_type
    
    def get_theme_id(self):
        """Get the currently active theme ID based on theme type.
    
        Returns:
            str: The current theme ID
        """
        theme_type = self.get_theme_type()
        if theme_type == "light":
            return self.get_light_theme_id()
        elif theme_type == "dark":
            return self.get_dark_theme_id()
        else:  # system theme
            # For system theme, we'll return the appropriate theme based on system detection
            # This will be handled by ThemeManager when applied
            return self._config.get("theme_id", "light_plus")
    
    def set_theme_id(self, theme_id):
        """Set the theme ID for the current theme type.
        
        Args:
            theme_id: The theme identifier
        """
        theme_type = self.get_theme_type()
        if theme_type == "light":
            self.set_light_theme_id(theme_id)
        elif theme_type == "dark":
            self.set_dark_theme_id(theme_id)
        # Also store in legacy theme_id for backward compatibility
        self._config["theme_id"] = theme_id
        
    def get_light_theme_id(self):
        """Get the light theme ID.
        
        Returns:
            str: The light theme ID
        """
        return self._config.get("light_theme_id", "light_plus")
    
    def set_light_theme_id(self, theme_id):
        """Set the light theme ID.
        
        Args:
            theme_id: The light theme identifier
        """
        self._config["light_theme_id"] = theme_id
    
    def get_dark_theme_id(self):
        """Get the dark theme ID.
        
        Returns:
            str: The dark theme ID
        """
        return self._config.get("dark_theme_id", "dark_plus")
    
    def set_dark_theme_id(self, theme_id):
        """Set the dark theme ID.
        
        Args:
            theme_id: The dark theme identifier
        """
        self._config["dark_theme_id"] = theme_id
