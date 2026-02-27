#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Shared stylesheet constants for standard Qt containers inside Fluent-themed windows.

Standard Qt widgets (QTabWidget, QGroupBox, QScrollArea, QLabel, etc.) do not
inherit the Fluent dark/light palette automatically.  The helpers here make them
transparent *and* set the correct text colour for the active theme.
"""

from qfluentwidgets import isDarkTheme

# ── Light/dark text colour tokens ────────────────────────────────────────────
_LIGHT_TEXT = "#1a1a1a"
_DARK_TEXT  = "#e4e4e4"


def _text_color() -> str:
    """Return the appropriate text hex colour for the current theme."""
    return _DARK_TEXT if isDarkTheme() else _LIGHT_TEXT


def combo_qss() -> str:
    """QSS for native QComboBox widgets — theme-aware.

    Apply directly to QComboBox widgets via setStyleSheet() so that
    the rules have highest priority and are not overridden by parent
    widget styles (e.g. qfluentwidgets SettingCard internals).
    """
    dark = isDarkTheme()
    tc = _DARK_TEXT if dark else _LIGHT_TEXT
    combo_bg = "rgba(50,50,50,0.95)" if dark else "rgba(255,255,255,0.9)"
    combo_border = "rgba(255,255,255,0.08)" if dark else "rgba(0,0,0,0.12)"
    combo_hover = "rgba(60,60,60,0.95)" if dark else "rgba(249,249,249,0.7)"
    combo_sel = "rgba(80,80,80,1)" if dark else "rgba(200,210,230,0.6)"
    return (
        f"QComboBox {{"
        f"  color: {tc};"
        f"  background: {combo_bg};"
        f"  border: 1px solid {combo_border};"
        f"  border-radius: 5px;"
        f"  padding: 5px 25px 5px 11px;"
        f"  min-height: 28px;"
        f"}}"
        f"QComboBox:hover {{"
        f"  background: {combo_hover};"
        f"}}"
        f"QComboBox::drop-down {{"
        f"  border: none;"
        f"  padding-right: 8px;"
        f"}}"
        f"QComboBox QAbstractItemView {{"
        f"  color: {tc};"
        f"  background: {combo_bg};"
        f"  border: 1px solid {combo_border};"
        f"  selection-background-color: {combo_sel};"
        f"  outline: none;"
        f"}}"
    )


def container_qss() -> str:
    """QSS for QTabWidget / QGroupBox / QLabel / form widgets — theme-aware."""
    dark = isDarkTheme()
    tc = _DARK_TEXT if dark else _LIGHT_TEXT
    tab_bg = "rgba(50,50,50,0.9)" if dark else "rgba(240,240,240,0.9)"
    tab_sel = "rgba(60,60,60,1)" if dark else "rgba(255,255,255,1)"
    return (
        f"QTabWidget::pane {{"
        f"  background: transparent;"
        f"  border: 1px solid rgba(128,128,128,0.3);"
        f"}}"
        f"QTabBar::tab {{"
        f"  color: {tc};"
        f"  background: {tab_bg};"
        f"  padding: 6px 16px;"
        f"  border: 1px solid rgba(128,128,128,0.25);"
        f"  border-bottom: none;"
        f"}}"
        f"QTabBar::tab:selected {{"
        f"  background: {tab_sel};"
        f"}}"
        f"QGroupBox {{"
        f"  background: transparent;"
        f"  border: 1px solid rgba(128,128,128,0.25);"
        f"  border-radius: 6px;"
        f"  margin-top: 8px;"
        f"  color: {tc};"
        f"}}"
        f"QGroupBox::title {{"
        f"  subcontrol-origin: margin;"
        f"  left: 8px;"
        f"  padding: 0 4px;"
        f"}}"
        f"QLabel {{"
        f"  color: {tc};"
        f"}}"
        f"QRadioButton {{"
        f"  color: {tc};"
        f"}}"
        f"QCheckBox {{"
        f"  color: {tc};"
        f"}}"
        + combo_qss()
    )


# Applied to QScrollArea wrappers (e.g. the SettingsInterface container).
SCROLL_AREA_QSS = "QScrollArea { background: transparent; border: none; }"

# Applied to QSplitter to show a subtle 1px divider line between panes.
SPLITTER_QSS = (
    "QSplitter::handle:horizontal {"
    "  background: rgba(128, 128, 128, 0.18);"
    "  width: 1px;"
    "  margin: 4px 0;"
    "}"
)
