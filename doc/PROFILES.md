# Multi-Profile Support

deSEC Qt DNS Manager supports multiple user profiles, allowing you to manage different deSEC accounts, environments, or configurations with complete data isolation.

## Overview

Each profile maintains its own:
- **API tokens** (encrypted and stored securely)
- **Cache data** (zones and DNS records)
- **Configuration settings** (sync intervals, themes, UI preferences)
- **Application state** (offline mode, log visibility, etc.)

This enables you to:
- Manage multiple deSEC accounts from a single application
- Separate work and personal DNS configurations
- Maintain different environments (production, staging, development)
- Switch between configurations without losing data or settings

## Profile Structure

Profiles are stored in your user configuration directory:

```
~/.config/desecqt/
├── profiles.json          # Profile metadata and settings
└── profiles/
    ├── default/           # Default profile (created automatically)
    │   ├── config.json    # Profile-specific configuration
    │   └── cache/         # Profile-specific cached data
    ├── work/              # Example work profile
    │   ├── config.json
    │   └── cache/
    └── personal/          # Example personal profile
        ├── config.json
        └── cache/
```

## Using Profiles

### Accessing Profile Management

1. Open the application
2. Go to **Profile → Manage Profiles...** in the menu bar
3. The Profile Management dialog will open

### Current Profile Display

The active profile is shown in the **Profile** menu as "Current: [Profile Name]".

### Creating a New Profile

1. In the Profile Management dialog, click **Create New...**
2. Enter a **Profile Name** (used internally, alphanumeric and underscores only)
3. Enter a **Display Name** (shown in the interface, can contain spaces)
4. Click **OK**

Example:
- Profile Name: `work_account`
- Display Name: `Work Account`

### Switching Profiles

1. In the Profile Management dialog, select the desired profile
2. Click **Switch To** (or double-click the profile)
3. Confirm the switch in the dialog
4. The application will restart automatically with the new profile

**Note:** Profile switching requires an application restart to ensure complete isolation of data and settings.

### Renaming Profiles

1. Select a profile in the Profile Management dialog
2. Click **Rename...**
3. Update the Profile Name and/or Display Name
4. Click **OK**

**Special case:** The default profile's internal name cannot be changed, but you can update its display name.

### Deleting Profiles

1. Select a profile in the Profile Management dialog
2. Click **Delete**
3. Confirm the deletion

**Safety restrictions:**
- Cannot delete the default profile
- Cannot delete the currently active profile (switch to another profile first)
- Deletion permanently removes all profile data (API tokens, cache, settings)

### Profile Information

The Profile Management dialog shows detailed information about each profile:
- **Name:** Internal profile identifier
- **Display Name:** Human-readable name
- **Created:** When the profile was created
- **Last Used:** When the profile was last active

## Migration from Single Profile

If you're upgrading from a version without multi-profile support:

1. Your existing configuration and cache will be automatically migrated to a "Default Profile"
2. No data is lost during the migration
3. The application will continue working exactly as before
4. You can create additional profiles as needed

## Use Cases

### Multiple deSEC Accounts

Create separate profiles for different deSEC accounts:
```
- personal (your personal domains)
- work (company domains)
- client_a (client project domains)
```

### Environment Separation

Separate different environments:
```
- production (live domains)
- staging (test domains)
- development (dev domains)
```

### Team Collaboration

Different team members can have their own profiles:
```
- admin (full access account)
- developer (limited access account)
- readonly (monitoring account)
```

## Best Practices

### Profile Naming

- Use descriptive names that clearly identify the purpose
- For Profile Names: use lowercase, underscores, and no spaces
- For Display Names: use clear, readable descriptions

### Security

- Each profile stores its API token encrypted and isolated
- Switching profiles clears sensitive data from memory
- Profile data is completely separated on disk

### Organization

- Create profiles based on logical separation of concerns
- Use consistent naming conventions across your profiles
- Document your profile purposes for team environments

## Troubleshooting

### Profile Won't Switch

- Ensure you have permission to write to the configuration directory
- Check that the target profile exists and isn't corrupted
- Try restarting the application manually if automatic restart fails

### Missing Profile Data

- Profiles are stored in `~/.config/desecqt/profiles/`
- Check file permissions on the profiles directory
- Verify the `profiles.json` file isn't corrupted

### Migration Issues

- Legacy data is migrated to the "default" profile automatically
- If migration fails, your original data remains in `~/.config/desecqt/`
- You can manually copy files to the appropriate profile directory

### Application Won't Start After Profile Switch

- The application automatically restarts after profile switches
- If restart fails, manually start the application
- Check the log files for error details

## Technical Details

### Profile Manager

The `ProfileManager` class handles all profile operations:
- Profile creation, deletion, and switching
- Configuration and cache isolation
- Legacy data migration
- Profile metadata management

### Data Isolation

Each profile has completely isolated:
- **Configuration:** API URLs, tokens, sync settings, themes
- **Cache:** Zone data, DNS records, timestamps
- **State:** UI preferences, window positions, log visibility

### File Locations

- **Profile metadata:** `~/.config/desecqt/profiles.json`
- **Profile data:** `~/.config/desecqt/profiles/[profile_name]/`
- **Logs:** Shared across profiles in `~/.config/desecqt/logs/`

## API Reference

For developers integrating with the profile system:

```python
from profile_manager import ProfileManager

# Initialize profile manager
pm = ProfileManager()

# Get available profiles
profiles = pm.get_available_profiles()

# Switch to a profile
success = pm.switch_to_profile("work")

# Create a new profile
success = pm.create_profile("staging", "Staging Environment")

# Get current profile info
current = pm.get_current_profile_info()

# Get managers for current profile
config_mgr = pm.get_config_manager()
cache_mgr = pm.get_cache_manager()
```
