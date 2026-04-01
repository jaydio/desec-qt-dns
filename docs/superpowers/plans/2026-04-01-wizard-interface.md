# DNS Record Wizard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a step-by-step wizard sidebar page that creates DNS records across multiple domains, supporting both curated preset templates and custom user-defined record sets with variable substitution.

**Architecture:** Two new files — `wizard_templates.py` (pure data, all preset templates as dicts) and `wizard_interface.py` (sidebar page with 7-step QStackedWidget wizard). Integration via one modification to `main_window.py` to register the sidebar page and wire signals. All record mutations flow through the existing `APIQueue`. Conflict detection uses cached records.

**Tech Stack:** Python 3, PySide6, PySide6-FluentWidgets, existing `api_client`/`api_queue`/`cache_manager`/`version_manager` infrastructure.

**Spec:** `docs/superpowers/specs/2026-04-01-wizard-interface-design.md`

**Testing:** This project has no automated test suite. Each task includes manual verification steps (run the app, navigate to the wizard, check behavior). Run with `python src/main.py` from the project root (requires venv with requirements.txt).

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/wizard_templates.py` | **Create** | Pure data module. `TEMPLATES` list of dicts and `CATEGORIES` ordered list. No UI code, no imports beyond stdlib. |
| `src/wizard_interface.py` | **Create** | Sidebar page. `WizardInterface(QWidget)` with `QStackedWidget` holding 7 private step widgets. Navigation bar, variable resolution, conflict detection, execution logic. |
| `src/main_window.py` | **Modify** | Import `WizardInterface`, instantiate it, register with `addSubInterface`, wire `log_message` and `records_changed` signals. |

---

## Task 1: Create Template Data Module

**Files:**
- Create: `src/wizard_templates.py`

This is a pure data module — no UI, no complex logic. It defines all preset templates used by the wizard.

- [ ] **Step 1: Create `src/wizard_templates.py` with template structure and all presets**

```python
"""
DNS Record Wizard — preset templates.

Each template is a plain dict with:
  id          Unique slug
  name        Display name
  description One-line summary
  category    Grouping key (must appear in CATEGORIES)
  variables   Dict of {var_name: {label, hint, default, required}}
  records     List of {type, subname, ttl, content} — may contain {variables}

Reserved variables (auto-handled by the wizard, never in `variables` dict):
  {domain}             Auto-populated per target domain
  {subdomain_prefix}   Optional prefix prepended to all subnames
"""

CATEGORIES = [
    "Email",
    "Chat / Social",
    "Web",
    "Security",
    "ACME / Certificates",
    "Verification",
]

