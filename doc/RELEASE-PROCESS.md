# Release Process

This document outlines the step-by-step process for creating a new release of the deSEC Qt DNS Manager.

## 📋 Pre-Release Checklist

Before starting the release process, ensure:

- [ ] All planned features for the release are complete and tested
- [ ] All open issues tagged for the release are resolved
- [ ] Code has been thoroughly tested on target platforms
- [ ] Documentation is up to date
- [ ] All tests pass (if applicable)

## 🔄 Release Process Steps

### 1. Version Planning

Determine the new version number following [Semantic Versioning](https://semver.org/):
- **Major** (X.0.0): Breaking changes or major feature overhauls
- **Minor** (0.X.0): New features, backward compatible
- **Patch** (0.0.X): Bug fixes, backward compatible
- **Beta** (0.X.0-beta): Pre-release versions for testing

### 2. Update Version References

The following files must be updated with the new version number:

#### 🎯 Critical Files (Must Update)

**`src/main_window.py`**
- **Location**: Line ~820 in the `show_about_dialog()` method
- **What to change**: Update the version string in the HTML content
- **Example**: `"<p align=\"center\"><b>Version 0.6.0-beta</b></p>"`
- **Why**: This is displayed in the application's About dialog

#### 📚 Documentation Files (Should Update)

**`CHANGELOG.md`**
- **Location**: Top of file
- **What to add**: New version section with release date and changes
- **Format**:
  ```markdown
  ## [X.Y.Z-beta] - YYYY-MM-DD
  
  ### Added in X.Y.Z-beta
  - New feature descriptions
  
  ### Fixed in X.Y.Z-beta
  - Bug fix descriptions
  
  ### Technical Improvements in X.Y.Z-beta
  - Technical changes
  ```
- **Why**: Documents what changed in each release

**`README.md`**
- **Location**: Feature sections and headings
- **What to change**: Update version references in feature descriptions
- **Example**: `## 📁 Enhanced Import/Export Functionality (vX.Y.Z-beta)`
- **Why**: Keeps documentation current with latest features

**`ROADMAP.md`**
- **Location**: Feature completion markers
- **What to change**: Update version references for completed features
- **Example**: `- [x] **Feature Name** (Enhanced in vX.Y.Z-beta)`
- **Why**: Tracks when features were implemented

#### 🔍 Files That May Need Updates

**Documentation in `doc/` directory**
- Review all `.md` files for version-specific references
- Update examples that reference specific versions
- Ensure compatibility notes are current

**Import/Export related files**
- `src/import_export_manager.py`: Check for version metadata in export formats
- `doc/IMPORT_EXPORT.md`: Update version references in examples

### 3. Update Documentation

#### Update Feature Documentation
- Review all documentation for accuracy with new features
- Update screenshots if UI has changed significantly
- Verify all code examples and configurations are current

#### Update Installation Instructions
- Verify system requirements are current
- Test installation process on clean system
- Update any dependency versions if needed

### 4. Testing

#### Manual Testing
- [ ] Test core functionality (zone management, record CRUD operations)
- [ ] Test new features added in this release
- [ ] Test on different platforms (if applicable)
- [ ] Verify About dialog shows correct version

#### Regression Testing
- [ ] Test import/export functionality
- [ ] Test multi-profile support
- [ ] Test theme switching
- [ ] Test configuration management

### 5. Create Release

#### Git Operations
```bash
# Ensure you're on the main branch and up to date
git checkout main
git pull origin main

# Create and push version update commit
git add .
git commit -m "Release vX.Y.Z-beta: Update version references and documentation"
git push origin main

# Create and push tag
git tag -a vX.Y.Z-beta -m "Release vX.Y.Z-beta"
git push origin vX.Y.Z-beta
```

#### GitHub Release (if applicable)
- Create release from tag on GitHub
- Copy changelog content to release notes
- Attach any release artifacts (if applicable)

### 6. Post-Release

#### Verification
- [ ] Verify version is displayed correctly in application
- [ ] Test download/installation process
- [ ] Check that documentation is accessible and current

#### Communication
- [ ] Update any external documentation or websites
- [ ] Notify users through appropriate channels
- [ ] Update project status in relevant forums/communities

## 🔧 Tools and Scripts

### Version Consistency Check
To verify all version references are consistent:

```bash
# Search for old version references
grep -r "X\.Y\.Z-beta" . --exclude-dir=.git --exclude-dir=venv

# Search for current version references
grep -r "NEW\.VERSION-beta" . --exclude-dir=.git --exclude-dir=venv
```

### Automated Checks
Consider creating scripts to:
- Validate version consistency across all files
- Run automated tests before release
- Generate changelog entries from git commits

## 📝 Version History Template

When updating `CHANGELOG.md`, use this template:

```markdown
## [X.Y.Z-beta] - YYYY-MM-DD

### Added in X.Y.Z-beta
- New feature 1
- New feature 2

### Fixed in X.Y.Z-beta
- Bug fix 1
- Bug fix 2

### Technical Improvements in X.Y.Z-beta
- Technical improvement 1
- Code refactoring details

### Use Cases Enhanced in X.Y.Z-beta
- Use case 1: Description
- Use case 2: Description
```

## 🚨 Common Pitfalls

1. **Forgetting to update `src/main_window.py`**: This is the most visible version reference to users
2. **Inconsistent version formats**: Ensure all references use the same format (e.g., "vX.Y.Z-beta" vs "X.Y.Z-beta")
3. **Not updating documentation**: Features without documentation are harder for users to discover
4. **Skipping testing**: Always test the About dialog and core functionality after version updates
5. **Not preserving changelog history**: Don't remove or modify existing changelog entries

## 📚 Related Documentation

- [CHANGELOG.md](../CHANGELOG.md) - Complete version history
- [ROADMAP.md](../ROADMAP.md) - Planned features and their target versions
- [README.md](../README.md) - Current feature documentation
- [CONFIG.md](CONFIG.md) - Configuration options by version
