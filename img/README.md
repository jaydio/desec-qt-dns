# Screenshots

All screenshots are from the dark theme on Linux. The sidebar is expanded to its full 180 px width unless otherwise noted.

---

## 01 — Main Window

<img src="01_dark_main_window.png" width="100%">

- Two-pane layout: zone list on the left (42/100 account limit), DNS records table on the right
- Zone list sorted alphabetically; active zone `aborttrap.zone` highlighted
- Records table search bar with dedicated **Type** and **TTL** filter fields to the right
- Records show colour-coded type labels (TXT, AAAA, A, NS, CNAME) with TTL and content
- Toolbar: **Add Record**, **Select All**, **Select None**, **Delete Selected**
- Sidebar shows all top-level items: DNS, DNSSEC, Search, **Wizard**, Import, Export, Queue, History, Profile, Tokens, Settings
- Bottom bar: About, Log Console, Sync, Online status (green), last sync timestamp

---

## 02 — Add Record Panel

<img src="02_dark_add_record.png" width="100%">

- `RecordEditPanel` slide-in (440 px) overlaying the records table
- Fields: Subdomain (`myrecord`), Type (`A (IPv4 Address)`), TTL (`3600 seconds (1 hour)`), Record Content (`1.1.1.1`)
- Green **"✓ Valid record format"** indicator with format hint and example below the content field
- Cancel / Done buttons at the bottom right

---

## 03 — Error Toast (Duplicate Record)

<img src="03_dark_error_toast_duplicate_record.png" width="100%">

- Red **InfoBar** toast anchored to the top-centre of the window: *"Record Save Failed — Error 400: Another RRset with the same subdomain and type exists for this domain. (Try modifying it.)"*
- Toast auto-dismisses after 8 seconds; no user interaction required
- Underlying DNS page and record table remain fully visible and usable

---

## 04 — DNSSEC Keys

<img src="04_dark_dnssec_records.png" width="100%">

- **DNSSEC** sidebar page with zone selector; `aborttrap.zone` loaded (1 key)
- Introductory text explains DS format vs. DNSKEY format and provider-specific requirements
- **DS Format** card: two digest variants in one card
  - SHA-256 section: Key Tag 18684 · Algorithm 13 (ECDSAP256SHA256) · Digest Type 2
  - SHA-384 section: Key Tag 18684 · Algorithm 13 · Digest Type 4 · full digest hex shown
- **DNSKEY Format** card: Flags 257 (KSK) · Protocol 3 · Algorithm 13 (ECDSAP256SHA256) · Public Key field
- **Copy** button on each card; **Validate DNSSEC setup** links to Verisign Debugger and DNSViz
- Collapsible amber **DNSSEC migration warning** card at the bottom with multi-signer (RFC 8901) and "go insecure" guidance

---

## 05 — Global Search & Replace

<img src="05_dark_search.png" width="100%">

- **Search** sidebar page; 4 results across 3 zones after searching content `1.1.1.1`
- Search filters: Subname, Content, Type, TTL, Zone, Use regex toggle
- Results table: Zone, Subname, Type, TTL, Content columns
- Actions panel (right): Replace Content (Find / Replace / Subname / TTL fields), Delete Records, Change Log
- **Select All**, **Select None**, **Export Results…** controls at the bottom

---

## 06 — Import

<img src="06_dark_import.png" width="100%">

- **Import** sidebar page; left pane: file selector with Browse button and read-only preview area
- Right pane — Import Settings:
  - **Format**: JSON (API-compatible), YAML (Infrastructure-as-Code), BIND Zone File, djbdns/tinydns
  - **Target Zone**: use zone name from file (or select/create)
  - **Existing Records Handling**: Append / Merge / Replace with descriptions
- **Preview Import** and **Import Zone** buttons at the bottom

---

## 07 — Export

<img src="07_dark_export.png" width="100%">