TEMPLATES = [
    # ── Email ──────────────────────────────────────────────────────────
    {
        "id": "google-workspace",
        "name": "Google Workspace",
        "description": "MX, SPF, DKIM, and DMARC records for Google Workspace email",
        "category": "Email",
        "variables": {
            "dkim_selector": {
                "label": "DKIM Selector",
                "hint": "Usually 'google' — found in Google Admin Console",
                "default": "google",
                "required": True,
            },
        },
        "records": [
            {"type": "MX", "subname": "", "ttl": 3600,
             "content": "1 aspmx.l.google.com."},
            {"type": "MX", "subname": "", "ttl": 3600,
             "content": "5 alt1.aspmx.l.google.com."},
            {"type": "MX", "subname": "", "ttl": 3600,
             "content": "5 alt2.aspmx.l.google.com."},
            {"type": "MX", "subname": "", "ttl": 3600,
             "content": "10 alt3.aspmx.l.google.com."},
            {"type": "MX", "subname": "", "ttl": 3600,
             "content": "10 alt4.aspmx.l.google.com."},
            {"type": "TXT", "subname": "", "ttl": 3600,
             "content": "\"v=spf1 include:_spf.google.com ~all\""},
            {"type": "TXT", "subname": "_dmarc", "ttl": 3600,
             "content": "\"v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}\""},
            {"type": "CNAME", "subname": "{dkim_selector}._domainkey", "ttl": 3600,
             "content": "{dkim_selector}.domainkey.{domain}."},
        ],
    },
    {
        "id": "microsoft-365",
        "name": "Microsoft 365",
        "description": "MX, SPF, Autodiscover, and DMARC for Microsoft 365",
        "category": "Email",
        "variables": {},
        "records": [
            {"type": "MX", "subname": "", "ttl": 3600,
             "content": "0 {domain}.mail.protection.outlook.com."},
            {"type": "TXT", "subname": "", "ttl": 3600,
             "content": "\"v=spf1 include:spf.protection.outlook.com ~all\""},
            {"type": "CNAME", "subname": "autodiscover", "ttl": 3600,
             "content": "autodiscover.outlook.com."},
            {"type": "TXT", "subname": "_dmarc", "ttl": 3600,
             "content": "\"v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}\""},
        ],
    },
    {
        "id": "fastmail",
        "name": "Fastmail",
        "description": "MX, SPF, DKIM, and DMARC records for Fastmail",
        "category": "Email",
        "variables": {},
        "records": [
            {"type": "MX", "subname": "", "ttl": 3600,
             "content": "10 in1-smtp.messagingengine.com."},
            {"type": "MX", "subname": "", "ttl": 3600,
             "content": "20 in2-smtp.messagingengine.com."},
            {"type": "TXT", "subname": "", "ttl": 3600,
             "content": "\"v=spf1 include:spf.messagingengine.com ~all\""},
            {"type": "CNAME", "subname": "fm1._domainkey", "ttl": 3600,
             "content": "fm1.{domain}.dkim.fmhosted.com."},
            {"type": "CNAME", "subname": "fm2._domainkey", "ttl": 3600,
             "content": "fm2.{domain}.dkim.fmhosted.com."},
            {"type": "CNAME", "subname": "fm3._domainkey", "ttl": 3600,
             "content": "fm3.{domain}.dkim.fmhosted.com."},
            {"type": "TXT", "subname": "_dmarc", "ttl": 3600,
             "content": "\"v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}\""},
        ],
    },
    {
        "id": "proton-mail",
        "name": "Proton Mail",
        "description": "MX, SPF, DKIM, and DMARC records for Proton Mail",
        "category": "Email",
        "variables": {
            "proton_verify": {
                "label": "Proton Verification Code",
                "hint": "Found in Proton Mail Settings → Custom domain",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "MX", "subname": "", "ttl": 3600,
             "content": "10 mail.protonmail.ch."},
            {"type": "MX", "subname": "", "ttl": 3600,
             "content": "20 mailsec.protonmail.ch."},
            {"type": "TXT", "subname": "", "ttl": 3600,
             "content": "\"v=spf1 include:_spf.protonmail.ch ~all\""},
            {"type": "TXT", "subname": "", "ttl": 3600,
             "content": "\"protonmail-verification={proton_verify}\""},
            {"type": "CNAME", "subname": "protonmail._domainkey", "ttl": 3600,
             "content": "protonmail.domainkey.{proton_verify}.domains.proton.ch."},
            {"type": "CNAME", "subname": "protonmail2._domainkey", "ttl": 3600,
             "content": "protonmail2.domainkey.{proton_verify}.domains.proton.ch."},
            {"type": "CNAME", "subname": "protonmail3._domainkey", "ttl": 3600,
             "content": "protonmail3.domainkey.{proton_verify}.domains.proton.ch."},
            {"type": "TXT", "subname": "_dmarc", "ttl": 3600,
             "content": "\"v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}\""},
        ],
    },
    {
        "id": "basic-email",
        "name": "Basic MX + SPF + DMARC",
        "description": "Minimal email setup with custom mail server",
        "category": "Email",
        "variables": {
            "mail_server": {
                "label": "Mail Server Hostname",
                "hint": "e.g. mail.example.com. (include trailing dot)",
                "default": "",
                "required": True,
            },
            "mx_priority": {
                "label": "MX Priority",
                "hint": "Usually 10",
                "default": "10",
                "required": True,
            },
        },
        "records": [
            {"type": "MX", "subname": "", "ttl": 3600,
             "content": "{mx_priority} {mail_server}"},
            {"type": "TXT", "subname": "", "ttl": 3600,
             "content": "\"v=spf1 mx ~all\""},
            {"type": "TXT", "subname": "_dmarc", "ttl": 3600,
             "content": "\"v=DMARC1; p=none; rua=mailto:postmaster@{domain}\""},
        ],
    },

    # ── Chat / Social ──────────────────────────────────────────────────
    {
        "id": "matrix-synapse",
        "name": "Matrix (Synapse)",
        "description": "SRV and well-known delegation for Matrix/Synapse homeserver",
        "category": "Chat / Social",
        "variables": {
            "matrix_server": {
                "label": "Matrix Server Hostname",
                "hint": "e.g. matrix.example.com. (include trailing dot)",
                "default": "",
                "required": True,
            },
            "matrix_port": {
                "label": "Federation Port",
                "hint": "Usually 8448",
                "default": "8448",
                "required": True,
            },
        },
        "records": [
            {"type": "SRV", "subname": "_matrix._tcp", "ttl": 3600,
             "content": "10 0 {matrix_port} {matrix_server}"},
            {"type": "SRV", "subname": "_matrix-fed._tcp", "ttl": 3600,
             "content": "10 0 {matrix_port} {matrix_server}"},
        ],
    },
    {
        "id": "xmpp-jabber",
        "name": "XMPP / Jabber",
        "description": "SRV records for XMPP client and server-to-server federation",
        "category": "Chat / Social",
        "variables": {
            "xmpp_server": {
                "label": "XMPP Server Hostname",
                "hint": "e.g. xmpp.example.com. (include trailing dot)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "SRV", "subname": "_xmpp-client._tcp", "ttl": 3600,
             "content": "5 0 5222 {xmpp_server}"},
            {"type": "SRV", "subname": "_xmpp-server._tcp", "ttl": 3600,
             "content": "5 0 5269 {xmpp_server}"},
        ],
    },

    # ── Web ────────────────────────────────────────────────────────────
    {
        "id": "letsencrypt-caa",
        "name": "Let's Encrypt CAA",
        "description": "CAA record restricting certificate issuance to Let's Encrypt",
        "category": "Web",
        "variables": {},
        "records": [
            {"type": "CAA", "subname": "", "ttl": 3600,
             "content": '0 issue "letsencrypt.org"'},
            {"type": "CAA", "subname": "", "ttl": 3600,
             "content": '0 issuewild "letsencrypt.org"'},
        ],
    },
    {
        "id": "web-hosting-redirect",
        "name": "Web Hosting CNAME",
        "description": "CNAME pointing www and apex to a hosting provider",
        "category": "Web",
        "variables": {
            "hosting_target": {
                "label": "Hosting Target",
                "hint": "e.g. mysite.netlify.app. or mysite.github.io. (trailing dot)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "CNAME", "subname": "www", "ttl": 3600,
             "content": "{hosting_target}"},
        ],
    },

    # ── Security ───────────────────────────────────────────────────────
    {
        "id": "dmarc-standalone",
        "name": "DMARC Policy",
        "description": "DMARC TXT record with configurable policy and reporting",
        "category": "Security",
        "variables": {
            "dmarc_policy": {
                "label": "DMARC Policy",
                "hint": "'none' (monitor), 'quarantine', or 'reject'",
                "default": "quarantine",
                "required": True,
            },
            "dmarc_rua": {
                "label": "Aggregate Report Email",
                "hint": "e.g. dmarc-reports@example.com",
                "default": "dmarc@{domain}",
                "required": True,
            },
        },
        "records": [
            {"type": "TXT", "subname": "_dmarc", "ttl": 3600,
             "content": "\"v=DMARC1; p={dmarc_policy}; rua=mailto:{dmarc_rua}\""},
        ],
    },
    {
        "id": "spf-standalone",
        "name": "SPF Record",
        "description": "SPF TXT record with configurable includes",
        "category": "Security",
        "variables": {
            "spf_includes": {
                "label": "SPF Includes",
                "hint": "Space-separated, e.g. '_spf.google.com _spf.example.com'",
                "default": "",
                "required": True,
            },
            "spf_policy": {
                "label": "SPF Policy Qualifier",
                "hint": "'~all' (softfail) or '-all' (hardfail)",
                "default": "~all",
                "required": True,
            },
        },
        "records": [
            {"type": "TXT", "subname": "", "ttl": 3600,
             "content": "\"v=spf1 {spf_includes} {spf_policy}\""},
        ],
    },
    {
        "id": "mta-sts",
        "name": "MTA-STS",
        "description": "MTA-STS TXT record for enforcing TLS on inbound mail",
        "category": "Security",
        "variables": {
            "mta_sts_id": {
                "label": "MTA-STS Policy ID",
                "hint": "Unique string, e.g. a timestamp like '20260401T000000'",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "TXT", "subname": "_mta-sts", "ttl": 3600,
             "content": "\"v=STSv1; id={mta_sts_id}\""},
        ],
    },
    {
        "id": "dane-tlsa",
        "name": "DANE / TLSA",
        "description": "TLSA record for DANE certificate pinning on SMTP",
        "category": "Security",
        "variables": {
            "tlsa_port": {
                "label": "Port",
                "hint": "Usually 25 for SMTP, 443 for HTTPS",
                "default": "25",
                "required": True,
            },
            "tlsa_usage": {
                "label": "Usage Field",
                "hint": "3 = DANE-EE (most common for SMTP)",
                "default": "3",
                "required": True,
            },
            "tlsa_selector": {
                "label": "Selector Field",
                "hint": "1 = SubjectPublicKeyInfo",
                "default": "1",
                "required": True,
            },
            "tlsa_matching": {
                "label": "Matching Type",
                "hint": "1 = SHA-256",
                "default": "1",
                "required": True,
            },
            "tlsa_hash": {
                "label": "Certificate Hash",
                "hint": "SHA-256 hash of the certificate or public key",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "TLSA", "subname": "_{tlsa_port}._tcp", "ttl": 3600,
             "content": "{tlsa_usage} {tlsa_selector} {tlsa_matching} {tlsa_hash}"},
        ],
    },

    # ── ACME / Certificates ────────────────────────────────────────────
    {
        "id": "dns01-challenge",
        "name": "DNS-01 Challenge (TXT)",
        "description": "TXT record for ACME DNS-01 certificate validation",
        "category": "ACME / Certificates",
        "variables": {
            "acme_token": {
                "label": "Challenge Token",
                "hint": "Base64url value from your ACME client (certbot, acme.sh, etc.)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "TXT", "subname": "_acme-challenge", "ttl": 60,
             "content": "\"{acme_token}\""},
        ],
    },
    {
        "id": "dns01-cname-delegation",
        "name": "DNS-01 CNAME Delegation",
        "description": "Delegate ACME DNS-01 validation to an external domain",
        "category": "ACME / Certificates",
        "variables": {
            "validation_domain": {
                "label": "Validation Domain",
                "hint": "e.g. _acme-challenge.example.com.acme-dns.example.org. (trailing dot)",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "CNAME", "subname": "_acme-challenge", "ttl": 3600,
             "content": "{validation_domain}"},
        ],
    },
    {
        "id": "caa-acme-account",
        "name": "CAA with ACME Account Binding",
        "description": "CAA record restricting issuance to a specific CA and account",
        "category": "ACME / Certificates",
        "variables": {
            "ca_domain": {
                "label": "CA Domain",
                "hint": "e.g. letsencrypt.org",
                "default": "letsencrypt.org",
                "required": True,
            },
            "account_uri": {
                "label": "ACME Account URI",
                "hint": "e.g. https://acme-v02.api.letsencrypt.org/acme/acct/123456",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "CAA", "subname": "", "ttl": 3600,
             "content": '0 issue "{ca_domain}; accounturi={account_uri}"'},
        ],
    },

    # ── Verification ───────────────────────────────────────────────────
    {
        "id": "google-site-verification",
        "name": "Google Site Verification",
        "description": "TXT record for verifying domain ownership with Google",
        "category": "Verification",
        "variables": {
            "google_verify_code": {
                "label": "Verification Code",
                "hint": "The full google-site-verification=... string from Google Search Console",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "TXT", "subname": "", "ttl": 3600,
             "content": "\"{google_verify_code}\""},
        ],
    },
    {
        "id": "facebook-domain-verification",
        "name": "Facebook Domain Verification",
        "description": "TXT record for verifying domain ownership with Facebook",
        "category": "Verification",
        "variables": {
            "fb_verify_code": {
                "label": "Verification Code",
                "hint": "The full facebook-domain-verification=... string from Meta Business Suite",
                "default": "",
                "required": True,
            },
        },
        "records": [
            {"type": "TXT", "subname": "", "ttl": 3600,
             "content": "\"{fb_verify_code}\""},
        ],
    },
]
```

- [ ] **Step 2: Verify the module imports cleanly**

Run: `cd /home/neoplex/Desktop/scm-autocoder/desec-qt-dns && python -c "from src.wizard_templates import TEMPLATES, CATEGORIES; print(f'{len(TEMPLATES)} templates in {len(CATEGORIES)} categories')"`

Expected: `19 templates in 6 categories` (adjust count if templates were added/removed)

- [ ] **Step 3: Commit**

```bash
git add src/wizard_templates.py
git commit -m "feat(wizard): add preset template data module

