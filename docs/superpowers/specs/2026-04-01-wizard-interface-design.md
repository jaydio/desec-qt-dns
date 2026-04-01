# DNS Record Wizard — Design Spec

**Date:** 2026-04-01
**Status:** Draft
**Scope:** Unified wizard for preset and custom DNS record creation across multiple domains

---

## Overview

A step-by-step wizard sidebar page that lets users create DNS records across one or more domains. Two modes: **preset templates** (Google Workspace, Matrix, ACME, etc.) with variable input masks, and **custom** mode where users build their own record sets with variable substitution. Both modes share the same execution pipeline.

### Design Principles

- **API-derived state only** — no local-only user-facing entities. Templates are code, domain lists come from the API/cache. The client is stateless and portable.
- **Queue-first** — all record mutations flow through the existing `APIQueue` system. No direct API calls.
- **Preview before execute** — batch operations are high-stakes; every run shows a full preview with conflict detection before committing.

---

## Architecture

### New Files

| File | Purpose |
|---|---|
| `src/wizard_interface.py` | Sidebar page. `QWidget` subinterface containing a `QStackedWidget` with 7 wizard steps. Each step is a private widget class within the file. |
| `src/wizard_templates.py` | Pure data module. All preset templates as structured dicts. No UI code. |

### Integration Points

- **Constructor:** `WizardInterface(api_client, cache_manager, api_queue=None, version_manager=None, parent=None)` — follows codebase convention of optional `api_queue`, but the Execute step is disabled when `api_queue` is None
- **Sidebar registration:** `self.addSubInterface(self.wizard_interface, FluentIcon.BOOK_SHELF, "Wizard")` — placed after Search & Replace
- **Signals:** `log_message = Signal(str, str)` wired to `self.log_message`, `records_changed = Signal()` wired to refresh the DNS page
- **Validation:** imports `_validate_record_content` from `record_widget.py`
- **Domains:** fetched from `cache_manager.get_cached_zones()`
- **Record creation:** via `api_client.create_record()` enqueued as `QueueItem` with `PRIORITY_NORMAL`, category `"wizard"`
- **Versioning:** `version_manager.snapshot()` called per-domain after successful record creation

### No Changes Needed To

- `api_client.py` — existing `create_record()` / `update_record()` methods are sufficient
- `api_queue.py` — standard `QueueItem` enqueue pattern
- `cache_manager.py` — existing `get_cached_zones()` and record cache used as-is

---

## Wizard Step Flow

Seven steps via `QStackedWidget` with shared Back / Next / Execute navigation at the bottom.

### Step 1 — Mode Selection

Two large clickable radio cards:
- **"Use a Preset"** — choose from curated templates for common services
- **"Custom"** — build your own record set from scratch

Clicking a card highlights it and enables the Next button.

### Step 2 — Template / Record Builder

**Preset path:** Searchable list of templates grouped by category. Each template shows name, short description, and record count. Selecting one shows a read-only preview of the records it will create.

**Custom path:** Editable record table with columns: Type (ComboBox), Subdomain (LineEdit), TTL (ComboBox), Content (LineEdit). Buttons: Add Row, Remove Row. Content fields support `{variable}` placeholders. Minimum 1 row to proceed.

### Step 3 — Variable Input Mask

Dynamically generated form based on all `{variables}` found in the selected template or custom records:

- **`{domain}`** — reserved, shown as read-only label (auto-populated per domain at resolve time)
- **`{subdomain_prefix}`** — reserved, always shown. Optional field. When set, prepended to all subnames (e.g. prefix `staging` + subname `_dmarc` → `_dmarc.staging`)
- **Template-specific variables** — each gets a labeled LineEdit with hint text, default value (if any), and required/optional indicator

Validation: all required variables must be non-empty to proceed.

### Step 4 — Domain Selection

Checkbox list populated from `cache_manager.get_cached_zones()`:
- `SearchLineEdit` filter at top
- "Select All" / "Deselect All" buttons
- Count label: "X of Y domains selected"
- Minimum 1 domain selected to proceed

### Step 5 — Conflict Strategy

Radio group with three options and short descriptions:
- **Merge** — append new content to existing RRsets (e.g. add a second MX record)
- **Replace** — overwrite existing RRsets entirely with the new content
- **Skip** — leave existing records untouched, only create where the RRset doesn't exist

Default: Merge.

### Step 6 — Preview

Read-only table showing every operation that will be performed:

| Column | Description |
|---|---|
| Domain | Target domain |
| Subdomain | Resolved subname (variables substituted, prefix applied) |
| Type | Record type |
| TTL | TTL value |
| Content | Resolved content (variables substituted) |
| Status | `New` (green), `Conflict → Merge/Replace` (amber), `Skipped` (grey) |

**Pre-flight conflict detection:** When entering this step, the wizard checks cached records for all selected domains. For each planned record, it looks up whether a matching RRset (same subname + type) already exists and applies the chosen conflict strategy to determine the status.

**Summary line** at the top: "23 records across 5 domains (3 conflicts, 2 will be skipped)"

User confirms to proceed or goes back to adjust.

### Step 7 — Execution

