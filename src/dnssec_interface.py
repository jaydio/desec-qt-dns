#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DNSSEC information sidebar page.

Left pane:  domain list (single selection)
Right pane: DS and DNSKEY key material, styled with card sections,
            copyable long-value fields, and contextual annotations.
"""

import logging

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve

from qfluentwidgets import (
    PushButton, SearchLineEdit, LineEdit, ListWidget,
    StrongBodyLabel, CaptionLabel, isDarkTheme,
    InfoBar, InfoBarPosition,
)

from fluent_styles import container_qss, SPLITTER_QSS

logger = logging.getLogger(__name__)

_ALGO_NAMES = {
    "8":  "RSA/SHA-256",      "10": "RSA/SHA-512",
    "13": "ECDSAP256SHA256",  "14": "ECDSAP384SHA384",
    "15": "Ed25519",          "16": "Ed448",
}

_DIGEST_NAMES = {
    "1": "SHA-1", "2": "SHA-256", "3": "GOST R 34.11-94", "4": "SHA-384",
}

_FLAG_NAMES = {"256": "ZSK", "257": "KSK"}


class _CollapsibleWarning(QtWidgets.QFrame):
    """Collapsible amber warning card with animated expand/collapse."""

    _DURATION = 200  # ms

    def __init__(self, title: str, body_html: str, parent=None):
        super().__init__(parent)
        self._collapsed = True

        self.setObjectName("dnssecWarning")
        self._apply_style()

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header (always visible, clickable) ─────────────────────────
        self._header = QtWidgets.QFrame()
        self._header.setObjectName("dnssecWarningHdr")
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.mousePressEvent = lambda _: self.toggle()

        hdr_lay = QtWidgets.QHBoxLayout(self._header)
        hdr_lay.setContentsMargins(14, 10, 14, 10)
        hdr_lay.setSpacing(10)

        icon = QtWidgets.QLabel("\u26A0")
        icon.setStyleSheet("font-size: 16px; background: transparent; border: none;")
        hdr_lay.addWidget(icon)

        title_lbl = StrongBodyLabel(title)
        title_lbl.setStyleSheet("background: transparent; border: none;")
        hdr_lay.addWidget(title_lbl, 1)

        self._chevron = QtWidgets.QLabel("\u25BC")
        self._chevron.setStyleSheet(
            "font-size: 11px; color: rgba(150,150,150,0.85); "
            "background: transparent; border: none;"
        )
        hdr_lay.addWidget(self._chevron)

        root.addWidget(self._header)

        # ── Body (collapsible) ─────────────────────────────────────────
        self._body = QtWidgets.QWidget()
        self._body.setObjectName("dnssecWarningBody")
        self._body.setStyleSheet(
            "QWidget#dnssecWarningBody { background: transparent; border: none; }"
        )
        body_lay = QtWidgets.QVBoxLayout(self._body)
        body_lay.setContentsMargins(14, 4, 14, 14)
        body_lay.setSpacing(0)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        dark = isDarkTheme()
        sep.setStyleSheet(
            f"color: {'rgba(255,193,7,0.18)' if dark else 'rgba(200,160,0,0.25)'};"
        )
        body_lay.addWidget(sep)

        content = QtWidgets.QLabel(body_html)
        content.setWordWrap(True)
        content.setTextFormat(Qt.TextFormat.RichText)
        content.setOpenExternalLinks(True)
        content.setStyleSheet(
            "background: transparent; border: none; "
            "padding-top: 10px; line-height: 1.5;"
        )
        body_lay.addWidget(content)

        root.addWidget(self._body)

        # Start collapsed
        self._body.setMaximumHeight(0)
        self._body.setVisible(False)
        self._chevron.setText("\u25BC")

    def _apply_style(self):
        dark = isDarkTheme()
        self.setStyleSheet(
            f"QFrame#dnssecWarning {{"
            f"  background: {'rgba(255,193,7,0.08)' if dark else '#FFF8E1'};"
            f"  border: 1px solid {'rgba(255,193,7,0.22)' if dark else 'rgba(245,190,0,0.35)'};"
            f"  border-left: 3px solid {'#FFB300' if dark else '#F9A825'};"
            f"  border-radius: 6px;"
            f"}}"
            f"QFrame#dnssecWarningHdr {{"
            f"  background: transparent; border: none;"
            f"}}"
        )

    def toggle(self):
        if self._collapsed:
            self._expand()
        else:
            self._collapse()

    def _expand(self):
        self._collapsed = False
        self._chevron.setText("\u25B2")
        self._body.setVisible(True)

        # Measure natural height
        self._body.setMaximumHeight(16777215)
        self._body.adjustSize()
        target = self._body.sizeHint().height()

        self._body.setMaximumHeight(0)
        anim = QPropertyAnimation(self._body, b"maximumHeight", self)
        anim.setDuration(self._DURATION)
        anim.setStartValue(0)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(
            lambda: self._body.setMaximumHeight(16777215)
        )
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _collapse(self):
        self._collapsed = True
        self._chevron.setText("\u25BC")

        anim = QPropertyAnimation(self._body, b"maximumHeight", self)
        anim.setDuration(self._DURATION)
        anim.setStartValue(self._body.height())
        anim.setEndValue(0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(lambda: self._body.setVisible(False))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


class DnssecInterface(QtWidgets.QWidget):
    """Sidebar page showing DNSSEC DS / DNSKEY information per domain."""

    log_message = Signal(str, str)

    def __init__(self, api_client, cache_manager, api_queue=None, parent=None):
        super().__init__(parent)
        self.setObjectName("dnssecInterface")
        self._api = api_client
        self._cache = cache_manager
        self._api_queue = api_queue
        self._current_domain = None
        self._keys = []
        self._setup_ui()

    # ── Static style helpers ────────────────────────────────────────────

    @staticmethod
    def _theme_colors():
        dark = isDarkTheme()
        return {
            "card_bg":    "rgba(255,255,255,0.04)" if dark else "rgba(0,0,0,0.03)",
            "card_border":"rgba(255,255,255,0.10)" if dark else "rgba(0,0,0,0.12)",
            "hdr_bg":     "rgba(255,255,255,0.06)" if dark else "rgba(0,0,0,0.05)",
            "div":        "rgba(255,255,255,0.08)" if dark else "rgba(0,0,0,0.08)",
            "note":       "rgba(160,160,160,0.85)",
        }

    # ── UI setup ────────────────────────────────────────────────────────

    def _setup_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(SPLITTER_QSS)
        outer.addWidget(splitter, 1)

        # ── Left pane ───────────────────────────────────────────────────
        left = QtWidgets.QWidget()
        left.setMinimumWidth(220)
        ll = QtWidgets.QVBoxLayout(left)
        ll.setContentsMargins(6, 6, 6, 6)
        ll.setSpacing(6)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addWidget(StrongBodyLabel("Domains"))
        title_row.addStretch()
        self._zone_count = CaptionLabel("0 domains")
        title_row.addWidget(self._zone_count)
        ll.addLayout(title_row)

        self._search = SearchLineEdit()
        self._search.setPlaceholderText("Search domains...")
        self._search.textChanged.connect(self._filter_zones)
        ll.addWidget(self._search)

        self._zone_list = ListWidget()
        self._zone_list.setAlternatingRowColors(True)
        self._zone_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._zone_list.currentItemChanged.connect(self._on_zone_selected)
        ll.addWidget(self._zone_list, 1)

        splitter.addWidget(left)

        # ── Right pane ──────────────────────────────────────────────────
        right = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(right)
        rl.setContentsMargins(6, 6, 6, 6)
        rl.setSpacing(6)

        right_title = QtWidgets.QHBoxLayout()
        right_title.setContentsMargins(0, 0, 0, 0)
        right_title.addWidget(StrongBodyLabel("DNSSEC Keys"))
        right_title.addStretch()
        self._status_label = CaptionLabel("Select a domain")
        right_title.addWidget(self._status_label)
        rl.addLayout(right_title)

        # Scroll area wraps all key cards
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )

        self._content = QtWidgets.QWidget()
        self._clay = QtWidgets.QVBoxLayout(self._content)
        self._clay.setContentsMargins(0, 0, 4, 0)
        self._clay.setSpacing(10)
        self._clay.addStretch()

        scroll.setWidget(self._content)
        rl.addWidget(scroll, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

    # ── Theme ───────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self.setStyleSheet(container_qss())
        self._refresh_zones()

    # ── Zone list ───────────────────────────────────────────────────────

    def _refresh_zones(self):
        cached, _ = self._cache.get_cached_zones()
        zones = cached or []
        self._all_zones = sorted(z.get("name", "") for z in zones)
        self._filter_zones(self._search.text())

    def _filter_zones(self, text):
        ft = text.strip().lower()
        self._zone_list.clear()
        shown = 0
        for name in self._all_zones:
            if ft and ft not in name.lower():
                continue
            self._zone_list.addItem(name)
            shown += 1
        self._zone_count.setText(f"{shown} domain{'s' if shown != 1 else ''}")

    def _on_zone_selected(self, current, _previous):
        if current is None:
            self._current_domain = None
            self._clear()
            self._status_label.setText("Select a domain")
            return
        domain = current.text()
        if domain == self._current_domain:
            return
        self._current_domain = domain
        self._fetch_keys(domain)

    # ── API fetch (no caching) ──────────────────────────────────────────

    def _fetch_keys(self, domain):
        self._clear()
        self._status_label.setText("Loading...")

        if self._api_queue:
            from api_queue import QueueItem, PRIORITY_NORMAL

            def _done(ok, data):
                if domain != self._current_domain:
                    return
                if ok:
                    self._keys = data.get("keys", [])
                    self._render(domain)
                else:
                    self._status_label.setText("Failed to load")
                    self.log_message.emit(
                        f"DNSSEC fetch failed for {domain}: {data}", "error"
                    )
                    InfoBar.error(
                        title="DNSSEC Fetch Failed",
                        content=f"Could not load DNSSEC keys for {domain}.",
                        parent=self.window(),
                        duration=8000,
                        position=InfoBarPosition.TOP,
                    )

            self._api_queue.enqueue(QueueItem(
                priority=PRIORITY_NORMAL, category="dnssec",
                action=f"DNSSEC keys for {domain}",
                callable=self._api.get_zone, args=(domain,),
                callback=_done,
            ))
        else:
            ok, data = self._api.get_zone(domain)
            if ok:
                self._keys = data.get("keys", [])
                self._render(domain)
            else:
                self._status_label.setText("Failed to load")
                InfoBar.error(
                    title="DNSSEC Fetch Failed",
                    content=f"Could not load DNSSEC keys for {domain}.",
                    parent=self.window(),
                    duration=8000,
                    position=InfoBarPosition.TOP,
                )

    # ── Layout helpers ──────────────────────────────────────────────────

    def _clear(self):
        while self._clay.count() > 1:
            item = self._clay.takeAt(0)
            if w := item.widget():
                w.deleteLater()

    def _ins(self, widget):
        """Insert a widget above the bottom stretch."""
        self._clay.insertWidget(self._clay.count() - 1, widget)

    # ── Main render ─────────────────────────────────────────────────────

    def _render(self, domain):
        self._clear()

        if not self._keys:
            self._status_label.setText("No DNSSEC keys")
            lbl = CaptionLabel("No DNSSEC keys are published for this domain.")
            lbl.setWordWrap(True)
            self._ins(lbl)
            return

        n = len(self._keys)
        self._status_label.setText(f"{n} key{'s' if n != 1 else ''}")

        intro = QtWidgets.QLabel(
            "You also need to forward the following DNSSEC information to your domain provider. "
            "The exact steps depend on your provider: You may have to enter the information as a "
            "block in either <b>DS format</b> or <b>DNSKEY format</b>, or as <b>individual values</b>."
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        self._ins(intro)

        note = CaptionLabel(
            "Note: When using block format, some providers require you to add the domain name "
            "in the beginning. Depending on your domain's suffix, deSEC may perform this step automatically."
        )
        note.setWordWrap(True)
        self._ins(note)

        for idx, key_obj in enumerate(self._keys):
            self._build_ds_card(key_obj, idx)
            self._build_dnskey_card(key_obj, idx)

        # Validate buttons
        check = QtWidgets.QWidget()
        check_lay = QtWidgets.QHBoxLayout(check)
        check_lay.setContentsMargins(0, 4, 0, 0)
        check_lay.setSpacing(8)
        check_lay.addWidget(CaptionLabel("Validate DNSSEC setup:"))

        verisign_btn = PushButton("Verisign Debugger")
        verisign_btn.clicked.connect(
            lambda _=False, d=domain: QtGui.QDesktopServices.openUrl(
                QtCore.QUrl(f"https://dnssec-analyzer.verisignlabs.com/{d}")
            )
        )
        check_lay.addWidget(verisign_btn)

        dnsviz_btn = PushButton("DNSViz")
        dnsviz_btn.clicked.connect(
            lambda _=False, d=domain: QtGui.QDesktopServices.openUrl(
                QtCore.QUrl(f"https://dnsviz.net/d/{d}/dnssec/")
            )
        )
        check_lay.addWidget(dnsviz_btn)
        check_lay.addStretch()

        self._ins(check)

        # ── Migration warning (collapsible) ────────────────────────────
        warning = _CollapsibleWarning(
            "Moving a domain that had DNSSEC enabled before? Read this!",
            '<b>Be careful!</b> Simply replacing records can cause errors, '
            'because resolvers may have old NS or DNSSEC settings cached. '
            'To prevent this, choose one of the following:'
            '<ul style="margin-top: 6px; margin-bottom: 0;">'
            '<li>Keep DNSSEC enabled throughout: please contact support to '
            'configure a temporary &quot;multi-signer&quot; setup '
            '(RFC 8901).</li>'
            '<li>Temporarily &quot;go insecure&quot; (easier): turn off old '
            'DNSSEC, wait 24h, change NS records, wait 24h, re-enable '
            'DNSSEC.</li>'
            '</ul>',
        )
        self._ins(warning)

    # ── DS card ─────────────────────────────────────────────────────────

    def _build_ds_card(self, key_obj, idx):
        ds_list = key_obj.get("ds") or []
        if not ds_list:
            return

        n_keys = idx  # used only for title when multiple keys exist
        title = "DS Format" if idx == 0 else f"DS Format (Key {idx + 1})"
        card, body = self._make_card(title, "\n".join(ds_list))

        for i, ds_str in enumerate(ds_list):
            parts = ds_str.split(None, 3)
            key_tag = algo = dtype = digest = ds_str
            if len(parts) == 4:
                key_tag, algo, dtype, digest = parts

            digest_name = _DIGEST_NAMES.get(dtype, f"Type {dtype}")

            if i > 0:
                body.addWidget(self._divider())

            # Section label when there are multiple digest variants
            if len(ds_list) > 1:
                lbl = QtWidgets.QLabel(digest_name)
                lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: rgba(150,150,150,0.9);")
                body.addWidget(lbl)

            grid = QtWidgets.QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(24)
            grid.setVerticalSpacing(2)

            for col, (lbl_text, val, note) in enumerate([
                ("Key Tag",     key_tag, ""),
                ("Algorithm",   algo,    _ALGO_NAMES.get(algo, "")),
                ("Digest Type", dtype,   digest_name),
            ]):
                grid.addWidget(CaptionLabel(lbl_text), 0, col)
                grid.addWidget(self._long_field(val), 1, col)
                if note:
                    grid.addWidget(self._note_label(note), 2, col)

            body.addLayout(grid)

            body.addWidget(CaptionLabel("Digest"))
            body.addWidget(self._long_field(digest))

        self._ins(card)

    # ── DNSKEY card ─────────────────────────────────────────────────────

    def _build_dnskey_card(self, key_obj, idx):
        dk = key_obj.get("dnskey")
        if not dk:
            return

        dk_list = dk if isinstance(dk, list) else [dk]

        title = "DNSKEY Format" if idx == 0 else f"DNSKEY Format (Key {idx + 1})"
        card, body = self._make_card(title, "\n".join(dk_list))

        for i, dk_str in enumerate(dk_list):
            parts = dk_str.split(None, 3)
            flags = proto = algo = pubkey = dk_str
            if len(parts) == 4:
                flags, proto, algo, pubkey = parts

            key_type = _FLAG_NAMES.get(flags, f"Flags {flags}")

            if i > 0:
                body.addWidget(self._divider())

            if len(dk_list) > 1:
                lbl = QtWidgets.QLabel(key_type)
                lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: rgba(150,150,150,0.9);")
                body.addWidget(lbl)

            grid = QtWidgets.QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(24)
            grid.setVerticalSpacing(2)

            for col, (lbl_text, val, note) in enumerate([
                ("Flags",     flags, key_type),
                ("Protocol",  proto, ""),
                ("Algorithm", algo,  _ALGO_NAMES.get(algo, "")),
            ]):
                grid.addWidget(CaptionLabel(lbl_text), 0, col)
                grid.addWidget(self._long_field(val), 1, col)
                if note:
                    grid.addWidget(self._note_label(note), 2, col)

            body.addLayout(grid)

            body.addWidget(CaptionLabel("Public Key"))
            body.addWidget(self._long_field(pubkey))

        self._ins(card)

    # ── Card factory ────────────────────────────────────────────────────

    def _make_card(self, title, full_record):
        """
        Return (card_frame, body_layout).
        card_frame uses specific objectName so its QSS doesn't bleed to children.
        """
        c = self._theme_colors()

        card = QtWidgets.QFrame()
        card.setObjectName("dnssecCard")
        card.setStyleSheet(
            f"QFrame#dnssecCard {{"
            f"  background: {c['card_bg']};"
            f"  border: 1px solid {c['card_border']};"
            f"  border-radius: 6px;"
            f"}}"
        )
        card_lay = QtWidgets.QVBoxLayout(card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)

        # Header bar
        hdr = QtWidgets.QFrame()
        hdr.setObjectName("dnssecHdr")
        hdr.setStyleSheet(
            f"QFrame#dnssecHdr {{"
            f"  background: {c['hdr_bg']};"
            f"  border: none;"
            f"  border-bottom: 1px solid {c['div']};"
            f"  border-top-left-radius: 6px;"
            f"  border-top-right-radius: 6px;"
            f"}}"
        )
        hdr_lay = QtWidgets.QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(12, 8, 12, 8)
        hdr_lay.setSpacing(8)
        hdr_lay.addWidget(StrongBodyLabel(title))
        hdr_lay.addStretch()

        copy_btn = PushButton("Copy")
        copy_btn.setFixedWidth(80)
        copy_btn.clicked.connect(
            lambda _=False, t=full_record:
                QtWidgets.QApplication.clipboard().setText(t)
        )
        hdr_lay.addWidget(copy_btn)
        card_lay.addWidget(hdr)

        # Body
        body_widget = QtWidgets.QWidget()
        body_widget.setObjectName("dnssecBody")
        body_widget.setStyleSheet(
            "QWidget#dnssecBody { background: transparent; }"
        )
        body_lay = QtWidgets.QVBoxLayout(body_widget)
        body_lay.setContentsMargins(12, 10, 12, 12)
        body_lay.setSpacing(8)
        card_lay.addWidget(body_widget)

        return card, body_lay

    # ── Small widget factories ──────────────────────────────────────────

    @staticmethod
    def _note_label(text):
        """Small grey annotation below a value."""
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet("font-size: 10px; color: rgba(150,150,150,0.85);")
        return lbl

    @staticmethod
    def _long_field(text):
        """Full-width read-only monospace LineEdit — selects all on click."""
        edit = LineEdit()
        edit.setReadOnly(True)
        edit.setText(text)
        edit.setCursorPosition(0)
        edit.setFont(QtGui.QFont("monospace", 10))
        edit.mousePressEvent = lambda e, ed=edit: (
            QtWidgets.QLineEdit.mousePressEvent(ed, e),
            ed.selectAll(),
        )
        return edit

    @staticmethod
    def _divider():
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        line.setStyleSheet("color: rgba(128,128,128,0.18);")
        return line