Define 19 DNS record templates across 6 categories (Email, Chat,
Web, Security, ACME, Verification) for the wizard feature."
```

---

## Task 2: Wizard Interface Scaffold + Navigation

**Files:**
- Create: `src/wizard_interface.py`

Create the main `WizardInterface` class with `QStackedWidget`, Back/Next/Execute navigation bar, and placeholder widgets for all 7 steps. This establishes the skeleton that subsequent tasks fill in.

- [ ] **Step 1: Create `src/wizard_interface.py` with scaffold**

```python
"""
DNS Record Wizard sidebar page.

Step-by-step wizard for creating DNS records across multiple domains,
using preset templates or custom record definitions with variable
substitution.
"""

import logging
import re

from PySide6 import QtWidgets, QtCore
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

logger = logging.getLogger(__name__)

# Step indices
_STEP_MODE = 0
_STEP_TEMPLATE = 1
_STEP_VARIABLES = 2
_STEP_DOMAINS = 3
_STEP_CONFLICT = 4
_STEP_PREVIEW = 5
_STEP_EXECUTE = 6

_STEP_TITLES = [
    "Choose Mode",
    "Select Template",
    "Fill In Variables",
    "Select Domains",
    "Conflict Strategy",
    "Preview",
    "Execution",
]


class WizardInterface(QtWidgets.QWidget):
    """Sidebar page — DNS record creation wizard."""

    log_message = Signal(str, str)
    records_changed = Signal()

    def __init__(self, api_client, cache_manager, api_queue=None,
                 version_manager=None, parent=None):
        super().__init__(parent)
        self.setObjectName("wizardInterface")
        self._api = api_client
        self._cache = cache_manager
        self._api_queue = api_queue
        self._version_manager = version_manager

        # Wizard state
        self._mode = None          # "preset" or "custom"
        self._template = None      # selected template dict
        self._custom_records = []   # list of record dicts for custom mode
        self._variables = {}        # {var_name: value}
        self._selected_domains = [] # list of domain name strings
        self._conflict_strategy = "merge"
        self._preview_rows = []     # resolved records for preview
        self._execution_items = []  # QueueItem ids for tracking

        self._setup_ui()

    # ── UI setup ───────────────────────────────────────────────────────

    def _setup_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(0)

        # Title row
        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 8)
        self._title_label = StrongBodyLabel("DNS Record Wizard")
        title_row.addWidget(self._title_label)
        title_row.addStretch()
        self._step_label = CaptionLabel("Step 1 of 7")
        title_row.addWidget(self._step_label)
        outer.addLayout(title_row)

        # Stacked widget for steps
        self._stack = QtWidgets.QStackedWidget()
        outer.addWidget(self._stack, 1)

        # Build step widgets
        self._step_mode = self._build_step_mode()
        self._step_template = self._build_step_template()
        self._step_variables = self._build_step_variables()
        self._step_domains = self._build_step_domains()
        self._step_conflict = self._build_step_conflict()
        self._step_preview = self._build_step_preview()
        self._step_execute = self._build_step_execute()

        self._stack.addWidget(self._step_mode)
        self._stack.addWidget(self._step_template)
        self._stack.addWidget(self._step_variables)
        self._stack.addWidget(self._step_domains)
        self._stack.addWidget(self._step_conflict)
        self._stack.addWidget(self._step_preview)
        self._stack.addWidget(self._step_execute)

        # Navigation bar
        nav = QtWidgets.QHBoxLayout()
        nav.setContentsMargins(0, 12, 0, 0)
        nav.setSpacing(8)

        self._btn_start_over = PushButton("Start Over")
        self._btn_start_over.clicked.connect(self._reset)
        self._btn_start_over.setVisible(False)
        nav.addWidget(self._btn_start_over)

        nav.addStretch()

        self._btn_back = PushButton("Back")
        self._btn_back.clicked.connect(self._go_back)
        nav.addWidget(self._btn_back)

        self._btn_next = PrimaryPushButton("Next")
        self._btn_next.clicked.connect(self._go_next)
        nav.addWidget(self._btn_next)

        outer.addLayout(nav)

        # Initial state
        self._go_to_step(_STEP_MODE)

    # ── Navigation ─────────────────────────────────────────────────────

    def _go_to_step(self, idx):
        self._stack.setCurrentIndex(idx)
        self._step_label.setText(f"Step {idx + 1} of 7 — {_STEP_TITLES[idx]}")

        self._btn_back.setVisible(idx > _STEP_MODE)
        self._btn_back.setEnabled(idx < _STEP_EXECUTE)
        self._btn_start_over.setVisible(idx == _STEP_EXECUTE)

        if idx == _STEP_PREVIEW:
            self._btn_next.setText("Execute")
        elif idx == _STEP_EXECUTE:
            self._btn_next.setVisible(False)
        else:
            self._btn_next.setText("Next")
            self._btn_next.setVisible(True)

        # Run step entry hooks
        if idx == _STEP_TEMPLATE:
            self._on_enter_template_step()
        elif idx == _STEP_VARIABLES:
            self._on_enter_variables_step()
        elif idx == _STEP_DOMAINS:
            self._on_enter_domains_step()
        elif idx == _STEP_PREVIEW:
            self._on_enter_preview_step()

        self._validate_current_step()

    def _go_next(self):
        current = self._stack.currentIndex()
        if not self._validate_current_step():
            return
        if current == _STEP_PREVIEW:
            self._execute()
            self._go_to_step(_STEP_EXECUTE)
        elif current < _STEP_EXECUTE:
            self._go_to_step(current + 1)

    def _go_back(self):
        current = self._stack.currentIndex()
        if current > _STEP_MODE:
            self._go_to_step(current - 1)

    def _reset(self):
        self._mode = None
        self._template = None
        self._custom_records = []
        self._variables = {}
        self._selected_domains = []
        self._conflict_strategy = "merge"
        self._preview_rows = []
        self._execution_items = []
        self._go_to_step(_STEP_MODE)

    def _validate_current_step(self):
        """Validate current step and enable/disable Next. Returns True if valid."""
        idx = self._stack.currentIndex()
        valid = True
        if idx == _STEP_MODE:
            valid = self._mode is not None
        elif idx == _STEP_TEMPLATE:
            valid = self._validate_template_step()
        elif idx == _STEP_VARIABLES:
            valid = self._validate_variables_step()
        elif idx == _STEP_DOMAINS:
            valid = len(self._selected_domains) > 0
        elif idx == _STEP_CONFLICT:
            valid = True  # always valid, has a default
        elif idx == _STEP_PREVIEW:
            valid = len(self._preview_rows) > 0
        self._btn_next.setEnabled(valid)
        return valid

    # ── Theme ──────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self.setStyleSheet(container_qss())

    # ── Step builders (placeholders — filled in by subsequent tasks) ───

    def _build_step_mode(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(CaptionLabel("Step 1: Choose Mode — placeholder"))
        lay.addStretch()
        return w

    def _build_step_template(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(CaptionLabel("Step 2: Template — placeholder"))
        lay.addStretch()
        return w

    def _build_step_variables(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(CaptionLabel("Step 3: Variables — placeholder"))
        lay.addStretch()
        return w

    def _build_step_domains(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(CaptionLabel("Step 4: Domains — placeholder"))
        lay.addStretch()
        return w

    def _build_step_conflict(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(CaptionLabel("Step 5: Conflict Strategy — placeholder"))
        lay.addStretch()
        return w

    def _build_step_preview(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(CaptionLabel("Step 6: Preview — placeholder"))
        lay.addStretch()
        return w

    def _build_step_execute(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(CaptionLabel("Step 7: Execute — placeholder"))
        lay.addStretch()
        return w

    # ── Step entry hooks (placeholders) ────────────────────────────────

    def _on_enter_template_step(self):
        pass

    def _on_enter_variables_step(self):
        pass

    def _on_enter_domains_step(self):
        pass

    def _on_enter_preview_step(self):
        pass

    # ── Validation hooks (placeholders) ────────────────────────────────

    def _validate_template_step(self):
        return self._template is not None or len(self._custom_records) > 0

    def _validate_variables_step(self):
        return True

    # ── Execution (placeholder) ────────────────────────────────────────

    def _execute(self):
        pass
```

- [ ] **Step 2: Verify syntax**

Run: `cd /home/neoplex/Desktop/scm-autocoder/desec-qt-dns && python -m py_compile src/wizard_interface.py && echo OK`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/wizard_interface.py
git commit -m "feat(wizard): scaffold WizardInterface with QStackedWidget navigation

7-step wizard skeleton with Back/Next/Execute nav, step validation
hooks, and placeholder step widgets. Ready for step implementations."
```

---

## Task 3: Main Window Integration

**Files:**
- Modify: `src/main_window.py`

Register the wizard as a sidebar page, wire signals.

- [ ] **Step 1: Add import**

At the top of `main_window.py`, after the existing `from dnssec_interface import DnssecInterface` line (around line 45), add:

```python
from wizard_interface import WizardInterface
```

- [ ] **Step 2: Instantiate WizardInterface**

In the `setup_ui()` method, after the `self.dnssec_interface` block (after the `self.dnssec_interface.log_message.connect(self.log_message)` line), add:

```python
self.wizard_interface = WizardInterface(
    self.api_client, self.cache_manager,
    api_queue=self.api_queue, version_manager=self.version_manager,
)
self.wizard_interface.log_message.connect(self.log_message)
self.wizard_interface.records_changed.connect(self.on_records_changed)
```

- [ ] **Step 3: Register in sidebar**

In the `addSubInterface` block, after the `self.addSubInterface(self.search_replace_interface, FluentIcon.SEARCH, "Search")` line, add:

```python
self.addSubInterface(self.wizard_interface, FluentIcon.BOOK_SHELF, "Wizard")
```

- [ ] **Step 4: Verify app launches**

Run: `cd /home/neoplex/Desktop/scm-autocoder/desec-qt-dns && python src/main.py`

Expected: App launches, "Wizard" appears in the sidebar after "Search". Clicking it shows the placeholder step 1 content. Back/Next buttons work (Next disabled since no mode selected).

- [ ] **Step 5: Commit**

```bash
git add src/main_window.py
git commit -m "feat(wizard): register WizardInterface in sidebar navigation

Add Wizard page after Search with BOOK_SHELF icon, wire log_message
and records_changed signals."
```

---

## Task 4: Step 1 — Mode Selection

**Files:**
- Modify: `src/wizard_interface.py`

Replace the `_build_step_mode` placeholder with two large clickable radio cards.

- [ ] **Step 1: Replace `_build_step_mode` method**

Replace the existing `_build_step_mode` method with:

```python
def _build_step_mode(self):
    w = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(w)
    lay.setContentsMargins(0, 8, 0, 0)
    lay.setSpacing(16)

    lay.addWidget(StrongBodyLabel("What would you like to do?"))
    lay.addWidget(CaptionLabel(
        "Choose a preset for common services, or create a custom record set."
    ))

    # Preset card
    self._card_preset = self._make_mode_card(
        "Use a Preset",
        "Choose from curated templates for Google Workspace, Microsoft 365, "
        "Matrix, ACME DNS-01, and more. Each template includes all required "
        "DNS records with guided variable input.",
    )
    self._card_preset.mousePressEvent = lambda e: self._select_mode("preset")
    lay.addWidget(self._card_preset)

    # Custom card
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
    """Create a clickable card frame for mode selection."""
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
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile src/wizard_interface.py && echo OK`

Expected: `OK`

- [ ] **Step 3: Manual test**

Run the app: `python src/main.py`

Expected: Wizard step 1 shows two cards. Clicking one highlights it with a blue border, clicking the other switches the highlight. Next button enables when a card is selected.

- [ ] **Step 4: Commit**

```bash
git add src/wizard_interface.py
git commit -m "feat(wizard): implement step 1 — mode selection cards

Clickable Preset/Custom cards with blue highlight on selection.
Next button enables when a mode is chosen."
```

---

## Task 5: Step 2 — Template Selection (Preset Path)

**Files:**
- Modify: `src/wizard_interface.py`

Replace `_build_step_template` placeholder. This step has two views depending on mode: a template picker list for preset, or a record builder table for custom. This task implements the preset path.

- [ ] **Step 1: Add template import at top of file**

After the existing `from api_queue import ...` line, add:

```python
from wizard_templates import TEMPLATES, CATEGORIES
```

- [ ] **Step 2: Replace `_build_step_template` and add `_on_enter_template_step`**

Replace the `_build_step_template` method with:

```python
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

def _on_enter_template_step(self):
    if self._mode == "preset":
        self._template_stack.setCurrentIndex(0)
        self._populate_template_list()
    else:
        self._template_stack.setCurrentIndex(1)

def _populate_template_list(self):
    self._template_list.clear()
    self._template_search.clear()
    for cat in CATEGORIES:
        # Category header (non-selectable)
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
            # Category header — hide if no children visible
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
        # Category header clicked
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
```

- [ ] **Step 3: Add a placeholder `_build_custom_builder`**

Add this method (the full custom builder is implemented in Task 6):

```python
def _build_custom_builder(self):
    """Custom record builder — placeholder, implemented in Task 6."""
    w = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(w)
    lay.addWidget(StrongBodyLabel("Custom Record Builder"))
    lay.addWidget(CaptionLabel("Build your own record set — placeholder"))
    lay.addStretch()
    return w
```

- [ ] **Step 4: Verify syntax and test**

Run: `python -m py_compile src/wizard_interface.py && echo OK`

Manual test: Select "Use a Preset" → Next → template list appears grouped by category. Select a template → preview table populates. Search filters the list.

- [ ] **Step 5: Commit**

```bash
git add src/wizard_interface.py
git commit -m "feat(wizard): implement step 2 — template selection with search and preview

Categorized template list, search filter, and read-only record
preview table. Custom builder placeholder included."
```

---

## Task 6: Step 2 — Custom Record Builder

**Files:**
- Modify: `src/wizard_interface.py`

Replace the `_build_custom_builder` placeholder with an editable record table.

- [ ] **Step 1: Replace `_build_custom_builder`**

```python
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

    # Toolbar
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

    # Record table
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

def _custom_add_row(self):
    row = self._custom_table.rowCount()
    self._custom_table.insertRow(row)

    # Type combo
    type_combo = ComboBox()
    for t in self._RECORD_TYPES:
        type_combo.addItem(t)
    type_combo.setCurrentIndex(0)
    self._custom_table.setCellWidget(row, 0, type_combo)

    # Subdomain
    sub_edit = LineEdit()
    sub_edit.setPlaceholderText("@ (apex)")
    self._custom_table.setCellWidget(row, 1, sub_edit)

    # TTL combo
    ttl_combo = ComboBox()
    for val, label in self._TTL_OPTIONS:
        ttl_combo.addItem(f"{label} ({val}s)")
    ttl_combo.setCurrentIndex(3)  # default 1 hour
    self._custom_table.setCellWidget(row, 2, ttl_combo)

    # Content
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
        # Also check for selected rows via selection model
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
        # Extract numeric TTL from "1 hour (3600s)" format
        ttl_match = re.search(r'\((\d+)s\)', ttl_text)
        ttl = int(ttl_match.group(1)) if ttl_match else 3600
        records.append({
            "type": type_combo.currentText(),
            "subname": sub_edit.text().strip() if sub_edit else "",
            "ttl": ttl,
            "content": content,
        })
    return records
```

- [ ] **Step 2: Update `_validate_template_step` to handle custom mode**

Replace the existing `_validate_template_step` method:

```python
def _validate_template_step(self):
    if self._mode == "preset":
        return self._template is not None
    else:
        records = self._read_custom_records()
        self._custom_records = records
        return len(records) > 0
```

- [ ] **Step 3: Verify and test**

Run: `python -m py_compile src/wizard_interface.py && echo OK`

Manual test: Select "Custom" → Next → record builder appears. Add rows, fill in content. Next enables when at least one row has content. Remove rows works.

- [ ] **Step 4: Commit**

```bash
git add src/wizard_interface.py
git commit -m "feat(wizard): implement step 2 custom path — editable record builder

Add Row/Remove Row table with Type combo, Subdomain, TTL, and
Content columns. Supports {variable} placeholders in fields."
```

---

## Task 7: Step 3 — Variable Input Mask

**Files:**
- Modify: `src/wizard_interface.py`

Replace `_build_step_variables` and `_on_enter_variables_step`. Dynamically generates input fields for all `{variables}` found in the selected template or custom records.

- [ ] **Step 1: Replace `_build_step_variables`, `_on_enter_variables_step`, and `_validate_variables_step`**

```python
def _build_step_variables(self):
    w = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(w)
    lay.setContentsMargins(0, 8, 0, 0)
    lay.setSpacing(8)

    lay.addWidget(StrongBodyLabel("Fill In Variables"))
    self._var_desc = CaptionLabel(
        "Provide values for the template variables below. "
        "{domain} is automatically set per target domain."
    )
    self._var_desc.setWordWrap(True)
    lay.addWidget(self._var_desc)

    # Scrollable form area
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
    self._var_form_layout.setSpacing(12)

    scroll.setWidget(self._var_form_widget)
    lay.addWidget(scroll, 1)

    # This dict maps var_name → LineEdit widget
    self._var_inputs = {}

    return w

def _on_enter_variables_step(self):
    """Rebuild the variable form based on the current template/custom records."""
    # Clear existing form
    while self._var_form_layout.rowCount() > 0:
        self._var_form_layout.removeRow(0)
    self._var_inputs.clear()

    # Collect variables from template or custom records
    if self._mode == "preset" and self._template:
        tpl_vars = self._template.get("variables", {})
        records = self._template.get("records", [])
    else:
        tpl_vars = {}
        records = self._custom_records

    # Find all {var} placeholders in records
    found_vars = set()
    for rec in records:
        for field in ("subname", "content"):
            found_vars.update(re.findall(r'\{(\w+)\}', rec.get(field, "")))

    # Remove reserved variables from user input
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

    # Template-defined variables (with metadata)
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

    # If no user variables needed, show a note
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

def _validate_variables_step(self):
    """Check all required variables have values."""
    if self._mode == "preset" and self._template:
        tpl_vars = self._template.get("variables", {})
    else:
        tpl_vars = {}

    for var_name, edit in self._var_inputs.items():
        if var_name == "subdomain_prefix":
            continue  # always optional
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
```

- [ ] **Step 2: Verify and test**

Run: `python -m py_compile src/wizard_interface.py && echo OK`

Manual test (preset path): Select Google Workspace → Next → variable form shows `{domain}` (read-only), `{subdomain_prefix}` (optional), and `{dkim_selector}` (required, default "google"). Next is enabled with default. Clear the field → Next disables.

Manual test (custom path): Add a record with content `{ip_address}` → Next → form shows `{ip_address}` as a required field.

- [ ] **Step 3: Commit**

```bash
git add src/wizard_interface.py
git commit -m "feat(wizard): implement step 3 — dynamic variable input mask

Auto-discovers {variables} from template/custom records, generates
form fields with hints and defaults. Reserved {domain} and
{subdomain_prefix} always shown."
```

---

## Task 8: Step 4 — Domain Selection

**Files:**
- Modify: `src/wizard_interface.py`

Replace `_build_step_domains` and `_on_enter_domains_step` with a checkbox list populated from the cache.

- [ ] **Step 1: Replace `_build_step_domains` and `_on_enter_domains_step`**

```python
def _build_step_domains(self):
    w = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(w)
    lay.setContentsMargins(0, 8, 0, 0)
    lay.setSpacing(8)

    lay.addWidget(StrongBodyLabel("Select Target Domains"))
    lay.addWidget(CaptionLabel(
        "Records will be created on all selected domains."
    ))

    # Toolbar
    toolbar = QtWidgets.QHBoxLayout()
    toolbar.setSpacing(8)

    self._domain_search = SearchLineEdit()
    self._domain_search.setPlaceholderText("Filter domains...")
    self._domain_search.textChanged.connect(self._filter_domain_checkboxes)
    toolbar.addWidget(self._domain_search, 1)

    btn_all = PushButton("Select All")
    btn_all.clicked.connect(lambda: self._set_all_domains(True))
    toolbar.addWidget(btn_all)

    btn_none = PushButton("Deselect All")
    btn_none.clicked.connect(lambda: self._set_all_domains(False))
    toolbar.addWidget(btn_none)

    lay.addLayout(toolbar)

    self._domain_count_label = CaptionLabel("0 of 0 domains selected")
    lay.addWidget(self._domain_count_label)

    # Scrollable checkbox list
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        "QScrollArea > QWidget > QWidget { background: transparent; }"
    )
    self._domain_check_widget = QtWidgets.QWidget()
    self._domain_check_layout = QtWidgets.QVBoxLayout(self._domain_check_widget)
    self._domain_check_layout.setContentsMargins(0, 0, 0, 0)
    self._domain_check_layout.setSpacing(4)
    self._domain_check_layout.addStretch()
    scroll.setWidget(self._domain_check_widget)
    lay.addWidget(scroll, 1)

    self._domain_checkboxes = []  # list of (domain_name, CheckBox)
    return w

def _on_enter_domains_step(self):
    """Rebuild the checkbox list from cached zones."""
    # Clear existing
    while self._domain_check_layout.count() > 1:
        item = self._domain_check_layout.takeAt(0)
        if w := item.widget():
            w.deleteLater()
    self._domain_checkboxes.clear()

    cached, _ = self._cache.get_cached_zones()
    zones = sorted(z.get("name", "") for z in (cached or []))

    for name in zones:
        cb = CheckBox(name)
        cb.stateChanged.connect(self._on_domain_check_changed)
        self._domain_check_layout.insertWidget(
            self._domain_check_layout.count() - 1, cb
        )
        self._domain_checkboxes.append((name, cb))

    self._domain_search.clear()
    self._update_domain_count()

def _filter_domain_checkboxes(self, text):
    ft = text.strip().lower()
    for name, cb in self._domain_checkboxes:
        cb.setVisible(not ft or ft in name.lower())

def _set_all_domains(self, checked):
    for name, cb in self._domain_checkboxes:
        if cb.isVisible():
            cb.setChecked(checked)

def _on_domain_check_changed(self):
    self._selected_domains = [
        name for name, cb in self._domain_checkboxes if cb.isChecked()
    ]
    self._update_domain_count()
    self._validate_current_step()

def _update_domain_count(self):
    total = len(self._domain_checkboxes)
    selected = len([1 for _, cb in self._domain_checkboxes if cb.isChecked()])
    self._domain_count_label.setText(
        f"{selected} of {total} domain{'s' if total != 1 else ''} selected"
    )
```

- [ ] **Step 2: Verify and test**

Run: `python -m py_compile src/wizard_interface.py && echo OK`

Manual test: Navigate to step 4. Checkbox list populates from cache. Search filters. Select All/Deselect All work. Count label updates. Next enables when at least one domain is checked.

- [ ] **Step 3: Commit**

```bash
git add src/wizard_interface.py
git commit -m "feat(wizard): implement step 4 — domain selection with checkboxes

Checkbox list from cached zones, search filter, Select/Deselect All,
live count label. Next requires at least one domain."
```

---

## Task 9: Step 5 — Conflict Strategy

**Files:**
- Modify: `src/wizard_interface.py`

Replace `_build_step_conflict` placeholder with a radio group.

- [ ] **Step 1: Replace `_build_step_conflict`**

```python
def _build_step_conflict(self):
    w = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(w)
    lay.setContentsMargins(0, 8, 0, 0)
    lay.setSpacing(12)

    lay.addWidget(StrongBodyLabel("Conflict Strategy"))
    lay.addWidget(CaptionLabel(
        "Choose how to handle cases where a record with the same "
        "subdomain and type already exists on a target domain."
    ))

    self._conflict_radios = {}

    # Merge
    r_merge = RadioButton("Merge")
    r_merge.setChecked(True)
    self._conflict_strategy = "merge"
    r_merge.toggled.connect(lambda checked: self._set_conflict("merge") if checked else None)
    lay.addWidget(r_merge)
    lay.addWidget(CaptionLabel(
        "  Append new content to the existing record set. "
        "For example, adds a new MX record alongside existing ones."
    ))
    self._conflict_radios["merge"] = r_merge

    # Replace
    r_replace = RadioButton("Replace")
    r_replace.toggled.connect(lambda checked: self._set_conflict("replace") if checked else None)
    lay.addWidget(r_replace)
    lay.addWidget(CaptionLabel(
        "  Overwrite the existing record set entirely with the new content. "
        "Use with caution — existing records of the same type will be lost."
    ))
    self._conflict_radios["replace"] = r_replace

    # Skip
    r_skip = RadioButton("Skip")
    r_skip.toggled.connect(lambda checked: self._set_conflict("skip") if checked else None)
    lay.addWidget(r_skip)
    lay.addWidget(CaptionLabel(
        "  Leave existing records untouched. Only create records where "
        "no matching subdomain + type combination exists yet."
    ))
    self._conflict_radios["skip"] = r_skip

    lay.addStretch()
    return w

def _set_conflict(self, strategy):
    self._conflict_strategy = strategy
```

- [ ] **Step 2: Verify and test**

Run: `python -m py_compile src/wizard_interface.py && echo OK`

Manual test: Step 5 shows three radio buttons. Merge is default. Switching works. Next is always enabled.

- [ ] **Step 3: Commit**

```bash
git add src/wizard_interface.py
git commit -m "feat(wizard): implement step 5 — conflict strategy radio group

Merge (default), Replace, and Skip options with descriptions."
```

---

## Task 10: Variable Resolution Engine

**Files:**
- Modify: `src/wizard_interface.py`

Add the core logic that resolves templates + variables into concrete per-domain record operations. This is used by both the preview and execution steps.

- [ ] **Step 1: Add `_resolve_records` method**

```python
def _resolve_records(self):
    """
    Resolve template/custom records × variables × domains into a flat
    list of concrete record operations.

    Returns list of dicts:
        {domain, subname, type, ttl, content, status, existing_records, error}
    where status is "new", "conflict", or "skipped".
    """
    variables = self._collect_variables()
    prefix = variables.pop("subdomain_prefix", "").strip()

    if self._mode == "preset" and self._template:
        records = self._template["records"]
    else:
        records = self._custom_records

    result = []
    for domain in self._selected_domains:
        # Get cached records for conflict detection
        cached_records, _ = self._cache.get_cached_records(domain)
        existing_index = {}
        if cached_records:
            for rr in cached_records:
                key = (rr.get("subname", ""), rr.get("type", ""))
                existing_index[key] = rr.get("records", [])

        domain_vars = {**variables, "domain": domain}

        for rec in records:
            # Resolve variables in content and subname
            content = rec["content"]
            subname = rec["subname"]
            for var, val in domain_vars.items():
                content = content.replace(f"{{{var}}}", val)
                subname = subname.replace(f"{{{var}}}", val)

            # Apply subdomain prefix
            if prefix:
                if subname:
                    subname = f"{subname}.{prefix}"
                else:
                    subname = prefix

            # Validate
            is_valid, err_msg = _validate_record_content(rec["type"], content)

            # Conflict detection
            existing = existing_index.get((subname, rec["type"]))
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
                "type": rec["type"],
                "ttl": rec["ttl"],
                "content": content,
                "status": status,
                "existing_records": existing or [],
                "error": err_msg if not is_valid else "",
            })

    return result
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile src/wizard_interface.py && echo OK`

- [ ] **Step 3: Commit**

```bash
git add src/wizard_interface.py
git commit -m "feat(wizard): add variable resolution engine

Resolves template records × variables × domains into concrete
operations with conflict detection against cached records."
```

---

## Task 11: Step 6 — Preview

**Files:**
- Modify: `src/wizard_interface.py`

Replace `_build_step_preview` and `_on_enter_preview_step` with a read-only table showing all resolved operations.

- [ ] **Step 1: Replace `_build_step_preview` and `_on_enter_preview_step`**

```python
def _build_step_preview(self):
    w = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(w)
    lay.setContentsMargins(0, 8, 0, 0)
    lay.setSpacing(8)

    lay.addWidget(StrongBodyLabel("Preview"))
    self._preview_summary = CaptionLabel("")
    self._preview_summary.setWordWrap(True)
    lay.addWidget(self._preview_summary)

    self._preview_table = TableWidget()
    self._preview_table.setColumnCount(6)
    self._preview_table.setHorizontalHeaderLabels(
        ["Domain", "Subdomain", "Type", "TTL", "Content", "Status"]
    )
    self._preview_table.setEditTriggers(
        QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
    )
    self._preview_table.horizontalHeader().setStretchLastSection(True)
    self._preview_table.setSelectionBehavior(
        QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
    )
    lay.addWidget(self._preview_table, 1)

    return w

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
        self._preview_table.setItem(r, 4, QtWidgets.QTableWidgetItem(row["content"]))

        # Status with color
        if row["error"]:
            status_text = f"Error: {row['error']}"
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

    # Disable Execute if nothing actionable or there are errors
    self._btn_next.setEnabled(actionable > 0 and n_error == 0)
```

- [ ] **Step 2: Add QtGui import if not already present**

At the top of the file, ensure the import line reads:

```python
from PySide6 import QtWidgets, QtCore, QtGui
```

- [ ] **Step 3: Verify and test**

Run: `python -m py_compile src/wizard_interface.py && echo OK`

Manual test: Walk through all steps to step 6. Preview table populates with resolved records. Status column shows colored text. Summary line shows counts.

- [ ] **Step 4: Commit**

```bash
git add src/wizard_interface.py
git commit -m "feat(wizard): implement step 6 — preview table with conflict status

Read-only table showing all resolved operations with color-coded
status (New/Conflict/Skipped/Error) and summary counts."
```

---

## Task 12: Step 7 — Execution

**Files:**
- Modify: `src/wizard_interface.py`

Replace `_build_step_execute` and `_execute` with the real execution logic that enqueues items to the API queue.

- [ ] **Step 1: Replace `_build_step_execute` and `_execute`**

```python
def _build_step_execute(self):
    w = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(w)
    lay.setContentsMargins(0, 8, 0, 0)
    lay.setSpacing(8)

    lay.addWidget(StrongBodyLabel("Execution"))
    self._exec_summary = CaptionLabel("Preparing...")
    lay.addWidget(self._exec_summary)

    self._exec_progress = ProgressBar()
    lay.addWidget(self._exec_progress)

    self._exec_status_label = CaptionLabel("")
    lay.addWidget(self._exec_status_label)

    # Results table
    self._exec_table = TableWidget()
    self._exec_table.setColumnCount(5)
    self._exec_table.setHorizontalHeaderLabels(
        ["Domain", "Subdomain", "Type", "Content", "Result"]
    )
    self._exec_table.setEditTriggers(
        QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
    )
    self._exec_table.horizontalHeader().setStretchLastSection(True)
    lay.addWidget(self._exec_table, 1)

    # Retry / Start Over buttons
    btn_row = QtWidgets.QHBoxLayout()
    btn_row.setSpacing(8)
    btn_row.addStretch()
    self._btn_retry = PushButton("Retry Failed")
    self._btn_retry.clicked.connect(self._retry_failed)
    self._btn_retry.setVisible(False)
    btn_row.addWidget(self._btn_retry)
    lay.addLayout(btn_row)

    return w

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
        if row["status"] in ("new", "conflict") and not row["error"]
    ]

    self._exec_table.setRowCount(len(actionable))
    self._exec_progress.setRange(0, len(actionable))
    self._exec_progress.setValue(0)
    self._exec_completed = 0
    self._exec_succeeded = 0
    self._exec_failed = 0
    self._exec_total = len(actionable)
    self._exec_actionable = actionable
    self._exec_results = {}  # row_idx → (success, error_msg)

    for i, row in enumerate(actionable):
        self._exec_table.setItem(i, 0, QtWidgets.QTableWidgetItem(row["domain"]))
        self._exec_table.setItem(i, 1, QtWidgets.QTableWidgetItem(row["subname"] or "@"))
        self._exec_table.setItem(i, 2, QtWidgets.QTableWidgetItem(row["type"]))
        self._exec_table.setItem(i, 3, QtWidgets.QTableWidgetItem(row["content"]))
        self._exec_table.setItem(i, 4, QtWidgets.QTableWidgetItem("Pending..."))

        self._enqueue_record(i, row)

    self._exec_summary.setText(
        f"Executing {len(actionable)} operations..."
    )

def _enqueue_record(self, row_idx, row):
    """Enqueue a single record operation."""
    domain = row["domain"]
    subname = row["subname"]
    rtype = row["type"]
    ttl = row["ttl"]
    content = row["content"]

    if row["status"] == "conflict" and self._conflict_strategy == "merge":
        # Merge: need to combine with existing records
        existing = list(row.get("existing_records", []))
        if content not in existing:
            existing.append(content)
        api_method = self._api.update_record
        records = existing
        action_desc = f"Merge {rtype} for {subname or '@'} in {domain}"
    elif row["status"] == "conflict" and self._conflict_strategy == "replace":
        api_method = self._api.update_record
        records = [content]
        action_desc = f"Replace {rtype} for {subname or '@'} in {domain}"
    else:
        api_method = self._api.create_record
        records = [content]
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
        # Snapshot version
        if self._version_manager:
            try:
                self._version_manager.snapshot(domain)
            except Exception:
                pass
    else:
        self._exec_failed += 1
        err = str(response) if response else "Unknown error"
        self._exec_results[row_idx] = (False, err)
        if result_item:
            result_item.setText(f"Failed: {err}")
            result_item.setForeground(QtGui.QColor("#E53935"))

    # Update summary
    self._exec_status_label.setText(
        f"{self._exec_completed}/{self._exec_total} complete — "
        f"{self._exec_succeeded} succeeded, {self._exec_failed} failed"
    )

    # All done?
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
```

- [ ] **Step 2: Verify and test**

Run: `python -m py_compile src/wizard_interface.py && echo OK`

Manual test: Walk through all 7 steps. On step 6, click Execute. Step 7 shows progress bar advancing, per-row results updating in real-time. Retry Failed appears if any fail.

- [ ] **Step 3: Commit**

```bash
git add src/wizard_interface.py
git commit -m "feat(wizard): implement step 7 — execution with progress and retry

Enqueues operations to APIQueue, real-time progress bar and per-row
results. Retry Failed button for error recovery. Emits records_changed
on completion."
```

---

## Task 13: Polish and Final Integration

**Files:**
- Modify: `src/wizard_interface.py`

Final pass: ensure the step 2 custom builder wires into the variable resolution correctly, resize columns, and handle edge cases.

- [ ] **Step 1: Wire custom records into the flow**

In `_go_next`, before advancing from step 2, store custom records:

Find the `_go_next` method and replace it with:

```python
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
```

- [ ] **Step 2: Full walkthrough test**

Run: `python src/main.py`

Test both paths end-to-end:
1. Preset: Select a template → fill variables → select domains → choose conflict strategy → preview → execute
2. Custom: Build records with `{variable}` placeholders → fill variables → select domains → preview → execute
3. Verify "Start Over" resets everything
4. Verify Back navigation preserves state

- [ ] **Step 3: Commit**

```bash
git add src/wizard_interface.py
git commit -m "feat(wizard): wire custom records and variables into execution flow

Ensure custom record builder data and variable values are captured
when advancing between steps."
```

---

## Summary

| Task | Description | New/Modified Files |
|---|---|---|
| 1 | Template data module | Create `wizard_templates.py` |
| 2 | Wizard scaffold + navigation | Create `wizard_interface.py` |
| 3 | Main window integration | Modify `main_window.py` |
| 4 | Step 1 — Mode selection | Modify `wizard_interface.py` |
| 5 | Step 2 — Template selection (preset) | Modify `wizard_interface.py` |
| 6 | Step 2 — Custom record builder | Modify `wizard_interface.py` |
| 7 | Step 3 — Variable input mask | Modify `wizard_interface.py` |
| 8 | Step 4 — Domain selection | Modify `wizard_interface.py` |
| 9 | Step 5 — Conflict strategy | Modify `wizard_interface.py` |
| 10 | Variable resolution engine | Modify `wizard_interface.py` |
| 11 | Step 6 — Preview | Modify `wizard_interface.py` |
| 12 | Step 7 — Execution | Modify `wizard_interface.py` |
| 13 | Polish and final integration | Modify `wizard_interface.py` |
