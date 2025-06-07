#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Record Widget for deSEC Qt DNS Manager.
Displays and manages DNS records for a selected zone.
"""

import logging
import time
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool

from workers import LoadRecordsWorker

logger = logging.getLogger(__name__)

class RecordWidget(QtWidgets.QWidget):
    """Widget for displaying and managing DNS records."""
    
    # Custom signals
    records_changed = pyqtSignal()  # Emitted when records are changed
    log_message = pyqtSignal(str, str)  # Emitted to log messages (message, level)
    
    # Supported record types
    SUPPORTED_TYPES = [
        'A', 'AAAA', 'AFSDB', 'APL', 'CAA', 'CDNSKEY', 'CDS', 'CERT', 'CNAME', 'DHCID',
        'DNAME', 'DNSKEY', 'DLV', 'DS', 'EUI48', 'EUI64', 'HINFO', 'HTTPS', 'KX', 'L32',
        'L64', 'LOC', 'LP', 'MX', 'NAPTR', 'NID', 'NS', 'OPENPGPKEY', 'PTR', 'RP',
        'SMIMEA', 'SPF', 'SRV', 'SSHFP', 'SVCB', 'TLSA', 'TXT', 'URI'
    ]
    
    # Record type format guidance
    RECORD_TYPE_GUIDANCE = {
        'A': {
            'format': 'IPv4 address',
            'example': '192.0.2.1',
            'tooltip': 'Enter an IPv4 address (e.g., 192.0.2.1)',
            'validation': r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        },
        'AAAA': {
            'format': 'IPv6 address',
            'example': '2001:db8::1',
            'tooltip': 'Enter an IPv6 address (e.g., 2001:db8::1)',
            'validation': r'^[0-9a-fA-F:]+$'
        },
        'CAA': {
            'format': '<flags> <tag> <value>',
            'example': '0 issue "letsencrypt.org"',
            'tooltip': 'Certificate Authority Authorization record that specifies which CAs are allowed to issue certificates',
            'validation': r'^\d+\s+(issue|issuewild|iodef)\s+"[^"]+"$'
        },
        'SSHFP': {
            'format': '<algorithm> <type> <fingerprint>',
            'example': '2 1 123456789abcdef67890123456789abcdef67890',
            'tooltip': 'SSH Public Key Fingerprint record for SSH server authentication',
            'validation': r'^[1-4]\s+[1-2]\s+[0-9a-fA-F]+$'
        },
        'TLSA': {
            'format': 'usage selector matching-type certificate-data',
            'example': '3 1 1 d2abde240d7cd3ee6b4b28c54df034b97983a1d16e8a410e4561cb106618e971',
            'tooltip': 'TLS Authentication record to provide certificate association data for TLS servers',
            'validation': r'^[0-3]\s+[0-1]\s+[0-2]\s+[0-9a-fA-F]+$'
        },
        'AFSDB': {
            'format': 'subtype hostname',
            'example': '1 afsdb.example.com.',
            'tooltip': 'Enter subtype (1 or 2) and hostname with trailing dot',
            'validation': r'^[1-2]\s+[a-zA-Z0-9.-]+\.$'
        },
        'APL': {
            'format': 'address prefix list',
            'example': '1:192.0.2.0/24',
            'tooltip': 'IPv4 prefixes start with 1:, IPv6 with 2:, ! negates'
        },
        'CAA': {
            'format': 'flags tag "value"',
            'example': '0 issue "ca.example.com"',
            'tooltip': 'Flags (0-255), tag (issue, issuewild, iodef), value in quotes'
        },
        'CDNSKEY': {
            'format': 'flags protocol algorithm key',
            'example': '257 3 13 mdsswUyr3DPW132mOi8V9xESWE8jTo0dxCjjnopKl+GqJxpVXckHAeF+KkxLbxILfDLUT0rAK9iUzy1L53eKGQ==',
            'tooltip': 'Enter flags, protocol, algorithm, and base64 key data'
        },
        'CDS': {
            'format': 'key-tag algorithm digest-type digest',
            'example': '12345 13 2 123456789abcdef67890123456789abcdef67890123456789abcdef123456789',
            'tooltip': 'Enter key-tag, algorithm, digest-type, and digest value'
        },
        'CERT': {
            'format': 'type key-tag algorithm cert-data',
            'example': '1 12345 1 MIICW...base64data...Q==',
            'tooltip': 'Enter type, key-tag, algorithm, and certificate data'
        },
        'CNAME': {
            'format': 'domain name with trailing dot',
            'example': 'example.com.',
            'tooltip': 'Enter canonical name (FQDN with trailing dot). Only one CNAME record allowed per name.',
            'validation': r'^.+\.$'
        },
        'DHCID': {
            'format': 'base64 encoded identifier',
            'example': 'AAIBY2/AuCccgoJbsaxcQc9TUapptP69lOjxfNuVAA2kjEA=',
            'tooltip': 'Enter base64 encoded DHCP client identifier'
        },
        'DNAME': {
            'format': 'domain name with trailing dot',
            'example': 'example.com.',
            'tooltip': 'Enter delegation name (FQDN with trailing dot)',
            'validation': r'^.+\.$'
        },
        'DNSKEY': {
            'format': 'flags protocol algorithm key-data',
            'example': '257 3 13 mdsswUyr3DPW132mOi8V9xESWE8jTo0dxCjjnopKl+GqJxpVXckHAeF+KkxLbxILfDLUT0rAK9iUzy1L53eKGQ==',
            'tooltip': 'Enter flags, protocol, algorithm, and base64 key data'
        },
        'DLV': {
            'format': 'key-tag algorithm digest-type digest',
            'example': '12345 13 2 123456789abcdef67890123456789abcdef67890123456789abcdef123456789',
            'tooltip': 'Enter key-tag, algorithm, digest-type, and digest value'
        },
        'DS': {
            'format': 'key-tag algorithm digest-type digest',
            'example': '12345 13 2 123456789abcdef67890123456789abcdef67890123456789abcdef123456789',
            'tooltip': 'Enter key-tag, algorithm, digest-type, and digest value'
        },
        'EUI48': {
            'format': 'EUI-48 address with hyphens',
            'example': 'ab-cd-ef-01-23-45',
            'tooltip': 'Enter EUI-48/MAC address with hyphens (ab-cd-ef-01-23-45)',
            'validation': r'^[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}$'
        },
        'EUI64': {
            'format': 'EUI-64 address with hyphens',
            'example': 'ab-cd-ef-01-23-45-67-89',
            'tooltip': 'Enter EUI-64 address with hyphens (ab-cd-ef-01-23-45-67-89)',
            'validation': r'^[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}$'
        },
        'HINFO': {
            'format': '"cpu" "os"',
            'example': '"Intel" "Windows"',
            'tooltip': 'Enter CPU type and OS in quotes, separated by space'
        },
        'HTTPS': {
            'format': 'priority target [params]',
            'example': '1 . alpn="h2,h3"',
            'tooltip': 'Enter priority, target (. for origin), and optional params like alpn="h2,h3"'
        },
        'KX': {
            'format': 'priority target',
            'example': '10 kx.example.com.',
            'tooltip': 'Enter priority and key exchanger host with trailing dot'
        },
        'L32': {
            'format': 'preference locator',
            'example': '10 10.1.2.3',
            'tooltip': 'Enter preference (0-65535) and IPv4 address as locator'
        },
        'L64': {
            'format': 'preference locator',
            'example': '10 2001:db8:1:2',
            'tooltip': 'Enter preference (0-65535) and IPv6 address as locator'
        },
        'LOC': {
            'format': 'coordinates',
            'example': '51 30 12.748 N 0 7 39.611 W 0.00m 0.00m 0.00m 0.00m',
            'tooltip': 'Enter lat lon altitude and optional precision parameters'
        },
        'LP': {
            'format': 'preference FQDN',
            'example': '10 example.com.',
            'tooltip': 'Enter preference and FQDN with trailing dot'
        },
        'MX': {
            'format': 'priority mail server with trailing dot',
            'example': '10 mail.example.com.',
            'tooltip': 'Enter priority (0-65535) followed by mail server FQDN with trailing dot'
        },
        'NAPTR': {
            'format': 'order preference flags service regexp replacement',
            'example': '100 10 "u" "sip+E2U" "!^.*$!sip:info@example.com!" .',
            'tooltip': 'Enter order, preference, flags, service, regexp, and replacement (quoted as needed)'
        },
        'NID': {
            'format': 'preference value',
            'example': '10 0014:4fff:ff20:ee64',
            'tooltip': 'Enter preference and 64-bit node identifier value'
        },
        'NS': {
            'format': 'nameserver with trailing dot',
            'example': 'ns1.example.com.',
            'tooltip': 'Enter nameserver FQDN with trailing dot',
            'validation': r'^.+\.$'
        },
        'OPENPGPKEY': {
            'format': 'base64 encoded key data',
            'example': 'mQENBFVHm5sBCAD...base64data....',
            'tooltip': 'Enter OpenPGP public key data in base64 format'
        },
        'PTR': {
            'format': 'target domain with trailing dot',
            'example': 'example.com.',
            'tooltip': 'Enter target domain name with trailing dot',
            'validation': r'^.+\.$'
        },
        'RP': {
            'format': 'mbox-dname txt-dname',
            'example': 'admin.example.com. text.example.com.',
            'tooltip': 'Enter mailbox domain name and text domain name, both with trailing dots'
        },
        'SMIMEA': {
            'format': 'usage selector type certificate',
            'example': '3 0 0 MIIC...base64data...Q==',
            'tooltip': 'Enter usage, selector, type, and certificate data'
        },
        'SPF': {
            'format': 'SPF record in quotes',
            'example': '"v=spf1 mx a ip4:192.0.2.0/24 -all"',
            'tooltip': 'Enter SPF policy in quotes (same format as TXT record)'
        },
        'SRV': {
            'format': 'priority weight port target',
            'example': '0 5 443 example.com.',
            'tooltip': 'Specify location of service (e.g., XMPP, SIP). All values must be integers (0-65535) and the target must end with a dot.',
            'validation': r'^[0-9]+\s+[0-9]+\s+[0-9]+\s+[a-zA-Z0-9.\-_]+\.$'
        },
        'SSHFP': {
            'format': 'algorithm type fingerprint',
            'example': '2 1 123456789abcdef67890123456789abcdef67890',
            'tooltip': 'Enter algorithm (1=RSA, 2=DSA, 3=ECDSA, 4=ED25519), type (1=SHA-1, 2=SHA-256), and fingerprint'
        },
        'SVCB': {
            'format': 'priority target [params]',
            'example': '1 web.example.com. alpn="h2,h3" port=443',
            'tooltip': 'Enter priority, target hostname, and optional service parameters'
        },
        'TLSA': {
            'format': 'usage selector type certificate',
            'example': '3 0 1 123456789abcdef67890123456789abcdef67890123456789abcdef123456789',
            'tooltip': 'Enter usage (0-3), selector (0-1), type (0-2), and certificate data'
        },
        'TXT': {
            'format': 'text in quotes',
            'example': '"This is a text record"',
            'tooltip': 'Enter text record content in quotes ("example")',
            'validation': r'^".*"$'
        },
        'URI': {
            'format': 'priority weight target',
            'example': '10 1 "https://example.com/"',
            'tooltip': 'Enter priority, weight, and URI target in quotes'
        }
    }
    
    def __init__(self, api_client, cache_manager, config_manager=None, parent=None):
        """
        Initialize the record widget.
        
        Args:
            api_client: API client instance
            cache_manager: Cache manager instance
            config_manager: Configuration manager instance for settings (optional)
        """
        super().__init__()
        
        # Store API client for API interactions
        self.api_client = api_client
        self.cache_manager = cache_manager
        self.config_manager = config_manager
        self.current_domain = None
        self.records = []
        self.is_online = True  # Start assuming we are online
        
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
        self.records_table.setColumnCount(5)  # Name, Type, TTL, Content, Actions
        
        # Create header items with sort icons for sortable columns
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
        
        self.records_table.setHorizontalHeaderItem(0, name_header)
        self.records_table.setHorizontalHeaderItem(1, type_header)
        self.records_table.setHorizontalHeaderItem(2, ttl_header)
        self.records_table.setHorizontalHeaderItem(3, content_header)
        self.records_table.setHorizontalHeaderItem(4, actions_header)
        
        # Set table properties
        self.records_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.records_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.records_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.records_table.setAlternatingRowColors(True)
        # Enable interactive column width adjustment by the user
        self.records_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Interactive)  # Name column
        self.records_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Interactive)  # Type column
        self.records_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Interactive)  # TTL column
        self.records_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)  # Content column stretches
        self.records_table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Interactive)  # Actions column
        
        # Set initial default widths for better appearance
        self.records_table.setColumnWidth(0, 120)  # Name column
        self.records_table.setColumnWidth(1, 100)  # Type column
        self.records_table.setColumnWidth(2, 80)   # TTL column
        self.records_table.setColumnWidth(4, 140)  # Actions column
        self.records_table.verticalHeader().setVisible(False)
        
        # Enhance sort indicator visibility
        self.records_table.horizontalHeader().setSortIndicatorShown(True)
        self.records_table.horizontalHeader().sortIndicatorChanged.connect(self.sort_records_table)
        
        # Set default sort by name (column 0) in ascending order
        self.records_table.setSortingEnabled(True)
        self.records_table.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)
        self.records_table.cellDoubleClicked.connect(self.handle_cell_double_clicked)
        
        # Set table style to match zone list
        self.records_table.setStyleSheet(
            "QTableWidget { border: 1px solid #ccc; }"
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
        
        # Add stretch to align buttons to the left
        actions_layout.addStretch()
        
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
        """Enable or disable record editing controls based on online mode.
        
        Args:
            enabled (bool): Whether editing is enabled
        """
        # Enable/disable add button
        if hasattr(self, 'add_record_btn'):
            self.add_record_btn.setEnabled(enabled)
            # Update the tooltip to explain why it's disabled
            if not enabled:
                self.add_record_btn.setToolTip("Adding records is disabled in offline mode")
            else:
                self.add_record_btn.setToolTip("")
        
        # Enable/disable edit button
        for row in range(self.records_table.rowCount()):
            edit_btn = self.records_table.cellWidget(row, 4).layout().itemAt(0).widget()
            edit_btn.setEnabled(enabled)
            # Update the tooltip to explain why it's disabled
            if not enabled:
                edit_btn.setToolTip("Editing records is disabled in offline mode")
            else:
                edit_btn.setToolTip("Edit the selected record")
                
        # Enable/disable delete button
        for row in range(self.records_table.rowCount()):
            delete_btn = self.records_table.cellWidget(row, 4).layout().itemAt(1).widget()
            delete_btn.setEnabled(enabled)
            # Update the tooltip to explain why it's disabled
            if not enabled:
                delete_btn.setToolTip("Deleting records is disabled in offline mode")
            else:
                delete_btn.setToolTip("Delete the selected record")
    
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
            if self.api_client.is_online and self.cache_manager.is_cache_stale(cache_timestamp, 5):
                # Use worker for background API update
                self.fetch_records_async()
            
        # Only if cache is empty and we're online, fetch records asynchronously
        elif self.api_client.is_online:
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
        
        for row, record in enumerate(filtered_records):
            self.records_table.insertRow(row)
            
            # Name column (subname)
            name = record.get('subname', '')
            if not name:
                name = '@'  # Represent apex with @
            name_item = QtWidgets.QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, record)
            self.records_table.setItem(row, 0, name_item)
            
            # Type column
            record_type = record.get('type', '')
            type_item = QtWidgets.QTableWidgetItem(record_type)
            
            # Apply color coding to differentiate record types
            if record_type == 'A':
                type_item.setForeground(QtGui.QColor('#2196F3'))  # Blue
            elif record_type == 'AAAA':
                type_item.setForeground(QtGui.QColor('#3F51B5'))  # Indigo
            elif record_type in ['CNAME', 'DNAME']:
                type_item.setForeground(QtGui.QColor('#4CAF50'))  # Green
            elif record_type == 'MX':
                type_item.setForeground(QtGui.QColor('#FF9800'))  # Orange
            elif record_type in ['TXT', 'SPF']:
                type_item.setForeground(QtGui.QColor('#673AB7'))  # Deep Purple
            elif record_type in ['NS', 'DS', 'DNSKEY']:
                type_item.setForeground(QtGui.QColor('#E91E63'))  # Pink
                
            # Add tooltip with guidance if available
            if record_type in self.RECORD_TYPE_GUIDANCE:
                guidance = self.RECORD_TYPE_GUIDANCE[record_type]
                type_item.setToolTip(guidance['tooltip'])
                
            self.records_table.setItem(row, 1, type_item)
            
            # TTL column - store as number for proper numeric sorting
            ttl_item = QtWidgets.QTableWidgetItem()
            ttl_item.setData(Qt.ItemDataRole.DisplayRole, int(record.get('ttl', 0)))
            self.records_table.setItem(row, 2, ttl_item)
            
            # Content column (join multiple records with newlines)
            records_list = record.get('records', [])
            
            # Always show all records in the content, but control row height separately
            content_text = "\n".join(records_list)
                    
            content_item = QtWidgets.QTableWidgetItem(content_text)
            content_item.setToolTip("\n".join(records_list))  # Show all in tooltip regardless of display mode
            self.records_table.setItem(row, 3, content_item)
            
            # Actions column
            actions_widget = QtWidgets.QWidget()
            actions_layout = QtWidgets.QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 0, 4, 0)
            actions_layout.setSpacing(4)
            
            # Edit button
            edit_btn = QtWidgets.QPushButton("Edit")
            edit_btn.setFixedSize(60, 25)
            # Store the record directly instead of row index to avoid sorting/filtering issues
            record_ref = record  # Make sure we reference this specific record
            edit_btn.clicked.connect(lambda _, rec=record_ref: self.edit_record_by_ref(rec))
            # Store the record as a property on the button for Delete key handling
            edit_btn.setProperty('record_ref', record_ref)
            edit_btn.setEnabled(self.is_online)
            if not self.is_online:
                edit_btn.setToolTip("Unavailable in offline mode")
            
            # Delete button
            delete_btn = QtWidgets.QPushButton("Delete")
            delete_btn.setFixedSize(60, 25)
            # Store the record directly instead of row index to avoid sorting/filtering issues
            record_ref = record  # Make sure we reference this specific record
            delete_btn.clicked.connect(lambda _, rec=record_ref: self.delete_record_by_ref(rec))
            # Store the record as a property on the button for Delete key handling
            delete_btn.setProperty('record_ref', record_ref)
            delete_btn.setEnabled(self.is_online)
            if not self.is_online:
                delete_btn.setToolTip("Unavailable in offline mode")
            
            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(delete_btn)
            actions_layout.addStretch()
            
            self.records_table.setCellWidget(row, 4, actions_widget)
        
        # Only set column stretch mode for content column
        # Don't resize other columns to preserve user column width preferences
        self.records_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)  # Content column
        
        # Adjust row heights based on multiline display setting
        if self.show_multiline:
            # Allow rows to expand to fit content
            self.records_table.resizeRowsToContents()
        else:
            # Use fixed height rows in condensed mode
            default_height = self.records_table.verticalHeader().defaultSectionSize()
            for row in range(self.records_table.rowCount()):
                self.records_table.setRowHeight(row, default_height)
    
        # Re-enable sorting if it was enabled before
        self.records_table.setSortingEnabled(was_sorting_enabled)
        
        # Ensure the default sort is by Name column (if sorting was enabled)
        if was_sorting_enabled:
            self.records_table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    
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

    def show_add_record_dialog(self):
        """Show dialog to add a new record."""
        if not self.current_domain or not self.is_online:
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
        # Only enable sorting on Name (0), Type (1), TTL (2), and Content (3) columns
        if column <= 3:
            self.records_table.sortItems(column, Qt.SortOrder(order))
            
            # Update header text to indicate current sort column and direction
            header_items = ["Name", "Type", "TTL", "Content", "Actions"]
            for i in range(len(header_items)):
                item = self.records_table.horizontalHeaderItem(i)
                if i == column:
                    # Add sort direction indicator
                    arrow = "↑" if order == Qt.SortOrder.AscendingOrder else "↓"
                    item.setText(f"{header_items[i]} {arrow}")
                elif i < 4:  # Only add sort indicator to sortable columns
                    # Reset other sortable headers
                    item.setText(f"{header_items[i]} ↕")
                else:
                    # Actions column has no sort indicator
                    item.setText(header_items[i])
    
    def handle_cell_double_clicked(self, row, column):
        """Handle double-click on a cell."""
        # Ignore double-click on the Actions column
        if column != 4:  # 4 is the Actions column
            record_item = self.records_table.item(row, 0)
            record = record_item.data(Qt.ItemDataRole.UserRole)
            if record:
                self.edit_record_by_ref(record)
    
    def edit_record_by_ref(self, record):
        """Edit a record by reference instead of by row index.
        
        Args:
            record (dict): The record object to edit
        """
        if not self.is_online or not record:
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
        if not self.is_online:
            return
            
        record_item = self.records_table.item(row, 0)
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
        if not hasattr(self, 'records_table') or not self.is_online:
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
            # Get reference to the actions column containing edit/delete buttons
            actions_cell = self.records_table.cellWidget(row, 4)  # Column 4 is actions
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
        self.setMinimumWidth(500)
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
            'CDS': 'CDS (Child Delegation Signer)',
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
        self.guidance_text.setStyleSheet("color: #666; background-color: #f9f9f9; padding: 8px; border-radius: 4px;")
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
            self.guidance_text.setStyleSheet(
                "background-color: #f0f4f8; padding: 10px; border-radius: 5px; margin-bottom: 10px;"
            )
            self.records_input.setPlaceholderText(guidance['example'])
        else:
            self.guidance_text.setText("")
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
            self.validation_status.setStyleSheet("color: green;")
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
