# 📍 Project Roadmap

This document outlines planned features and improvements for future releases of the deSEC Qt6 DNS Manager. Community feedback and contributions are welcome!

---

## ✅ Planned Features

- [x] **Theme Support**  (in 0.3.4-beta)
  Light, dark, and system-based themes for better visual integration and accessibility.

- [x] **Token Management** (in 0.9.0-beta)
  Comprehensive token management interface with the following capabilities:
  - [x] Create, view, edit, and delete API tokens
  - [x] Set token permissions (create/delete domains, manage tokens)
  - [x] Configure token policies for fine-grained access control
  - [x] Set token expiration (max age and max unused period)
  - [x] Restrict token usage by IP address/subnet
  - [x] View token usage statistics (last used, created date)
  - [ ] Bulk operations for token management (future)

- [x] **Global Search and Replace** (in 0.10.0-beta)
  Search across all zones and records with optional batch replace for efficient bulk edits.

- [x] **Multi-Profile Support** (in 0.5.0-beta)
  Isolated tokens, cache, and settings per profile for managing multiple identities or environments.
  - [x] Create, switch, rename, and delete profiles
  - [x] Complete data isolation per profile (API tokens, cache, settings)
  - [x] Automatic legacy configuration migration
  - [x] Profile management UI with safety checks
  - [x] Application restart on profile switch for complete isolation
  - [x] Comprehensive documentation (doc/PROFILES.md)

- [x] **Account Domain Limit Display** (in 0.12.0-beta)
  Zone list header shows current/maximum domain count (e.g. "Total zones: 3/100") fetched live from the deSEC account API.

- [x] **Batch Actions via Selectable List/Table** (in 0.11.0-beta)
  Multi-select checkboxes on the DNS records table with Select All / Select None and bulk Delete Selected (N) action.

- [x] **Import/Export Functionality** (Enhanced in v0.6.0-beta)
  Support for DNS zone import/export in various formats:
  - [x] JSON (API-compatible) - Direct deSEC API format for backups and programmatic processing
  - [x] YAML (Infrastructure-as-Code) - Human-readable format for version control and DevOps workflows
  - [x] BIND zone files - Industry standard format for DNS server configurations
  - [x] djbdns/tinydns format - Compact format for djbdns/tinydns server setups
  - [x] Enhanced import modes: Append, Merge, Replace with clear terminology and behavior
  - [x] Target zone selection with auto-creation for flexible import destinations
  - [x] Real-time progress tracking with percentage and status updates

- [x] **Record Timestamp Tooltips** (Added in v0.7.0-beta)
  Enhanced user experience with hover tooltips showing DNS record metadata:
  - [x] Creation and last modification timestamps for all DNS records
  - [x] Clean UTC timestamp display on hover over any record table column
  - [x] Non-intrusive interface enhancement with timestamp insights
  - [x] Timestamps sourced directly from deSEC API cache data
  - [x] Auto-generated export filenames with timestamps for better organization
  - [x] Post-import synchronization for immediate UI updates
  - [x] API rate limiting (0-10 req/sec) to prevent timeouts during bulk operations
  - [x] Comprehensive UI with export/import dialogs, preview functionality, and progress tracking
  - [x] Multiple use cases: backup & recovery, DNS migration, Infrastructure-as-Code, environment sync
  - [x] Complete documentation in doc/IMPORT_EXPORT.md and doc/RATE-LIMIT.md

- [x] **Bulk Export Functionality** (Added in v0.8.0-beta)
  Export multiple DNS zones simultaneously with ZIP compression:
  - [x] Bulk export toggle with adaptive UI for single/multiple zones
  - [x] Scrollable zone selection list with checkboxes
  - [x] Select All/Select None buttons for easy zone management
  - [x] ZIP compression of multiple zone files into single archive
  - [x] Progress tracking during bulk export operations
  - [x] Support for all existing export formats (JSON, YAML, BIND, djbdns)
  - [x] Graceful error handling - continues with other zones if one fails
  - [x] Auto-generated ZIP filenames with timestamp
  - [x] Optimized UI layout that adapts to number of available zones
  - [x] Enhanced documentation in doc/IMPORT_EXPORT.md

- [x] **Fluent Design UI Overhaul** (in v2.0.0-beta)
  Complete migration from PyQt6 to PySide6 + PySide6-FluentWidgets with Fluent Design System.
  - [x] FluentWindow with sidebar navigation (replaces menu bar)
  - [x] Slide-in panels for all forms — records, zones, tokens, profiles (replaces popup dialogs)
  - [x] Two-step confirmation drawers for destructive actions (replaces QMessageBox)
  - [x] Notification drawers for errors, warnings, and success messages
  - [x] Theme-aware styling throughout (dark/light/auto)

