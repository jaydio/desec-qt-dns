#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Theme manager for deSEC Qt DNS Manager.
Defines and applies theme presets for the application.
"""

import logging
from enum import Enum
from typing import Dict, Any, Optional, Tuple
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)

class ThemeType(Enum):
    """Enumeration for theme types."""
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"

class Theme:
    """Theme definition class."""
    
    def __init__(
        self,
        name: str,
        theme_type: ThemeType,
        background_color: str,
        foreground_color: str,
        accent_color: str,
        highlight_color: str,
        panel_color: str,
        border_color: str,
    ):
        """
        Initialize a theme.
        
        Args:
            name: Theme display name
            theme_type: Theme type (light or dark)
            background_color: Main background color
            foreground_color: Main text color
            accent_color: Accent color for buttons, etc.
            highlight_color: Highlight color for selections
            panel_color: Color for panels and dialogs
            border_color: Color for borders
        """
        self.name = name
        self.theme_type = theme_type
        self.background_color = background_color
        self.foreground_color = foreground_color
        self.accent_color = accent_color
        self.highlight_color = highlight_color
        self.panel_color = panel_color
        self.border_color = border_color

class ThemeManager:
    """Manages application themes."""
    
    # Define available themes
    LIGHT_THEMES = {
        "light_plus": Theme(
            name="Light+ (Default)",
            theme_type=ThemeType.LIGHT,
            background_color="#ffffff",
            foreground_color="#000000",
            accent_color="#0078d4",
            highlight_color="#d4d4d4",
            panel_color="#f3f3f3",
            border_color="#cccccc"
        ),
        "quiet_light": Theme(
            name="Quiet Light",
            theme_type=ThemeType.LIGHT,
            background_color="#f5f5f5",
            foreground_color="#333333",
            accent_color="#6a9955",
            highlight_color="#e8e8e8",
            panel_color="#f0f0f0",
            border_color="#d0d0d0"
        ),
        "solarized_light": Theme(
            name="Solarized Light",
            theme_type=ThemeType.LIGHT,
            background_color="#fdf6e3",
            foreground_color="#586e75",
            accent_color="#2aa198",
            highlight_color="#eee8d5",
            panel_color="#f5efdc",
            border_color="#d0d0d0"
        ),
        "github_light": Theme(
            name="GitHub Light",
            theme_type=ThemeType.LIGHT,
            background_color="#ffffff",
            foreground_color="#24292e",
            accent_color="#0366d6",
            highlight_color="#f1f8ff",
            panel_color="#f6f8fa",
            border_color="#e1e4e8"
        ),
        "atom_one_light": Theme(
            name="Atom One Light",
            theme_type=ThemeType.LIGHT,
            background_color="#fafafa",
            foreground_color="#383a42",
            accent_color="#4078f2",
            highlight_color="#e1e1e1",
            panel_color="#f0f0f0",
            border_color="#c0c0c0"
        )
    }
    
    DARK_THEMES = {
        "dark_plus": Theme(
            name="Dark+ (Default)",
            theme_type=ThemeType.DARK,
            background_color="#1e1e1e",
            foreground_color="#d4d4d4",
            accent_color="#0078d4",
            highlight_color="#264f78",
            panel_color="#252526",
            border_color="#454545"
        ),
        "monokai": Theme(
            name="Monokai",
            theme_type=ThemeType.DARK,
            background_color="#272822",
            foreground_color="#f8f8f2",
            accent_color="#a6e22e",
            highlight_color="#49483e",
            panel_color="#2d2e2a",
            border_color="#3e3d32"
        ),
        "dracula": Theme(
            name="Dracula",
            theme_type=ThemeType.DARK,
            background_color="#282a36",
            foreground_color="#f8f8f2",
            accent_color="#bd93f9",
            highlight_color="#44475a",
            panel_color="#383a4a",
            border_color="#6272a4"
        ),
        "one_dark_pro": Theme(
            name="One Dark Pro",
            theme_type=ThemeType.DARK,
            background_color="#282c34",
            foreground_color="#abb2bf",
            accent_color="#61afef",
            highlight_color="#3e4451",
            panel_color="#21252b",
            border_color="#5c6370"
        ),
        "github_dark": Theme(
            name="GitHub Dark",
            theme_type=ThemeType.DARK,
            background_color="#0d1117",
            foreground_color="#c9d1d9",
            accent_color="#58a6ff",
            highlight_color="#1f2937",
            panel_color="#161b22",
            border_color="#30363d"
        )
    }
    
    def __init__(self, config_manager):
        """
        Initialize the theme manager.
        
        Args:
            config_manager: The application configuration manager
        """
        self.config_manager = config_manager
        self.app = QtWidgets.QApplication.instance()
        self.current_theme = None
        self._is_dark_mode = None  # Initialize to None to force first check
        
        # Initialize timer first, so it can be referenced by other methods
        self.system_theme_timer = QtCore.QTimer()
        self.system_theme_timer.timeout.connect(self._check_system_theme)
        self.system_theme_timer.setInterval(5000)  # Check every 5 seconds
        
        # Force immediate system theme detection and theme application for system theme mode
        theme_type = self.config_manager.get_theme_type()
        if theme_type == ThemeType.SYSTEM.value:
            # For system theme, detect and apply immediately
            is_dark = self._detect_system_theme()
            theme_id = None
            
            if is_dark:
                theme_id = self.config_manager.get_dark_theme_id()
                logger.warning(f"STARTUP: Applying DARK theme based on system detection: {theme_id}")
            else:
                theme_id = self.config_manager.get_light_theme_id()
                logger.warning(f"STARTUP: Applying LIGHT theme based on system detection: {theme_id}")
                
            # Use our special initialization version that doesn't touch the timer
            self._apply_theme_startup(theme_id)  # Apply without touching timer
        
    def get_theme_types(self):
        """
        Get available theme types as a dictionary.
        
        Returns:
            Dict mapping theme type enum values to display names
        """
        return {
            ThemeType.LIGHT.value: "Light",
            ThemeType.DARK.value: "Dark",
            ThemeType.SYSTEM.value: "System Default",
        }
    
    def get_theme_names(self, theme_type=None) -> Dict[str, str]:
        """
        Get names of available themes by type.
        
        Args:
            theme_type: Optional theme type filter (can be ThemeType enum or string)
        
        Returns:
            Dict mapping theme IDs to display names
        """
        result = {}
        
        # Convert string to enum if needed
        if isinstance(theme_type, str):
            try:
                theme_type = ThemeType(theme_type)
            except ValueError:
                # Invalid theme type, treat as None
                theme_type = None
        
        if theme_type in (None, ThemeType.LIGHT, "light"):
            result.update({k: v.name for k, v in self.LIGHT_THEMES.items()})
        
        if theme_type in (None, ThemeType.DARK, "dark"):
            result.update({k: v.name for k, v in self.DARK_THEMES.items()})
        
        return result
    
    def get_theme(self, theme_id: str) -> Optional[Theme]:
        """
        Get a theme by ID.
        
        Args:
            theme_id: ID of the theme
        
        Returns:
            Theme object if found, None otherwise
        """
        return self.LIGHT_THEMES.get(theme_id) or self.DARK_THEMES.get(theme_id)
    
    def _detect_system_theme(self):
        """Detect the current system theme (light or dark).
        
        Uses multiple detection mechanisms for optimal platform compatibility:
        1. Qt platform theme hints (most reliable when available)
        2. System palette luminance analysis (fallback method)
        
        Returns:
            bool: True if system is in dark mode, False for light mode
        """
        # Platform-specific detection techniques
        is_dark = None
                
        # Try Qt platform theme hint first (most reliable when available)
        if hasattr(QtCore.Qt, 'ApplicationAttribute') and hasattr(QtCore.Qt.ApplicationAttribute, 'AA_UseDarkThemeOnDarkMode'):
            # Qt6.5+ provides direct dark mode detection
            if self.app.testAttribute(QtCore.Qt.ApplicationAttribute.AA_UseDarkThemeOnDarkMode):
                is_dark = True
                logger.debug("Dark mode detected via Qt platform hint")
            
        # Check palette if still undetermined
        if is_dark is None:
            # Calculate luminance of application background color
            palette = self.app.palette()
            
            # Try multiple color roles for more accuracy
            window_color = palette.color(QtGui.QPalette.ColorRole.Window)
            text_color = palette.color(QtGui.QPalette.ColorRole.WindowText)
            
            # Consider dark if background luminance is low
            win_luminance = (0.299 * window_color.red() + 
                          0.587 * window_color.green() + 
                          0.114 * window_color.blue()) / 255
            
            # Additional check: if text is light and background is dark
            text_luminance = (0.299 * text_color.red() + 
                           0.587 * text_color.green() + 
                           0.114 * text_color.blue()) / 255
            
            # Cross-check both luminance values for better detection
            # Dark theme typically has dark background (low luminance) and light text (high luminance)
            if win_luminance < 0.5 and text_luminance > 0.5:
                is_dark = True
            else:
                is_dark = win_luminance < 0.4  # Lower threshold for more accurate detection
                
            logger.debug(f"System theme detection via palette: bg_luminance={win_luminance:.2f}, text_luminance={text_luminance:.2f}")
            
        self._is_dark_mode = is_dark
        logger.debug(f"FINAL SYSTEM THEME DETECTION: {'DARK' if is_dark else 'LIGHT'}")
        return is_dark
    
    def _check_system_theme(self, force=False):
        """Check if system theme has changed and update if necessary.
        
        Args:
            force: Whether to force theme update even if system theme hasn't changed
        """
        # Get current system theme
        previous_is_dark = getattr(self, '_is_dark_mode', None)
        is_dark = self._detect_system_theme()
        
        # Only update if dark mode state has changed or force is True or first run
        if force or previous_is_dark is None or is_dark != previous_is_dark:
            # Only apply theme if we're in system theme mode
            if self.config_manager.get_theme_type() == ThemeType.SYSTEM.value:
                # Apply appropriate theme based on system detection
                if is_dark:
                    theme_id = self.config_manager.get_dark_theme_id()
                    self._apply_theme(theme_id)
                    logger.info(f"Applied dark theme based on system theme: {theme_id}")
                else:
                    theme_id = self.config_manager.get_light_theme_id() 
                    self._apply_theme(theme_id)
                    logger.info(f"Applied light theme based on system theme: {theme_id}")
    
    def _get_system_default_theme(self) -> Theme:
        """
        Get the appropriate theme based on system preferences.
        
        Returns:
            The appropriate theme object
        """
        palette = self.app.palette()
        window_color = palette.color(QtGui.QPalette.ColorRole.Window)
        # Consider dark if luminance is less than 0.5 (simplified calculation)
        luminance = (0.299 * window_color.red() + 
                     0.587 * window_color.green() + 
                     0.114 * window_color.blue()) / 255
        self._is_dark_mode = luminance < 0.5
        
        # Use the default theme for the detected mode
        if self._is_dark_mode:
            return self.DARK_THEMES["dark_plus"]
        else:
            return self.LIGHT_THEMES["light_plus"]
    
    def apply_theme(self):
        """
        Apply theme from configuration.
        """
        # Get theme type from configuration
        theme_type = self.config_manager.get_theme_type()
        
        if theme_type == ThemeType.LIGHT.value:
            # Use light theme ID
            theme_id = self.config_manager.get_light_theme_id()
            self._apply_theme(theme_id)
            logger.debug("Applied explicit light theme")
            # Stop system theme timer as we're using a fixed theme
            if self.system_theme_timer.isActive():
                self.system_theme_timer.stop()
                
        elif theme_type == ThemeType.DARK.value:
            # Use dark theme ID
            theme_id = self.config_manager.get_dark_theme_id()
            self._apply_theme(theme_id)
            logger.debug("Applied explicit dark theme")
            # Stop system theme timer as we're using a fixed theme
            if self.system_theme_timer.isActive():
                self.system_theme_timer.stop()
                
        elif theme_type == ThemeType.SYSTEM.value:
            # For system theme, check the current system appearance and apply appropriate theme
            is_dark = self._detect_system_theme()
            
            if is_dark:
                theme_id = self.config_manager.get_dark_theme_id()
                self._apply_theme(theme_id)
                logger.info(f"Applied dark theme (based on system detection): {theme_id}")
            else:
                theme_id = self.config_manager.get_light_theme_id()
                self._apply_theme(theme_id)
                logger.info(f"Applied light theme (based on system detection): {theme_id}")
                
            # Start the system theme monitoring timer if not already started
            if not self.system_theme_timer.isActive():
                self.system_theme_timer.start()
        else:
            # Default to light theme
            theme_id = self.config_manager.get_light_theme_id()
            self._apply_theme(theme_id)
    
    def _apply_theme_startup(self, theme_id):
        """Special version of _apply_theme for startup that doesn't touch the timer.
        
        Args:
            theme_id: ID of the theme to apply
        """
        self.current_theme = self.get_theme(theme_id)
        
        if not self.current_theme:
            # Fall back to default
            logger.warning(f"Theme {theme_id} not found, using default")
            self.current_theme = self.LIGHT_THEMES["light_plus"]
        
        self._apply_theme_to_app(self.current_theme)
        logger.info(f"Applied theme at startup: {self.current_theme.name}")
        
    def _apply_theme(self, theme_id):
        self.current_theme = self.get_theme(theme_id)
        if self.system_theme_timer.isActive():
            self.system_theme_timer.stop()
                
        if not self.current_theme:
            # Fall back to default
            logger.warning(f"Theme {theme_id} not found, using default")
            self.current_theme = self.LIGHT_THEMES["light_plus"]
        
        self._apply_theme_to_app(self.current_theme)
        logger.info(f"Applied theme: {self.current_theme.name}")
        
    def _apply_theme_to_app(self, theme: Theme):
        """
        Apply theme to application.
        
        Args:
            theme: Theme to apply
        """
        palette = QtGui.QPalette()
        
        # Set basic palette colors
        palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(theme.background_color))
        palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(theme.foreground_color))
        palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(theme.background_color))
        palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(theme.panel_color))
        palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(theme.panel_color))
        palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(theme.foreground_color))
        palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(theme.foreground_color))
        palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(theme.panel_color))
        palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(theme.foreground_color))
        palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor("#ffffff"))
        
        # Set highlight and link colors
        palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(theme.accent_color))
        palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#ffffff"))
        palette.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(theme.accent_color))
        
        # Set disabled colors
        if theme.theme_type == ThemeType.DARK:
            disabled_color = QtGui.QColor(theme.foreground_color)
            disabled_color.setAlpha(128)
            palette.setColor(QtGui.QPalette.ColorGroup.Disabled, 
                             QtGui.QPalette.ColorRole.WindowText, 
                             disabled_color)
            palette.setColor(QtGui.QPalette.ColorGroup.Disabled, 
                             QtGui.QPalette.ColorRole.Text, 
                             disabled_color)
            palette.setColor(QtGui.QPalette.ColorGroup.Disabled, 
                             QtGui.QPalette.ColorRole.ButtonText, 
                             disabled_color)
        
        # Apply the palette
        self.app.setPalette(palette)
        
        # Create and apply stylesheet
        stylesheet = f"""
        QToolTip {{
            border: 1px solid {theme.border_color};
            background-color: {theme.panel_color};
            color: {theme.foreground_color};
            padding: 4px;
        }}
        
        QStatusBar {{
            background-color: {theme.panel_color};
            color: {theme.foreground_color};
            border-top: 1px solid {theme.border_color};
        }}
        
        QMenuBar {{
            background-color: {theme.panel_color};
            color: {theme.foreground_color};
        }}
        
        QMenuBar::item:selected {{
            background-color: {theme.highlight_color};
        }}
        
        QMenu {{
            background-color: {theme.panel_color};
            color: {theme.foreground_color};
            border: 1px solid {theme.border_color};
        }}
        
        QMenu::item:selected {{
            background-color: {theme.highlight_color};
        }}
        
        QTableView {{
            gridline-color: {theme.border_color};
        }}
        
        QHeaderView::section {{
            background-color: {theme.panel_color};
            color: {theme.foreground_color};
            border: 1px solid {theme.border_color};
        }}
        
        QTabWidget::pane {{
            border: 1px solid {theme.border_color};
        }}
        
        QTabBar::tab {{
            background-color: {theme.panel_color};
            color: {theme.foreground_color};
            border: 1px solid {theme.border_color};
            padding: 5px 10px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {theme.background_color};
            border-bottom-color: {theme.background_color};
        }}
        
        QSplitter::handle {{
            background-color: {theme.border_color};
        }}
        
        QScrollBar {{
            background: {theme.panel_color};
            border: 1px solid {theme.border_color};
        }}
        
        QScrollBar::handle {{
            background: {theme.border_color};
        }}
        
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {theme.background_color};
            color: {theme.foreground_color};
            border: 1px solid {theme.border_color};
            selection-background-color: {theme.accent_color};
            selection-color: white;
        }}
        """
        
        self.app.setStyleSheet(stylesheet)
