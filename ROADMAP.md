# 📍 Project Roadmap

This document outlines planned features and improvements for future releases of the deSEC Qt6 DNS Manager. Community feedback and contributions are welcome!

---

## ✅ Planned Features

- [x] **Theme Support**  (in 0.3.4-beta)
  Light, dark, and system-based themes for better visual integration and accessibility.

- [ ] **Token Management**  
  Comprehensive token management interface with the following capabilities:
  - [ ] Create, view, edit, and delete API tokens
  - [ ] Set token permissions (create/delete domains, manage tokens)
  - [ ] Configure token policies for fine-grained access control
  - [ ] Set token expiration (max age and max unused period)
  - [ ] Restrict token usage by IP address/subnet
  - [ ] View token usage statistics (last used, created date)
  - [ ] Bulk operations for token management

- [ ] **Global Search and Replace**  
  Quickly search across all or selected zones and records, with optional batch replace functionality for efficient bulk edits.

- [x] **Multi-Profile Support** (in 0.5.0-beta)
  Isolated tokens, cache, and settings per profile for managing multiple identities or environments.
  - [x] Create, switch, rename, and delete profiles
  - [x] Complete data isolation per profile (API tokens, cache, settings)
  - [x] Automatic legacy configuration migration
  - [x] Profile management UI with safety checks
  - [x] Application restart on profile switch for complete isolation
  - [x] Comprehensive documentation (doc/PROFILES.md)

- [ ] **Batch Actions via Selectable List/Table**  
  Enable multi-select with checkboxes for performing actions on multiple records or zones at once.

- [x] **Import/Export Functionality** (Enhanced in v0.6.0-beta)
  Support for DNS zone import/export in various formats:
  - [x] JSON (API-compatible) - Direct deSEC API format for backups and programmatic processing
  - [x] YAML (Infrastructure-as-Code) - Human-readable format for version control and DevOps workflows
  - [x] BIND zone files - Industry standard format for DNS server configurations
  - [x] djbdns/tinydns format - Compact format for djbdns/tinydns server setups
  - [x] Enhanced import modes: Append, Merge, Replace with clear terminology and behavior
  - [x] Target zone selection with auto-creation for flexible import destinations
  - [x] Real-time progress tracking with percentage and status updates
  - [x] Auto-generated export filenames with timestamps for better organization
  - [x] Post-import synchronization for immediate UI updates
  - [x] API rate limiting (0-10 req/sec) to prevent timeouts during bulk operations
  - [x] Comprehensive UI with export/import dialogs, preview functionality, and progress tracking
  - [x] Multiple use cases: backup & recovery, DNS migration, Infrastructure-as-Code, environment sync
  - [x] Complete documentation in doc/IMPORT_EXPORT.md and doc/RATE-LIMIT.md

- [ ] **Record Creation Wizards**  
  Guided setup for common DNS record configurations, including:
  - [ ] Google Workspace / Gmail
  - [ ] Cloudflare
  - [ ] Microsoft 365
  - [ ] Mail-in-a-Box
  - [ ] Cloudron
  - [ ] Mailcow
  - [ ] rDNS Zone Setup
    - Create reverse DNS zones from IP prefixes (IPv4/IPv6)
    - Automatically generate PTR records for all IPs in the prefix
    - Customizable PTR record templates (e.g., {ip}.example.com or {dash-ip}.example.com)
    - Support for both in-addr.arpa (IPv4) and ip6.arpa (IPv6) zones
    - Batch PTR record generation with configurable TTL
    - Preview of zone configuration before creation
  - [ ] Zimbra
  - [ ] Redmail
  - [ ] Let's Encrypt DNS challenges
  - [ ] User defined templates
  *(More to come)*

---

## 💡 Ideas Under Consideration

Feel free to open an issue or PR if you have suggestions or want to help implement any of these!
