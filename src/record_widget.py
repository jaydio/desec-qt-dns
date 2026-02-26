#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Record Widget for deSEC Qt DNS Manager.
Displays and manages DNS records for a selected zone.
"""

import logging
import time
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, Signal, QThread, QThreadPool, QPropertyAnimation, QEasingCurve
from qfluentwidgets import (PushButton, PrimaryPushButton, SearchLineEdit, TableWidget, TextEdit,
                             LineEdit, StrongBodyLabel, CaptionLabel, SubtitleLabel,
                             isDarkTheme, InfoBar, InfoBarPosition)

from confirm_drawer import DeleteConfirmDrawer
from workers import LoadRecordsWorker
from api_queue import QueueItem, PRIORITY_NORMAL, PRIORITY_LOW

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column index constants
# ---------------------------------------------------------------------------
COL_NAME    = 0
COL_TYPE    = 1
COL_TTL     = 2
COL_CONTENT = 3

# ---------------------------------------------------------------------------
# Record type colors  (light_theme, dark_theme)
# ---------------------------------------------------------------------------
_TYPE_COLORS = {
    'A':          ('#1976D2', '#64B5F6'),  # blue
    'AAAA':       ('#0288D1', '#4FC3F7'),  # light blue
    'CNAME':      ('#7B1FA2', '#CE93D8'),  # purple
    'DNAME':      ('#9C27B0', '#BA68C8'),  # lighter purple
    'MX':         ('#E64A19', '#FF8A65'),  # deep orange
    'TXT':        ('#2E7D32', '#81C784'),  # green
    'SPF':        ('#388E3C', '#A5D6A7'),  # lighter green
    'NS':         ('#0097A7', '#4DD0E1'),  # cyan
    'SRV':        ('#00838F', '#80DEEA'),  # darker cyan
    'HTTPS':      ('#00796B', '#80CBC4'),  # teal
    'SVCB':       ('#00897B', '#4DB6AC'),  # teal
    'DS':         ('#F57C00', '#FFB74D'),  # orange (DNSSEC)
    'DNSKEY':     ('#FF8F00', '#FFD54F'),  # amber
    'CDNSKEY':    ('#FF8F00', '#FFD54F'),
    'CDS':        ('#FF8F00', '#FFD54F'),
    'SSHFP':      ('#5E35B1', '#B39DDB'),  # deep purple
    'TLSA':       ('#C2185B', '#F48FB1'),  # pink
    'SMIMEA':     ('#AD1457', '#F06292'),  # darker pink
    'CERT':       ('#D81B60', '#F48FB1'),
    'OPENPGPKEY': ('#4527A0', '#9575CD'),  # indigo
    'PTR':        ('#303F9F', '#7986CB'),  # indigo-blue
    'CAA':        ('#C62828', '#EF9A9A'),  # red
    'NAPTR':      ('#4E342E', '#A1887F'),  # brown
    'LOC':        ('#558B2F', '#AED581'),  # light green
    'SOA':        ('#455A64', '#90A4AE'),  # blue grey
}


# ---------------------------------------------------------------------------
# Bulk-delete background worker
# ---------------------------------------------------------------------------

class _BulkDeleteWorker(QThread):
    progress_update = Signal(int, str)   # pct, status message
    record_done     = Signal(bool, str)  # success, label
    finished        = Signal(int, int)   # deleted, failed

    def __init__(self, api_client, domain, records):
        super().__init__()
        self.api_client = api_client
        self.domain     = domain
        self.records    = records

    def run(self):
        total   = len(self.records)
        deleted = 0
        failed  = 0
        for idx, record in enumerate(self.records):
            pct   = int((idx / total) * 100) if total else 100
            sub   = record.get('subname', '') or ''
            rtype = record.get('type', '')
            label = f"{sub or '@'} {rtype}"
            self.progress_update.emit(pct, f"Deleting {label}…")
            ok, _ = self.api_client.delete_record(self.domain, sub, rtype)
            if ok:
                deleted += 1
            else:
                failed += 1
            self.record_done.emit(ok, label)
        self.progress_update.emit(100, "Done.")
        self.finished.emit(deleted, failed)


# ---------------------------------------------------------------------------
# Validation helper (module-level, used by RecordEditPanel)
# ---------------------------------------------------------------------------

def _validate_record_content(record_type, content):
    """Validate a single DNS record value. Returns (is_valid, error_message)."""
    import ipaddress as _ipaddress
    if not content.strip():
        return False, "Record content cannot be empty"
    if record_type in ['TXT', 'SPF']:
        if not (content.startswith('"') and content.endswith('"')):
            return False, f'{record_type} records must be enclosed in double quotes'
        # Check for unescaped quotes inside the outer pair
        inner = content[1:-1]
        import re as _re
        unescaped = _re.findall(r'(?<!\\)"', inner)
        if unescaped:
            return False, f'Quotes within {record_type} content must be escaped with backslash'
    elif record_type in ['CNAME', 'MX', 'NS', 'PTR', 'DNAME']:
        if not content.strip().endswith('.'):
            return False, f'{record_type} record target must end with a trailing dot'
        if record_type == 'MX':
            parts = content.strip().split()
            if len(parts) < 2:
                return False, 'MX records must include priority and domain'
            try:
                priority = int(parts[0])
                if not (0 <= priority <= 65535):
                    return False, 'MX priority must be between 0 and 65535'
            except ValueError:
                return False, 'MX priority must be a valid integer'
    elif record_type == 'A':
        try:
            octets = content.strip().split('.')
            if len(octets) != 4 or any(not (0 <= int(o) <= 255) for o in octets):
                return False, 'Invalid IPv4 address format'
        except ValueError:
            return False, 'Invalid IPv4 address format'
    elif record_type == 'AAAA':
        try:
            _ipaddress.IPv6Address(content.strip())
        except ValueError:
            return False, 'Invalid IPv6 address format'
    elif record_type == 'SRV':
        parts = content.strip().split()
        if len(parts) < 4:
            return False, 'SRV record must include priority, weight, port, and target'
        try:
            priority, weight, port = map(int, parts[0:3])
            if not (0 <= priority <= 65535 and 0 <= weight <= 65535 and 0 <= port <= 65535):
                return False, 'SRV priority, weight, and port must be between 0 and 65535'
            if not parts[3].endswith('.'):
                return False, 'SRV target must end with a trailing dot'
        except ValueError:
            return False, 'Invalid SRV record format'
    import re
    guidance = RecordWidget.RECORD_TYPE_GUIDANCE.get(record_type, {})
    pattern = guidance.get('validation')
    if pattern and not re.match(pattern, content.strip()):
        return False, f'Invalid format for {record_type} record'
    return True, ""


# ---------------------------------------------------------------------------
# RecordEditPanel — slide-in right panel for add / edit
# ---------------------------------------------------------------------------

class RecordEditPanel(QtWidgets.QWidget):
    """Slide-in right panel for adding and editing DNS records.

    Positioned absolutely as a child overlay of RecordWidget.
    Slide animation driven by QPropertyAnimation on the pos property.
    """

    PANEL_WIDTH = 440

    save_done  = Signal()           # emitted after successful API save
    cancelled  = Signal()           # emitted on Cancel
    log_signal = Signal(str, str)   # (message, level) forwarded to RecordWidget.log_message

    def __init__(self, api_client, parent=None, api_queue=None, version_manager=None):
        super().__init__(parent)
        self.api_client = api_client
        self.api_queue = api_queue
        self.version_manager = version_manager
        self._domain    = None
        self._record    = None      # None = add mode, dict = edit mode
        self._animation = None
        self.setObjectName("recordEditPanel")
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            "QWidget#recordEditPanel {"
            "  border-left: 1px solid rgba(128,128,128,0.35);"
            "}"
        )
        self.hide()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Paint — draw opaque Fluent-themed background so the panel is not
    # transparent when overlaid on the records table.
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        bg = QtGui.QColor(32, 32, 32) if isDarkTheme() else QtGui.QColor(243, 243, 243)
        painter.fillRect(self.rect(), bg)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header row: title + close button
        header_row = QtWidgets.QHBoxLayout()
        self._title_label = SubtitleLabel("Add Record")
        header_row.addWidget(self._title_label, 1)
        close_btn = PushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setToolTip("Close (Esc)")
        close_btn.clicked.connect(self.slide_out)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # Escape shortcut
        esc = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_Escape), self)
        esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc.activated.connect(self.slide_out)

        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.DontWrapRows)

        self._subname_input = LineEdit()
        self._subname_input.setPlaceholderText("e.g., www (leave blank for apex)")
        form.addRow("Subdomain:", self._subname_input)

        self._type_combo = QtWidgets.QComboBox()
        _type_labels = {
            'A': 'A (IPv4 Address)', 'AAAA': 'AAAA (IPv6 Address)',
            'AFSDB': 'AFSDB (AFS Database)', 'APL': 'APL (Address Prefix List)',
            'CAA': 'CAA (Certification Authority Authorization)',
            'CDNSKEY': 'CDNSKEY (Child DNS Key)', 'CERT': 'CERT (Certificate)',
            'CNAME': 'CNAME (Canonical Name)', 'DHCID': 'DHCID (DHCP Identifier)',
            'DNAME': 'DNAME (Delegation Name)', 'DNSKEY': 'DNSKEY (DNS Key)',
            'DLV': 'DLV (DNSSEC Lookaside Validation)', 'DS': 'DS (Delegation Signer)',
            'EUI48': 'EUI48 (MAC Address)', 'EUI64': 'EUI64 (Extended MAC Address)',
            'HINFO': 'HINFO (Host Information)', 'HTTPS': 'HTTPS (HTTPS Service)',
            'KX': 'KX (Key Exchanger)', 'L32': 'L32 (Location IPv4)',
            'L64': 'L64 (Location IPv6)', 'LOC': 'LOC (Location)',
            'LP': 'LP (Location Pointer)', 'MX': 'MX (Mail Exchange)',
            'NAPTR': 'NAPTR (Name Authority Pointer)', 'NID': 'NID (Node Identifier)',
            'NS': 'NS (Name Server)', 'OPENPGPKEY': 'OPENPGPKEY (OpenPGP Public Key)',
            'PTR': 'PTR (Pointer)', 'RP': 'RP (Responsible Person)',
            'SMIMEA': 'SMIMEA (S/MIME Cert Association)',
            'SPF': 'SPF (Sender Policy Framework)', 'SRV': 'SRV (Service)',
            'SSHFP': 'SSHFP (SSH Fingerprint)', 'SVCB': 'SVCB (Service Binding)',
            'TLSA': 'TLSA (TLS Association)', 'TXT': 'TXT (Text)',
            'URI': 'URI (Uniform Resource Identifier)',
        }
        for rtype in sorted(RecordWidget.SUPPORTED_TYPES):
            self._type_combo.addItem(_type_labels.get(rtype, rtype))
        self._type_combo.currentIndexChanged.connect(self._update_guidance)
        form.addRow("Type:", self._type_combo)

        self._ttl_input = QtWidgets.QComboBox()
        _ttl_values = [
            (60,    "60 seconds (1 minute)"),
            (300,   "300 seconds (5 minutes)"),
            (600,   "600 seconds (10 minutes)"),
            (900,   "900 seconds (15 minutes)"),
            (1800,  "1800 seconds (30 minutes)"),
            (3600,  "3600 seconds (1 hour)"),
            (7200,  "7200 seconds (2 hours)"),
            (14400, "14400 seconds (4 hours)"),
            (86400, "86400 seconds (24 hours)"),
        ]
        for i, (value, label) in enumerate(_ttl_values):
            self._ttl_input.addItem(label)
            self._ttl_input.setItemData(i, value)
        self._ttl_input.setCurrentIndex(5)  # default: 3600
        form.addRow("TTL:", self._ttl_input)

        layout.addLayout(form)
        layout.addWidget(QtWidgets.QLabel("Record Content:"))

        self._records_input = TextEdit()
        self._records_input.setPlaceholderText("Enter record content (one per line)")
        self._records_input.textChanged.connect(self._validate_input)
        layout.addWidget(self._records_input, 1)

        self._validation_label = QtWidgets.QLabel("")
        self._validation_label.setWordWrap(True)
        layout.addWidget(self._validation_label)

        self._guidance_text = QtWidgets.QLabel()
        self._guidance_text.setWordWrap(True)
        self._guidance_text.setTextFormat(QtCore.Qt.TextFormat.RichText)
        layout.addWidget(self._guidance_text)

        self._update_guidance(0)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = PushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(cancel_btn)
        self._done_btn = PrimaryPushButton("Done")
        self._done_btn.clicked.connect(self._on_done)
        btn_row.addWidget(self._done_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_for_add(self, domain: str):
        """Reset form and slide in for adding a new record."""
        if not domain:
            return
        self._domain = domain
        self._record = None
        self._title_label.setText("Add Record")
        self._reset_form()
        self._subname_input.setEnabled(True)
        self._type_combo.setEnabled(True)
        self.slide_in()

    def open_for_edit(self, domain: str, record: dict):
        """Populate form and slide in for editing an existing record."""
        self._domain = domain
        self._record = record
        self._title_label.setText(f"Edit {record.get('type', 'Record')}")
        self._reset_form()
        self._populate(record)
        self._subname_input.setEnabled(False)
        self._type_combo.setEnabled(False)
        self.slide_in()

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def slide_in(self):
        """Animate the panel sliding in from the right edge."""
        from fluent_styles import container_qss
        self.setStyleSheet(
            "QWidget#recordEditPanel { border-left: 1px solid rgba(128,128,128,0.35); }"
            + container_qss()
        )
        parent = self.parent()
        if parent is None:
            return
        pw, ph = parent.width(), parent.height()
        self.setGeometry(pw, 0, self.PANEL_WIDTH, ph)
        self.show()
        self.raise_()
        self._run_animation(
            QtCore.QPoint(pw, 0),
            QtCore.QPoint(pw - self.PANEL_WIDTH, 0),
            QEasingCurve.Type.OutCubic,
        )

    def slide_out(self):
        """Animate the panel sliding back out to the right, then hide."""
        parent = self.parent()
        if parent is None:
            self.hide()
            return
        pw = parent.width()
        anim = self._run_animation(
            self.pos(),
            QtCore.QPoint(pw, 0),
            QEasingCurve.Type.InCubic,
        )
        anim.finished.connect(self.hide)

    def _run_animation(self, start, end, easing):
        if self._animation and self._animation.state() == QPropertyAnimation.State.Running:
            self._animation.stop()
        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(220)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(easing)
        self._animation = anim
        anim.start()
        return anim

    def reposition(self, parent_size):
        """Keep panel flush-right when the parent widget is resized."""
        if not self.isVisible():
            return
        x = parent_size.width() - self.PANEL_WIDTH
        self.setGeometry(x, 0, self.PANEL_WIDTH, parent_size.height())

    # ------------------------------------------------------------------
    # Form helpers
    # ------------------------------------------------------------------

    def _reset_form(self):
        self._subname_input.clear()
        self._type_combo.setCurrentIndex(0)
        self._ttl_input.setCurrentIndex(5)
        self._records_input.clear()
        self._validation_label.clear()

    def _populate(self, record):
        record_type = record.get('type', '')
        for i in range(self._type_combo.count()):
            text = self._type_combo.itemText(i)
            if text.startswith(record_type + ' (') or text == record_type:
                self._type_combo.setCurrentIndex(i)
                break
        self._subname_input.setText(record.get('subname', ''))
        ttl_value = record.get('ttl', 3600)
        available = [self._ttl_input.itemData(i) for i in range(self._ttl_input.count())]
        idx = (
            available.index(ttl_value)
            if ttl_value in available
            else available.index(min(available, key=lambda x: abs(x - ttl_value)))
        )
        self._ttl_input.setCurrentIndex(idx)
        self._records_input.setPlainText('\n'.join(record.get('records', [])))

    def _update_guidance(self, _index=0):
        record_type = self._type_combo.currentText()
        if ' (' in record_type:
            record_type = record_type.split(' (')[0]
        guidance = RecordWidget.RECORD_TYPE_GUIDANCE.get(record_type, {})
        if guidance:
            self._guidance_text.setText(
                f"<b>{record_type}:</b> {guidance['tooltip']}<br>"
                f"<b>Format:</b> {guidance['format']}<br>"
                f"<b>Example:</b> {guidance['example']}"
            )
            self._records_input.setPlaceholderText(guidance.get('example', ''))
        else:
            self._guidance_text.setText("")
            self._records_input.setPlaceholderText("")
        self._validation_label.clear()
        self._validate_input()

    def _set_status(self, text, level="warning"):
        """Set the validation label with color-coded text.

        level: 'error' (red), 'warning' (orange), 'success' (green)
        """
        colors = {
            "error":   "#FF6B6B" if isDarkTheme() else "#C62828",
            "warning": "#FFB74D" if isDarkTheme() else "#E65100",
            "success": "#81C784" if isDarkTheme() else "#2E7D32",
        }
        color = colors.get(level, colors["warning"])
        self._validation_label.setStyleSheet(f"color: {color};")
        self._validation_label.setText(text)

    def _validate_input(self):
        record_type = self._type_combo.currentText()
        if ' (' in record_type:
            record_type = record_type.split(' (')[0]
        content = self._records_input.toPlainText().strip()
        if not content:
            self._validation_label.clear()
            return
        errors = []
        for line in [l.strip() for l in content.splitlines() if l.strip()]:
            ok, msg = _validate_record_content(record_type, line)
            if not ok:
                errors.append(msg)
        if errors:
            self._set_status("⚠ " + "\n".join(dict.fromkeys(errors)), "warning")
        else:
            self._set_status("✓ Valid record format", "success")

    def _on_cancel(self):
        self.slide_out()
        self.cancelled.emit()

    def _on_done(self):
        # Double-click guard: ignore if already processing
        if not self._done_btn.isEnabled():
            return
        self._done_btn.setEnabled(False)

        subname = self._subname_input.text().strip()
        record_type = self._type_combo.currentText()
        if ' (' in record_type:
            record_type = record_type.split(' (')[0]
        ttl = self._ttl_input.currentData()
        content = self._records_input.toPlainText().strip()
        records = [l.strip() for l in content.splitlines() if l.strip()]

        if not records:
            self._set_status("⚠ Please enter at least one record value.", "warning")
            self._done_btn.setEnabled(True)
            return

        for rec in records:
            ok, msg = _validate_record_content(record_type, rec)
            if not ok:
                self._set_status(f"⚠ {msg}", "warning")
                self._done_btn.setEnabled(True)
                return

        if record_type in ('TXT', 'SPF'):
            records = [
                r if r.startswith('"') and r.endswith('"') else f'"{r}"'
                for r in records
            ]

        is_edit = bool(self._record)
        domain = self._domain

        if self.api_queue:
            api_method = self.api_client.update_record if is_edit else self.api_client.create_record
            op = "updated" if is_edit else "created"

            def _on_done_callback(success, response):
                if success:
                    if self.version_manager and domain:
                        parent = self.parent()
                        recs = getattr(parent, 'records', None)
                        if recs:
                            self.version_manager.snapshot(
                                domain, recs,
                                f"{op.capitalize()} {record_type} record for '{subname or '@'}'",
                            )
                    self.log_signal.emit(
                        f"Successfully {op} {record_type} record for '{subname or '@'}' in {domain}",
                        "success",
                    )
                    self.save_done.emit()
                else:
                    if isinstance(response, dict) and 'message' in response:
                        msg = response['message']
                        self.log_signal.emit(f"Failed to save record: {msg}", "error")
                    else:
                        msg = str(response)
                        self.log_signal.emit(f"Failed to save record: {msg}", "error")
                    InfoBar.error(
                        title="Record Save Failed",
                        content=msg,
                        parent=self.window(),
                        duration=8000,
                        position=InfoBarPosition.TOP,
                    )

            item = QueueItem(
                priority=PRIORITY_NORMAL,
                category="records",
                action=f"{'Update' if is_edit else 'Create'} {record_type} for {subname or '@'} in {domain}",
                callable=api_method,
                args=(domain, subname, record_type, ttl, records),
                callback=_on_done_callback,
            )
            self.api_queue.enqueue(item)

            # Close panel immediately — the queue processes in the background
            self._done_btn.setEnabled(True)
            op_verb = "Update" if is_edit else "Create"
            self.log_signal.emit(
                f"Queued: {op_verb} {record_type} for '{subname or '@'}' in {domain}",
                "info",
            )
            self.slide_out()
        else:
            if is_edit:
                success, response = self.api_client.update_record(
                    self._domain, subname, record_type, ttl, records
                )
            else:
                success, response = self.api_client.create_record(
                    self._domain, subname, record_type, ttl, records
                )

            self._done_btn.setEnabled(True)
            self._done_btn.setText("Done")

            if success:
                op = "updated" if is_edit else "created"
                self.log_signal.emit(
                    f"Successfully {op} {record_type} record for '{subname or '@'}' in {self._domain}",
                    "success",
                )
                self.slide_out()
                self.save_done.emit()
            else:
                self._handle_save_error(response)

    def _handle_save_error(self, response):
        """Handle API error from record save."""
        if isinstance(response, dict) and 'message' in response:
            error_msg = response['message']
            raw = response.get('raw_response', {})
            if 'non_field_errors' in raw and isinstance(raw['non_field_errors'], list):
                detail = '\n'.join(raw['non_field_errors'])
            else:
                detail = error_msg
            self.log_signal.emit(f"API Error: {error_msg}\nDetails: {raw}", "error")
            self._set_status(f"⚠ API error: {detail}", "error")
        else:
            detail = str(response)
            self._set_status(f"⚠ Failed: {detail}", "error")
            self.log_signal.emit(f"API Error: {detail}", "error")
        InfoBar.error(
            title="Record Save Failed",
            content=detail,
            parent=self.window(),
            duration=8000,
            position=InfoBarPosition.TOP,
        )


class RecordWidget(QtWidgets.QWidget):
    """Widget for displaying and managing DNS records."""
    
    # Custom signals
    records_changed = Signal()  # Emitted when records are changed
    log_message = Signal(str, str)  # Emitted to log messages (message, level)
    
    # Supported record types
    SUPPORTED_TYPES = [
        'A', 'AAAA', 'AFSDB', 'APL', 'CAA', 'CDNSKEY', 'CERT', 'CNAME', 'DHCID',
        'DNAME', 'DNSKEY', 'DLV', 'DS', 'EUI48', 'EUI64', 'HINFO', 'HTTPS', 'KX', 'L32',
        'L64', 'LOC', 'LP', 'MX', 'NAPTR', 'NID', 'NS', 'OPENPGPKEY', 'PTR', 'RP',
        'SMIMEA', 'SPF', 'SRV', 'SSHFP', 'SVCB', 'TLSA', 'TXT', 'URI'
    ]
    # Note: CDS is auto-managed by deSEC and cannot be created via the API (returns 403).
    # DNSKEY, DS, CDNSKEY are also auto-managed but the API allows adding extra values
    # for advanced multi-signer DNSSEC setups only.
    
    # Record type format guidance
    RECORD_TYPE_GUIDANCE = {
        'A': {
            'format': '<ipv4-address>',
            'example': '192.0.2.1',
            'tooltip': 'Maps a hostname to an IPv4 address.',
            'validation': r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        },
        'AAAA': {
            'format': '<ipv6-address>',
            'example': '2001:db8::1',
            'tooltip': 'Maps a hostname to an IPv6 address.',
            'validation': r'^[0-9a-fA-F:]+$'
        },
        'AFSDB': {
            'format': '<subtype> <hostname.>',
            'example': '1 afsdb.example.com.',
            'tooltip': 'AFS Database record. Subtype 1 = AFS cell database server, 2 = DCE authenticated name server. Hostname must end with a trailing dot.',
            'validation': r'^[1-2]\s+[a-zA-Z0-9.-]+\.$'
        },
        'APL': {
            'format': '[!]<afi>:<address>/<prefix>',
            'example': '1:192.0.2.0/24 2:2001:db8::/32',
            'tooltip': 'Address Prefix List. AFI 1 = IPv4, AFI 2 = IPv6. Prefix entries are space-separated. Prepend ! to negate an entry.'
        },
        'CAA': {
            'format': '<flags> <tag> "<value>"',
            'example': '0 issue "letsencrypt.org"',
            'tooltip': 'Certification Authority Authorization — controls which CAs may issue certificates. Flags: 0 = advisory, 128 = critical. Tags: issue (permit issuance), issuewild (wildcards only), iodef (violation report URL). Value in double quotes.',
            'validation': r'^\d+\s+(issue|issuewild|iodef)\s+"[^"]+"$'
        },
        'CDNSKEY': {
            'format': '<flags> <protocol> <algorithm> <base64-key>',
            'example': '257 3 13 mdsswUyr3DPW132mOi8V9xESWE8jTo0dxCjjnopKl+GqJxpVXckHAeF+KkxLbxILfDLUT0rAK9iUzy1L53eKGQ==',
            'tooltip': 'WARNING: deSEC auto-manages CDNSKEY records. Only add extra values for advanced multi-signer DNSSEC setups — misuse can break DNSSEC for your domain.\n\nChild copy of a DNSKEY used for automated key rollover. Flags: 257 = KSK, 256 = ZSK. Protocol must be 3. Algorithms: 8 = RSASHA256, 13 = ECDSAP256SHA256, 15 = ED25519.'
        },
        'CERT': {
            'format': '<type> <key-tag> <algorithm> <base64-cert>',
            'example': '1 0 0 MIIC...base64...',
            'tooltip': 'Certificate record. Type: 1 = PKIX (X.509), 2 = SPKI, 3 = PGP. Key-tag and algorithm may be 0 for raw certificates. Certificate data is base64 encoded.'
        },
        'CNAME': {
            'format': '<target.>',
            'example': 'target.example.com.',
            'tooltip': 'Canonical Name — redirects this name to another hostname. Target must be a fully-qualified domain name with trailing dot. Cannot coexist with other record types at the same name.',
            'validation': r'^.+\.$'
        },
        'DHCID': {
            'format': '<base64-data>',
            'example': 'AAIBY2/AuCccgoJbsaxcQc9TUapptP69lOjxfNuVAA2kjEA=',
            'tooltip': 'DHCP Identifier — associates DHCP clients with DNS names to prevent conflicts. Value is base64 encoded.'
        },
        'DNAME': {
            'format': '<target.>',
            'example': 'new.example.com.',
            'tooltip': 'Delegation Name — redirects an entire DNS subtree to another domain. All names under this owner are rewritten to be under the target. Target must be an FQDN with trailing dot.',
            'validation': r'^.+\.$'
        },
        'DNSKEY': {
            'format': '<flags> <protocol> <algorithm> <base64-key>',
            'example': '257 3 13 mdsswUyr3DPW132mOi8V9xESWE8jTo0dxCjjnopKl+GqJxpVXckHAeF+KkxLbxILfDLUT0rAK9iUzy1L53eKGQ==',
            'tooltip': 'WARNING: deSEC auto-manages DNSKEY records. Only add extra values for advanced multi-signer DNSSEC setups — misuse can break DNSSEC for your domain.\n\nDNSSEC public key. Flags: 257 = KSK (Key Signing Key), 256 = ZSK (Zone Signing Key). Protocol must be 3. Algorithms: 8 = RSASHA256, 13 = ECDSAP256SHA256, 15 = ED25519.'
        },
        'DLV': {
            'format': '<key-tag> <algorithm> <digest-type> <digest-hex>',
            'example': '12345 13 2 abc123...sha256hex...',
            'tooltip': 'DNSSEC Lookaside Validation (obsolete, RFC 8749). Same format as DS. Algorithm: 13 = ECDSAP256SHA256. Digest type: 2 = SHA-256.'
        },
        'DS': {
            'format': '<key-tag> <algorithm> <digest-type> <digest-hex>',
            'example': '12345 13 2 abc123...sha256hex...',
            'tooltip': 'WARNING: deSEC auto-manages DS records. Only add extra values for advanced multi-signer DNSSEC setups — misuse can break DNSSEC for your domain.\n\nDelegation Signer — links parent and child zones in the DNSSEC chain of trust. Algorithm: 13 = ECDSAP256SHA256. Digest type: 1 = SHA-1, 2 = SHA-256.'
        },
        'EUI48': {
            'format': '<xx-xx-xx-xx-xx-xx>',
            'example': 'ab-cd-ef-01-23-45',
            'tooltip': 'EUI-48 / MAC address record. Six hex byte pairs separated by hyphens (not colons).',
            'validation': r'^[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}$'
        },
        'EUI64': {
            'format': '<xx-xx-xx-xx-xx-xx-xx-xx>',
            'example': 'ab-cd-ef-01-23-45-67-89',
            'tooltip': 'EUI-64 address record. Eight hex byte pairs separated by hyphens (not colons).',
            'validation': r'^[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}$'
        },
        'HINFO': {
            'format': '"<cpu>" "<os>"',
            'example': '"X86_64" "Linux"',
            'tooltip': 'Host Information — describes the hardware CPU type and operating system. Both values must be enclosed in double quotes.'
        },
        'HTTPS': {
            'format': '<priority> <target.> [<param>=<value> ...]',
            'example': '1 . alpn="h2,h3" ipv4hint="192.0.2.1"',
            'tooltip': 'HTTPS Service Binding. Priority 0 = alias mode (like CNAME). Use . as target to inherit the owner name. Common params: alpn, ipv4hint, ipv6hint, port, ech.'
        },
        'KX': {
            'format': '<preference> <exchanger.>',
            'example': '10 kx.example.com.',
            'tooltip': 'Key Exchanger — specifies a host for IPSEC key exchange. Lower preference value = higher priority. Exchanger must be an FQDN with trailing dot.'
        },
        'L32': {
            'format': '<preference> <locator>',
            'example': '10 10.1.2.3',
            'tooltip': 'ILNP 32-bit Locator. Lower preference = higher priority. Locator is an IPv4 address.'
        },
        'L64': {
            'format': '<preference> <locator>',
            'example': '10 2001:db8:1:2',
            'tooltip': 'ILNP 64-bit Locator. Lower preference = higher priority. Locator is the upper 64 bits of an IPv6 address (four 16-bit hex groups).'
        },
        'LOC': {
            'format': '<d> <m> <s> <N/S> <d> <m> <s> <E/W> <alt>m [<size>m [<hp>m [<vp>m]]]',
            'example': '51 30 12.748 N 0 7 39.611 W 0.00m 1m 10000m 10m',
            'tooltip': 'Geographic location. Degrees/minutes/seconds for latitude (N/S) and longitude (E/W), then altitude in metres. Optional: size of location, horizontal precision, vertical precision (all in metres).'
        },
        'LP': {
            'format': '<preference> <fqdn.>',
            'example': '10 l32.example.com.',
            'tooltip': 'ILNP Locator Pointer — points to a name that has L32/L64 records. Lower preference = higher priority. FQDN must end with a trailing dot.'
        },
        'MX': {
            'format': '<priority> <mailserver.>',
            'example': '10 mail.example.com.',
            'tooltip': 'Mail Exchange — specifies the mail server for this domain. Lower priority = preferred. Mail server must be an FQDN with trailing dot. Add one entry per line for multiple servers.'
        },
        'NAPTR': {
            'format': '<order> <pref> "<flags>" "<service>" "<regexp>" <replacement.>',
            'example': '100 10 "u" "E2U+sip" "!^.*$!sip:info@example.com!" .',
            'tooltip': 'Naming Authority Pointer — used for ENUM, SIP, and URI rewriting. Order and preference are integers. Flags: u = terminal URI, s = SRV lookup, a = A/AAAA lookup, empty = continue. Use . as replacement if the regexp is terminal.'
        },
        'NID': {
            'format': '<preference> <node-id>',
            'example': '10 0014:4fff:ff20:ee64',
            'tooltip': 'ILNP Node Identifier. Lower preference = higher priority. Node ID is a 64-bit value as four 16-bit hex groups separated by colons.'
        },
        'NS': {
            'format': '<nameserver.>',
            'example': 'ns1.example.com.',
            'tooltip': 'Name Server — delegates the zone to an authoritative nameserver. Must be an FQDN with trailing dot. Note: apex NS records at the zone root are managed by deSEC and cannot be modified here.',
            'validation': r'^.+\.$'
        },
        'OPENPGPKEY': {
            'format': '<base64-key-data>',
            'example': 'mQENBFVHm5sBCADH...base64...',
            'tooltip': 'OpenPGP public key for a user, looked up via the email local-part hash as the subdomain (e.g. hash._openpgpkey.example.com). Paste the full base64-encoded transferable public key.'
        },
        'PTR': {
            'format': '<target.>',
            'example': 'host.example.com.',
            'tooltip': 'Pointer — maps an IP address back to a hostname (reverse DNS). Used under in-addr.arpa (IPv4) or ip6.arpa (IPv6). Target must be an FQDN with trailing dot.',
            'validation': r'^.+\.$'
        },
        'RP': {
            'format': '<mbox-dname.> <txt-dname.>',
            'example': 'hostmaster.example.com. info.example.com.',
            'tooltip': 'Responsible Person. First field is the mailbox address with @ replaced by . (e.g. hostmaster.example.com = hostmaster@example.com). Second field is a name with a TXT record containing contact info. Both must end with a trailing dot.'
        },
        'SMIMEA': {
            'format': '<usage> <selector> <matching-type> <data>',
            'example': '3 1 1 abc123...sha256hex...',
            'tooltip': 'S/MIME Certificate Association (DANE for email). Usage: 0=PKIX-TA, 1=PKIX-EE, 2=DANE-TA, 3=DANE-EE. Selector: 0=full cert, 1=SubjectPublicKeyInfo. Matching type: 0=raw (base64), 1=SHA-256 hex, 2=SHA-512 hex.'
        },
        'SPF': {
            'format': '"v=spf1 <mechanisms> <qualifier>all"',
            'example': '"v=spf1 mx a ip4:192.0.2.0/24 -all"',
            'tooltip': 'Sender Policy Framework (legacy record type — use TXT records with SPF content instead). Value must be in double quotes. Mechanisms: mx, a, ip4:, ip6:, include:. Qualifiers: + pass, - fail, ~ softfail, ? neutral.'
        },
        'SRV': {
            'format': '<priority> <weight> <port> <target.>',
            'example': '10 20 443 svc.example.com.',
            'tooltip': 'Service Locator. Lower priority = preferred. Weight distributes load among equal-priority entries (higher weight = more traffic). Port is the service port number. Target must be an FQDN with trailing dot.',
            'validation': r'^[0-9]+\s+[0-9]+\s+[0-9]+\s+[a-zA-Z0-9.\-_]+\.$'
        },
        'SSHFP': {
            'format': '<algorithm> <type> <fingerprint-hex>',
            'example': '4 2 abc123...sha256hex...',
            'tooltip': 'SSH Fingerprint — allows SSH clients to verify host keys via DNS. Algorithm: 1=RSA, 2=DSA, 3=ECDSA, 4=ED25519. Type: 1=SHA-1, 2=SHA-256. Fingerprint is hex without colons.',
            'validation': r'^[1-4]\s+[1-2]\s+[0-9a-fA-F]+$'
        },
        'SVCB': {
            'format': '<priority> <target.> [<param>=<value> ...]',
            'example': '1 backend.example.com. alpn="h2" port=8443',
            'tooltip': 'Service Binding (generalised form of HTTPS). Priority 0 = alias mode. Use . as target to inherit the owner name. Common params: alpn, port, ipv4hint, ipv6hint, ech.'
        },
        'TLSA': {
            'format': '<usage> <selector> <matching-type> <data>',
            'example': '3 1 1 abc123...sha256hex...',
            'tooltip': 'TLS Certificate Association (DANE). Usage: 0=PKIX-TA, 1=PKIX-EE, 2=DANE-TA, 3=DANE-EE. Selector: 0=full cert, 1=SubjectPublicKeyInfo. Matching type: 0=raw, 1=SHA-256 hex, 2=SHA-512 hex.',
            'validation': r'^[0-3]\s+[0-1]\s+[0-2]\s+[0-9a-fA-F]+$'
        },
        'TXT': {
            'format': '"<text content>"',
            'example': '"v=spf1 include:example.com -all"',
            'tooltip': 'Text record — stores arbitrary text data. Content must be enclosed in double quotes. For multiple values (e.g. long SPF), enter one quoted string per line. Backslash-escape any double quotes within the content.',
            'validation': r'^".*"$'
        },
        'URI': {
            'format': '<priority> <weight> "<uri>"',
            'example': '10 1 "https://www.example.com/"',
            'tooltip': 'URI record — maps a service name to a URI. Lower priority = preferred. Higher weight = more traffic among equal-priority entries. URI must be enclosed in double quotes.'
        },
    }
    
    def __init__(self, api_client, cache_manager, config_manager=None, parent=None,
                 api_queue=None, version_manager=None):
        """
        Initialize the record widget.
        :param api_client: API client instance
        :param cache_manager: Cache manager instance
        :param config_manager: Configuration manager instance for settings (optional)
        :param parent: Parent widget
        :param api_queue: Central API queue (optional)
        :param version_manager: Git-based zone versioning (optional)
        """
        super().__init__(parent)
        self.api_client = api_client
        self.cache_manager = cache_manager
        self.config_manager = config_manager
        self.api_queue = api_queue
        self.version_manager = version_manager
        self.current_domain = None
        self.records = []
        self.is_online = True  # Start assuming we are online
        self.can_edit = True  # Single source of truth for editability
        # Initialize multiline display setting from config if available
        self.show_multiline = False  # Default value
        if self.config_manager:
            self.show_multiline = self.config_manager.get_show_multiline_records()

        self.threadpool = QThreadPool()
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)  # Standard 6px margin
        layout.setSpacing(6)  # Standard 6px spacing
        
        # Header section - title, count and search field
        header_layout = QtWidgets.QVBoxLayout()
        header_layout.setSpacing(6)  # Consistent spacing
        
        # Title and count
        title_layout = QtWidgets.QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        title = StrongBodyLabel("DNS Records (RRsets)")
        title.setMinimumWidth(100)  # Fixed width for right alignment
        title_layout.addWidget(title)

        title_layout.addStretch()

        self.records_count_label = CaptionLabel("Total records: 0")
        title_layout.addWidget(self.records_count_label)
        
        header_layout.addLayout(title_layout)
        
        # Search field (match spacing with Zone widget)
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.setContentsMargins(0, 6, 0, 6)  # Add vertical padding

        self.records_search_input = SearchLineEdit()
        self.records_search_input.setPlaceholderText("Type to filter records...")
        self.records_search_input.textChanged.connect(self._apply_filters)
        search_layout.addWidget(self.records_search_input)

        self.type_filter_input = LineEdit()
        self.type_filter_input.setPlaceholderText("Type")
        self.type_filter_input.setFixedWidth(90)
        self.type_filter_input.textChanged.connect(self._apply_filters)
        search_layout.addWidget(self.type_filter_input)

        self.ttl_filter_input = LineEdit()
        self.ttl_filter_input.setPlaceholderText("TTL")
        self.ttl_filter_input.setFixedWidth(80)
        self.ttl_filter_input.textChanged.connect(self._apply_filters)
        search_layout.addWidget(self.ttl_filter_input)
        
        header_layout.addLayout(search_layout)
        
        # Add header layout to main layout
        layout.addLayout(header_layout)
        
        # Records table
        self.records_table = TableWidget()
        self.records_table.setColumnCount(4)  # Name, Type, TTL, Content

        # Create header items
        name_header = QtWidgets.QTableWidgetItem("Name ↕")
        name_header.setToolTip("Click to sort by name")
        name_header.setTextAlignment(Qt.AlignmentFlag.AlignLeft)

        type_header = QtWidgets.QTableWidgetItem("Type ↕")
        type_header.setToolTip("Click to sort by record type")
        type_header.setTextAlignment(Qt.AlignmentFlag.AlignLeft)

        ttl_header = QtWidgets.QTableWidgetItem("TTL ↕")
        ttl_header.setToolTip("Click to sort by TTL value")
        ttl_header.setTextAlignment(Qt.AlignmentFlag.AlignLeft)

        content_header = QtWidgets.QTableWidgetItem("Content ↕")
        content_header.setToolTip("Click to sort by content")
        content_header.setTextAlignment(Qt.AlignmentFlag.AlignLeft)


        self.records_table.setHorizontalHeaderItem(COL_NAME,    name_header)
        self.records_table.setHorizontalHeaderItem(COL_TYPE,    type_header)
        self.records_table.setHorizontalHeaderItem(COL_TTL,     ttl_header)
        self.records_table.setHorizontalHeaderItem(COL_CONTENT, content_header)
        
        # Set table properties
        self.records_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.records_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.records_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.records_table.setAlternatingRowColors(True)
        # Column resize modes
        self.records_table.horizontalHeader().setSectionResizeMode(COL_NAME,    QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.records_table.horizontalHeader().setSectionResizeMode(COL_TYPE,    QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.records_table.horizontalHeader().setSectionResizeMode(COL_TTL,     QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.records_table.horizontalHeader().setSectionResizeMode(COL_CONTENT, QtWidgets.QHeaderView.ResizeMode.Stretch)

        # Set initial default widths (matched to typical column proportions)
        self.records_table.horizontalHeader().setMinimumSectionSize(60)
        self.records_table.setColumnWidth(COL_NAME,    180)
        self.records_table.setColumnWidth(COL_TYPE,    117)
        self.records_table.setColumnWidth(COL_TTL,     80)
        self.records_table.verticalHeader().setVisible(False)

        # Enhance sort indicator visibility
        self.records_table.horizontalHeader().setSortIndicatorShown(True)
        self.records_table.horizontalHeader().sortIndicatorChanged.connect(self.sort_records_table)

        # Set default sort by name column in ascending order
        self.records_table.setSortingEnabled(True)
        self.records_table.sortByColumn(COL_NAME, QtCore.Qt.SortOrder.AscendingOrder)
        self.records_table.cellDoubleClicked.connect(self.handle_cell_double_clicked)
        self.records_table.itemSelectionChanged.connect(self._update_bulk_btn)
        
        # Set the table to take all available space
        self.records_table.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        
        # Add stretch factor to match zone list widget
        layout.addWidget(self.records_table, 1)
        
        # Add spacer to push buttons to bottom for alignment with zone list widget
        button_spacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Policy.Minimum, 
                                          QtWidgets.QSizePolicy.Policy.Expanding)
        layout.addItem(button_spacer)
        
        # Action buttons
        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.setContentsMargins(0, 6, 0, 6)  # Add spacing for visual separation
        
        # Add record button
        self.add_record_btn = PushButton("Add Record")
        self.add_record_btn.clicked.connect(
            lambda: self.edit_panel.open_for_add(self.current_domain)
        )
        self.add_record_btn.setEnabled(self.is_online)
        if not self.is_online:
            self.add_record_btn.setToolTip("Unavailable in offline mode")
        actions_layout.addWidget(self.add_record_btn)
        
        actions_layout.addStretch()

        self.select_all_btn = PushButton("Select All")
        self.select_all_btn.setEnabled(False)
        self.select_all_btn.clicked.connect(self._select_all_records)
        actions_layout.addWidget(self.select_all_btn)

        self.select_none_btn = PushButton("Select None")
        self.select_none_btn.setEnabled(False)
        self.select_none_btn.clicked.connect(self._select_none_records)
        actions_layout.addWidget(self.select_none_btn)

        self.bulk_delete_btn = PushButton("Delete Selected")
        self.bulk_delete_btn.setEnabled(False)
        self.bulk_delete_btn.clicked.connect(self.delete_selected_records)
        actions_layout.addWidget(self.bulk_delete_btn)

        layout.addLayout(actions_layout)

        # Slide-in edit panel (absolutely positioned overlay — not part of the layout)
        self.edit_panel = RecordEditPanel(
            self.api_client, parent=self,
            api_queue=self.api_queue, version_manager=self.version_manager,
        )
        self.edit_panel.save_done.connect(self._on_record_saved)
        self.edit_panel.log_signal.connect(self.log_message)

        # Delete confirmation drawer (slides from top)
        self._delete_drawer = DeleteConfirmDrawer(parent=self)
    
    def set_domain(self, domain_name):
        """
        Set the current domain and load its records.
        
        Args:
            domain_name (str): Domain name to load records for
        """
        self.current_domain = domain_name
        self.refresh_records()
    
    def set_online_status(self, is_online):
        """Update the online status and enable/disable UI elements accordingly.
        
        Args:
            is_online (bool): Whether the application is online
        """
        self.is_online = is_online
        self.set_edit_enabled(is_online)
        
    def set_multiline_display(self, show_multiline):
        """Set whether to show multiline records in full or condensed format
        
        Args:
            show_multiline (bool): Whether to show multiline records in full
        """
        if self.show_multiline != show_multiline:
            self.show_multiline = show_multiline
            # Update the display immediately if we have records
            if hasattr(self, 'records') and self.records:
                self.update_records_table()
                
                # Adjust row heights if multiline display is enabled
                if self.show_multiline:
                    self.records_table.resizeRowsToContents()
                else:
                    # Reset to default row height when disabled
                    for row in range(self.records_table.rowCount()):
                        self.records_table.setRowHeight(row, self.records_table.verticalHeader().defaultSectionSize())
    
    def set_edit_enabled(self, enabled):
        """Enable or disable record editing controls based on online/offline mode.
        
        Args:
            enabled (bool): Whether editing is enabled
        """
        self.can_edit = enabled  # Single source of truth
        # Enable/disable add button
        if hasattr(self, 'add_record_btn'):
            self.add_record_btn.setEnabled(self.can_edit)
            if not self.can_edit:
                self.add_record_btn.setToolTip("Adding records is disabled in offline mode")
            else:
                self.add_record_btn.setToolTip("")
        
        # Enable/disable bulk action buttons
        if hasattr(self, 'select_all_btn'):
            has_rows = self.records_table.rowCount() > 0
            self.select_all_btn.setEnabled(self.can_edit and has_rows)
            self.select_none_btn.setEnabled(self.can_edit and has_rows)
            self._update_bulk_btn()
    
    def refresh_records(self):
        """Refresh the records for the current domain."""
        if not self.current_domain:
            return
            
        # First check cache regardless of online status
        start_time = time.time()
        cached_records, cache_timestamp = self.cache_manager.get_cached_records(self.current_domain)
        
        if cached_records is not None:
            # We have cached records, use them immediately for responsiveness
            self.records = cached_records
            self.update_records_table()
            elapsed = (time.time() - start_time) * 1000
            logger.debug(f"Loaded {len(cached_records)} cached records in {elapsed:.1f}ms")
            
            # Only fetch from API if online and cache is stale (or we need to refresh)
            # Default sync interval to 5 minutes for staleness check
            _can_sync = self.api_client.is_online and not self.config_manager.get_offline_mode()
            if _can_sync and self.cache_manager.is_cache_stale(cache_timestamp, 5):
                # Use worker for background API update
                self.fetch_records_async()

        # Only if cache is empty and we're online, fetch records asynchronously
        elif self.api_client.is_online and not self.config_manager.get_offline_mode():
            # Use worker for background API update
            self.fetch_records_async()
            # Show loading message
            self.log_message.emit(f"Loading records for {self.current_domain}...", "info")
        else:
            # Offline with no cache
            self.records = []
            self.update_records_table()
            self.log_message.emit("No cached records available for this zone", "warning")
    
    def _load_from_cache(self):
        """Load records from cache."""
        cached_records, _ = self.cache_manager.get_cached_records(self.current_domain)
        
        if cached_records:
            self.records = cached_records
            self.update_records_table()
            self.log_message.emit(
                f"Loaded {len(cached_records)} records for {self.current_domain} from cache", 
                "info"
            )
        else:
            self.log_message.emit(f"No cached records for {self.current_domain}", "warning")
    def fetch_records_async(self):
        """Fetch records asynchronously using the queue or a worker thread."""
        domain = self.current_domain
        if self.api_queue and domain:
            def _on_done(success, data):
                if success and isinstance(data, list):
                    self.cache_manager.cache_records(domain, data)
                    self.handle_records_result(True, data, domain, "")
                else:
                    self.handle_records_result(False, [], domain, str(data) if data else "")

            item = QueueItem(
                priority=PRIORITY_LOW,
                category="records",
                action=f"Load records for {domain}",
                callable=self.api_client.get_records,
                args=(domain,),
                callback=_on_done,
            )
            self.api_queue.enqueue(item)
        else:
            worker = LoadRecordsWorker(self.api_client, self.current_domain, self.cache_manager)
            worker.signals.finished.connect(self.handle_records_result)
            self.threadpool.start(worker)
        
    def handle_records_result(self, success, records, zone_name, error_msg):
        """Handle the result of asynchronous record loading.
        
        Args:
            success: Whether the operation was successful
            records: List of record dictionaries
            zone_name: Name of the zone
            error_msg: Error message if any
        """
        if success and zone_name == self.current_domain:
            # Only update if this is still the current domain
            self.records = records
            self.update_records_table()
        elif not success and error_msg:
            self.log_message.emit(f"Error: {error_msg}", "error")
            self.records = []
            self.update_records_table()
    
    def update_records_table(self):
        """Update the records table with current records."""
        # Temporarily disable sorting to prevent issues while populating
        was_sorting_enabled = self.records_table.isSortingEnabled()
        self.records_table.setSortingEnabled(False)
        
        # Clear the table
        self.records_table.setRowCount(0)
        
        # If no domain selected, nothing to display
        if not self.current_domain:
            self.records_table.setSortingEnabled(was_sorting_enabled)
            self.records_count_label.setText("No domain selected")
            return
        
        # Get current filter values
        filter_text = getattr(self, '_current_filter', '').lower()
        type_filter = getattr(self, '_type_filter', '').lower()
        ttl_filter = getattr(self, '_ttl_filter', '')

        # Calculate the number of filtered records for display
        total_records = len(self.records)
        filtered_records = []

        # Note: we no longer pre-sort the records since we'll use Qt's built-in sorting
        for record in self.records:
            # Main search: matches subname, type, or content
            if filter_text and not (
                filter_text in record.get('subname', '').lower()
                or filter_text in record.get('type', '').lower()
                or filter_text in "\n".join(record.get('records', [])).lower()
            ):
                continue
            # Type filter: record type must contain the filter text
            if type_filter and type_filter not in record.get('type', '').lower():
                continue
            # TTL filter: record TTL string must contain the filter text
            if ttl_filter and ttl_filter not in str(record.get('ttl', '')):
                continue
            filtered_records.append(record)

        # Update the records count label
        filtered_count = len(filtered_records)
        any_filter = filter_text or type_filter or ttl_filter
        if any_filter:
            self.records_count_label.setText(f"Showing {filtered_count} out of {total_records} records")
        else:
            self.records_count_label.setText(f"Total records: {total_records}")

        # Ensure edit controls reflect offline/online state after table update
        self.set_edit_enabled(self.is_online and not self.config_manager.get_offline_mode())
        
        for row, record in enumerate(filtered_records):
            self.records_table.insertRow(row)

            # Name column (subname)
            name = record.get('subname', '') or '@'
            name_item = QtWidgets.QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, record)
            timestamp_tooltip = self._get_timestamp_tooltip(record)
            if timestamp_tooltip:
                name_item.setToolTip(timestamp_tooltip)
            self.records_table.setItem(row, COL_NAME, name_item)

            # Type column — medium weight + colored
            record_type = record.get('type', '')
            type_item = QtWidgets.QTableWidgetItem(record_type)
            f = type_item.font()
            f.setWeight(QtGui.QFont.Weight.Medium)
            type_item.setFont(f)
            if record_type in _TYPE_COLORS:
                light_c, dark_c = _TYPE_COLORS[record_type]
                type_item.setForeground(QtGui.QColor(dark_c if isDarkTheme() else light_c))
            if timestamp_tooltip:
                type_item.setToolTip(timestamp_tooltip)
            self.records_table.setItem(row, COL_TYPE, type_item)

            # TTL column — store as number for proper numeric sorting
            ttl_item = QtWidgets.QTableWidgetItem()
            ttl_item.setData(Qt.ItemDataRole.DisplayRole, int(record.get('ttl', 0)))
            if timestamp_tooltip:
                ttl_item.setToolTip(timestamp_tooltip)
            self.records_table.setItem(row, COL_TTL, ttl_item)

            # Content column
            content_text = "\n".join(record.get('records', []))
            content_item = QtWidgets.QTableWidgetItem(content_text)
            if timestamp_tooltip:
                content_item.setToolTip(timestamp_tooltip)
            self.records_table.setItem(row, COL_CONTENT, content_item)


        self._update_bulk_btn()

        # Preserve content column stretch
        self.records_table.horizontalHeader().setSectionResizeMode(
            COL_CONTENT, QtWidgets.QHeaderView.ResizeMode.Stretch
        )

        # Adjust row heights based on multiline display setting
        if self.show_multiline:
            self.records_table.resizeRowsToContents()
        else:
            default_height = self.records_table.verticalHeader().defaultSectionSize()
            for row in range(self.records_table.rowCount()):
                self.records_table.setRowHeight(row, default_height)

        # Re-enable sorting if it was enabled before
        self.records_table.setSortingEnabled(was_sorting_enabled)

        if was_sorting_enabled:
            self.records_table.sortByColumn(COL_NAME, Qt.SortOrder.AscendingOrder)
    
    def filter_records(self, filter_text):
        """Legacy entry point — delegates to _apply_filters."""
        self.records_search_input.setText(filter_text)

    def _apply_filters(self):
        """Read all filter fields and refresh the table."""
        self._current_filter = self.records_search_input.text().lower()
        self._type_filter = self.type_filter_input.text().strip().lower()
        self._ttl_filter = self.ttl_filter_input.text().strip()
        self.update_records_table()
    
    def _get_timestamp_tooltip(self, record):
        """Generate timestamp tooltip text for a record.
        
        Args:
            record (dict): Record dictionary containing timestamp information
            
        Returns:
            str: Formatted timestamp tooltip text, or empty string if no timestamps available
        """
        tooltip_parts = []
        
        # Check for creation timestamp
        created = record.get('created')
        if created:
            try:
                from datetime import datetime
                # Parse ISO format timestamp
                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                tooltip_parts.append(f"Created: {created_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            except (ValueError, AttributeError):
                tooltip_parts.append(f"Created: {created}")
        
        # Check for last modified timestamp
        touched = record.get('touched')
        if touched:
            try:
                from datetime import datetime
                # Parse ISO format timestamp
                touched_dt = datetime.fromisoformat(touched.replace('Z', '+00:00'))
                tooltip_parts.append(f"Last Modified: {touched_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            except (ValueError, AttributeError):
                tooltip_parts.append(f"Last Modified: {touched}")
        
        return '\n'.join(tooltip_parts) if tooltip_parts else ''
    


    def sort_records_table(self, column, order):
        """Sort the records table based on column clicked.
        
        Args:
            column: The column index to sort by
            order: The sort order (ascending or descending)
        """
        # Only enable sorting on Name, Type, TTL, and Content columns
        if column in (COL_NAME, COL_TYPE, COL_TTL, COL_CONTENT):
            self.records_table.sortItems(column, Qt.SortOrder(order))

            # Update header text to indicate current sort column and direction
            header_items = {
                COL_NAME:    "Name",
                COL_TYPE:    "Type",
                COL_TTL:     "TTL",
                COL_CONTENT: "Content",
            }
            for col, label in header_items.items():
                item = self.records_table.horizontalHeaderItem(col)
                if item is None:
                    continue
                if col == column:
                    arrow = "↑" if order == Qt.SortOrder.AscendingOrder else "↓"
                    item.setText(f"{label} {arrow}")
                else:
                    item.setText(f"{label} ↕")
    
    def handle_cell_double_clicked(self, row, column):
        """Handle double-click on a cell — opens the edit panel."""
        if not self.can_edit:
            return
        record_item = self.records_table.item(row, COL_NAME)
        if record_item is None:
            return
        record = record_item.data(Qt.ItemDataRole.UserRole)
        if record:
            self.edit_record_by_ref(record)
    
    def edit_record_by_ref(self, record):
        if not self.can_edit or not record:
            return
        self.edit_panel.open_for_edit(self.current_domain, record)
    
    def edit_record(self, row):
        if not self.can_edit:
            return
        record_item = self.records_table.item(row, COL_NAME)
        record = record_item.data(Qt.ItemDataRole.UserRole)
        if not record:
            return
        self.edit_panel.open_for_edit(self.current_domain, record)

    def delete_selected_record(self):
        """Delete the currently selected record(s) in the table.
        Called when pressing the Delete key while the records table has focus.
        """
        if not hasattr(self, 'records_table') or not self.can_edit:
            return

        # Collect unique rows from the selection
        selected_indexes = self.records_table.selectedIndexes()
        if not selected_indexes:
            return

        seen_rows = set()
        records_to_delete = []
        for index in selected_indexes:
            row = index.row()
            if row in seen_rows:
                continue
            seen_rows.add(row)
            name_item = self.records_table.item(row, COL_NAME)
            if name_item is None:
                continue
            record = name_item.data(Qt.ItemDataRole.UserRole)
            if record:
                records_to_delete.append(record)

        if not records_to_delete:
            self.log_message.emit("No record found for deletion", "warning")
            return

        if len(records_to_delete) == 1:
            self.delete_record_by_ref(records_to_delete[0])
        else:
            # Multiple rows selected: use bulk delete flow
            count = len(records_to_delete)
            items = [
                f"{r.get('subname') or '@'} {r.get('type', '')}"
                for r in records_to_delete
            ]

            def _do_bulk_delete():
                self._set_bulk_busy(True)
                self._bulk_worker = _BulkDeleteWorker(self.api_client, self.current_domain, records_to_delete)
                self._bulk_worker.record_done.connect(self._on_bulk_record_done)
                self._bulk_worker.finished.connect(self._on_bulk_delete_finished)
                self._bulk_worker.start()

            self._delete_drawer.ask(
                title="Delete Records",
                message=f"Permanently delete {count} selected record(s)? This cannot be undone.",
                items=items,
                on_confirm=_do_bulk_delete,
                confirm_text=f"Delete {count} Records",
            )
    
    # ------------------------------------------------------------------
    # Bulk selection and delete
    # ------------------------------------------------------------------

    def _update_bulk_btn(self):
        if not hasattr(self, 'bulk_delete_btn'):
            return
        n = len(set(idx.row() for idx in self.records_table.selectedIndexes()))
        can = n > 0 and self.can_edit
        self.bulk_delete_btn.setEnabled(can)
        self.bulk_delete_btn.setText(f"Delete Selected ({n})" if n > 0 else "Delete Selected")
        has_rows = self.records_table.rowCount() > 0
        self.select_all_btn.setEnabled(has_rows and self.can_edit)
        self.select_none_btn.setEnabled(has_rows and self.can_edit)

    def _select_all_records(self):
        self.records_table.selectAll()

    def _select_none_records(self):
        self.records_table.clearSelection()

    def delete_selected_records(self):
        if not self.can_edit:
            return
        seen_rows = set()
        records = []
        for idx in self.records_table.selectedIndexes():
            row = idx.row()
            if row in seen_rows:
                continue
            seen_rows.add(row)
            name_item = self.records_table.item(row, COL_NAME)
            if name_item:
                rec = name_item.data(Qt.ItemDataRole.UserRole)
                if rec:
                    records.append(rec)
        if not records:
            return
        count = len(records)
        items = [
            f"{r.get('subname') or '@'} {r.get('type', '')}"
            for r in records
        ]

        def _do_bulk_delete():
            self._set_bulk_busy(True)
            if self.api_queue:
                self._bulk_pending = len(records)
                self._bulk_deleted = 0
                self._bulk_failed = 0
                domain = self.current_domain
                for rec in records:
                    sub = rec.get('subname', '') or ''
                    rt = rec.get('type', '')
                    label = f"{sub or '@'} {rt}"

                    def _make_cb(lbl):
                        def _cb(success, data):
                            self._on_bulk_record_done(success, lbl)
                            if success:
                                self._bulk_deleted += 1
                            else:
                                self._bulk_failed += 1
                            self._bulk_pending -= 1
                            if self._bulk_pending <= 0:
                                self._on_bulk_delete_finished(self._bulk_deleted, self._bulk_failed)
                        return _cb

                    item = QueueItem(
                        priority=PRIORITY_NORMAL,
                        category="records",
                        action=f"Delete {rt} for {sub or '@'} in {domain}",
                        callable=self.api_client.delete_record,
                        args=(domain, sub, rt),
                        callback=_make_cb(label),
                    )
                    self.api_queue.enqueue(item)
            else:
                self._bulk_worker = _BulkDeleteWorker(self.api_client, self.current_domain, records)
                self._bulk_worker.record_done.connect(self._on_bulk_record_done)
                self._bulk_worker.finished.connect(self._on_bulk_delete_finished)
                self._bulk_worker.start()

        self._delete_drawer.ask(
            title="Delete Records",
            message=f"Permanently delete {count} selected record(s)? This cannot be undone.",
            items=items,
            on_confirm=_do_bulk_delete,
            confirm_text=f"Delete {count} Records",
        )

    def _set_bulk_busy(self, busy):
        self.bulk_delete_btn.setEnabled(not busy)
        self.select_all_btn.setEnabled(not busy)
        self.select_none_btn.setEnabled(not busy)
        self.add_record_btn.setEnabled(not busy)

    def _on_bulk_record_done(self, success, label):
        self.log_message.emit(
            f"{'Deleted' if success else 'Failed to delete'}: {label}",
            "success" if success else "error",
        )

    def _on_bulk_delete_finished(self, deleted, failed):
        self.cache_manager.clear_domain_cache(self.current_domain)
        self.records_changed.emit()
        self.refresh_records()
        self._set_bulk_busy(False)
        self.log_message.emit(
            f"Bulk delete: {deleted} deleted, {failed} failed.", "info"
        )

    def delete_record_by_ref(self, record):
        """Delete a record by reference instead of by row index.

        Args:
            record (dict): The record object to delete
        """
        if not self.is_online or not record:
            return

        # Get record details
        subname = record.get('subname', '')
        rtype = record.get('type', '')
        record_name = subname or '@'
        domain = self.current_domain

        def _do_delete():
            record_content = "\n".join(record.get('records', ['<empty>']))
            ttl = record.get('ttl', 0)
            self.log_message.emit(
                f"Deleting {rtype} record for '{record_name}' with TTL: {ttl}, content: {record_content}", "info"
            )

            if self.api_queue:
                def _on_done(success, response):
                    if success:
                        if self.version_manager and domain:
                            self.version_manager.snapshot(
                                domain, self.records,
                                f"Delete {rtype} record for '{record_name}'"
                            )
                        self.log_message.emit(
                            f"Successfully deleted {rtype} record for '{record_name}' with TTL: {ttl}", "success"
                        )
                        self.cache_manager.clear_domain_cache(domain)
                        self.records_changed.emit()
                        self.refresh_records()
                    else:
                        err_msg = response.get('message', str(response)) if isinstance(response, dict) else str(response)
                        self.log_message.emit(f"Failed to delete record: {err_msg}", "error")
                        InfoBar.error(
                            title="Delete Failed",
                            content=err_msg,
                            parent=self.window(),
                            duration=8000,
                            position=InfoBarPosition.TOP,
                        )

                item = QueueItem(
                    priority=PRIORITY_NORMAL,
                    category="records",
                    action=f"Delete {rtype} for {record_name} in {domain}",
                    callable=self.api_client.delete_record,
                    args=(domain, subname, rtype),
                    callback=_on_done,
                )
                self.api_queue.enqueue(item)
            else:
                success, response = self.api_client.delete_record(domain, subname, rtype)
                if success:
                    self.log_message.emit(
                        f"Successfully deleted {rtype} record for '{record_name}' with TTL: {ttl}", "success"
                    )
                    self.cache_manager.clear_domain_cache(domain)
                    self.records_changed.emit()
                    self.refresh_records()
                else:
                    err_msg = response.get('message', str(response)) if isinstance(response, dict) else str(response)
                    self.log_message.emit(f"Failed to delete record: {err_msg}", "error")
                    InfoBar.error(
                        title="Delete Failed",
                        content=err_msg,
                        parent=self.window(),
                        duration=8000,
                        position=InfoBarPosition.TOP,
                    )

        self._delete_drawer.ask(
            title="Delete Record",
            message=f"Delete the {rtype} record for '{record_name}'?",
            on_confirm=_do_delete,
            confirm_text="Delete Record",
        )

    def _on_record_saved(self):
        """Called when RecordEditPanel reports a successful save."""
        if self.current_domain:
            self.cache_manager.clear_domain_cache(self.current_domain)
        self.records_changed.emit()
        self.refresh_records()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'edit_panel'):
            self.edit_panel.reposition(event.size())
        if hasattr(self, '_delete_drawer'):
            self._delete_drawer.reposition(event.size())
