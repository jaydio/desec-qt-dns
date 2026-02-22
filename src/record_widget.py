#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Record Widget for deSEC Qt DNS Manager.
Displays and manages DNS records for a selected zone.
"""

import logging
import time
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QThreadPool

from workers import LoadRecordsWorker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column index constants
# ---------------------------------------------------------------------------
COL_CHECK   = 0
COL_NAME    = 1
COL_TYPE    = 2
COL_TTL     = 3
COL_CONTENT = 4
COL_ACTIONS = 5


# ---------------------------------------------------------------------------
# Bulk-delete background worker
# ---------------------------------------------------------------------------

class _BulkDeleteWorker(QThread):
    progress_update = pyqtSignal(int, str)   # pct, status message
    record_done     = pyqtSignal(bool, str)  # success, label
    finished        = pyqtSignal(int, int)   # deleted, failed

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

class RecordWidget(QtWidgets.QWidget):
    """Widget for displaying and managing DNS records."""
    
    # Custom signals
    records_changed = pyqtSignal()  # Emitted when records are changed
    log_message = pyqtSignal(str, str)  # Emitted to log messages (message, level)
    
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
    
    def __init__(self, api_client, cache_manager, config_manager=None, parent=None):
        """
        Initialize the record widget.
        :param api_client: API client instance
        :param cache_manager: Cache manager instance
        :param config_manager: Configuration manager instance for settings (optional)
        :param parent: Parent widget
        """
        super().__init__(parent)
        self.api_client = api_client
        self.cache_manager = cache_manager
        self.config_manager = config_manager
        self.current_domain = None
        self.records = []
        self.is_online = True  # Start assuming we are online
        self.can_edit = True  # Single source of truth for editability
        # Initialize multiline display setting from config if available
        self.show_multiline = False  # Default value
        if self.config_manager:
            self.show_multiline = self.config_manager.get_show_multiline_records()
        
        self.threadpool = QThreadPool()
        
        # Setup UI
        # Set up the UI
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
        
        title = QtWidgets.QLabel("DNS Records (RRsets)")
        title.setStyleSheet("font-weight: bold;")
        title.setMinimumWidth(100)  # Fixed width for right alignment
        title_layout.addWidget(title)
        
        title_layout.addStretch()
        
        self.records_count_label = QtWidgets.QLabel("Total records: 0")
        title_layout.addWidget(self.records_count_label)
        
        header_layout.addLayout(title_layout)
        
        # Search field (match spacing with Zone widget)
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.setContentsMargins(0, 6, 0, 6)  # Add vertical padding
        
        search_label = QtWidgets.QLabel("Search:")
        search_label.setMinimumWidth(50)  # Fixed width for right alignment
        search_layout.addWidget(search_label)
        
        self.records_search_input = QtWidgets.QLineEdit()
        self.records_search_input.setFixedHeight(25)  # Consistent height with zone widget
        self.records_search_input.setPlaceholderText("Type to filter records...")
        self.records_search_input.textChanged.connect(self.filter_records)
        search_layout.addWidget(self.records_search_input)
        
        header_layout.addLayout(search_layout)
        
        # Add header layout to main layout
        layout.addLayout(header_layout)
        
        # Records table
        self.records_table = QtWidgets.QTableWidget()
        self.records_table.setColumnCount(6)  # Check, Name, Type, TTL, Content, Actions

        # Create header items
        check_header = QtWidgets.QTableWidgetItem("")
        check_header.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

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

        actions_header = QtWidgets.QTableWidgetItem("Actions")
        actions_header.setTextAlignment(Qt.AlignmentFlag.AlignLeft)

        self.records_table.setHorizontalHeaderItem(COL_CHECK,   check_header)
        self.records_table.setHorizontalHeaderItem(COL_NAME,    name_header)
        self.records_table.setHorizontalHeaderItem(COL_TYPE,    type_header)
        self.records_table.setHorizontalHeaderItem(COL_TTL,     ttl_header)
        self.records_table.setHorizontalHeaderItem(COL_CONTENT, content_header)
        self.records_table.setHorizontalHeaderItem(COL_ACTIONS, actions_header)
        
        # Set table properties
        self.records_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.records_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.records_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.records_table.setAlternatingRowColors(True)
        # Column resize modes
        self.records_table.horizontalHeader().setSectionResizeMode(COL_CHECK,   QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.records_table.horizontalHeader().setSectionResizeMode(COL_NAME,    QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.records_table.horizontalHeader().setSectionResizeMode(COL_TYPE,    QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.records_table.horizontalHeader().setSectionResizeMode(COL_TTL,     QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.records_table.horizontalHeader().setSectionResizeMode(COL_CONTENT, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.records_table.horizontalHeader().setSectionResizeMode(COL_ACTIONS, QtWidgets.QHeaderView.ResizeMode.Interactive)

        # Set initial default widths (matched to typical column proportions)
        self.records_table.setColumnWidth(COL_CHECK,   28)
        self.records_table.setColumnWidth(COL_NAME,    220)
        self.records_table.setColumnWidth(COL_TYPE,    90)
        self.records_table.setColumnWidth(COL_TTL,     80)
        self.records_table.setColumnWidth(COL_ACTIONS, 140)
        self.records_table.verticalHeader().setVisible(False)

        # Enhance sort indicator visibility
        self.records_table.horizontalHeader().setSortIndicatorShown(True)
        self.records_table.horizontalHeader().sortIndicatorChanged.connect(self.sort_records_table)

        # Set default sort by name column in ascending order
        self.records_table.setSortingEnabled(True)
        self.records_table.sortByColumn(COL_NAME, QtCore.Qt.SortOrder.AscendingOrder)
        self.records_table.cellDoubleClicked.connect(self.handle_cell_double_clicked)
        
        # Set table style to match zone list
        self.records_table.setStyleSheet(
            "QTableWidget { border: 1px solid palette(mid); }"
        )
        
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
        self.add_record_btn = QtWidgets.QPushButton("Add Record")
        self.add_record_btn.setFixedHeight(25)
        self.add_record_btn.setFixedWidth(90)
        self.add_record_btn.clicked.connect(self.show_add_record_dialog)
        self.add_record_btn.setEnabled(self.is_online)
        if not self.is_online:
            self.add_record_btn.setToolTip("Unavailable in offline mode")
        actions_layout.addWidget(self.add_record_btn)
        
        actions_layout.addStretch()

        self.select_all_btn = QtWidgets.QPushButton("Select All")
        self.select_all_btn.setFixedHeight(25)
        self.select_all_btn.setEnabled(False)
        self.select_all_btn.clicked.connect(self._select_all_records)
        actions_layout.addWidget(self.select_all_btn)

        self.select_none_btn = QtWidgets.QPushButton("Select None")
        self.select_none_btn.setFixedHeight(25)
        self.select_none_btn.setEnabled(False)
        self.select_none_btn.clicked.connect(self._select_none_records)
        actions_layout.addWidget(self.select_none_btn)

        self.bulk_delete_btn = QtWidgets.QPushButton("Delete Selected")
        self.bulk_delete_btn.setFixedHeight(25)
        self.bulk_delete_btn.setEnabled(False)
        self.bulk_delete_btn.setStyleSheet("QPushButton { color: #c62828; }")
        self.bulk_delete_btn.clicked.connect(self.delete_selected_records)
        actions_layout.addWidget(self.bulk_delete_btn)

        layout.addLayout(actions_layout)
    
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
        
        # Enable/disable per-row edit and delete buttons
        for row in range(self.records_table.rowCount()):
            cell = self.records_table.cellWidget(row, COL_ACTIONS)
            if not cell or not cell.layout():
                continue
            edit_btn = cell.layout().itemAt(0).widget()
            if edit_btn:
                edit_btn.setEnabled(self.can_edit)
                edit_btn.setToolTip("" if self.can_edit else "Editing records is disabled in offline mode")
            delete_btn = cell.layout().itemAt(1).widget()
            if delete_btn:
                delete_btn.setEnabled(self.can_edit)
                delete_btn.setToolTip("" if self.can_edit else "Deleting records is disabled in offline mode")

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
        """Fetch records asynchronously using a worker thread."""
        # Create and start a worker to fetch records in background
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
        
        # Get current filter text
        filter_text = getattr(self, '_current_filter', '').lower()
        
        # Calculate the number of filtered records for display
        total_records = len(self.records)
        filtered_records = []
        
        # Note: we no longer pre-sort the records since we'll use Qt's built-in sorting
        for row, record in enumerate(self.records):
            # Filter records by name, type, or content
            if filter_text in record.get('subname', '').lower() or filter_text in record.get('type', '').lower() or filter_text in "\n".join(record.get('records', [])).lower():
                filtered_records.append(record)
        
        # Update the records count label
        filtered_count = len(filtered_records)
        if filter_text:
            self.records_count_label.setText(f"Showing {filtered_count} out of {total_records} records")
        else:
            self.records_count_label.setText(f"Total records: {total_records}")

        # Ensure edit controls reflect offline/online state after table update
        self.set_edit_enabled(self.is_online and not self.config_manager.get_offline_mode())
        
        for row, record in enumerate(filtered_records):
            self.records_table.insertRow(row)

            # Checkbox column — native centered QCheckBox via cell widget
            check_container = QtWidgets.QWidget()
            check_layout = QtWidgets.QHBoxLayout(check_container)
            check_layout.setContentsMargins(0, 0, 0, 0)
            check_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb = QtWidgets.QCheckBox()
            cb.stateChanged.connect(self._on_checkbox_state_changed)
            check_layout.addWidget(cb)
            self.records_table.setCellWidget(row, COL_CHECK, check_container)

            # Name column (subname)
            name = record.get('subname', '') or '@'
            name_item = QtWidgets.QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, record)
            timestamp_tooltip = self._get_timestamp_tooltip(record)
            if timestamp_tooltip:
                name_item.setToolTip(timestamp_tooltip)
            self.records_table.setItem(row, COL_NAME, name_item)

            # Type column
            record_type = record.get('type', '')
            type_item = QtWidgets.QTableWidgetItem(record_type)
            if record_type == 'A':
                type_item.setForeground(QtGui.QColor('#2196F3'))
            elif record_type == 'AAAA':
                type_item.setForeground(QtGui.QColor('#3F51B5'))
            elif record_type in ['CNAME', 'DNAME']:
                type_item.setForeground(QtGui.QColor('#4CAF50'))
            elif record_type == 'MX':
                type_item.setForeground(QtGui.QColor('#FF9800'))
            elif record_type in ['TXT', 'SPF']:
                type_item.setForeground(QtGui.QColor('#673AB7'))
            elif record_type in ['NS', 'DS', 'DNSKEY']:
                type_item.setForeground(QtGui.QColor('#E91E63'))
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

            # Actions column
            actions_widget = QtWidgets.QWidget()
            actions_layout = QtWidgets.QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 0, 4, 0)
            actions_layout.setSpacing(4)

            record_ref = record
            edit_btn = QtWidgets.QPushButton("Edit")
            edit_btn.setFixedSize(60, 25)
            edit_btn.clicked.connect(lambda _, rec=record_ref: self.edit_record_by_ref(rec))
            edit_btn.setProperty('record_ref', record_ref)
            edit_btn.setEnabled(self.can_edit)
            edit_btn.setToolTip("" if self.can_edit else "Editing records is disabled in offline mode")

            delete_btn = QtWidgets.QPushButton("Delete")
            delete_btn.setFixedSize(60, 25)
            delete_btn.clicked.connect(lambda _, rec=record_ref: self.delete_record_by_ref(rec))
            delete_btn.setProperty('record_ref', record_ref)
            delete_btn.setEnabled(self.can_edit)
            delete_btn.setToolTip("" if self.can_edit else "Deleting records is disabled in offline mode")

            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(delete_btn)
            actions_layout.addStretch()

            self.records_table.setCellWidget(row, COL_ACTIONS, actions_widget)

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
        """
        Filter the records table by name, type, or content.
        
        Args:
            filter_text (str): Text to filter by
        """
        # Store the filter text for later use
        self._current_filter = filter_text.lower()
        
        # Reapply the filter by updating the table
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
    


    def show_add_record_dialog(self):
        """Show dialog to add a new record."""
        if not self.current_domain or not self.can_edit:
            return
            
        dialog = RecordDialog(self.current_domain, self.api_client, parent=self)
        dialog.setWindowTitle("Add DNS Record")
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.records_changed.emit()
            self.refresh_records()
    
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
                COL_ACTIONS: "Actions",
            }
            for col, label in header_items.items():
                item = self.records_table.horizontalHeaderItem(col)
                if item is None:
                    continue
                if col == column:
                    arrow = "↑" if order == Qt.SortOrder.AscendingOrder else "↓"
                    item.setText(f"{label} {arrow}")
                elif col != COL_ACTIONS:
                    item.setText(f"{label} ↕")
                else:
                    item.setText(label)
    
    def handle_cell_double_clicked(self, row, column):
        """Handle double-click on a cell."""
        if not self.can_edit:
            return
        # Ignore double-click on the checkbox and Actions columns
        if column not in (COL_CHECK, COL_ACTIONS):
            record_item = self.records_table.item(row, COL_NAME)
            record = record_item.data(Qt.ItemDataRole.UserRole)
            if record:
                self.edit_record_by_ref(record)
    
    def edit_record_by_ref(self, record):
        """Edit a record by reference instead of by row index.
        
        Args:
            record (dict): The record object to edit
        """
        if not self.can_edit or not record:
            return
            
        dialog = RecordDialog(self.current_domain, self.api_client, record=record, parent=self)
        dialog.setWindowTitle("Edit DNS Record")
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.records_changed.emit()
            self.refresh_records()
    
    def edit_record(self, row):
        """
        Edit a record.
        
        Args:
            row (int): Row index in the table
        """
        if not self.can_edit:
            return
            
        record_item = self.records_table.item(row, COL_NAME)
        record = record_item.data(Qt.ItemDataRole.UserRole)

        if not record:
            return

        dialog = RecordDialog(self.current_domain, self.api_client, record=record, parent=self)
        dialog.setWindowTitle("Edit DNS Record")

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.records_changed.emit()
            self.refresh_records()

    def delete_selected_record(self):
        """Delete the currently selected record in the table.
        Called when pressing the Delete key while the records table has focus.
        """
        if not hasattr(self, 'records_table') or not self.can_edit:
            return
        
        # Get the currently selected row
        selected_rows = self.records_table.selectedIndexes()
        if not selected_rows:
            return
        
        # Get the row of the first selected cell
        row = selected_rows[0].row()
        if row < 0 or row >= self.records_table.rowCount():
            return
        
        # Get the record reference from the delete button in the actions column
        try:
            actions_cell = self.records_table.cellWidget(row, COL_ACTIONS)
            if not actions_cell or not actions_cell.layout():
                self.log_message.emit("Could not access actions cell for deletion", "warning")
                return
            
            # Get the delete button (second button in the layout)
            if actions_cell.layout().count() > 1:
                delete_btn = actions_cell.layout().itemAt(1).widget()
                if delete_btn and delete_btn.property('record_ref'):
                    record = delete_btn.property('record_ref')
                    if record:
                        self.delete_record_by_ref(record)
                        return
                    
            # Fallback: try to get the reference from any buttons in the layout
            for i in range(actions_cell.layout().count()):
                item = actions_cell.layout().itemAt(i)
                if item and item.widget() and hasattr(item.widget(), 'property'):
                    btn = item.widget()
                    record = btn.property('record_ref')
                    if record:
                        self.delete_record_by_ref(record)
                        return
                        
            self.log_message.emit("No record reference found for deletion", "warning")
            
        except Exception as e:
            self.log_message.emit(f"Error accessing record for deletion: {str(e)}", "error")
    
    # ------------------------------------------------------------------
    # Bulk selection and delete
    # ------------------------------------------------------------------

    def _on_checkbox_state_changed(self):
        """Called when any row's QCheckBox changes state."""
        sender = self.sender()
        for row in range(self.records_table.rowCount()):
            widget = self.records_table.cellWidget(row, COL_CHECK)
            if widget:
                cb = widget.findChild(QtWidgets.QCheckBox)
                if cb is sender:
                    self._update_row_highlight(row, cb.isChecked())
                    break
        self._update_bulk_btn()

    def _row_highlight_color(self):
        """Return a soft highlight QColor derived from the current palette."""
        palette = self.records_table.palette()
        hl = palette.color(QtGui.QPalette.ColorRole.Highlight)
        base = palette.color(QtGui.QPalette.ColorRole.Base)
        # Blend: 25% highlight + 75% base — works for any theme
        return QtGui.QColor(
            int(hl.red()   * 0.25 + base.red()   * 0.75),
            int(hl.green() * 0.25 + base.green() * 0.75),
            int(hl.blue()  * 0.25 + base.blue()  * 0.75),
        )

    def _update_row_highlight(self, row, checked):
        """Highlight or clear a row depending on its checked state."""
        widget = self.records_table.cellWidget(row, COL_CHECK)
        if checked:
            bg_color = self._row_highlight_color()
            bg_hex = bg_color.name()
            if widget:
                widget.setStyleSheet(f"background-color: {bg_hex};")
            for col in (COL_NAME, COL_TYPE, COL_TTL, COL_CONTENT):
                item = self.records_table.item(row, col)
                if item:
                    item.setBackground(bg_color)
        else:
            if widget:
                widget.setStyleSheet("")
            for col in (COL_NAME, COL_TYPE, COL_TTL, COL_CONTENT):
                item = self.records_table.item(row, col)
                if item:
                    # Remove the role so Qt restores alternating-row colours
                    item.setData(Qt.ItemDataRole.BackgroundRole, None)

    def _update_bulk_btn(self):
        if not hasattr(self, 'bulk_delete_btn'):
            return
        n = len(self._get_checked_records())
        can = n > 0 and self.can_edit
        self.bulk_delete_btn.setEnabled(can)
        self.bulk_delete_btn.setText(f"Delete Selected ({n})" if n > 0 else "Delete Selected")
        has_rows = self.records_table.rowCount() > 0
        self.select_all_btn.setEnabled(has_rows and self.can_edit)
        self.select_none_btn.setEnabled(has_rows and self.can_edit)

    def _select_all_records(self):
        for row in range(self.records_table.rowCount()):
            widget = self.records_table.cellWidget(row, COL_CHECK)
            if widget:
                cb = widget.findChild(QtWidgets.QCheckBox)
                if cb:
                    cb.blockSignals(True)
                    cb.setChecked(True)
                    cb.blockSignals(False)
                    self._update_row_highlight(row, True)
        self._update_bulk_btn()

    def _select_none_records(self):
        for row in range(self.records_table.rowCount()):
            widget = self.records_table.cellWidget(row, COL_CHECK)
            if widget:
                cb = widget.findChild(QtWidgets.QCheckBox)
                if cb:
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)
                    self._update_row_highlight(row, False)
        self._update_bulk_btn()

    def _get_checked_records(self):
        result = []
        for row in range(self.records_table.rowCount()):
            widget = self.records_table.cellWidget(row, COL_CHECK)
            if widget:
                cb = widget.findChild(QtWidgets.QCheckBox)
                if cb and cb.isChecked():
                    name_item = self.records_table.item(row, COL_NAME)
                    if name_item:
                        record = name_item.data(Qt.ItemDataRole.UserRole)
                        if record:
                            result.append(record)
        return result

    def delete_selected_records(self):
        records = self._get_checked_records()
        if not records or not self.can_edit:
            return
        confirm = QtWidgets.QMessageBox.question(
            self, "Confirm Bulk Delete",
            f"Permanently delete {len(records)} selected record(s)?\n\nThis cannot be undone.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._set_bulk_busy(True)
        self._bulk_worker = _BulkDeleteWorker(self.api_client, self.current_domain, records)
        self._bulk_worker.record_done.connect(self._on_bulk_record_done)
        self._bulk_worker.finished.connect(self._on_bulk_delete_finished)
        self._bulk_worker.start()

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
        type = record.get('type', '')
        
        # Confirm deletion
        record_name = subname or '@'
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the {type} record for '{record_name}'?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return
            
        # Get record content for detailed logging
        record_content = "\n".join(record.get('records', ['<empty>']))
        
        # Delete record with detailed logging
        ttl = record.get('ttl', 0)  # Include TTL in log
        self.log_message.emit(f"Deleting {type} record for '{record_name}' with TTL: {ttl}, content: {record_content}", "info")
        
        success, response = self.api_client.delete_record(self.current_domain, subname, type)
        
        if success:
            self.log_message.emit(f"Successfully deleted {type} record for '{record_name}' with TTL: {ttl}", "success")
            # Force invalidation of the cache for this domain
            self.cache_manager.clear_domain_cache(self.current_domain)
            # Emit signal first (for any listeners)
            self.records_changed.emit()
            # Then refresh our own view
            self.refresh_records()
        else:
            self.log_message.emit(f"Failed to delete record: {response}", "error")


class RecordDialog(QtWidgets.QDialog):
    """Dialog for adding or editing DNS records."""
    
    # Create a signal for logging messages
    log_signal = QtCore.pyqtSignal(str, str)
    
    def __init__(self, domain, api_client, record=None, parent=None):
        """
        Initialize the record dialog.
        
        Args:
            domain (str): Domain name
            api_client: API client instance
            record (dict, optional): Existing record for editing
            parent: Parent widget, if any
        """
        super(RecordDialog, self).__init__(parent)
        
        self.domain = domain
        self.api_client = api_client
        self.record = record  # None for new record, dict for editing
        self.parent = parent
        
        # Connect our log_signal to the parent's log_message signal if available
        if parent and hasattr(parent, 'log_message'):
            self.log_signal.connect(parent.log_message)
        
        # Set up the UI
        self.setup_ui()
        
        # Initialize values from record if editing
        if record:
            self.initialize_values()
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("DNS Record Editor")
        self.setMinimumSize(560, 640)
        layout = QtWidgets.QVBoxLayout(self)
        
        # Form layout
        form = QtWidgets.QFormLayout()
        
        # Subdomain field
        self.subname_input = QtWidgets.QLineEdit()
        self.subname_input.setPlaceholderText("e.g., www (leave blank for apex)")
        form.addRow("Subdomain:", self.subname_input)
        
        # Type field
        self.type_combo = QtWidgets.QComboBox()
        # Sort the record types alphabetically for easier finding
        record_type_descriptions = {
            'A': 'A (IPv4 Address)',
            'AAAA': 'AAAA (IPv6 Address)',
            'AFSDB': 'AFSDB (AFS Database)',
            'APL': 'APL (Address Prefix List)',
            'CAA': 'CAA (Certification Authority Authorization)',
            'CDNSKEY': 'CDNSKEY (Child DNS Key)',
            'CERT': 'CERT (Certificate)',
            'CNAME': 'CNAME (Canonical Name)',
            'DHCID': 'DHCID (DHCP Identifier)',
            'DNAME': 'DNAME (Delegation Name)',
            'DNSKEY': 'DNSKEY (DNS Key)',
            'DLV': 'DLV (DNSSEC Lookaside Validation)',
            'DS': 'DS (Delegation Signer)',
            'EUI48': 'EUI48 (MAC Address)',
            'EUI64': 'EUI64 (Extended MAC Address)',
            'HINFO': 'HINFO (Host Information)',
            'HTTPS': 'HTTPS (HTTPS Service)',
            'KX': 'KX (Key Exchanger)',
            'L32': 'L32 (Location IPv4)',
            'L64': 'L64 (Location IPv6)',
            'LOC': 'LOC (Location)',
            'LP': 'LP (Location Pointer)',
            'MX': 'MX (Mail Exchange)',
            'NAPTR': 'NAPTR (Name Authority Pointer)',
            'NID': 'NID (Node Identifier)',
            'NS': 'NS (Name Server)',
            'OPENPGPKEY': 'OPENPGPKEY (OpenPGP Public Key)',
            'PTR': 'PTR (Pointer)',
            'RP': 'RP (Responsible Person)',
            'SMIMEA': 'SMIMEA (S/MIME Cert Association)',
            'SPF': 'SPF (Sender Policy Framework)',
            'SRV': 'SRV (Service)',
            'SSHFP': 'SSHFP (SSH Fingerprint)',
            'SVCB': 'SVCB (Service Binding)',
            'TLSA': 'TLSA (TLS Association)',
            'TXT': 'TXT (Text)',
            'URI': 'URI (Uniform Resource Identifier)'
        }
        for record_type in sorted(RecordWidget.SUPPORTED_TYPES):
            self.type_combo.addItem(record_type_descriptions.get(record_type, record_type))
        self.type_combo.currentIndexChanged.connect(self.update_record_type_guidance)
        form.addRow("Type:", self.type_combo)
        
        # TTL field - replace spinbox with combo box of common values
        self.ttl_input = QtWidgets.QComboBox()
        
        # Add common TTL values with human-readable labels
        ttl_values = [
            (60, "60 seconds (1 minute)"),
            (300, "300 seconds (5 minutes)"),
            (600, "600 seconds (10 minutes)"),
            (900, "900 seconds (15 minutes)"),
            (1800, "1800 seconds (30 minutes)"),
            (3600, "3600 seconds (1 hour)"),
            (7200, "7200 seconds (2 hours)"),
            (14400, "14400 seconds (4 hours)"),
            (86400, "86400 seconds (24 hours)")
            # 604800 removed - deSEC only supports up to 86400 (24 hours)
        ]
        
        for value, label in ttl_values:
            self.ttl_input.addItem(label, value)
            
        # Set default to 1 hour
        self.ttl_input.setCurrentIndex(5)  # 3600 seconds (1 hour)
        
        # Create a layout with the dropdown and a note for low TTL values
        ttl_layout = QtWidgets.QVBoxLayout()
        ttl_layout.setContentsMargins(0, 0, 0, 0)
        ttl_layout.addWidget(self.ttl_input)
        
        ttl_note = QtWidgets.QLabel("Note: deSEC supports TTL values between 3600-86400 seconds (1-24 hours).\nTTL below 3600 (1 hour) is possible but requires account modification via support@desec.io.")
        ttl_note.setStyleSheet("color: #666; font-size: 10px;")
        ttl_note.setWordWrap(True)
        ttl_layout.addWidget(ttl_note)
        
        ttl_container = QtWidgets.QWidget()
        ttl_container.setLayout(ttl_layout)
        form.addRow("TTL:", ttl_container)
        
        # Records field
        self.records_label = QtWidgets.QLabel("Record Content:")
        layout.addLayout(form)
        layout.addWidget(self.records_label)
        
        self.records_input = QtWidgets.QTextEdit()
        self.records_input.setPlaceholderText("Enter record content (one per line)")
        self.records_input.textChanged.connect(self.validate_input)
        layout.addWidget(self.records_input)
        
        # Validation status indicator
        self.validation_status = QtWidgets.QLabel("")
        self.validation_status.setStyleSheet("color: #666;")
        self.validation_status.setWordWrap(True)
        layout.addWidget(self.validation_status)
        
        # Guidance text
        self.guidance_text = QtWidgets.QLabel()
        self.guidance_text.setWordWrap(True)
        # Use palette colors instead of hardcoded colors for theme compatibility
        self.guidance_text.setAutoFillBackground(True)
        # We'll set the actual styling in update_record_type_guidance for theme awareness
        self.guidance_text.setTextFormat(QtCore.Qt.TextFormat.RichText)
        layout.addWidget(self.guidance_text)
        
        # Initialize guidance for the default record type
        self.update_record_type_guidance(0)
        
        # Add buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def initialize_values(self):
        """Initialize form values from record if editing."""
        if not self.record:
            return
            
        # Disable changing the record type and subname when editing
        record_type = self.record.get('type', '')
        
        # Find the matching record type in the dropdown (which now has descriptions)
        for i in range(self.type_combo.count()):
            current_type = self.type_combo.itemText(i)
            # Check if this dropdown item starts with our record type
            if current_type.startswith(record_type + ' (') or current_type == record_type:
                self.type_combo.setCurrentIndex(i)
                break
        
        self.type_combo.setEnabled(False)
        
        self.subname_input.setText(self.record.get('subname', ''))
        self.subname_input.setEnabled(False)
        
        # Find and select the matching TTL value in the dropdown
        ttl_value = self.record.get('ttl', 3600)
        index = self.ttl_input.findData(ttl_value)
        
        # If exact match not found, find closest value
        if index == -1:
            # Get all available TTL values
            available_ttls = [self.ttl_input.itemData(i) for i in range(self.ttl_input.count())]
            # Find closest match by minimizing absolute difference
            closest_ttl = min(available_ttls, key=lambda x: abs(x - ttl_value))
            index = self.ttl_input.findData(closest_ttl)
            
        self.ttl_input.setCurrentIndex(max(0, index))
        
        # Set window title to indicate edit mode
        # Always use the original record type (without description) from the record data
        self.setWindowTitle(f"Edit {self.record.get('type', '')} Record")
        
        # Set record content
        records = self.record.get('records', [])
        self.records_input.setPlainText('\n'.join(records))
    
    def update_record_type_guidance(self, index):
        """Update guidance text based on selected record type."""
        record_type = self.type_combo.currentText()
        
        # Extract just the record type without description
        if ' (' in record_type:
            record_type = record_type.split(' (')[0]
            
        if record_type in RecordWidget.RECORD_TYPE_GUIDANCE:
            guidance = RecordWidget.RECORD_TYPE_GUIDANCE[record_type]
            self.guidance_text.setText(
                f"<b>{record_type} Record:</b><br>{guidance['tooltip']}<br><br>" +
                f"<b>Format:</b><br>{guidance['format']}<br><br>" +
                f"<b>Example:</b><br>{guidance['example']}"
            )
            
            # Use palette colors for theme compatibility
            palette = self.guidance_text.palette()
            bg_color = palette.color(QtGui.QPalette.ColorRole.Base)
            text_color = palette.color(QtGui.QPalette.ColorRole.Text)
            
            # Slightly adjust the background color to stand out from the main background
            # For light themes, make it slightly darker, for dark themes make it slightly lighter
            luminance = (0.299 * bg_color.red() + 0.587 * bg_color.green() + 0.114 * bg_color.blue()) / 255
            if luminance > 0.5:  # Light background
                # Make it slightly darker for contrast
                bg_color = bg_color.darker(110)
            else:  # Dark background
                # Make it slightly lighter for contrast
                bg_color = bg_color.lighter(120)
                
            # Create custom palette for the guidance text
            guidance_palette = QtGui.QPalette(palette)
            guidance_palette.setColor(QtGui.QPalette.ColorRole.Window, bg_color)
            guidance_palette.setColor(QtGui.QPalette.ColorRole.WindowText, text_color)
            self.guidance_text.setPalette(guidance_palette)
            
            # Add padding and border radius with stylesheet
            self.guidance_text.setStyleSheet(
                f"padding: 10px; border-radius: 5px; margin-bottom: 10px;"
            )
            
            self.records_input.setPlaceholderText(guidance['example'])
        else:
            self.guidance_text.setText("")
            # Reset to default palette
            self.guidance_text.setPalette(self.palette())
            self.guidance_text.setStyleSheet("")
            self.records_input.setPlaceholderText("")
        
        # Clear validation status when record type changes
        self.validation_status.setText("")
        self.validation_status.setStyleSheet("color: #666;")
        
        # Validate existing content with the new record type
        self.validate_input()
    
    def validate_record_content(self, record_type, content):
        """Validate record content based on type.
        
        Args:
            record_type (str): Record type
            content (str): Record content
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not content.strip():
            return False, "Record content cannot be empty"
            
        # Extract just the record type without description
        if ' (' in record_type:
            record_type = record_type.split(' (')[0]
            
        # Check if we have regex validation defined for this record type
        validation_pattern = None
        if record_type in RecordWidget.RECORD_TYPE_GUIDANCE:
            validation_pattern = RecordWidget.RECORD_TYPE_GUIDANCE[record_type].get('validation')
        
        # Specific validations for different record types
        if record_type in ['TXT', 'SPF']:
            # TXT records should be enclosed in quotes
            if not (content.startswith('"') and content.endswith('"')):
                return False, f"{record_type} records must be enclosed in double quotes (e.g., \"v=spf1 -all\")"
            # Check for proper escaping of quotes within the content
            if '\"' not in content and content.count('"') > 2:
                return False, f"Quotes within {record_type} content must be escaped with backslash (e.g., \"Example with \\\"quoted\\\" text\")"
                
        elif record_type in ['CNAME', 'MX', 'NS', 'PTR', 'DNAME']:
            # Check for trailing dots on domains
            if not content.strip().endswith('.'):
                return False, f"{record_type} record target must end with a trailing dot (e.g., example.com.)"
                
            # For MX records, check the priority format
            if record_type == 'MX':
                parts = content.strip().split()
                if len(parts) < 2:
                    return False, "MX records must include priority and domain (e.g., '10 mail.example.com.')"
                try:
                    priority = int(parts[0])
                    if priority < 0 or priority > 65535:
                        return False, "MX priority must be between 0 and 65535"
                except ValueError:
                    return False, "MX priority must be a valid integer"
            
        elif record_type == 'A':
            # Basic IPv4 validation (more comprehensive than regex)
            try:
                octets = content.strip().split('.')
                if len(octets) != 4 or any(not (0 <= int(o) <= 255) for o in octets):
                    return False, "Invalid IPv4 address format (must be four decimal numbers between 0-255)"
            except ValueError:
                return False, "Invalid IPv4 address format"
            
        elif record_type == 'AAAA':
            # Basic IPv6 format check
            if not ':' in content or len(content.replace(':', '').strip()) < 1:
                return False, "Invalid IPv6 address format"
                
        elif record_type == 'SRV':
            # Check SRV record format: priority weight port target
            parts = content.strip().split()
            if len(parts) < 4:
                return False, "SRV record must include priority, weight, port, and target (e.g., '0 5 443 example.com.')"
            try:
                priority, weight, port = map(int, parts[0:3])
                if not (0 <= priority <= 65535 and 0 <= weight <= 65535 and 0 <= port <= 65535):
                    return False, "SRV priority, weight, and port must be between 0 and 65535"
                if not parts[3].endswith('.'):
                    return False, "SRV target must end with a trailing dot (e.g., example.com.)"
            except ValueError:
                return False, "Invalid SRV record format"
                
        # Use regex validation if defined
        if validation_pattern:
            import re
            if not re.match(validation_pattern, content.strip()):
                return False, f"Invalid format for {record_type} record"
                
        return True, ""

    def validate_input(self, content=None):
        """Validate the record input based on selected record type.
        
        Args:
            content (str, optional): Content to validate. If not provided, uses current input.
                    
        Returns:
            bool: True if valid, False otherwise
        """
        record_type = self.type_combo.currentText()
        
        # Extract just the record type without description
        if ' (' in record_type:
            record_type = record_type.split(' (')[0]
            
        content = content if content is not None else self.records_input.toPlainText().strip()
            
        # If there's no content, clear validation status
        if not content.strip():
            self.validation_status.setText("")
            self.validation_status.setStyleSheet("color: #666;")
            return
            
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        all_valid = True
        errors = []
            
        # Validate each line
        for line in lines:
            is_valid, message = self.validate_record_content(record_type, line)
            if not is_valid:
                all_valid = False
                errors.append(message)
        
        # Update validation status
        if all_valid:
            self.validation_status.setText("✓ Valid record format")
            self.validation_status.setStyleSheet("color: #4caf50;")
        else:
            unique_errors = set(errors)  # Remove duplicates
            self.validation_status.setText("⚠️ " + "\n".join(unique_errors))
            self.validation_status.setStyleSheet("color: #c62828;")

    def log_action(self, message, level="info"):
        """Log an action and emit the log signal."""
        getattr(logger, level)(message)
        self.log_signal.emit(message, level)

    def format_api_error(self, response):
        """Format API error response for display in log widget.
        
        Args:
            response (dict): Error response from API
            
        Returns:
            str: Formatted error message
        """
        if not isinstance(response, dict):
            return str(response)
            
        # Extract message and format it
        if 'message' in response:
            error_msg = response['message']
            raw_response = response.get('raw_response', {})
            return f"{error_msg}\nDetails: {raw_response}"
        else:
            return str(response)
    
    def accept(self):
        """Process the dialog data when the user clicks OK."""
        subname = self.subname_input.text().strip()
        record_type = self.type_combo.currentText().strip()
        
        # Extract just the record type without description
        if ' (' in record_type:
            record_type = record_type.split(' (')[0]
        
        # Get the TTL value from the combo box's current data
        ttl = self.ttl_input.currentData()
        content = self.records_input.toPlainText().strip()
        
        # Parse multi-line content into a list of records
        records = [line.strip() for line in content.split('\n') if line.strip()]
        
        if not records:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing Content",
                "Please enter at least one record content"
            )
            return
        
        # Validate each record's content according to its type
        for record in records:
            is_valid, error_message = self.validate_record_content(record_type, record)
            if not is_valid:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Invalid Record Format",
                    f"{error_message}\n\nPlease check your record format and try again."
                )
                return
                
        # Special case for TXT and SPF records - ensure they are properly quoted
        if record_type in ['TXT', 'SPF']:
            # Make sure each record is enclosed in quotes
            records = [
                r if r.startswith('"') and r.endswith('"') else f'"{r}"' 
                for r in records
            ]
        
        # Handle API calls differently for edit vs. create
        if self.record:
            # Update existing record
            success, response = self.api_client.update_record(
                self.domain, subname, record_type, ttl, records
            )
        else:
            # Create new record
            success, response = self.api_client.create_record(
                self.domain, subname, record_type, ttl, records
            )
        
        if success:
            # Log successful operation with detailed information
            operation_type = "updated" if self.record else "created"
            record_details = f"{record_type} record for '{subname or '@'}' in domain '{self.domain}'"
            
            # For updates, show both old and new values
            if self.record:
                old_records = "\n".join(self.record.get('records', ['<empty>']))
                new_records = "\n".join(records)
                old_ttl = self.record.get('ttl', 0)
                self.log_signal.emit(f"Successfully {operation_type} {record_details} - TTL: {ttl} - changed content from '{old_records}' to '{new_records}'", "success")
            else:
                # For new records, just show the new values
                content_summary = "\n".join(records)
                self.log_signal.emit(f"Successfully {operation_type} {record_details} with TTL: {ttl}, content: {content_summary}", "success")
                
            # First accept the dialog to close it properly
            super(RecordDialog, self).accept()
            
            # Then trigger a refresh through the parent if possible
            if hasattr(self.parent, 'records_changed') and self.parent is not None:
                # Clear any cached data for the domain to ensure we get fresh data
                if hasattr(self.parent, 'cache_manager') and hasattr(self.parent, 'current_domain'):
                    self.parent.cache_manager.clear_domain_cache(self.parent.current_domain)
                # Signal that records have changed
                self.parent.records_changed.emit()
        else:
            # Handle the updated error response format
            if isinstance(response, dict) and 'message' in response:
                error_msg = response['message']
                raw_response = response.get('raw_response', {})
                
                # Format a user-friendly message based on the error type
                friendly_msg = ""
                
                # Case: Duplicate record error
                if 'already exists' in error_msg:
                    friendly_msg = ("A record with this name and type already exists.\n"
                                   "You must edit the existing record instead of creating a new one.")
                # Case: FQDN (fully qualified domain name) error
                elif 'fully qualified' in error_msg and 'end in a dot' in error_msg:
                    friendly_msg = ("The hostname must be fully qualified (end with a dot).\n"
                                   "Example: 'example.com.' instead of 'example.com'")
                # Case: Invalid record format
                elif raw_response and 'non_field_errors' in raw_response:
                    if isinstance(raw_response['non_field_errors'], list):
                        friendly_msg = "\n".join(raw_response['non_field_errors'])
                    else:
                        friendly_msg = str(raw_response['non_field_errors'])
                
                # Also log the full error for debugging
                self.log_signal.emit(f"API Error: {error_msg}\nDetails: {raw_response}", "error")
                
                # Display the error message box with detailed information
                msg_box = QtWidgets.QMessageBox(self)
                msg_box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
                msg_box.setWindowTitle("Error")
                msg_box.setText(f"Failed to {'update' if self.record else 'create'} record")
                
                # Add the friendly message if available
                if friendly_msg:
                    msg_box.setInformativeText(friendly_msg)
                else:
                    # If no specific friendly message, use the error message
                    msg_box.setInformativeText("The API rejected this record. See details for more information.")
                
                # Add the technical details
                msg_box.setDetailedText(f"API Error: {error_msg}\n\nFull Response: {raw_response}")
                
                # Allow the message box to size properly based on content
                layout = msg_box.layout()
                if layout is not None:
                    layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetDefaultConstraint)
                
                # Execute the message box
                msg_box.exec()
            else:
                # Fallback for legacy error format
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to {'update' if self.record else 'create'} record: {response}"
                )
                
                # Log the error
                self.log_signal.emit(f"API Error: {response}", "error")
