#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Profile Manager for deSEC Qt DNS Manager.
Handles multiple user profiles with isolated tokens, cache, and settings.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from config_manager import ConfigManager
from cache_manager import CacheManager

logger = logging.getLogger(__name__)


class ProfileManager:
    """
    Manages multiple user profiles with isolated configurations and caches.
    
    Each profile has its own:
    - Configuration directory
    - ConfigManager instance
    - CacheManager instance
    - API tokens and settings
    """
    
    BASE_DIR = os.path.expanduser("~/.config/desecqt")
    PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
    PROFILE_CONFIG_FILE = os.path.join(BASE_DIR, "profiles.json")
    DEFAULT_PROFILE_NAME = "default"
    
    def __init__(self):
        """Initialize the profile manager."""
        self._ensure_directories_exist()
        self._profiles_config = self._load_profiles_config()
        self._current_profile_name = None
        self._current_config_manager = None
        self._current_cache_manager = None
        
        # Initialize with the last used profile or default
        last_profile = self._profiles_config.get("last_used_profile", self.DEFAULT_PROFILE_NAME)
        self.switch_to_profile(last_profile)
    
    def _ensure_directories_exist(self):
        """Create necessary directories if they don't exist."""
        try:
            os.makedirs(self.PROFILES_DIR, exist_ok=True)
            logger.info(f"Ensured profiles directory exists: {self.PROFILES_DIR}")
        except OSError as e:
            logger.error(f"Failed to create profiles directory: {e}")
    
    def _load_profiles_config(self) -> Dict:
        """Load the profiles configuration file."""
        default_config = {
            "profiles": {},
            "last_used_profile": self.DEFAULT_PROFILE_NAME,
            "created_at": datetime.now().isoformat()
        }
        
        if os.path.exists(self.PROFILE_CONFIG_FILE):
            try:
                with open(self.PROFILE_CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    # Ensure required keys exist
                    for key in default_config:
                        if key not in config:
                            config[key] = default_config[key]
                    return config
            except Exception as e:
                logger.error(f"Failed to load profiles config: {e}")
                return default_config
        else:
            # Create default profile entry
            default_config["profiles"][self.DEFAULT_PROFILE_NAME] = {
                "name": self.DEFAULT_PROFILE_NAME,
                "display_name": "Default Profile",
                "created_at": datetime.now().isoformat(),
                "last_used": datetime.now().isoformat()
            }
            self._save_profiles_config(default_config)
            return default_config
    
    def _save_profiles_config(self, config: Dict = None):
        """Save the profiles configuration to file."""
        if config is None:
            config = self._profiles_config
            
        try:
            with open(self.PROFILE_CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            logger.debug("Profiles configuration saved")
        except Exception as e:
            logger.error(f"Failed to save profiles config: {e}")
    
    def _get_profile_directory(self, profile_name: str) -> str:
        """Get the directory path for a specific profile."""
        return os.path.join(self.PROFILES_DIR, profile_name)
    
    def _migrate_legacy_config(self):
        """Migrate legacy single-profile config to default profile."""
        legacy_config_file = os.path.join(self.BASE_DIR, "config.json")
        legacy_cache_dir = os.path.join(self.BASE_DIR, "cache")
        
        if os.path.exists(legacy_config_file) or os.path.exists(legacy_cache_dir):
            logger.info("Migrating legacy configuration to default profile...")
            
            default_profile_dir = self._get_profile_directory(self.DEFAULT_PROFILE_NAME)
            os.makedirs(default_profile_dir, exist_ok=True)
            
            # Move config file
            if os.path.exists(legacy_config_file):
                new_config_file = os.path.join(default_profile_dir, "config.json")
                try:
                    os.rename(legacy_config_file, new_config_file)
                    logger.info(f"Migrated config file to {new_config_file}")
                except Exception as e:
                    logger.error(f"Failed to migrate config file: {e}")
            
            # Move cache directory
            if os.path.exists(legacy_cache_dir):
                new_cache_dir = os.path.join(default_profile_dir, "cache")
                try:
                    os.rename(legacy_cache_dir, new_cache_dir)
                    logger.info(f"Migrated cache directory to {new_cache_dir}")
                except Exception as e:
                    logger.error(f"Failed to migrate cache directory: {e}")
    
    def get_available_profiles(self) -> List[Dict]:
        """Get list of available profiles with metadata."""
        profiles = []
        for profile_name, profile_data in self._profiles_config.get("profiles", {}).items():
            profiles.append({
                "name": profile_name,
                "display_name": profile_data.get("display_name", profile_name),
                "created_at": profile_data.get("created_at"),
                "last_used": profile_data.get("last_used"),
                "is_current": profile_name == self._current_profile_name
            })
        return sorted(profiles, key=lambda x: x["last_used"] or "", reverse=True)
    
    def create_profile(self, profile_name: str, display_name: str = None) -> bool:
        """
        Create a new profile.
        
        Args:
            profile_name: Internal profile name (used for directories)
            display_name: Human-readable profile name
            
        Returns:
            True if successful, False otherwise
        """
        if not profile_name or profile_name in self._profiles_config.get("profiles", {}):
            logger.error(f"Profile '{profile_name}' already exists or is invalid")
            return False
        
        try:
            # Create profile directory
            profile_dir = self._get_profile_directory(profile_name)
            os.makedirs(profile_dir, exist_ok=True)
            
            # Add to profiles config
            self._profiles_config.setdefault("profiles", {})[profile_name] = {
                "name": profile_name,
                "display_name": display_name or profile_name,
                "created_at": datetime.now().isoformat(),
                "last_used": None
            }
            
            self._save_profiles_config()
            logger.info(f"Created profile '{profile_name}' at {profile_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create profile '{profile_name}': {e}")
            return False
    
    def delete_profile(self, profile_name: str) -> bool:
        """
        Delete a profile and all its data.
        
        Args:
            profile_name: Profile name to delete
            
        Returns:
            True if successful, False otherwise
        """
        if profile_name == self.DEFAULT_PROFILE_NAME:
            logger.error("Cannot delete the default profile")
            return False
            
        if profile_name not in self._profiles_config.get("profiles", {}):
            logger.error(f"Profile '{profile_name}' does not exist")
            return False
        
        try:
            # Remove profile directory and all contents
            profile_dir = self._get_profile_directory(profile_name)
            if os.path.exists(profile_dir):
                import shutil
                shutil.rmtree(profile_dir)
                logger.info(f"Removed profile directory: {profile_dir}")
            
            # Remove from profiles config
            del self._profiles_config["profiles"][profile_name]
            
            # If this was the current profile, switch to default
            if profile_name == self._current_profile_name:
                self.switch_to_profile(self.DEFAULT_PROFILE_NAME)
            
            self._save_profiles_config()
            logger.info(f"Deleted profile '{profile_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete profile '{profile_name}': {e}")
            return False
    
    def switch_to_profile(self, profile_name: str) -> bool:
        """
        Switch to a different profile.
        
        Args:
            profile_name: Profile name to switch to
            
        Returns:
            True if successful, False otherwise
        """
        # Check if profile exists, create it if it's the default
        if profile_name not in self._profiles_config.get("profiles", {}):
            if profile_name == self.DEFAULT_PROFILE_NAME:
                self.create_profile(self.DEFAULT_PROFILE_NAME, "Default Profile")
            else:
                logger.error(f"Profile '{profile_name}' does not exist")
                return False
        
        try:
            # Migrate legacy config if switching to default for the first time
            if profile_name == self.DEFAULT_PROFILE_NAME and self._current_profile_name is None:
                self._migrate_legacy_config()
            
            profile_dir = self._get_profile_directory(profile_name)
            os.makedirs(profile_dir, exist_ok=True)
            
            # Create new managers for this profile
            # Override the default paths to use profile-specific directories
            config_manager = ConfigManager()
            config_manager.CONFIG_DIR = profile_dir
            config_manager.CONFIG_FILE = os.path.join(profile_dir, "config.json")
            config_manager._ensure_config_dir_exists()
            config_manager._load_config()
            
            cache_manager = CacheManager()
            cache_manager.CACHE_DIR = os.path.join(profile_dir, "cache")
            cache_manager.ZONES_CACHE_FILE = os.path.join(cache_manager.CACHE_DIR, "zones.json")
            cache_manager._ensure_cache_dir_exists()
            
            # Update current profile
            self._current_profile_name = profile_name
            self._current_config_manager = config_manager
            self._current_cache_manager = cache_manager
            
            # Update last used timestamp
            self._profiles_config["profiles"][profile_name]["last_used"] = datetime.now().isoformat()
            self._profiles_config["last_used_profile"] = profile_name
            self._save_profiles_config()
            
            logger.info(f"Switched to profile '{profile_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch to profile '{profile_name}': {e}")
            return False
    
    def get_current_profile_name(self) -> Optional[str]:
        """Get the name of the currently active profile."""
        return self._current_profile_name
    
    def get_current_profile_info(self) -> Optional[Dict]:
        """Get information about the currently active profile."""
        if not self._current_profile_name:
            return None
            
        profile_data = self._profiles_config.get("profiles", {}).get(self._current_profile_name)
        if profile_data:
            return {
                "name": self._current_profile_name,
                "display_name": profile_data.get("display_name", self._current_profile_name),
                "created_at": profile_data.get("created_at"),
                "last_used": profile_data.get("last_used")
            }
        return None
    
    def get_config_manager(self) -> Optional[ConfigManager]:
        """Get the ConfigManager for the current profile."""
        return self._current_config_manager
    
    def get_cache_manager(self) -> Optional[CacheManager]:
        """Get the CacheManager for the current profile."""
        return self._current_cache_manager
    
    def rename_profile(self, old_name: str, new_name: str, new_display_name: str = None) -> bool:
        """
        Rename a profile.
        
        Args:
            old_name: Current profile name
            new_name: New profile name
            new_display_name: New display name (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if old_name == self.DEFAULT_PROFILE_NAME:
            # For default profile, only allow changing display name
            if new_name != self.DEFAULT_PROFILE_NAME:
                logger.error("Cannot rename the default profile's internal name")
                return False
            
            if new_display_name:
                self._profiles_config["profiles"][old_name]["display_name"] = new_display_name
                self._save_profiles_config()
                logger.info(f"Updated default profile display name to '{new_display_name}'")
                return True
            return False
        
        if old_name not in self._profiles_config.get("profiles", {}):
            logger.error(f"Profile '{old_name}' does not exist")
            return False
            
        if new_name in self._profiles_config.get("profiles", {}):
            logger.error(f"Profile '{new_name}' already exists")
            return False
        
        try:
            # Rename directory
            old_dir = self._get_profile_directory(old_name)
            new_dir = self._get_profile_directory(new_name)
            
            if os.path.exists(old_dir):
                os.rename(old_dir, new_dir)
            
            # Update profiles config
            profile_data = self._profiles_config["profiles"][old_name].copy()
            profile_data["name"] = new_name
            if new_display_name:
                profile_data["display_name"] = new_display_name
            
            del self._profiles_config["profiles"][old_name]
            self._profiles_config["profiles"][new_name] = profile_data
            
            # Update current profile reference if needed
            if self._current_profile_name == old_name:
                self._current_profile_name = new_name
                
            # Update last used profile reference if needed
            if self._profiles_config.get("last_used_profile") == old_name:
                self._profiles_config["last_used_profile"] = new_name
            
            self._save_profiles_config()
            logger.info(f"Renamed profile from '{old_name}' to '{new_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rename profile from '{old_name}' to '{new_name}': {e}")
            return False