- **Export** sidebar page; left pane: search filter + scrollable zone list (42 zones); `dnsdisaster.zone` selected
- Right pane — Export Settings:
  - **Format**: JSON, YAML, BIND Zone File, djbdns/tinydns
  - **Options**: Include metadata (timestamps) checkbox ticked
  - **Output File**: auto-generated filename field with Browse and Auto-Generate buttons
- **Export (1)** primary button at the bottom right; **Select All** / **Select None** below the zone list

---

## 08 — Queue Overview

<img src="08_dark_queue_overview.png" width="100%">

- **Queue** sidebar page; left pane shows 0 pending items
- Right pane — History: 975 completed, 42 failed entries with columns Action, Status, Duration, Time
- Entries include: Check token permissions (OK), Fetch account limit (OK), Check connectivity (OK), DNSSEC keys for aborttrap.zone (OK), Create CNAME for www in aborttrap.zone (**Failed**)
- Filter bar above history; status dropdown (All / OK / Failed)
- Controls: **Cancel Selected**, **Pause**, **Retry Failed**, **Clear History**

---

## 09 — Queue Entry Detail

<img src="09_dark_queue_entry.png" width="100%">

- `QueueDetailPanel` slide-in (480 px) for the selected failed entry
- Header: *"Create CNAME for www in aborttrap.zone"*
- Metadata: Status **✗ Failed** (red), Category: records, Priority: Normal, Created/Completed timestamps, Duration: 4.20 s
- **Error** section in red: *"Error 400: Another RRset with the same subdomain and type exists for this domain."*
- **Request** JSON block and **Response** JSON block with full API payload
- **Copy Response** button; **Retry Failed (1)** and **Clear History** in the toolbar

---

## 10 — Version History

<img src="10_dark_version_history.png" width="100%">

- **History** sidebar page; 6 versioned zones listed on the left; `waborttrap.site` selected
- Timeline on the right: 6 commits with date, descriptive message (e.g. *"Created A record for 'test1'"*, *"Pre-delete snapshot (zone destroyed)"*), and short git hash
- **Record preview** panel at the bottom shows the zone state at the selected commit (name, TTL, type, content columns)
- **Restore This Version** primary button; **Delete Selected** for removing old snapshots

---

## 11 — Token Manager

<img src="11_dark_token_overview.png" width="100%">

- **Tokens** sidebar page; token list (4 tokens) with columns: Name (sorted A→Z), Created, Last Used, Perms
- `test` token selected; **Token Details** right panel with **Details** and **RRset Policies** tabs
- Details tab — Token Info: ID (with Copy button), Owner, Created, Last Used, Valid, MFA type
- Settings section: Name field, permission checkboxes (Create Domains, Delete Domains, Manage Tokens, Auto Policy), Max Age, Max Unused Period, Allowed Subnets (0.0.0.0/0 + ::/0)
- **Save Changes** button; **New Token**, **Delete**, **Refresh** at the bottom of the token list

---

## 12 — Token Policy Edit Panel

<img src="12_dark_token_policy.png" width="100%">

- `TokenPolicyPanel` slide-in (400 px) overlaying the Token Details area
- Title: **Edit Policy**; description text explains blank fields act as catch-all
- Fields: Domain (`test123.com`), Subname (blank = match all), Type (Any — match all types), Write (**Allow write access** checkbox ticked)
- **Add Policy**, **Cancel**, **Save** buttons; underlying Policies tab shows existing entries

---

## 13 — Settings

<img src="13_dark_settings_global.png" width="100%">

- **Settings** sidebar page; two-column `SettingCardGroup` layout
- Left column — **Connection**: API URL (`https://desec.io/api/v1`), API Token (Change Token button); **Synchronization**: Sync Interval (15 min), API Rate Limit (0.3 req/s)
- Right column — **Appearance**: Theme (Follow OS / Auto); **Queue**: Persist Queue History (On), History Retention (5000 entries); **Advanced**: Debug Mode (On), Token Manager shortcut (Open button)
- **Save Settings** primary button at the bottom right

---

## 14 — Log Console

<img src="14_dark_log_console.png" width="100%">

