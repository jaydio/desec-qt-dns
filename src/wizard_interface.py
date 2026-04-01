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
from wizard_templates import TEMPLATES, CATEGORIES

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

    _RECORD_TYPES = [
        "A", "AAAA", "CAA", "CNAME", "DNAME", "HTTPS", "MX", "NAPTR",
        "NS", "PTR", "SPF", "SRV", "SSHFP", "SVCB", "TLSA", "TXT", "URI",
    ]

    _TTL_OPTIONS = [
        ("60", "1 min"),
        ("300", "5 min"),
        ("900", "15 min"),
        ("3600", "1 hour"),
        ("21600", "6 hours"),
        ("43200", "12 hours"),
        ("86400", "24 hours"),
    ]

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
        if self._mode == "preset":
            self._template_stack.setCurrentIndex(0)
            self._populate_template_list()
        else:
            self._template_stack.setCurrentIndex(1)

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
        if self._mode == "preset":
            return self._template is not None
        else:
            records = self._read_custom_records()
            self._custom_records = records
            return len(records) > 0

    def _validate_variables_step(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Template step helpers
    # ------------------------------------------------------------------

    def _populate_template_list(self):
        self._template_list.clear()
        self._template_search.clear()
        for cat in CATEGORIES:
            header_item = QtWidgets.QListWidgetItem(f"── {cat} ──")
            header_item.setFlags(Qt.ItemFlag.NoItemFlags)
            font = header_item.font()
            font.setBold(True)
            header_item.setFont(font)
            self._template_list.addItem(header_item)

            for tpl in TEMPLATES:
                if tpl["category"] != cat:
                    continue
                item = QtWidgets.QListWidgetItem(
                    f"  {tpl['name']}  ({len(tpl['records'])} records)"
                )
                item.setData(Qt.ItemDataRole.UserRole, tpl["id"])
                self._template_list.addItem(item)

    def _filter_templates(self, text):
        ft = text.strip().lower()
        for i in range(self._template_list.count()):
            item = self._template_list.item(i)
            tpl_id = item.data(Qt.ItemDataRole.UserRole)
            if tpl_id is None:
                item.setHidden(False)
                continue
            tpl = next((t for t in TEMPLATES if t["id"] == tpl_id), None)
            if tpl and ft:
                visible = (ft in tpl["name"].lower()
                           or ft in tpl["description"].lower()
                           or ft in tpl["category"].lower())
            else:
                visible = True
            item.setHidden(not visible)

        # Hide category headers with no visible children
        last_header = None
        last_header_has_children = False
        for i in range(self._template_list.count()):
            item = self._template_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) is None:
                if last_header is not None:
                    last_header.setHidden(not last_header_has_children)
                last_header = item
                last_header_has_children = False
            elif not item.isHidden():
                last_header_has_children = True
        if last_header is not None:
            last_header.setHidden(not last_header_has_children)

    def _on_template_selected(self, current, _previous):
        if current is None:
            self._template = None
            self._validate_current_step()
            return
        tpl_id = current.data(Qt.ItemDataRole.UserRole)
        if tpl_id is None:
            self._template = None
            self._validate_current_step()
            return
        tpl = next((t for t in TEMPLATES if t["id"] == tpl_id), None)
        self._template = tpl
        if tpl:
            self._template_name_label.setText(tpl["name"])
            self._template_desc_label.setText(tpl["description"])
            self._template_records_table.setRowCount(len(tpl["records"]))
            for r, rec in enumerate(tpl["records"]):
                self._template_records_table.setItem(
                    r, 0, QtWidgets.QTableWidgetItem(rec["type"]))
                self._template_records_table.setItem(
                    r, 1, QtWidgets.QTableWidgetItem(rec["subname"] or "@"))
                self._template_records_table.setItem(
                    r, 2, QtWidgets.QTableWidgetItem(str(rec["ttl"])))
                self._template_records_table.setItem(
                    r, 3, QtWidgets.QTableWidgetItem(rec["content"]))
        self._validate_current_step()

    def _build_custom_builder(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lay.addWidget(StrongBodyLabel("Build Custom Record Set"))
        lay.addWidget(CaptionLabel(
            "Add records below. Use {variable} placeholders in subdomain or "
            "content fields (e.g. {domain}, {ip_address}). Variables will be "
            "prompted in the next step."
        ))

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(8)
        btn_add = PushButton("Add Row")
        btn_add.clicked.connect(self._custom_add_row)
        toolbar.addWidget(btn_add)
        btn_remove = PushButton("Remove Selected")
        btn_remove.clicked.connect(self._custom_remove_row)
        toolbar.addWidget(btn_remove)
        toolbar.addStretch()
        self._custom_row_count = CaptionLabel("0 records")
        toolbar.addWidget(self._custom_row_count)
        lay.addLayout(toolbar)

        self._custom_table = TableWidget()
        self._custom_table.setColumnCount(4)
        self._custom_table.setHorizontalHeaderLabels(
            ["Type", "Subdomain", "TTL", "Content"]
        )
        self._custom_table.horizontalHeader().setStretchLastSection(True)
        self._custom_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._custom_table.cellChanged.connect(
            lambda: self._validate_current_step()
        )
        lay.addWidget(self._custom_table, 1)

        return w

    def _custom_add_row(self):
        row = self._custom_table.rowCount()
        self._custom_table.insertRow(row)

        type_combo = ComboBox()
        for t in self._RECORD_TYPES:
            type_combo.addItem(t)
        type_combo.setCurrentIndex(0)
        self._custom_table.setCellWidget(row, 0, type_combo)

        sub_edit = LineEdit()
        sub_edit.setPlaceholderText("@ (apex)")
        self._custom_table.setCellWidget(row, 1, sub_edit)

        ttl_combo = ComboBox()
        for val, label in self._TTL_OPTIONS:
            ttl_combo.addItem(f"{label} ({val}s)")
        ttl_combo.setCurrentIndex(3)  # default 1 hour
        self._custom_table.setCellWidget(row, 2, ttl_combo)

        content_edit = LineEdit()
        content_edit.setPlaceholderText("Record content...")
        self._custom_table.setCellWidget(row, 3, content_edit)

        self._custom_row_count.setText(
            f"{self._custom_table.rowCount()} record"
            f"{'s' if self._custom_table.rowCount() != 1 else ''}"
        )
        self._validate_current_step()

    def _custom_remove_row(self):
        rows = sorted(set(i.row() for i in self._custom_table.selectedItems()),
                      reverse=True)
        if not rows:
            rows = sorted(set(idx.row() for idx in
                              self._custom_table.selectionModel().selectedRows()),
                          reverse=True)
        for r in rows:
            self._custom_table.removeRow(r)
        self._custom_row_count.setText(
            f"{self._custom_table.rowCount()} record"
            f"{'s' if self._custom_table.rowCount() != 1 else ''}"
        )
        self._validate_current_step()

    def _read_custom_records(self):
        """Read the custom table into a list of record dicts."""
        records = []
        for row in range(self._custom_table.rowCount()):
            type_combo = self._custom_table.cellWidget(row, 0)
            sub_edit = self._custom_table.cellWidget(row, 1)
            ttl_combo = self._custom_table.cellWidget(row, 2)
            content_edit = self._custom_table.cellWidget(row, 3)
            if not type_combo or not content_edit:
                continue
            content = content_edit.text().strip()
            if not content:
                continue
            ttl_text = ttl_combo.currentText() if ttl_combo else "3600"
            ttl_match = re.search(r'\((\d+)s\)', ttl_text)
            ttl = int(ttl_match.group(1)) if ttl_match else 3600
            records.append({
                "type": type_combo.currentText(),
                "subname": sub_edit.text().strip() if sub_edit else "",
                "ttl": ttl,
                "content": content,
            })
        return records

    # ------------------------------------------------------------------
    # Execution placeholder
    # ------------------------------------------------------------------

    def _execute(self):
        pass

    # ------------------------------------------------------------------
    # Step builder placeholders
    # ------------------------------------------------------------------

    def _build_step_mode(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(16)

        lay.addWidget(StrongBodyLabel("What would you like to do?"))
        lay.addWidget(CaptionLabel(
            "Choose a preset for common services, or create a custom record set."
        ))

        self._card_preset = self._make_mode_card(
            "Use a Preset",
            "Choose from curated templates for Google Workspace, Microsoft 365, "
            "Matrix, ACME DNS-01, and more. Each template includes all required "
            "DNS records with guided variable input.",
        )
        self._card_preset.mousePressEvent = lambda e: self._select_mode("preset")
        lay.addWidget(self._card_preset)

        self._card_custom = self._make_mode_card(
            "Custom",
            "Build your own record set from scratch. Define multiple records "
            "with type, subdomain, TTL, and content. Supports {variable} "
            "placeholders for dynamic values.",
        )
        self._card_custom.mousePressEvent = lambda e: self._select_mode("custom")
        lay.addWidget(self._card_custom)

        lay.addStretch()
        return w

    def _make_mode_card(self, title, description):
        card = QtWidgets.QFrame()
        card.setObjectName("wizardModeCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setProperty("selected", False)
        self._style_mode_card(card, False)

        card_lay = QtWidgets.QVBoxLayout(card)
        card_lay.setContentsMargins(16, 14, 16, 14)
        card_lay.setSpacing(6)
        card_lay.addWidget(StrongBodyLabel(title))

        desc = CaptionLabel(description)
        desc.setWordWrap(True)
        card_lay.addWidget(desc)

        return card

    def _style_mode_card(self, card, selected):
        dark = isDarkTheme()
        if selected:
            bg = "rgba(0,120,212,0.12)" if dark else "rgba(0,120,212,0.08)"
            border = "rgba(0,120,212,0.6)" if dark else "rgba(0,120,212,0.5)"
        else:
            bg = "rgba(255,255,255,0.04)" if dark else "rgba(0,0,0,0.03)"
            border = "rgba(255,255,255,0.10)" if dark else "rgba(0,0,0,0.12)"
        card.setStyleSheet(
            f"QFrame#wizardModeCard {{"
            f"  background: {bg}; border: 1px solid {border}; border-radius: 6px;"
            f"}}"
        )

    def _select_mode(self, mode):
        self._mode = mode
        self._style_mode_card(self._card_preset, mode == "preset")
        self._style_mode_card(self._card_custom, mode == "custom")
        self._validate_current_step()

    def _build_step_template(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(8)

        lay.addWidget(StrongBodyLabel("Select a Template"))

        self._template_search = SearchLineEdit()
        self._template_search.setPlaceholderText("Search templates...")
        self._template_search.textChanged.connect(self._filter_templates)
        lay.addWidget(self._template_search)

        # Split: template list left, preview right
        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Template list
        self._template_list = ListWidget()
        self._template_list.currentItemChanged.connect(self._on_template_selected)
        splitter.addWidget(self._template_list)

        # Preview panel
        preview_w = QtWidgets.QWidget()
        self._template_preview_lay = QtWidgets.QVBoxLayout(preview_w)
        self._template_preview_lay.setContentsMargins(8, 0, 0, 0)
        self._template_preview_lay.setSpacing(6)

        self._template_name_label = StrongBodyLabel("")
        self._template_desc_label = CaptionLabel("")
        self._template_desc_label.setWordWrap(True)
        self._template_preview_lay.addWidget(self._template_name_label)
        self._template_preview_lay.addWidget(self._template_desc_label)

        self._template_records_table = TableWidget()
        self._template_records_table.setColumnCount(4)
        self._template_records_table.setHorizontalHeaderLabels(
            ["Type", "Subdomain", "TTL", "Content"]
        )
        self._template_records_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._template_records_table.horizontalHeader().setStretchLastSection(True)
        self._template_preview_lay.addWidget(self._template_records_table, 1)

        splitter.addWidget(preview_w)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        # Custom mode panel (stacked with the splitter)
        self._custom_builder = self._build_custom_builder()

        self._template_stack = QtWidgets.QStackedWidget()
        self._template_stack.addWidget(splitter)
        self._template_stack.addWidget(self._custom_builder)

        lay.addWidget(self._template_stack, 1)
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
