# deSEC Qt DNS Manager — Record Management

## Supported Record Types

The application supports 37 record types via the deSEC API:

A, AAAA, AFSDB, APL, CAA, CDNSKEY, CERT, CNAME, DHCID, DNAME, DNSKEY, DLV, DS, EUI48, EUI64, HINFO, HTTPS, KX, L32, L64, LOC, LP, MX, NAPTR, NID, NS, OPENPGPKEY, PTR, RP, SMIMEA, SPF, SRV, SSHFP, SVCB, TLSA, TXT, URI

> **Note — DNSSEC types**: `DNSKEY`, `DS`, and `CDNSKEY` are auto-managed by deSEC. The API allows adding *extra* values for advanced multi-signer setups only — misuse can break DNSSEC for your domain. `CDS` is fully managed by deSEC and cannot be written via the API (returns 403); it is excluded from the type list entirely.

Each type has a format hint, realistic example, tooltip, and optional regex validation shown in the Add/Edit dialog.

---

## TTL Management

The deSEC API enforces the following TTL range for standard accounts:

| Limit | Value |
|-------|-------|
| Minimum | 3600 seconds (1 hour) |
| Maximum | 86400 seconds (24 hours) |

### Preset Options

| Value | Label |
|-------|-------|
| 3600 | 1 hour *(recommended minimum)* |
| 7200 | 2 hours |
| 14400 | 4 hours |
| 86400 | 24 hours *(maximum)* |

Lower values (60, 300, 600, 900, 1800) are shown for completeness but will typically be rejected by the API for standard accounts. Contact [support@desec.io](mailto:support@desec.io) for account-specific TTL adjustments.

---

## Multiline Record Content

Multiple values for a single RRset are entered one per line in the content area:

```
10 mail1.example.com.
20 mail2.example.com.
30 mail3.example.com.
```

The deSEC API accepts these as an array of record values (`records` field). By default the table shows the first 3 lines; toggle **View → Show Multiline Records** to see all lines.

---

## Record Operations

### Adding a Record

1. Select a zone from the zone list
2. Click **Add Record** — the RecordEditPanel slides in from the right (440 px)
3. Fill in:
   - **Type** — choose from the dropdown (format hint updates automatically)
   - **Subname** — leave blank for apex (`@`), or enter e.g. `www`, `mail`
   - **TTL** — select a preset
   - **Content** — one value per line; see format hint below the field
4. Click **Done** — the record is created via the API queue and a version snapshot is committed

### Editing a Record

1. Select a zone
2. Either:
   - Click **Edit** in the Actions column for that row
   - Double-click the row
3. The RecordEditPanel slides in with the current values pre-filled
4. Modify as needed
5. Click **Done** — the record is updated and a version snapshot is committed

### Deleting a Single Record

1. Select a zone
2. Either:
   - Click **Delete** in the Actions column
   - Select the row and press the **Delete** key
3. Confirm deletion in the two-step DeleteConfirmDrawer

### Batch Deleting Records

1. Check the checkbox in the leftmost column for each record to delete
   - Use **Select All** to check all visible rows
   - Use **Select None** to uncheck all
2. Click **Delete Selected (N)** (red button — count updates live)
3. Confirm in the two-step DeleteConfirmDrawer
4. A background worker deletes each record and logs success/failure individually
5. The table refreshes automatically when complete

> All batch controls are disabled in offline mode.

---

## Record Sorting and Filtering

### Sorting

Click any column header to sort:
- **Name** — alphabetical by subdomain
- **Type** — alphabetical by record type
- **TTL** — numerical
- **Content** — alphabetical

First click: ascending ↑; second click: descending ↓; third click: default (name ascending).
Sort preference is maintained when switching zones and after add/edit/delete.

### Filtering

Type in the search field above the table. Filtering is:
- Real-time (updates as you type)
- Case-insensitive
- Applied across all fields (name, type, TTL, content)

Press `Ctrl+F` to focus the filter field; `Escape` clears it.

---

## Global Search & Replace

For cross-zone record operations, use **File → Global Search & Replace**. See [UI-FEATURES.md](./UI-FEATURES.md#global-search--replace) for full documentation.

---

## Caching Behaviour

| Operation | Cache effect |
|-----------|-------------|
| Load records | Cached when zone is selected; served from cache on subsequent views |
| Add / Edit / Delete | Domain cache cleared immediately; table refreshed from API |
| Bulk delete | Domain cache cleared after worker completes |
| Zone sync | Full zone list refreshed; individual record caches preserved |

Records are loaded on demand (not pre-cached for all zones) to keep startup fast and avoid rate limiting.

---

## Troubleshooting

### Common API Errors

| Error | Cause | Solution |
|-------|-------|---------|
| "Another RRset with the same subdomain and type exists" | Duplicate RRset | Edit the existing record instead of creating a new one |
| "Ensure this value is less than or equal to 86400" | TTL too high | Use a TTL ≤ 86400 |
| "Ensure this value is greater than or equal to 3600" | TTL too low | Use a TTL ≥ 3600 (or request adjustment from deSEC) |
| 403 Forbidden on DNSKEY / DS / CDNSKEY | Auto-managed DNSSEC record | Only add extra values for multi-signer setups; see tooltip warning |
| 429 Too Many Requests | API rate limit hit | Lower the rate limit in Settings (File → Settings → API Rate Limit) |

### Validation Errors

The record dialog validates input client-side before submission:
- Format regex for supported types (e.g. CAA must match `\d+ (issue|issuewild|iodef) "..."`)
- Trailing-dot check for hostname fields (CNAME, MX, NS, etc.)
- Invalid content is flagged in red; a brief description is shown below the content area
