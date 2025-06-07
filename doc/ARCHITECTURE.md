# deSEC Qt DNS Manager - Architecture Documentation

## Overview

The deSEC Qt DNS Manager is a desktop application built with PyQt4 and Python that provides an interface for managing DNS records through the deSEC API. The application follows a modular architecture pattern to ensure maintainability, testability, and future portability.

## Core Components

### 1. Configuration Management

The `ConfigManager` class handles:

- Reading/writing configuration from `~/.config/desecqt/config.json`
- Securely storing API tokens using encryption
- Managing application settings (API URL, sync interval, etc.)

### 2. API Client

The `APIClient` class provides:

- Methods for interacting with the deSEC API
- Error handling and response parsing
- Connectivity checking and status management
- Implementation of all necessary API endpoints

### 3. Cache System

The `CacheManager` class implements a multi-layered caching system. For detailed information, refer to [CACHING.md](./CACHING.md).

### 4. UI Components

#### Main Window

- Implements the two-pane layout required in the specification
- Manages component interactions and event handling

#### Zone Management

- Lists all zones with search/filtering capability
- Provides add/delete zone functionality
- Handles zone selection to display records

#### Record Management

- Displays DNS records in a sortable table
- In-place editing and deletion of records
- Support for common record types (A, CNAME, MX, TXT)
- Type-specific validation and guidance

#### Configuration UI

- Authentication token management
- API settings configuration
- Sync interval settings

#### Logging

- Visual feedback for actions (success, error, warning)
- Timestamped action log display
- Detailed contextual information for all record operations
- Comparison of old and new values for record updates

## Data Flow

1. **Authentication Flow**
   - On startup, check for API token
   - If missing, prompt via AuthDialog
   - Store token securely in configuration

2. **Sync Flow**
   - Periodic sync based on configured interval
   - Manual sync via UI button
   - Update cache for offline access
   - Visual feedback for sync status

3. **Record Management Flow**
   - Zone selection -> Record loading
   - Record editing -> API update -> Cache update
   - Online/offline state management

## Design Patterns

1. **Model-View Separation**
   - Data logic (API client, cache) separated from presentation
   - UI components focused on display and interaction

2. **Observer Pattern**
   - Signal/slot connections for loose coupling
   - Event-driven updates between components

3. **Proxy Pattern**
   - Cache manager acts as a proxy for API data
   - Transparently serves data from different cache layers or API

## Security Considerations

- API tokens encrypted using user-specific key derivation
- No storage of plaintext credentials
- Confirmation required for destructive actions

## Extensibility

The modular design allows for:

- Easy addition of new record types
- Potential migration to Qt5/PySide in the future
- Enhanced validation or additional features

## Testing Approach

The application is designed for testability:

- Components with clear interfaces
- Dependency injection for easier mocking
- Separation of concerns

## Error Handling Flow

The application implements a comprehensive error handling system to provide clear feedback for users:

1. **API Client Error Detection**
   - The `_make_request` method in `APIClient` catches and categorizes HTTP errors
   - Parses error responses from the deSEC API to extract meaningful information
   - Handles special cases like duplicate records with specific error messages
   - Returns structured error data that includes both user-friendly messages and technical details

2. **Record Dialog Error Processing**
   - Client-side validation prevents common errors before API submission
   - Real-time validation with color-coded feedback for immediate user guidance
   - Dialog displays detailed error messages when API calls fail
   - Special handling for common errors (duplicate records, invalid formats, etc.)

3. **Record Creation Workflow**
   - Record input is validated for type-specific format requirements
   - Appropriate API endpoints are called based on record type
   - Error responses are processed and displayed to users
   - Successful creations update the UI and local cache

4. **Logging System**
   - All errors are logged to the application log widget
   - Error messages include both user-friendly descriptions and technical details
   - Log entries are timestamped and categorized by severity

This multi-layered approach ensures users receive appropriate guidance when errors occur while also providing detailed information for troubleshooting.