- [x] **Central API Queue** (in v2.0.0-beta)
  All API calls processed through a central background queue thread.
  - [x] Priority-based processing (High / Normal / Low)
  - [x] Auto-retry on transient 429 rate-limit responses (up to 3 retries)
  - [x] Adaptive rate limiting — halves rate on 429, self-heals over time
  - [x] Cooldown mode for extended rate limits (>60s) with auto-resume
  - [x] Queue monitor sidebar page (pending, history, detail view, batch retry)
  - [x] Persistent queue history (configurable, JSON)

- [x] **Git-Based Zone Version History** (in v2.0.0-beta)
  Automatic zone versioning backed by a local Git repository.
  - [x] Snapshot committed on every record mutation (create, update, delete)
  - [x] Version history sidebar page with commit timeline per zone
  - [x] Record preview for any historical version
  - [x] One-click restore via bulk API PUT
  - [x] Delete version history per zone

- [x] **Record Creation Wizard** (in v2.1.0-beta)
  Step-by-step wizard for creating DNS records across multiple domains.
  - [x] Preset templates: Google Workspace, Microsoft 365, Fastmail, Proton Mail, Basic MX+SPF+DMARC
  - [x] Chat/Social: Matrix (Synapse), XMPP/Jabber
  - [x] Web: Let's Encrypt CAA, Web Hosting CNAME
  - [x] Security: DMARC, SPF, MTA-STS, DANE/TLSA
  - [x] ACME/Certificates: DNS-01 TXT, DNS-01 CNAME delegation, CAA with account binding
  - [x] Verification: Google Site, Facebook Domain
  - [x] Custom record builder with {variable} substitution
  - [x] Multi-template selection (combine multiple presets in one run)
  - [x] Multi-domain checkbox selection with search filter
  - [x] Conflict strategy: Merge / Replace / Skip
  - [x] Preview with conflict detection before execution
  - [x] APIQueue integration with progress tracking and retry
  - [ ] Slide-in template search panel (like RecordEditPanel)
  - [ ] Extended email templates: Tutanota/Tuta, Infomaniak, Mailfence, Zoho Mail
  - [ ] Extended web hosting: Netlify, Vercel, GitHub Pages, Cloudflare Pages
  - [ ] Service provider bundles: Google (Workspace + Verification), Microsoft (365 + Teams + Intune), Proton (Mail + VPN)
  - [ ] Subdomain delegation mode (create subdomain + NS records)

- [ ] **Reverse DNS Zone Creation**
  Batch-create reverse DNS zones from IP prefixes via the Add Zone dialog.
  - [ ] Forward vs reverse toggle in Add Zone
  - [ ] Accept IPv4 /24 and IPv6 /64 prefixes
  - [ ] Auto-encode to in-addr.arpa / ip6.arpa zone names
  - [ ] Batch zone creation via APIQueue

- [ ] **Keyboard Shortcuts / Hotkeys**
  Configurable keyboard shortcuts for common actions.
  - [ ] Shortcut reference dialog / cheat sheet
  - [ ] Customizable keybindings
  - [ ] Navigation shortcuts (switch between sidebar pages)
  - [ ] Action shortcuts (sync, search, create record, etc.)

- [ ] **Per-Profile Queue & History**
  Isolate queue entries and version history per profile (currently shared).
  - [ ] Queue history stored under profile directory
  - [ ] Version history (git repos) scoped to active profile
  - [ ] Migration of shared history on first profile switch

- [ ] **SPF Record Builder & RRset Merging**
  Intelligent handling of SPF and other TXT records that need merging or length management.
  - [ ] SPF builder: visual editor for constructing SPF records from includes, IPs, and mechanisms
  - [ ] SPF flattening/compression: resolve `include:` chains to direct IP ranges to reduce DNS lookups (10-lookup limit)
  - [ ] SPF record splitting: auto-split long SPF into multiple `include:` sub-records when exceeding 255-byte TXT limit
  - [ ] TXT RRset merging: when wizard/batch creates TXT records at the same subname, offer to merge into existing RRset
  - [ ] Length validation: warn when TXT records approach the 512-byte UDP response limit or 255-byte string limit
  - [ ] FQDN-to-IP resolution for corporate SPF lists (replace verbose include chains with ip4:/ip6: blocks)

- [ ] **Multi-Select UX Discoverability**
  Make it clearer in lists and tables where multi-selection is available.
  - [ ] Subtle visual indicator or onboarding tooltip for multi-select (Ctrl+click, Shift+click, Ctrl+A)
  - [ ] Applies to: DNS record table, Export zone list, Wizard template/domain selection
  - [ ] Consider status bar hint, first-time tooltip, or selection count in header

---

## 💡 Ideas Under Consideration

Feel free to open an issue or PR if you have suggestions or want to help implement any of these!
