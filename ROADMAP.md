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

- [ ] **Multi-Profile Support**  
  Isolated tokens, cache, and settings per profile for managing multiple identities or environments.

- [ ] **Batch Actions via Selectable List/Table**  
  Enable multi-select with checkboxes for performing actions on multiple records or zones at once.

- [ ] **Import/Export Functionality**  
  Support for DNS zone import/export in various formats:
  - [ ] JSON (API-compatible)
  - [ ] YAML (Infra-as-Code tools)
  - [ ] BIND zone files
  - [ ] djbdns/tinydns format  
  *(and others as needed)*

- [ ] **Record Creation Wizards**  
  Guided setup for common DNS record configurations, including:
  - [ ] Google Workspace / Gmail
  - [ ] Microsoft 365
  - [ ] Mail-in-a-Box
  - [ ] Mailcow
  - [ ] Zimbra
  - [ ] Redmail
  - [ ] Let's Encrypt DNS challenges
  *(More to come)*

---

## 💡 Ideas Under Consideration

Feel free to open an issue or PR if you have suggestions or want to help implement any of these!
