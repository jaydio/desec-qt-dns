#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration manager for deSEC Qt DNS Manager.
Handles reading, writing, and verifying configuration settings.
"""

import os
import stat
import json
import logging
import tempfile
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration including API token storage."""
    
    CONFIG_DIR = os.path.expanduser("~/.config/desecqt")
    CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
    SALT_FILE = os.path.join(CONFIG_DIR, "salt")
    DEFAULT_API_URL = "https://desec.io/api/v1"
    
    def __init__(self):
        """Initialize the configuration manager."""
        self._config = {
            "api_url": self.DEFAULT_API_URL,
            "auth_token": "",
            "sync_interval_minutes": 15,  # Default sync interval in minutes
            "debug_mode": False,
            "show_log_console": True,  # Default to showing log console
            "keepalive_interval": 60,  # Default keepalive check interval in seconds
            "offline_mode": False,  # Default to online mode
            "show_multiline_records": True,  # Default to full display of multiline records
            "api_rate_limit": 1.0,  # Default API requests per second (0 = no limit)
            "theme_type": "auto",  # Default theme type: auto, light, dark
            "queue_history_persist": True,  # Persist queue history across restarts
            "queue_history_limit": 5000,  # Max queue history entries to retain
        }
        self._ensure_config_dir_exists()
        self._load_config()
        
    def _ensure_config_dir_exists(self):
        """Create configuration directory if it doesn't exist, with restrictive permissions."""
        try:
            os.makedirs(self.CONFIG_DIR, exist_ok=True)
            os.chmod(self.CONFIG_DIR, stat.S_IRWXU)  # 0700
        except OSError as e:
            logger.error(f"Failed to create/secure config directory: {e}")
    
    def _get_legacy_encryption_key(self):
        """Derive the old (pre-salt-file) encryption key for migration."""
        salt = (os.path.expanduser("~") + os.name).encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(b"desecqt-fixed-passphrase"))

    def _get_salt(self):
        """Read or create the random salt file (0600 permissions)."""
        if os.path.exists(self.SALT_FILE):
            with open(self.SALT_FILE, "rb") as f:
                salt = f.read()
            if len(salt) == 32:
                return salt
            logger.warning("Salt file has unexpected length, regenerating")
        salt = os.urandom(32)
        fd = os.open(self.SALT_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, salt)
        finally:
            os.close(fd)
        logger.info("Generated new random salt")
        return salt

    def _get_encryption_key(self):
        """Derive an encryption key using a per-installation random salt."""
        salt = self._get_salt()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(b"desecqt-fixed-passphrase"))
    
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
        """Load configuration from file, migrating encryption salt if needed."""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    stored_config = json.load(f)

                # Decrypt the auth token if it exists
                if 'encrypted_auth_token' in stored_config:
                    enc_token = stored_config['encrypted_auth_token']
                    token = self._decrypt_token(enc_token)

                    # Migration: if new-key decryption failed but legacy key works,
                    # re-encrypt with the new random salt.
                    if not token and enc_token:
                        try:
                            legacy_key = self._get_legacy_encryption_key()
                            f_legacy = Fernet(legacy_key)
                            token = f_legacy.decrypt(enc_token.encode()).decode()
                            if token:
                                logger.info("Migrated token encryption to random salt")
                        except Exception:
                            token = ""

                    stored_config['auth_token'] = token
                    del stored_config['encrypted_auth_token']

                    # Persist immediately so the token is re-encrypted with the new salt
                    if token:
                        self._config.update(stored_config)
                        self.save_config()
                        logger.info("Configuration loaded and token re-encrypted successfully")
                        return

                # Only update with explicitly set values
                self._config.update(stored_config)
                logger.info("Configuration loaded successfully")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load config: {e}")
        else:
            logger.info("No configuration file found, using defaults")
    
    def save_config(self):
        """Save current configuration to file with atomic write and restrictive permissions."""
        try:
            config_to_save = self._config.copy()

            # Encrypt the auth token for storage
            if 'auth_token' in config_to_save and config_to_save['auth_token']:
                config_to_save['encrypted_auth_token'] = self._encrypt_token(config_to_save['auth_token'])
                del config_to_save['auth_token']

            # Atomic write: write to temp file then rename into place
            fd, tmp_path = tempfile.mkstemp(dir=self.CONFIG_DIR, suffix=".tmp")
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(config_to_save, f, indent=2)
                os.replace(tmp_path, self.CONFIG_FILE)
            except BaseException:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
            os.chmod(self.CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0600
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
        
    def get_api_rate_limit(self):
        """Get the API request rate limit in requests per second.
        
        Returns:
            float: The maximum requests per second (0 = no limit)
        """
        return self._config.get("api_rate_limit", 1.0)  # Default to 1 request per second
    
    def set_api_rate_limit(self, rate_limit):
        """Set the API request rate limit.
        
        Args:
            rate_limit (float): Maximum requests per second (0 = no limit)
        """
        self._config["api_rate_limit"] = float(rate_limit)
    
    def get_setting(self, key, default=None):
        """Get a configuration setting by key.
        
        Args:
            key (str): Configuration key
            default: Default value if key doesn't exist
            
        Returns:
            The configuration value or default
        """
        return self._config.get(key, default)
    
    def set_setting(self, key, value):
        """Set a configuration setting by key.
        
        Args:
            key (str): Configuration key
            value: Value to set
        """
        self._config[key] = value
    
    def set_api_throttle_seconds(self, seconds):
        """Set the API request throttling delay in seconds.
        
        Args:
            seconds (float): Delay between API requests in seconds
        """
        self._config["api_throttle_seconds"] = seconds
        
    def get_theme_type(self):
        """Get the theme type.

        Returns:
            str: 'auto', 'light', or 'dark'
        """
        raw = self._config.get("theme_type", "auto")
        # Migrate legacy 'system' value from old config files
        if raw == "system":
            return "auto"
        return raw

    def set_theme_type(self, theme_type):
        """Set the theme type.

        Args:
            theme_type (str): 'auto', 'light', or 'dark'
        """
        self._config["theme_type"] = theme_type

    def get_queue_history_persist(self):
        """Get whether queue history should persist across restarts."""
        return self._config.get("queue_history_persist", True)

    def set_queue_history_persist(self, enabled):
        """Set whether queue history should persist across restarts."""
        self._config["queue_history_persist"] = enabled

    def get_queue_history_limit(self):
        """Get the maximum number of queue history entries to retain."""
        return self._config.get("queue_history_limit", 5000)

    def set_queue_history_limit(self, limit):
        """Set the maximum number of queue history entries to retain."""
        self._config["queue_history_limit"] = int(limit)
