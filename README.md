# deSEC Qt6 DNS Manager

![deSEC DNS Manager - Main Window](img/0.3.0/01-main-window.png)

![deSEC DNS Manager - Edit Dialog](img/0.3.0/02-edit-dialog-mx.png)

A Qt6 desktop application for managing DNS zones and records using the deSEC DNS API.

## ✨ Key Features

- **Multi-Profile Support** - Manage multiple deSEC accounts or environments with isolated tokens, cache, and settings per profile
- **Enhanced Import/Export Functionality** - Backup, migrate, and manage DNS configurations with advanced features: multiple formats (JSON, YAML, BIND, djbdns), real-time progress tracking, flexible import modes (Append/Merge/Replace), and API rate limiting
- **Intuitive Zone Management** - Create, delete, and manage DNS zones with a clean interface
- **Comprehensive Record Support** - Full support for all DNS record types (A, AAAA, CNAME, MX, TXT, SRV, CAA, and more)
- **Real-time Sync** - Automatic synchronization with deSEC API
- **Offline Mode** - Continue working with cached data when offline
- **Smart Caching** - Intelligent caching system for improved performance
- **Theme Support** - Light, dark, and system-based themes
- **Robust Error Handling** - Clear error messages and graceful failure handling
- Authentication with deSEC API token
- Zone management (add, delete, list, search)
- DNS record management (view, add, edit, delete)
- Support for the following resource record types: ```A, AAAA, AFSDB, APL, CAA, CDNSKEY, CDS, CERT, CNAME, DHCID, DNAME, DNSKEY, DLV, DS, EUI48, EUI64, HINFO, HTTPS, KX, L32, L64, LOC, LP, MX, NAPTR, NID, NS, OPENPGPKEY, PTR, RP, SMIMEA, SPF, SRV, SSHFP, SVCB, TLSA, TXT, URI```
- Reverse DNS Zone support
- Record-specific TTL management
- Data caching for offline access
- Clear Cache functionality to refresh data
- Two-pane layout for easy navigation
- Configuration editor for API settings
- Performance-optimized with indexed lookups
- Full keyboard navigation with shortcuts
- DNS record table sorting by clicking column headers
- Double-click to edit records
- Multiline DNS records display for better readability
- Integrated log console within the main window
- Offline mode with visual indicators
- Elapsed time display since last sync

## Limitations

- TTL values are limited to a range of 3600-86400 seconds (1-24 hours) by the deSEC API
- For values outside this range, contact deSEC directly for account-specific adjustments

## Unsupported

- Automatically managed resource records are not exposed via deSEC API, namingly: ```DNSKEY, DS, CDNSKEY, CDS, NSEC3PARAM, RRSIG```
- Additional resource records of the following types can be added e.g. to add extra public keys for DNSSEC: ```DNSKEY, DS, CDNSKEY```
- See [DNSSEC Caveat](https://desec.io/api/v1/records#dnssec-caveat) for more details.

## Setup

### 1. Create and activate a virtual environment

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 2. Install the Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the application

```bash
python src/main.py
```

### 4. Enter your deSEC API token when prompted

When you're done using the application, you can deactivate the virtual environment:

```bash
deactivate
```

Alternatively, just close the terminal.

## Multi-Profile Support

The application supports multiple user profiles, allowing you to manage different deSEC accounts or environments with complete data isolation. Each profile maintains its own API tokens, cache, and configuration settings.

### Quick Start with Profiles

1. **Access Profile Management**: Go to **Profile → Manage Profiles...** in the menu
2. **Create New Profile**: Click "Create New..." and enter a name (e.g., "work", "personal")
3. **Switch Profiles**: Select a profile and click "Switch To" (application will restart)
4. **Configure Each Profile**: Set up API tokens and settings independently for each profile

### Use Cases

- **Multiple deSEC Accounts**: Separate work and personal DNS management
- **Environment Separation**: Different profiles for production, staging, and development
- **Team Collaboration**: Individual profiles for different team members or access levels

For detailed information about multi-profile features, see [doc/PROFILES.md](doc/PROFILES.md).

## 📁 Enhanced Import/Export Functionality (v0.6.0-beta)

The application supports importing and exporting DNS zones and records in multiple formats with advanced features for backup, migration, and Infrastructure-as-Code workflows.

### Supported Formats

- **JSON** (API-compatible) - Direct deSEC API format, perfect for backups and programmatic processing
- **YAML** (Infrastructure-as-Code) - Human-readable format ideal for version control and DevOps workflows
- **BIND Zone Files** - Industry standard format for DNS server configurations
- **djbdns/tinydns** - Compact format for djbdns/tinydns server setups

### New Features in v0.6.0-beta

- **Enhanced Import Modes**: Clear terminology with Append, Merge, and Replace modes
- **Real-time Progress Tracking**: Visual progress bar with percentage and status updates
- **Target Zone Selection**: Import to existing zones or auto-create new ones
- **API Rate Limiting**: Configurable rate limiting (0-10 req/sec) to prevent timeouts
- **Auto-generated Filenames**: Timestamp-based export filenames for better organization
- **Post-import Sync**: Automatic UI refresh after successful imports

### Quick Start

1. **Export a Zone**: `File → Import/Export...` → Export tab
   - Select zone to export
   - Choose format (JSON, YAML, BIND, djbdns)
   - Configure options (include/exclude metadata)
   - Auto-generated filename with timestamp
   - Save to file

2. **Import a Zone**: `File → Import/Export...` → Import tab
   - Select file to import
   - Choose matching format and target zone
   - Select import mode (Append/Merge/Replace)
   - Preview import data (recommended)
   - Watch real-time progress during import
   - Automatic UI sync after completion

### Use Cases

- **Backup & Recovery**: Regular exports for disaster recovery
- **DNS Migration**: Move configurations between DNS providers
- **Infrastructure-as-Code**: Version control DNS configurations with Git
- **Environment Sync**: Keep staging and production DNS in sync
- **Multi-Provider Setup**: Export from one provider, import to another

For comprehensive documentation, see [doc/IMPORT_EXPORT.md](doc/IMPORT_EXPORT.md) and [doc/RATE-LIMIT.md](doc/RATE-LIMIT.md).

## Configuration

The application stores configuration in:

```plaintext
~/.config/desecqt/config.json
```

You can edit the API URL and authentication token through the application's configuration editor.

## Documentation

Detailed documentation is available in the `doc/` directory:

- [Multi-Profile Support](doc/PROFILES.md) - Complete guide to managing multiple deSEC accounts and environments
- [Import/Export Functionality](doc/IMPORT_EXPORT.md) - Comprehensive documentation for backup, migration, and Infrastructure-as-Code workflows
- [API Rate Limiting](doc/RATE-LIMIT.md) - Guide to configurable API rate limiting for bulk operations
- [Architecture](doc/ARCHITECTURE.md) - Details on the application's structure and design patterns
- [Caching System](doc/CACHING.md) - Information about the multi-layered caching implementation with optimized indexing
- [Configuration](doc/CONFIG.md) - Guide to configuration options and settings
- [Logs and Notifications](doc/LOGS-AND-NOTIFICATIONS.md) - Logging and notification system information

## License

This project is open source software licensed under the MIT License.

