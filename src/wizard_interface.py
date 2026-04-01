#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WizardInterface — DNS Record Wizard sidebar page.

A multi-step wizard (QStackedWidget) for applying DNS record templates
across one or more zones.  Steps:
  0 Choose Mode
  1 Select Template
  2 Fill In Variables
  3 Select Domains
  4 Conflict Strategy
  5 Preview
  6 Execution
"""

import logging
import re

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, Signal

from qfluentwidgets import (
    PushButton, PrimaryPushButton, SearchLineEdit, LineEdit,
    ComboBox, CheckBox, RadioButton, ListWidget, TableWidget,
    StrongBodyLabel, CaptionLabel, ProgressBar,
    isDarkTheme, InfoBar, InfoBarPosition,
)

from fluent_styles import container_qss
from record_widget import _validate_record_content
from api_queue import QueueItem, PRIORITY_NORMAL

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Step index constants
# ---------------------------------------------------------------------------

_STEP_MODE      = 0
_STEP_TEMPLATE  = 1
_STEP_VARIABLES = 2
_STEP_DOMAINS   = 3
_STEP_CONFLICT  = 4
_STEP_PREVIEW   = 5
_STEP_EXECUTE   = 6

_STEP_TITLES = [
    "Choose Mode",
    "Select Template",
    "Fill In Variables",
    "Select Domains",
    "Conflict Strategy",
    "Preview",
    "Execution",
]


# ---------------------------------------------------------------------------
# WizardInterface
# ---------------------------------------------------------------------------

class WizardInterface(QtWidgets.QWidget):
    """Multi-step DNS record wizard sidebar page."""

    log_message    = Signal(str, str)   # (message, level)
    records_changed = Signal()

    def __init__(self, api_client, cache_manager, api_queue=None,
                 version_manager=None, parent=None):
        super().__init__(parent)
        self.setObjectName("wizardInterface")

        # Injected dependencies
        self._api             = api_client
        self._cache           = cache_manager
        self._api_queue       = api_queue
        self._version_manager = version_manager

        # Wizard state
        self._mode              = None
        self._template          = None
        self._custom_records    = []
        self._variables         = {}
        self._selected_domains  = []
        self._conflict_strategy = "merge"
        self._preview_rows      = []
        self._execution_items   = []

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(8)

        # ── Title row ──────────────────────────────────────────────────
        title_row = QtWidgets.QHBoxLayout()
        title_row.setSpacing(8)

        self._title_label = StrongBodyLabel("DNS Record Wizard")
        title_row.addWidget(self._title_label)
        title_row.addStretch()

        self._step_label = CaptionLabel("")
        title_row.addWidget(self._step_label)

        outer.addLayout(title_row)

        # ── Step stack ─────────────────────────────────────────────────
        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(self._build_step_mode())
        self._stack.addWidget(self._build_step_template())
        self._stack.addWidget(self._build_step_variables())
        self._stack.addWidget(self._build_step_domains())
        self._stack.addWidget(self._build_step_conflict())
        self._stack.addWidget(self._build_step_preview())
        self._stack.addWidget(self._build_step_execute())
        outer.addWidget(self._stack, 1)

        # ── Navigation bar ─────────────────────────────────────────────
        nav_row = QtWidgets.QHBoxLayout()
        nav_row.setSpacing(8)

        self._btn_reset = PushButton("Start Over")
        self._btn_reset.setVisible(False)
        self._btn_reset.clicked.connect(self._reset)
        nav_row.addWidget(self._btn_reset)

        nav_row.addStretch()

        self._btn_back = PushButton("Back")
        self._btn_back.setVisible(False)
        self._btn_back.clicked.connect(self._go_back)
        nav_row.addWidget(self._btn_back)

        self._btn_next = PrimaryPushButton("Next")
        self._btn_next.clicked.connect(self._go_next)
        nav_row.addWidget(self._btn_next)

        outer.addLayout(nav_row)

        # Initialise to step 0
        self._go_to_step(_STEP_MODE)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_to_step(self, idx: int):
        """Navigate the stack to *idx* and refresh controls."""
        self._stack.setCurrentIndex(idx)

        total = len(_STEP_TITLES)
        self._step_label.setText(
            f"Step {idx + 1} of {total} \u2014 {_STEP_TITLES[idx]}"
        )

        # Back button: hidden on first step
        self._btn_back.setVisible(idx > _STEP_MODE)

        # Start Over: only visible on the last (execution) step
        self._btn_reset.setVisible(idx == _STEP_EXECUTE)

        # Next button label and visibility
        if idx == _STEP_EXECUTE:
            self._btn_next.setVisible(False)
        else:
            self._btn_next.setVisible(True)
            if idx == _STEP_PREVIEW:
                self._btn_next.setText("Execute")
            else:
                self._btn_next.setText("Next")

        # Step entry hooks
        _entry_hooks = {
            _STEP_TEMPLATE:  self._on_enter_template_step,
            _STEP_VARIABLES: self._on_enter_variables_step,
            _STEP_DOMAINS:   self._on_enter_domains_step,
            _STEP_PREVIEW:   self._on_enter_preview_step,
        }
        hook = _entry_hooks.get(idx)
        if hook is not None:
            hook()

        self._validate_current_step()

    def _go_next(self):
        """Advance to the next step (or execute on the preview step)."""
        if not self._validate_current_step():
            return

        current = self._stack.currentIndex()

        if current == _STEP_PREVIEW:
            self._execute()
            self._go_to_step(_STEP_EXECUTE)
        else:
            self._go_to_step(current + 1)

    def _go_back(self):
        """Return to the previous step."""
        current = self._stack.currentIndex()
        if current > _STEP_MODE:
            self._go_to_step(current - 1)

    def _reset(self):
        """Reset all wizard state and return to step 0."""
        self._mode              = None
        self._template          = None
        self._custom_records    = []
        self._variables         = {}
        self._selected_domains  = []
        self._conflict_strategy = "merge"
        self._preview_rows      = []
        self._execution_items   = []
        self._go_to_step(_STEP_MODE)

    def _validate_current_step(self) -> bool:
        """Validate the current step and enable/disable the Next button."""
        idx = self._stack.currentIndex()

        if idx == _STEP_MODE:
            ok = self._mode is not None
        elif idx == _STEP_TEMPLATE:
            ok = self._validate_template_step()
        elif idx == _STEP_VARIABLES:
            ok = self._validate_variables_step()
        elif idx == _STEP_DOMAINS:
            ok = len(self._selected_domains) > 0
        elif idx == _STEP_CONFLICT:
            ok = True
        elif idx == _STEP_PREVIEW:
            ok = len(self._preview_rows) > 0
        else:
            ok = True

        self._btn_next.setEnabled(ok)
        return ok

    # ------------------------------------------------------------------
    # Step entry hooks (no-op placeholders)
    # ------------------------------------------------------------------

    def _on_enter_template_step(self):
        pass

    def _on_enter_variables_step(self):
        pass

    def _on_enter_domains_step(self):
        pass

    def _on_enter_preview_step(self):
        pass

    # ------------------------------------------------------------------
    # Validation hooks (placeholders)
    # ------------------------------------------------------------------

    def _validate_template_step(self) -> bool:
        return self._template is not None or len(self._custom_records) > 0

    def _validate_variables_step(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Execution placeholder
    # ------------------------------------------------------------------

    def _execute(self):
        pass

    # ------------------------------------------------------------------
    # Step builder placeholders
    # ------------------------------------------------------------------

    def _build_step_mode(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.addWidget(CaptionLabel("Step placeholder: Choose Mode"))
        layout.addStretch()
        return w

    def _build_step_template(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.addWidget(CaptionLabel("Step placeholder: Select Template"))
        layout.addStretch()
        return w

    def _build_step_variables(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.addWidget(CaptionLabel("Step placeholder: Fill In Variables"))
        layout.addStretch()
        return w

    def _build_step_domains(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.addWidget(CaptionLabel("Step placeholder: Select Domains"))
        layout.addStretch()
        return w

    def _build_step_conflict(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.addWidget(CaptionLabel("Step placeholder: Conflict Strategy"))
        layout.addStretch()
        return w

    def _build_step_preview(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.addWidget(CaptionLabel("Step placeholder: Preview"))
        layout.addStretch()
        return w

    def _build_step_execute(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.addWidget(CaptionLabel("Step placeholder: Execution"))
        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.setStyleSheet(container_qss())
