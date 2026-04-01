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
    ComboBox, CheckBox, RadioButton, ListWidget, ListView, TableWidget,
    StrongBodyLabel, CaptionLabel, ProgressBar,
    isDarkTheme, InfoBar, InfoBarPosition,
)

from fluent_styles import container_qss, SPLITTER_QSS
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
        self._templates         = []
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
        # Match the splitter-pane pattern: outer (0,0,0,0) → single
        # content widget with (6,6,6,6), same as Search & Replace panes.
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        content = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(content)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # ── Title row ──────────────────────────────────────────────────
        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        self._title_label = StrongBodyLabel("DNS Record Wizard")
        title_row.addWidget(self._title_label)
        title_row.addStretch()

        self._step_label = CaptionLabel("")
        title_row.addWidget(self._step_label)

        lay.addLayout(title_row)

        # ── Step stack ─────────────────────────────────────────────────
        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(self._build_step_mode())
        self._stack.addWidget(self._build_step_template())
        self._stack.addWidget(self._build_step_variables())
        self._stack.addWidget(self._build_step_domains())
        self._stack.addWidget(self._build_step_conflict())
        self._stack.addWidget(self._build_step_preview())
        self._stack.addWidget(self._build_step_execute())
        lay.addWidget(self._stack, 1)

        # ── Navigation bar ─────────────────────────────────────────────
        nav_row = QtWidgets.QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
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

        lay.addLayout(nav_row)
        outer.addWidget(content, 1)

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

        # Back button: hidden on first step and during execution
        self._btn_back.setVisible(idx > _STEP_MODE and idx < _STEP_EXECUTE)

        # Start Over: only visible on the last (execution) step
        self._btn_reset.setVisible(idx > _STEP_MODE)

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
        current = self._stack.currentIndex()
        if not self._validate_current_step():
            return
        # Store custom records when leaving step 2
        if current == _STEP_TEMPLATE and self._mode == "custom":
            self._custom_records = self._read_custom_records()
        # Collect variables when leaving step 3
        if current == _STEP_VARIABLES:
            self._variables = self._collect_variables()
        if current == _STEP_PREVIEW:
            self._execute()
            self._go_to_step(_STEP_EXECUTE)
        elif current < _STEP_EXECUTE:
            self._go_to_step(current + 1)

    def _go_back(self):
        """Return to the previous step."""
        current = self._stack.currentIndex()
        if current > _STEP_MODE:
            self._go_to_step(current - 1)

    def _reset(self):
        """Reset all wizard state and return to step 0."""
        self._mode              = None
        self._templates         = []
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
            self._template_search.setVisible(True)
            self._template_stack.setCurrentIndex(0)
            self._populate_template_list()
        else:
            self._template_search.setVisible(False)
            self._template_stack.setCurrentIndex(1)

    def _on_enter_variables_step(self):
        """Rebuild the variable form based on the current template/custom records."""
        while self._var_form_layout.rowCount() > 0:
            self._var_form_layout.removeRow(0)
        self._var_inputs.clear()

        if self._mode == "preset" and self._templates:
            # Merge variables and records from all selected templates
            tpl_vars = {}
            records = []
            for tpl in self._templates:
                for k, v in tpl.get("variables", {}).items():
                    if k not in tpl_vars:
                        tpl_vars[k] = v
                records.extend(tpl.get("records", []))
        else:
            tpl_vars = {}
            records = self._custom_records

        found_vars = set()
        for rec in records:
            for field in ("subname", "content"):
                found_vars.update(re.findall(r'\{(\w+)\}', rec.get(field, "")))

        found_vars.discard("domain")
        found_vars.discard("subdomain_prefix")

        # Always show {domain} as read-only
        domain_label = CaptionLabel("{domain} — auto-populated per selected domain")
        self._var_form_layout.addRow(StrongBodyLabel("{domain}"), domain_label)

        # Always show subdomain prefix
        prefix_edit = LineEdit()
        prefix_edit.setPlaceholderText("Optional — e.g. 'staging'")
        prefix_edit.textChanged.connect(lambda: self._validate_current_step())
        self._var_inputs["subdomain_prefix"] = prefix_edit
        prefix_label = QtWidgets.QWidget()
        prefix_lay = QtWidgets.QVBoxLayout(prefix_label)
        prefix_lay.setContentsMargins(0, 0, 0, 0)
        prefix_lay.setSpacing(2)
        prefix_lay.addWidget(prefix_edit)
        prefix_lay.addWidget(CaptionLabel(
            "If set, prepended to all subnames (e.g. _dmarc → _dmarc.staging)"
        ))
        self._var_form_layout.addRow(
            StrongBodyLabel("{subdomain_prefix}"), prefix_label
        )

        # Template-defined variables
        for var_name in sorted(found_vars):
            meta = tpl_vars.get(var_name, {})
            edit = LineEdit()
            edit.setPlaceholderText(meta.get("hint", f"Value for {{{var_name}}}"))
            default = meta.get("default", "")
            if default:
                edit.setText(default)
            edit.textChanged.connect(lambda: self._validate_current_step())
            self._var_inputs[var_name] = edit

            label_text = meta.get("label", f"{{{var_name}}}")
            required = meta.get("required", True)

            field_widget = QtWidgets.QWidget()
            field_lay = QtWidgets.QVBoxLayout(field_widget)
            field_lay.setContentsMargins(0, 0, 0, 0)
            field_lay.setSpacing(2)
            field_lay.addWidget(edit)
            if meta.get("hint"):
                field_lay.addWidget(CaptionLabel(meta["hint"]))
            if required:
                field_lay.addWidget(CaptionLabel("Required"))

            row_label = StrongBodyLabel(label_text)
            self._var_form_layout.addRow(row_label, field_widget)

        if not found_vars:
            self._var_desc.setText(
                "This template has no custom variables. "
                "You can optionally set a subdomain prefix below."
            )
        else:
            self._var_desc.setText(
                "Provide values for the template variables below. "
                "{domain} is automatically set per target domain."
            )

        self._validate_current_step()

    def _on_enter_domains_step(self):
        """Populate the domain list from cached zones."""
        self._selected_domains = []
        cached, _ = self._cache.get_cached_zones()
        self._all_domain_names = sorted(
            z.get("name", "") for z in (cached or [])
        )
        self._domain_model.setStringList(self._all_domain_names)
        self._domain_list.clearSelection()
        self._domain_list.selectionModel().selectionChanged.connect(
            self._on_domain_selection_changed
        )
        self._domain_search.clear()
        self._update_domain_count()

    def _filter_domains(self, text):
        ft = text.strip().lower()
        if ft:
            filtered = [n for n in self._all_domain_names if ft in n.lower()]
        else:
            filtered = self._all_domain_names
        self._domain_model.setStringList(filtered)

    def _select_all_domains(self):
        sel = self._domain_list.selectionModel()
        model = self._domain_model
        if model.rowCount() == 0:
            return
        sel.select(
            QtCore.QItemSelection(model.index(0), model.index(model.rowCount() - 1)),
            QtCore.QItemSelectionModel.SelectionFlag.Select,
        )

    def _select_no_domains(self):
        self._domain_list.clearSelection()

    def _on_domain_selection_changed(self):
        self._selected_domains = [
            idx.data() for idx in self._domain_list.selectedIndexes()
        ]
        self._update_domain_count()
        self._validate_current_step()

    def _update_domain_count(self):
        total = len(self._all_domain_names)
        selected = len(self._domain_list.selectedIndexes())
        self._domain_count_label.setText(
            f"{selected} of {total} domain{'s' if total != 1 else ''} selected"
        )

    def _on_enter_preview_step(self):
        """Resolve all records and populate the preview table."""
        self._preview_rows = self._resolve_records()

        self._preview_table.setRowCount(len(self._preview_rows))
        n_new = n_conflict = n_skip = n_error = 0
        domains_seen = set()

        for r, row in enumerate(self._preview_rows):
            domains_seen.add(row["domain"])
            self._preview_table.setItem(r, 0, QtWidgets.QTableWidgetItem(row["domain"]))
            self._preview_table.setItem(r, 1, QtWidgets.QTableWidgetItem(row["subname"] or "@"))
            self._preview_table.setItem(r, 2, QtWidgets.QTableWidgetItem(row["type"]))
            self._preview_table.setItem(r, 3, QtWidgets.QTableWidgetItem(str(row["ttl"])))
            content_display = "\n".join(row["contents"])
            self._preview_table.setItem(r, 4, QtWidgets.QTableWidgetItem(content_display))

            if row["errors"]:
                status_text = f"Error: {row['errors'][0]}"
                n_error += 1
            elif row["status"] == "new":
                status_text = "New"
                n_new += 1
            elif row["status"] == "conflict":
                label = "Merge" if self._conflict_strategy == "merge" else "Replace"
                status_text = f"Conflict → {label}"
                n_conflict += 1
            else:
                status_text = "Skipped"
                n_skip += 1

            status_item = QtWidgets.QTableWidgetItem(status_text)
            if row["error"]:
                status_item.setForeground(QtGui.QColor("#E53935"))
            elif row["status"] == "new":
                status_item.setForeground(QtGui.QColor("#43A047"))
            elif row["status"] == "skipped":
                status_item.setForeground(QtGui.QColor("#9E9E9E"))
            else:
                status_item.setForeground(QtGui.QColor("#FB8C00"))
            self._preview_table.setItem(r, 5, status_item)

        actionable = n_new + n_conflict
        parts = [f"{len(self._preview_rows)} records across {len(domains_seen)} domains"]
        detail = []
        if n_new:
            detail.append(f"{n_new} new")
        if n_conflict:
            detail.append(f"{n_conflict} conflicts")
        if n_skip:
            detail.append(f"{n_skip} skipped")
        if n_error:
            detail.append(f"{n_error} errors")
        if detail:
            parts.append(f"({', '.join(detail)})")
        self._preview_summary.setText(" ".join(parts))

        # Disable Execute if nothing actionable or there are validation errors
        self._btn_next.setEnabled(actionable > 0 and n_error == 0)

    # ------------------------------------------------------------------
    # Validation hooks (placeholders)
    # ------------------------------------------------------------------

    def _validate_template_step(self) -> bool:
        if self._mode == "preset":
            return len(self._templates) > 0
        else:
            records = self._read_custom_records()
            self._custom_records = records
            if not records:
                return False
            # Validate each record inline (skip if content has {variables})
            all_valid = True
            for row in range(self._custom_table.rowCount()):
                type_combo = self._custom_table.cellWidget(row, 0)
                content_edit = self._custom_table.cellWidget(row, 3)
                if not type_combo or not content_edit:
                    continue
                content = content_edit.text().strip()
                if not content:
                    continue
                # Skip validation for unresolved variables
                if re.search(r'\{\w+\}', content):
                    content_edit.setToolTip("")
                    continue
                is_valid, err = _validate_record_content(
                    type_combo.currentText(), content
                )
                if not is_valid:
                    content_edit.setToolTip(f"\u26A0 {err}")
                    all_valid = False
                else:
                    content_edit.setToolTip("")
            return all_valid

    def _validate_variables_step(self) -> bool:
        """Check all required variables have values."""
        tpl_vars = {}
        if self._mode == "preset" and self._templates:
            for tpl in self._templates:
                for k, v in tpl.get("variables", {}).items():
                    if k not in tpl_vars:
                        tpl_vars[k] = v

        for var_name, edit in self._var_inputs.items():
            if var_name == "subdomain_prefix":
                continue
            meta = tpl_vars.get(var_name, {})
            required = meta.get("required", True)
            if required and not edit.text().strip():
                return False
        return True

    def _collect_variables(self):
        """Read all variable values from the form."""
        result = {}
        for var_name, edit in self._var_inputs.items():
            result[var_name] = edit.text().strip()
        return result

    def _resolve_records(self):
        """
        Resolve template/custom records × variables × domains into a list
        of RRset-level operations.

        Records sharing the same (domain, subname, type) are grouped into a
        single operation with a ``contents`` list, because the deSEC API
        treats an RRset as one atomic unit.

        Returns list of dicts:
            {domain, subname, type, ttl, contents, status, existing_records, errors}
        """
        variables = self._collect_variables()
        prefix = variables.pop("subdomain_prefix", "").strip()

        if self._mode == "preset" and self._templates:
            records = []
            for tpl in self._templates:
                records.extend(tpl["records"])
        else:
            records = self._custom_records

        result = []
        for domain in self._selected_domains:
            cached_records, _ = self._cache.get_cached_records(domain)
            existing_index = {}
            if cached_records:
                for rr in cached_records:
                    key = (rr.get("subname", ""), rr.get("type", ""))
                    existing_index[key] = rr.get("records", [])

            domain_vars = {**variables, "domain": domain}

            # First pass: resolve variables and group by (subname, type)
            groups = {}  # (subname, type) → {ttl, contents, errors}
            for rec in records:
                content = rec["content"]
                subname = rec["subname"]
                for var, val in domain_vars.items():
                    content = content.replace(f"{{{var}}}", val)
                    subname = subname.replace(f"{{{var}}}", val)

                if prefix:
                    if subname:
                        subname = f"{subname}.{prefix}"
                    else:
                        subname = prefix

                is_valid, err_msg = _validate_record_content(rec["type"], content)
                key = (subname, rec["type"])
                if key not in groups:
                    groups[key] = {
                        "ttl": rec["ttl"],
                        "contents": [],
                        "errors": [],
                    }
                groups[key]["contents"].append(content)
                if not is_valid:
                    groups[key]["errors"].append(err_msg)

            # Second pass: determine conflict status per group
            for (subname, rtype), grp in groups.items():
                existing = existing_index.get((subname, rtype))
                if existing is not None:
                    if self._conflict_strategy == "skip":
                        status = "skipped"
                    else:
                        status = "conflict"
                else:
                    status = "new"

                result.append({
                    "domain": domain,
                    "subname": subname,
                    "type": rtype,
                    "ttl": grp["ttl"],
                    "contents": grp["contents"],
                    "status": status,
                    "existing_records": existing or [],
                    "errors": grp["errors"],
                })

        return result

    # ------------------------------------------------------------------
    # Template step helpers
    # ------------------------------------------------------------------

    def _populate_template_list(self):
        self._template_list.blockSignals(True)
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
                    f"{tpl['name']}  ({len(tpl['records'])} records)"
                )
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, tpl["id"])
                self._template_list.addItem(item)
        self._template_list.blockSignals(False)

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

    def _on_template_checked(self, item):
        """Respond to checkbox toggle on a template list item."""
        selected = []
        for i in range(self._template_list.count()):
            it = self._template_list.item(i)
            tpl_id = it.data(Qt.ItemDataRole.UserRole)
            if tpl_id is None:
                continue
            if it.checkState() == Qt.CheckState.Checked:
                tpl = next((t for t in TEMPLATES if t["id"] == tpl_id), None)
                if tpl:
                    selected.append(tpl)
        self._templates = selected

        # Preview: combined records from all checked templates
        all_records = []
        for tpl in selected:
            all_records.extend(tpl["records"])

        if selected:
            self._template_name_label.setText(
                f"{len(selected)} template{'s' if len(selected) != 1 else ''} selected"
            )
            self._template_desc_label.setText(
                ", ".join(t["name"] for t in selected)
            )
        else:
            self._template_name_label.setText("")
            self._template_desc_label.setText("Select one or more templates from the list.")

        self._template_records_table.setRowCount(len(all_records))
        for r, rec in enumerate(all_records):
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
        lay.setSpacing(6)

        group = QtWidgets.QGroupBox("Custom Record Set")
        glay = QtWidgets.QVBoxLayout(group)
        glay.setSpacing(6)
        glay.addWidget(CaptionLabel(
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
        glay.addLayout(toolbar)

        self._custom_table = TableWidget()
        self._custom_table.setColumnCount(4)
        self._custom_table.setHorizontalHeaderLabels(
            ["Type", "Subdomain", "TTL", "Content"]
        )
        self._custom_table.verticalHeader().setVisible(False)
        self._custom_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Fixed
        )
        self._custom_table.setColumnWidth(0, 100)   # Type
        self._custom_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Fixed
        )
        self._custom_table.setColumnWidth(1, 150)   # Subdomain
        self._custom_table.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Fixed
        )
        self._custom_table.setColumnWidth(2, 140)   # TTL
        self._custom_table.horizontalHeader().setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.Stretch  # Content
        )
        self._custom_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._custom_table.cellChanged.connect(
            lambda: self._validate_current_step()
        )
        glay.addWidget(self._custom_table, 1)

        lay.addWidget(group, 1)
        return w

    def _custom_add_row(self):
        row = self._custom_table.rowCount()
        self._custom_table.insertRow(row)

        type_combo = ComboBox()
        for t in self._RECORD_TYPES:
            type_combo.addItem(t)
        type_combo.setCurrentIndex(0)
        type_combo.currentIndexChanged.connect(
            lambda: self._validate_current_step()
        )
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
        content_edit.textChanged.connect(lambda: self._validate_current_step())
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
    # Execution
    # ------------------------------------------------------------------

    def _execute(self):
        """Enqueue all actionable preview rows to the API queue."""
        if not self._api_queue:
            InfoBar.error(
                title="No API Queue",
                content="Cannot execute — API queue is not available.",
                parent=self.window(), duration=5000,
                position=InfoBarPosition.TOP,
            )
            return

        actionable = [
            row for row in self._preview_rows
            if row["status"] in ("new", "conflict") and not row["errors"]
        ]

        self._exec_table.setRowCount(len(actionable))
        self._exec_progress.setRange(0, len(actionable))
        self._exec_progress.setValue(0)
        self._exec_completed = 0
        self._exec_succeeded = 0
        self._exec_failed = 0
        self._exec_total = len(actionable)
        self._exec_actionable = actionable
        self._exec_results = {}

        for i, row in enumerate(actionable):
            self._exec_table.setItem(i, 0, QtWidgets.QTableWidgetItem(row["domain"]))
            self._exec_table.setItem(i, 1, QtWidgets.QTableWidgetItem(row["subname"] or "@"))
            self._exec_table.setItem(i, 2, QtWidgets.QTableWidgetItem(row["type"]))
            self._exec_table.setItem(i, 3, QtWidgets.QTableWidgetItem(
                ", ".join(row["contents"])))
            self._exec_table.setItem(i, 4, QtWidgets.QTableWidgetItem("Pending..."))

            self._enqueue_record(i, row)

        self._exec_summary.setText(
            f"Executing {len(actionable)} operations..."
        )

    def _enqueue_record(self, row_idx, row):
        """Enqueue a single RRset operation (may contain multiple record values)."""
        domain = row["domain"]
        subname = row["subname"]
        rtype = row["type"]
        ttl = row["ttl"]
        contents = row["contents"]

        if row["status"] == "conflict" and self._conflict_strategy == "merge":
            existing = list(row.get("existing_records", []))
            for c in contents:
                if c not in existing:
                    existing.append(c)
            api_method = self._api.update_record
            records = existing
            action_desc = f"Merge {rtype} for {subname or '@'} in {domain}"
        elif row["status"] == "conflict" and self._conflict_strategy == "replace":
            api_method = self._api.update_record
            records = contents
            action_desc = f"Replace {rtype} for {subname or '@'} in {domain}"
        else:
            api_method = self._api.create_record
            records = contents
            action_desc = f"Create {rtype} for {subname or '@'} in {domain}"

        def _on_done(success, response, idx=row_idx, d=domain):
            self._on_exec_item_done(idx, d, success, response)

        item = QueueItem(
            priority=PRIORITY_NORMAL,
            category="wizard",
            action=action_desc,
            callable=api_method,
            args=(domain, subname, rtype, ttl, records),
            callback=_on_done,
        )
        self._api_queue.enqueue(item)

    def _on_exec_item_done(self, row_idx, domain, success, response):
        """Callback for each completed queue item."""
        self._exec_completed += 1
        self._exec_progress.setValue(self._exec_completed)

        result_item = self._exec_table.item(row_idx, 4)
        if success:
            self._exec_succeeded += 1
            self._exec_results[row_idx] = (True, "")
            if result_item:
                result_item.setText("Success")
                result_item.setForeground(QtGui.QColor("#43A047"))
            if self._version_manager:
                try:
                    cached_recs, _ = self._cache.get_cached_records(domain)
                    if cached_recs:
                        self._version_manager.snapshot(
                            domain, cached_recs,
                            f"Wizard: batch record creation",
                        )
                except Exception:
                    pass
        else:
            self._exec_failed += 1
            err = str(response) if response else "Unknown error"
            self._exec_results[row_idx] = (False, err)
            if result_item:
                result_item.setText(f"Failed: {err}")
                result_item.setForeground(QtGui.QColor("#E53935"))

        self._exec_status_label.setText(
            f"{self._exec_completed}/{self._exec_total} complete — "
            f"{self._exec_succeeded} succeeded, {self._exec_failed} failed"
        )

        if self._exec_completed >= self._exec_total:
            self._exec_summary.setText(
                f"Complete: {self._exec_succeeded}/{self._exec_total} succeeded"
                + (f", {self._exec_failed} failed" if self._exec_failed else "")
            )
            if self._exec_failed > 0:
                self._btn_retry.setVisible(True)
            self.records_changed.emit()
            self.log_message.emit(
                f"Wizard: {self._exec_succeeded}/{self._exec_total} records created",
                "info" if self._exec_failed == 0 else "warning",
            )

    def _retry_failed(self):
        """Re-enqueue only the failed items."""
        self._btn_retry.setVisible(False)
        failed_indices = [
            idx for idx, (ok, _) in self._exec_results.items() if not ok
        ]
        self._exec_completed = self._exec_total - len(failed_indices)
        self._exec_failed = 0
        self._exec_progress.setValue(self._exec_completed)

        for idx in failed_indices:
            row = self._exec_actionable[idx]
            result_item = self._exec_table.item(idx, 4)
            if result_item:
                result_item.setText("Retrying...")
                result_item.setForeground(QtGui.QColor("#FB8C00"))
            self._enqueue_record(idx, row)

    # ------------------------------------------------------------------
    # Step builder placeholders
    # ------------------------------------------------------------------

    def _build_step_mode(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        group = QtWidgets.QGroupBox("Choose Mode")
        glay = QtWidgets.QVBoxLayout(group)
        glay.setSpacing(12)
        glay.addWidget(CaptionLabel(
            "Choose a preset for common services, or create a custom record set."
        ))

        self._card_preset = self._make_mode_card(
            "Use a Preset",
            "Choose from curated templates for Google Workspace, Microsoft 365, "
            "Matrix, ACME DNS-01, and more. Each template includes all required "
            "DNS records with guided variable input.",
        )
        self._card_preset.mousePressEvent = lambda e: self._select_mode("preset")
        glay.addWidget(self._card_preset)

        self._card_custom = self._make_mode_card(
            "Custom",
            "Build your own record set from scratch. Define multiple records "
            "with type, subdomain, TTL, and content. Supports {variable} "
            "placeholders for dynamic values.",
        )
        self._card_custom.mousePressEvent = lambda e: self._select_mode("custom")
        glay.addWidget(self._card_custom)

        lay.addWidget(group)
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
            bg = "rgba(255,255,255,0.06)" if dark else "rgba(0,0,0,0.04)"
            border = "rgba(128,128,128,0.35)" if dark else "rgba(0,0,0,0.20)"
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
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # Search bar — visible in both preset and custom mode
        self._template_search = SearchLineEdit()
        self._template_search.setPlaceholderText("Search templates...")
        self._template_search.textChanged.connect(self._filter_templates)
        lay.addWidget(self._template_search)

        # ── Preset path: splitter (list | preview) ─────────────────────
        preset_w = QtWidgets.QWidget()
        preset_lay = QtWidgets.QVBoxLayout(preset_w)
        preset_lay.setContentsMargins(0, 0, 0, 0)
        preset_lay.setSpacing(6)

        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(SPLITTER_QSS)

        # Template list — checkboxes for multi-select (click to toggle)
        self._template_list = ListWidget()
        self._template_list.itemChanged.connect(self._on_template_checked)
        splitter.addWidget(self._template_list)

        # Preview panel
        preview_w = QtWidgets.QWidget()
        self._template_preview_lay = QtWidgets.QVBoxLayout(preview_w)
        self._template_preview_lay.setContentsMargins(6, 0, 0, 0)
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
        self._template_records_table.verticalHeader().setVisible(False)
        self._template_records_table.setAlternatingRowColors(True)
        for col in (0, 1, 2):
            self._template_records_table.horizontalHeader().setSectionResizeMode(
                col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        self._template_records_table.horizontalHeader().setStretchLastSection(True)
        self._template_preview_lay.addWidget(self._template_records_table, 1)

        splitter.addWidget(preview_w)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        preset_lay.addWidget(splitter, 1)

        # ── Custom path ───────────────────────────────────────────────
        self._custom_builder = self._build_custom_builder()

        # Stack preset vs custom
        self._template_stack = QtWidgets.QStackedWidget()
        self._template_stack.addWidget(preset_w)
        self._template_stack.addWidget(self._custom_builder)

        lay.addWidget(self._template_stack, 1)
        return w

    def _build_step_variables(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        group = QtWidgets.QGroupBox("Variables")
        glay = QtWidgets.QVBoxLayout(group)
        glay.setSpacing(6)

        self._var_desc = CaptionLabel(
            "Provide values for the template variables below. "
            "{domain} is automatically set per target domain."
        )
        self._var_desc.setWordWrap(True)
        glay.addWidget(self._var_desc)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )

        self._var_form_widget = QtWidgets.QWidget()
        self._var_form_layout = QtWidgets.QFormLayout(self._var_form_widget)
        self._var_form_layout.setContentsMargins(0, 0, 0, 0)
        self._var_form_layout.setSpacing(10)

        scroll.setWidget(self._var_form_widget)
        glay.addWidget(scroll, 1)

        self._var_inputs = {}

        lay.addWidget(group, 1)
        return w

    def _build_step_domains(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        group = QtWidgets.QGroupBox("Target Domains")
        glay = QtWidgets.QVBoxLayout(group)
        glay.setSpacing(6)
        glay.addWidget(CaptionLabel(
            "Ctrl+click to select multiple. Shift+click for range."
        ))

        # Search filter
        self._domain_search = SearchLineEdit()
        self._domain_search.setPlaceholderText("Filter domains...")
        self._domain_search.textChanged.connect(self._filter_domains)
        glay.addWidget(self._domain_search)

        self._domain_count_label = CaptionLabel("0 of 0 domains selected")
        glay.addWidget(self._domain_count_label)

        # ListView with ExtendedSelection (Ctrl+click / Shift+click)
        self._domain_model = QtCore.QStringListModel()
        self._domain_list = ListView()
        self._domain_list.setModel(self._domain_model)
        self._domain_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._domain_list.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._domain_list.setAlternatingRowColors(True)
        glay.addWidget(self._domain_list, 1)

        # Select All / Select None buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        btn_all = PushButton("Select All")
        btn_all.clicked.connect(self._select_all_domains)
        btn_row.addWidget(btn_all)
        btn_none = PushButton("Select None")
        btn_none.clicked.connect(self._select_no_domains)
        btn_row.addWidget(btn_none)
        btn_row.addStretch()
        glay.addLayout(btn_row)

        # Store all zones for filtering
        self._all_domain_names = []

        lay.addWidget(group, 1)
        return w

    def _build_step_conflict(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        group = QtWidgets.QGroupBox("Conflict Strategy")
        glay = QtWidgets.QVBoxLayout(group)
        glay.setSpacing(8)
        glay.addWidget(CaptionLabel(
            "Choose how to handle cases where a record with the same "
            "subdomain and type already exists on a target domain."
        ))

        self._conflict_radios = {}

        r_merge = RadioButton("Merge")
        r_merge.setChecked(True)
        self._conflict_strategy = "merge"
        r_merge.toggled.connect(lambda checked: self._set_conflict("merge") if checked else None)
        glay.addWidget(r_merge)
        glay.addWidget(CaptionLabel(
            "  Append new content to the existing record set. "
            "For example, adds a new MX record alongside existing ones."
        ))
        self._conflict_radios["merge"] = r_merge

        r_replace = RadioButton("Replace")
        r_replace.toggled.connect(lambda checked: self._set_conflict("replace") if checked else None)
        glay.addWidget(r_replace)
        glay.addWidget(CaptionLabel(
            "  Overwrite the existing record set entirely with the new content. "
            "Use with caution — existing records of the same type will be lost."
        ))
        self._conflict_radios["replace"] = r_replace

        r_skip = RadioButton("Skip")
        r_skip.toggled.connect(lambda checked: self._set_conflict("skip") if checked else None)
        glay.addWidget(r_skip)
        glay.addWidget(CaptionLabel(
            "  Leave existing records untouched. Only create records where "
            "no matching subdomain + type combination exists yet."
        ))
        self._conflict_radios["skip"] = r_skip

        lay.addWidget(group)
        lay.addStretch()
        return w

    def _set_conflict(self, strategy):
        self._conflict_strategy = strategy

    def _build_step_preview(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        group = QtWidgets.QGroupBox("Preview")
        glay = QtWidgets.QVBoxLayout(group)
        glay.setSpacing(6)

        self._preview_summary = CaptionLabel("")
        self._preview_summary.setWordWrap(True)
        glay.addWidget(self._preview_summary)

        self._preview_table = TableWidget()
        self._preview_table.setColumnCount(6)
        self._preview_table.setHorizontalHeaderLabels(
            ["Domain", "Subdomain", "Type", "TTL", "Content", "Status"]
        )
        self._preview_table.verticalHeader().setVisible(False)
        self._preview_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._preview_table.setAlternatingRowColors(True)
        for col in (0, 1, 2, 3, 5):
            self._preview_table.horizontalHeader().setSectionResizeMode(
                col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        self._preview_table.horizontalHeader().setSectionResizeMode(
            4, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self._preview_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        glay.addWidget(self._preview_table, 1)

        lay.addWidget(group, 1)
        return w

    def _build_step_execute(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        group = QtWidgets.QGroupBox("Execution")
        glay = QtWidgets.QVBoxLayout(group)
        glay.setSpacing(6)

        self._exec_summary = CaptionLabel("Preparing...")
        glay.addWidget(self._exec_summary)

        self._exec_progress = ProgressBar()
        glay.addWidget(self._exec_progress)

        self._exec_status_label = CaptionLabel("")
        glay.addWidget(self._exec_status_label)

        self._exec_table = TableWidget()
        self._exec_table.setColumnCount(5)
        self._exec_table.setHorizontalHeaderLabels(
            ["Domain", "Subdomain", "Type", "Content", "Result"]
        )
        self._exec_table.verticalHeader().setVisible(False)
        self._exec_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._exec_table.setAlternatingRowColors(True)
        for col in (0, 1, 2):
            self._exec_table.horizontalHeader().setSectionResizeMode(
                col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        self._exec_table.horizontalHeader().setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self._exec_table.horizontalHeader().setSectionResizeMode(
            4, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        glay.addWidget(self._exec_table, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()
        self._btn_retry = PushButton("Retry Failed")
        self._btn_retry.clicked.connect(self._retry_failed)
        self._btn_retry.setVisible(False)
        btn_row.addWidget(self._btn_retry)
        glay.addLayout(btn_row)

        lay.addWidget(group, 1)
        return w

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.setStyleSheet(container_qss())
        # Re-apply card styles after container_qss() to prevent override
        self._style_mode_card(self._card_preset, self._mode == "preset")
        self._style_mode_card(self._card_custom, self._mode == "custom")
