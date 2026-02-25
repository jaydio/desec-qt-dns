#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Theme manager for deSEC Qt DNS Manager.
Thin wrapper around qfluentwidgets theming — supports dark, light, and auto (OS) modes.
"""

import logging
from qfluentwidgets import setTheme, Theme, qconfig

logger = logging.getLogger(__name__)

# Map config string values to qfluentwidgets Theme enum
_THEME_MAP = {
    "dark":   Theme.DARK,
    "light":  Theme.LIGHT,
    "auto":   Theme.AUTO,
    # Legacy value from old config files
    "system": Theme.AUTO,
}


class ThemeManager:
    """Manages application theme using qfluentwidgets native theming."""

    def __init__(self, config_manager):
        self.config_manager = config_manager

    def apply_theme(self):
        """Read theme from config and apply it."""
        theme_str = self.config_manager.get_theme_type()
        theme = _THEME_MAP.get(theme_str, Theme.AUTO)
        setTheme(theme)
        logger.info(f"Applied theme: {theme_str} → {theme}")

    def set_dark(self):
        self.config_manager.set_theme_type("dark")
        setTheme(Theme.DARK)

    def set_light(self):
        self.config_manager.set_theme_type("light")
        setTheme(Theme.LIGHT)

    def set_auto(self):
        self.config_manager.set_theme_type("auto")
        setTheme(Theme.AUTO)

    def connect_theme_changed(self, callback):
        """Connect a callback to fire whenever the active theme changes."""
        qconfig.themeChanged.connect(callback)