Real-time progress view:
- Each non-skipped record becomes a `QueueItem` enqueued to `APIQueue`
- `ProgressBar` + status label for overall progress
- Per-domain rows update with success (green) or failure (red + error message)
- On completion: summary line ("18/20 succeeded, 2 failed")
- "Retry Failed" button re-enqueues only failed items
- "Start Over" button resets wizard to step 1
- `records_changed` signal emitted after all items complete
- `version_manager.snapshot()` called per-domain after successful creation

**Navigation rules:**
- Back is always available except on step 1 and during/after execution
- Next validates the current step before advancing
- Step 6 shows "Execute" instead of "Next"
- No going back from step 7 once execution starts

---

## Template Data Model

Templates in `wizard_templates.py` are plain dicts:

```python
TEMPLATES = [
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
            {"type": "MX",    "subname": "",     "ttl": 3600, "content": "1 aspmx.l.google.com."},
            {"type": "MX",    "subname": "",     "ttl": 3600, "content": "5 alt1.aspmx.l.google.com."},
            {"type": "MX",    "subname": "",     "ttl": 3600, "content": "5 alt2.aspmx.l.google.com."},
            {"type": "MX",    "subname": "",     "ttl": 3600, "content": "10 alt3.aspmx.l.google.com."},
            {"type": "MX",    "subname": "",     "ttl": 3600, "content": "10 alt4.aspmx.l.google.com."},
            {"type": "TXT",   "subname": "",     "ttl": 3600, "content": "\"v=spf1 include:_spf.google.com ~all\""},
            {"type": "TXT",   "subname": "_dmarc", "ttl": 3600, "content": "\"v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}\""},
            {"type": "CNAME", "subname": "{dkim_selector}._domainkey", "ttl": 3600, "content": "{dkim_selector}.domainkey.{domain}."},
        ],
    },
    # ... more templates
]
```

### Reserved Variables

| Variable | Behavior |
|---|---|
| `{domain}` | Auto-populated with each target domain. Read-only in the input mask. |
| `{subdomain_prefix}` | Optional. When set, prepended to all subnames: subname `_dmarc` + prefix `staging` → `_dmarc.staging` |

### Template Categories (v1)

| Category | Templates |
|---|---|
| **Email** | Google Workspace, Microsoft 365, Fastmail, Proton Mail, basic MX+SPF+DMARC |
| **Chat/Social** | Matrix (Synapse), XMPP/Jabber |
| **Web** | Let's Encrypt (CAA), HTTPS redirect (ALIAS/CNAME to hosting) |
| **Security** | DMARC (standalone), SPF (standalone), MTA-STS, DANE/TLSA |
| **ACME/Certificates** | DNS-01 challenge (TXT `_acme-challenge`), DNS-01 CNAME delegation (point to external validation domain), CAA with ACME account binding |
| **Verification** | Google Site Verification, Facebook Domain Verification |

---

## Variable Resolution

When resolving templates for the preview and execution:

1. Collect all variable values from step 3 input mask
2. For each selected domain:
   a. Set `{domain}` to the domain name
   b. For each record in the template:
      - Substitute all `{variables}` in `content` field
      - Substitute all `{variables}` in `subname` field
      - If `{subdomain_prefix}` is set and non-empty, append `.{subdomain_prefix}` to the subname (e.g. `_dmarc` → `_dmarc.staging`)
   c. Validate resolved content via `_validate_record_content(type, content)`

---

## Conflict Detection

When entering the preview step:

1. For each selected domain, retrieve cached records (subname + type → existing RRset)
2. For each planned record, check if a matching RRset exists (same subname + type on that domain)
3. Apply the chosen conflict strategy:
   - **Merge:** mark as "Conflict → Merge" — at execution time, GET the existing RRset content, append the new records, then PUT the combined set
   - **Replace:** mark as "Conflict → Replace" — PUT the new content directly, overwriting the existing RRset
   - **Skip:** mark as "Skipped" — no API call will be made
4. Records with no existing match are marked "New"

---

## Error Handling

- **Validation errors** (step 3/custom builder): inline error labels below the offending field, Next button disabled
- **API failures** (step 7): per-record error captured from `QueueItem` callback, displayed in the execution table, retryable via "Retry Failed"
- **Rate limiting:** handled transparently by `APIQueue`
- **Stale cache:** if conflict detection finds no cached records for a domain, the preview shows all records as "New" with a note that cache may be stale

---

## UI Components (Fluent Widgets)

| Component | Widget |
|---|---|
| Mode cards | Custom `QFrame` with radio behavior (like existing card pattern) |
| Template list | `ListWidget` grouped by category headers |
| Record table (custom) | `TableWidget` with ComboBox/LineEdit cell widgets |
| Variable inputs | `LineEdit` with `CaptionLabel` hints |
| Domain checkboxes | `CheckBox` items in a `QScrollArea` |
| Conflict strategy | `RadioButton` group |
| Preview table | Read-only `TableWidget` |
| Progress | `ProgressBar` + `CaptionLabel` status |
| Navigation | `PushButton` (Back) + `PrimaryPushButton` (Next/Execute) |
| Search filter | `SearchLineEdit` |
