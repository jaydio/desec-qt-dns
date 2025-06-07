# deSEC Qt DNS Manager: UI Features Guide

This document provides information about the user interface features in the deSEC Qt DNS Manager application.

## Main Interface Components

The application interface consists of several key components:

1. **Main Window**: Contains the menu bar, zone list, and record management panel
2. **Zone List Panel**: Displays available DNS zones with filtering capabilities
3. **Record Management Panel**: Shows and manages records for the selected zone
4. **Log Panel**: Displays notification messages and operation results

## Zone Management Features

### Zone List Display

- All zones are listed in alphabetical order for easy navigation
- Zone selection updates the record panel automatically
- Background loading ensures UI remains responsive during zone retrieval

### Zone Filtering

To filter zones:
1. Enter search text in the search field above the zone list
2. The list filters in real-time to show only matching zone names
3. Clear the search field to show all zones again

## Record Management Features

### Record Display

The record management panel shows all records for the selected zone with the following information:
- Record name (subdomain)
- Record type (A, AAAA, MX, etc.)
- TTL value
- Record content

By default, records with multiple lines of content display only the first 3 lines followed by a count of remaining entries. To view all content lines, use the "Show Multiline Records" option in the View menu.

### Record Sorting

The records table supports advanced sorting options:

- **Default Sorting**: Records are sorted by name in ascending order by default
- **Column Sorting**: Click any column header to sort by that column
  - Name: Sort alphabetically by subdomain
  - Type: Sort alphabetically by record type
  - TTL: Sort numerically by TTL value
  - Content: Sort alphabetically by record content
- **Sort Direction**: 
  - First click: Sort ascending (↑)
  - Second click: Sort descending (↓)
  - Third click: Return to default sorting
- **Sort Indicators**: Arrows in column headers show current sort direction

### Record Filtering

To filter records within a zone:
1. Enter search text in the search field above the record list
2. The list will filter in real-time to show only matching records
3. Filtering works across all fields (name, type, TTL, and content)

## Performance Optimizations

The application includes several performance optimizations for a smooth user experience:

- **Asynchronous Loading**: Zone and record data loads in background threads to keep the UI responsive
- **Multi-layered Caching**: Data is cached in memory and on disk for fast access
- **O(1) Indexing**: Zone and record lookups use optimized indexing for instant access
- **Immediate UI Updates**: The UI updates immediately after operations, then syncs with the API

## Notifications and Logging

The application provides several types of notifications:

- **Success Messages**: Displayed in green when operations complete successfully
- **Information Messages**: Displayed in blue for general information
- **Warning Messages**: Displayed in orange for potential issues
- **Error Messages**: Displayed in red when operations fail

All notifications are also written to the log file for reference.

## Navigation Shortcuts

The following keyboard shortcuts are available:

- **Ctrl+F**: Cycle and focus through search filter fields
- **F5**: Refresh current view
- **Escape**: Clear active search filter
- **Delete**: Delete selected zone or record (with confirmation)

## Offline Mode

When operating offline:

- The application will use cached data for both zones and records
- Modification operations are disabled until online connectivity is restored
- A notification appears to indicate offline mode is active

## View Menu Options

The View menu provides several display options:

### Log Console

- Toggle visibility of the log console at the bottom of the main window
- Keyboard shortcut: Ctrl+L
- The setting is remembered across application restarts

### Show Multiline Records

- When enabled, shows all lines for records with multiple entries
- When disabled (default), shows only the first 3 lines followed by a count of additional entries
- Setting is remembered across application restarts
- Useful for complex TXT records, multiple MX entries, or any record type with multiple values

## Advanced Features

### Sorting Persistence

- Sort preferences are maintained during your session
- If you select a sort order for a zone's records, that sort order will be preserved if you:
  - Switch to another zone and return
  - Add, edit, or delete records
  - Refresh the record list

### Automatic Refresh

The record list will automatically refresh when:
- A new zone is selected
- A record is added, edited, or deleted
- The refresh button is clicked
- The configured sync interval has passed and cache is stale