- **Log Console** sidebar page; 4 messages with timestamps
- Colour coding: default text (info) · green (success) · red (error)
- Messages shown: *Loaded data from cache* (info), *Retrieved 42 zones from API* (green), *Queued: Create CNAME for 'www' in aborttrap.zone* (info), *Failed to save record: Error 400…* (red, wrapped)
- **Clear** button and message count (`4 messages`) in the header

---

## 15 — Collapsed Sidebar

<img src="15_dark_menu_collapsed.png" width="100%">

- Same DNS page as screenshot 01 with the sidebar collapsed to icon-only mode (≈ 48 px)
- All sidebar items visible as icons only: globe, shield (DNSSEC), search, arrows (Import/Export), send (Queue), update (History), people, certificate, settings, info, history, sync, wifi
- Provides maximum horizontal space for the two-pane DNS view
- Collapse/expand toggled with the hamburger button at the top-left

---

## 16 — Wizard: Choose Mode

<img src="16_dark_wizard_mode.png" width="100%">

- **Wizard** sidebar page — Step 1 of 7: Choose Mode
- Two clickable cards: **Use a Preset** (curated templates) and **Custom** (build your own record set)
- Cards show description text; border highlights on selection
- **Next** button at bottom right (disabled until a mode is selected)

---

## 17 — Wizard: Preset Template List

<img src="17_dark_wizard_presets.png" width="100%">

- Step 2 of 7: Select Template (preset mode)
- Left pane: categorised template list grouped by section headers (Google, Microsoft 365, Proton, Email Providers, Self-Hosted Email, Transactional Email, Web Platforms, etc.)
- Each template shows record count; **Search templates** filter bar at the top
- Right pane: read-only preview table (Type, Name, TTL, Content) for the selected template
- **Start Over** and **Back** / **Next** navigation at the bottom

---

## 18 — Wizard: Multi-Template Selection

<img src="18_dark_wizard_multi_select.png" width="100%">

- Step 2 with multiple templates selected via Ctrl+click (Mailgun + Shopify)
- Header shows **"2 templates selected"** with template names
- Preview table combines records from all selected templates (MX, TXT, A, CNAME across both)
- Demonstrates combining unrelated services in a single wizard run

---

## 19 — Wizard: Variable Input

<img src="19_dark_wizard_variables.png" width="100%">

- Step 3 of 7: Fill In Variables
- Clean table layout with columns: **Variable**, **Value**, **Hint**
- `{domain}` shown as automatic (read-only); `{subdomain_prefix}` optional
- Template-specific variables with pre-filled defaults, placeholder hints, and Required/Optional status
- Variables auto-discovered from all selected templates

---

## 20 — Wizard: Domain Selection

<img src="20_dark_wizard_domains.png" width="100%">

- Step 4 of 7: Select Domains
- Full-height ListView with Ctrl+click / Shift+click multi-select (matching Export page pattern)
- **Filter domains** search bar at the top; count label ("1 of 42 domains selected")
- **Select All** / **Select None** buttons at the bottom
- Multiple domains highlighted with teal accent bar

---

## 21 — Wizard: Conflict Strategy

<img src="21_dark_wizard_conflict.png" width="100%">

- Step 5 of 7: Conflict Strategy
- Three radio options with descriptions:
  - **Merge** — append to existing record set
  - **Replace** — overwrite existing (selected in screenshot, shown with filled radio)
  - **Skip** — leave existing untouched
- Applies when a record with the same subdomain + type already exists on the target domain

---

## 22 — Wizard: Execution Results

<img src="22_dark_wizard_execution.png" width="100%">

- Step 7 of 7: Execution
- Summary: **"Complete: 6/6 succeeded"** with full-width teal progress bar
- Results table: Domain, Name, Type, Content, Result columns
- All 6 operations show green **"Success"** — Mailgun MX (grouped 2 values), SPF TXT, DKIM TXT, Shopify A, CNAME www, verification TXT
- **Start Over** button to begin a new wizard run
