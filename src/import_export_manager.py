#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Import/Export Manager for DNS zones and records.
Supports multiple formats: JSON, YAML, BIND zone files, djbdns/tinydns.
"""

import json
import yaml
import os
import re
import zipfile
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class ImportExportManager:
    """Manages import and export of DNS zones and records in various formats."""
    
    SUPPORTED_FORMATS = {
        'json': 'JSON (API-compatible)',
        'yaml': 'YAML (Infrastructure-as-Code)',
        'bind': 'BIND Zone File',
        'djbdns': 'djbdns/tinydns Format'
    }
    
    def __init__(self, api_client, cache_manager):
        """Initialize the import/export manager.
        
        Args:
            api_client: API client instance
            cache_manager: Cache manager instance
        """
        self.api_client = api_client
        self.cache_manager = cache_manager
    
    def generate_export_filename(self, zone_name: str, format_type: str) -> str:
        """Generate automatic export filename with timestamp.
        
        Args:
            zone_name: Name of the zone being exported
            format_type: Export format ('json', 'yaml', 'bind', 'djbdns')
            
        Returns:
            Generated filename with timestamp
        """
        # Get current timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Clean zone name for filename (replace dots with underscores)
        clean_zone_name = zone_name.replace('.', '_')
        
        # File extensions based on format
        extensions = {
            'json': 'json',
            'yaml': 'yaml', 
            'bind': 'zone',
            'djbdns': 'data'
        }
        
        extension = extensions.get(format_type, 'txt')
        
        return f"{clean_zone_name}_export_{timestamp}.{extension}"
    
    def _delete_all_zone_records(self, zone_name: str) -> Tuple[bool, str]:
        """Delete all records from a zone (for overwrite mode).
        
        Args:
            zone_name: Name of the zone to clear
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Get all existing records for the zone
            success, existing_records = self.api_client.get_records(zone_name)
            if not success:
                return False, f"Failed to get existing records: {existing_records}"
            
            deleted_count = 0
            failed_count = 0
            
            # Delete each record
            for record in existing_records:
                # Skip NS and SOA records as they are required for the zone
                if record.get('type') in ['NS', 'SOA']:
                    continue
                
                success, result = self.api_client.delete_record(
                    zone_name,
                    record.get('subname', ''),
                    record.get('type')
                )
                
                if success:
                    deleted_count += 1
                else:
                    failed_count += 1
                    logger.warning(f"Failed to delete record {record}: {result}")
            
            message = f"Cleared {deleted_count} existing records"
            if failed_count > 0:
                message += f" ({failed_count} failed to delete)"
            
            return True, message
            
        except Exception as e:
            logger.error(f"Failed to clear zone records: {e}")
            return False, f"Failed to clear zone records: {str(e)}"
    
    def _overwrite_matching_records(self, zone_name: str, import_records: List[Dict], progress_callback=None) -> Tuple[int, int, int]:
        """Overwrite only records that exist in both the zone and import file.
        
        Args:
            zone_name: Name of the zone
            import_records: List of records from import file
            
        Returns:
            Tuple of (created_count, updated_count, failed_count)
        """
        try:
            # Get existing records from the zone
            success, existing_records = self.api_client.get_records(zone_name)
            if not success:
                logger.error(f"Failed to get existing records: {existing_records}")
                return 0, 0, len(import_records)
            
            # Create a set of existing record keys (subname, type) for fast lookup
            existing_keys = set()
            for record in existing_records:
                key = (record.get('subname', ''), record.get('type', ''))
                existing_keys.add(key)
            
            created_count = 0
            updated_count = 0
            failed_count = 0
            total_records = len(import_records)
            
            for i, record in enumerate(import_records):
                record_key = (record.get('subname', ''), record.get('type', ''))
                
                if record_key in existing_keys:
                    # Record exists - update it
                    success, result = self.api_client.update_record(
                        zone_name,
                        record['subname'],
                        record['type'],
                        record['ttl'],
                        record['records']
                    )
                    
                    if success:
                        updated_count += 1
                    else:
                        failed_count += 1
                        logger.warning(f"Failed to update record {record}: {result}")
                else:
                    # Record doesn't exist - create it
                    success, result = self.api_client.create_record(
                        zone_name,
                        record['subname'],
                        record['type'],
                        record['ttl'],
                        record['records']
                    )
                    
                    if success:
                        created_count += 1
                    else:
                        failed_count += 1
                        logger.warning(f"Failed to create record {record}: {result}")
                
                # Report progress for each record processed in merge mode
                if progress_callback and total_records > 0:
                    progress_percent = 40 + int((i + 1) / total_records * 50)  # 40-90% range
                    progress_callback(progress_percent, f"Processed {i + 1}/{total_records} records...")
            
            return created_count, updated_count, failed_count
            
        except Exception as e:
            logger.error(f"Failed to overwrite matching records: {e}")
            return 0, 0, len(import_records)
    
    def export_zone(self, zone_name: str, format_type: str, file_path: str, 
                   include_metadata: bool = True) -> Tuple[bool, str]:
        """Export a zone to file in specified format.
        
        Args:
            zone_name: Name of zone to export
            format_type: Export format ('json', 'yaml', 'bind', 'djbdns')
            file_path: Output file path
            include_metadata: Include timestamps and metadata
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Get zone data
            zone_data = self.cache_manager.get_zone_by_name(zone_name)
            if not zone_data:
                return False, f"Zone '{zone_name}' not found in cache"
            
            # Get records
            records, _ = self.cache_manager.get_cached_records(zone_name)
            if not records:
                return False, f"No records found for zone '{zone_name}'"
            
            # Export based on format
            if format_type == 'json':
                return self._export_json(zone_data, records, file_path, include_metadata)
            elif format_type == 'yaml':
                return self._export_yaml(zone_data, records, file_path, include_metadata)
            elif format_type == 'bind':
                return self._export_bind(zone_data, records, file_path)
            elif format_type == 'djbdns':
                return self._export_djbdns(zone_data, records, file_path)
            else:
                return False, f"Unsupported format: {format_type}"
                
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False, f"Export failed: {str(e)}"
    
    def import_zone(self, file_path: str, format_type: str, 
                   dry_run: bool = False, target_zone: str = None, 
                   existing_records_mode: str = 'ignore', 
                   progress_callback=None) -> Tuple[bool, str, Optional[Dict]]:
        """Import a zone from file.
        
        Args:
            file_path: Input file path
            format_type: Import format ('json', 'yaml', 'bind', 'djbdns')
            dry_run: If True, validate only without creating records
            target_zone: Override zone name (if None, use zone name from file)
            existing_records_mode: How to handle existing records ('append', 'merge', or 'replace')
            
        Returns:
            Tuple of (success, message, preview_data)
        """
        try:
            if not os.path.exists(file_path):
                return False, f"File not found: {file_path}", None
        
            # Report initial progress
            if progress_callback:
                progress_callback(5, "Reading import file...")
        
            # Parse based on format
            if format_type == 'json':
                zone_data, records = self._import_json(file_path)
            elif format_type == 'yaml':
                zone_data, records = self._import_yaml(file_path)
            elif format_type == 'bind':
                zone_data, records = self._import_bind(file_path)
            elif format_type == 'djbdns':
                zone_data, records = self._import_djbdns(file_path)
            else:
                return False, f"Unsupported format: {format_type}", None
        
            if progress_callback:
                progress_callback(15, f"Parsed {len(records)} records from file")
            
            # Override zone name if target_zone is specified
            if target_zone:
                zone_data['name'] = target_zone
                # Update records to use the target zone
                for record in records:
                    record['domain'] = target_zone
        
            if dry_run:
                preview = {
                    'zone': zone_data,
                    'records': records,
                    'record_count': len(records),
                    'target_zone': zone_data['name'],
                    'existing_records_mode': existing_records_mode
                }
                mode_desc = {
                    'append': 'add to existing',
                    'merge': 'merge matching', 
                    'replace': 'replace all'
                }.get(existing_records_mode, existing_records_mode)
                return True, f"Import preview: {len(records)} records to zone '{zone_data['name']}' ({mode_desc})" , preview
            
            # Create zone and records
            if progress_callback:
                progress_callback(25, "Creating zone and records...")
            success, message = self._create_zone_and_records(zone_data, records, existing_records_mode, progress_callback)
            return success, message, None
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            return False, f"Import failed: {str(e)}", None
    
    def _export_json(self, zone_data: Dict, records: List[Dict], 
                    file_path: str, include_metadata: bool) -> Tuple[bool, str]:
        """Export to JSON format."""
        export_data = {
            'format': 'deSEC JSON Export',
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'zone': zone_data,
            'records': records
        }
        
        if not include_metadata:
            # Remove metadata fields
            for record in export_data['records']:
                record.pop('created', None)
                record.pop('touched', None)
            export_data['zone'].pop('created', None)
            export_data['zone'].pop('published', None)
            export_data['zone'].pop('touched', None)
        
        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return True, f"Exported {len(records)} records to JSON"
    
    def _export_yaml(self, zone_data: Dict, records: List[Dict], 
                    file_path: str, include_metadata: bool) -> Tuple[bool, str]:
        """Export to YAML format."""
        export_data = {
            'format': 'deSEC YAML Export',
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'zone': zone_data,
            'records': records
        }
        
        if not include_metadata:
            for record in export_data['records']:
                record.pop('created', None)
                record.pop('touched', None)
            export_data['zone'].pop('created', None)
            export_data['zone'].pop('published', None)
            export_data['zone'].pop('touched', None)
        
        with open(file_path, 'w') as f:
            yaml.dump(export_data, f, default_flow_style=False, indent=2)
        
        return True, f"Exported {len(records)} records to YAML"
    
    def _export_bind(self, zone_data: Dict, records: List[Dict], 
                    file_path: str) -> Tuple[bool, str]:
        """Export to BIND zone file format."""
        zone_name = zone_data['name']
        lines = [
            f"; BIND zone file for {zone_name}",
            f"; Generated by deSEC Qt DNS Manager on {datetime.now().isoformat()}",
            f"",
            f"$ORIGIN {zone_name}.",
            f"$TTL {zone_data.get('minimum_ttl', 3600)}",
            f""
        ]
        
        # Sort records by type and subname for better organization
        sorted_records = sorted(records, key=lambda r: (r['type'], r['subname']))
        
        for record in sorted_records:
            subname = record['subname'] if record['subname'] else '@'
            ttl = record['ttl']
            rtype = record['type']
            
            for content in record['records']:
                lines.append(f"{subname:<20} {ttl:<8} IN {rtype:<8} {content}")
        
        with open(file_path, 'w') as f:
            f.write('\n'.join(lines))
        
        return True, f"Exported {len(records)} records to BIND format"
    
    def _export_djbdns(self, zone_data: Dict, records: List[Dict], 
                      file_path: str) -> Tuple[bool, str]:
        """Export to djbdns/tinydns format."""
        zone_name = zone_data['name']
        lines = [
            f"# djbdns/tinydns data file for {zone_name}",
            f"# Generated by deSEC Qt DNS Manager on {datetime.now().isoformat()}",
            f""
        ]
        
        for record in records:
            fqdn = f"{record['subname']}.{zone_name}" if record['subname'] else zone_name
            ttl = record['ttl']
            rtype = record['type']
            
            for content in record['records']:
                if rtype == 'A':
                    lines.append(f"+{fqdn}:{content}:{ttl}")
                elif rtype == 'AAAA':
                    lines.append(f"6{fqdn}:{content}:{ttl}")
                elif rtype == 'CNAME':
                    lines.append(f"C{fqdn}:{content}:{ttl}")
                elif rtype == 'MX':
                    priority, target = content.split(' ', 1)
                    lines.append(f"@{fqdn}::{target}:{priority}:{ttl}")
                elif rtype == 'TXT':
                    lines.append(f"'{fqdn}:{content}:{ttl}")
                elif rtype == 'NS':
                    lines.append(f"&{fqdn}::{content}:{ttl}")
        
        with open(file_path, 'w') as f:
            f.write('\n'.join(lines))
        
        return True, f"Exported {len(records)} records to djbdns format"
    
    def _import_json(self, file_path: str) -> Tuple[Dict, List[Dict]]:
        """Import from JSON format."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if 'zone' in data and 'records' in data:
            return data['zone'], data['records']
        else:
            # Assume direct zone/records format
            return data.get('zone', {}), data.get('records', [])
    
    def _import_yaml(self, file_path: str) -> Tuple[Dict, List[Dict]]:
        """Import from YAML format."""
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        if 'zone' in data and 'records' in data:
            return data['zone'], data['records']
        else:
            return data.get('zone', {}), data.get('records', [])
    
    def _import_bind(self, file_path: str) -> Tuple[Dict, List[Dict]]:
        """Import from BIND zone file format."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Parse BIND zone file (simplified parser)
        zone_name = None
        default_ttl = 3600
        records = []
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            
            if line.startswith('$ORIGIN'):
                zone_name = line.split()[1].rstrip('.')
            elif line.startswith('$TTL'):
                try:
                    default_ttl = int(line.split()[1])
                except (ValueError, IndexError):
                    logger.warning(f"Malformed $TTL directive, using default: {line!r}")
            else:
                # Parse record line
                parts = line.split()
                if len(parts) >= 4:
                    name = parts[0]
                    if name == '@':
                        subname = ''
                    else:
                        subname = name
                    
                    # Find TTL, IN, TYPE, DATA
                    ttl = default_ttl
                    rtype = None
                    data = None
                    
                    for i, part in enumerate(parts[1:], 1):
                        if part.isdigit():
                            ttl = int(part)
                        elif part == 'IN':
                            continue
                        elif part.isupper() and len(part) <= 6:
                            rtype = part
                            data = ' '.join(parts[i+1:])
                            break
                    
                    if rtype and data:
                        records.append({
                            'subname': subname,
                            'type': rtype,
                            'ttl': ttl,
                            'records': [data]
                        })
        
        zone_data = {
            'name': zone_name or 'imported-zone.com',
            'minimum_ttl': default_ttl
        }
        
        return zone_data, records
    
    def _import_djbdns(self, file_path: str) -> Tuple[Dict, List[Dict]]:
        """Import from djbdns/tinydns format."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        records = []
        zone_name = None
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if line.startswith('+'):  # A record
                parts = line[1:].split(':')
                if len(parts) >= 3:
                    fqdn, ip, ttl_str = parts[0], parts[1], parts[2] or '3600'
                    try:
                        ttl_val = int(ttl_str)
                    except (ValueError, TypeError):
                        ttl_val = 3600
                    if not zone_name:
                        zone_name = '.'.join(fqdn.split('.')[1:])
                    subname = fqdn.split('.')[0] if '.' in fqdn else ''
                    records.append({
                        'subname': subname,
                        'type': 'A',
                        'ttl': ttl_val,
                        'records': [ip]
                    })

            elif line.startswith('C'):  # CNAME record
                parts = line[1:].split(':')
                if len(parts) >= 3:
                    fqdn, target, ttl_str = parts[0], parts[1], parts[2] or '3600'
                    try:
                        ttl_val = int(ttl_str)
                    except (ValueError, TypeError):
                        ttl_val = 3600
                    if not zone_name:
                        zone_name = '.'.join(fqdn.split('.')[1:])
                    subname = fqdn.split('.')[0] if '.' in fqdn else ''
                    records.append({
                        'subname': subname,
                        'type': 'CNAME',
                        'ttl': ttl_val,
                        'records': [target]
                    })
        
        zone_data = {
            'name': zone_name or 'imported-zone.com',
            'minimum_ttl': 3600
        }
        
        return zone_data, records
    
    def _create_zone_and_records(self, zone_data: Dict, 
                           records: List[Dict], existing_records_mode: str = 'ignore', 
                           progress_callback=None) -> Tuple[bool, str]:
        """Create zone and records via API."""
        zone_name = zone_data['name']
        
        # Check if zone exists
        existing_zone = self.cache_manager.get_zone_by_name(zone_name)
        if not existing_zone:
            # Create zone
            if progress_callback:
                progress_callback(30, f"Creating zone {zone_name}...")
            success, result = self.api_client.create_zone(zone_name)
            if not success:
                return False, f"Failed to create zone: {result}"
        else:
            # Zone exists - handle existing records based on mode
            if existing_records_mode == 'replace':
                # Delete all existing records first (replace mode)
                if progress_callback:
                    progress_callback(35, "Deleting existing records...")
                success, message = self._delete_all_zone_records(zone_name)
                if not success:
                    return False, f"Failed to replace existing records: {message}"
        
        # Handle records based on mode
        if existing_records_mode == 'merge' and existing_zone:
            # Merge mode: only update records that exist in both zone and import file
            if progress_callback:
                progress_callback(40, "Merging existing records...")
            created_count, updated_count, failed_count = self._overwrite_matching_records(zone_name, records, progress_callback)
        else:
            # Append mode or new zone: create all records
            created_count = 0
            failed_count = 0
            updated_count = 0
            total_records = len(records)
            
            if progress_callback:
                progress_callback(40, f"Creating {total_records} records...")
            
            for i, record in enumerate(records):
                success, result = self.api_client.create_record(
                    zone_name,
                    record['subname'],
                    record['type'],
                    record['ttl'],
                    record['records']
                )
                
                if success:
                    created_count += 1
                else:
                    failed_count += 1
                    logger.warning(f"Failed to create record {record}: {result}")
                
                # Report progress for each record created
                if progress_callback and total_records > 0:
                    progress_percent = 40 + int((i + 1) / total_records * 50)  # 40-90% range
                    progress_callback(progress_percent, f"Created {i + 1}/{total_records} records...")
        
        # Report final completion
        if progress_callback:
            progress_callback(95, "Finalizing import...")
        
        # Build completion message based on mode and results
        if existing_records_mode == 'merge' and existing_zone:
            message = f"Import completed: {created_count} records created, {updated_count} records updated"
        else:
            message = f"Import completed: {created_count} records created"
        
        if failed_count > 0:
            message += f", {failed_count} failed"
        
        # Add information about existing records handling
        if existing_zone and existing_records_mode == 'replace':
            message = f"Zone replaced and rebuilt. {message}"
        
        # Report 100% completion
        if progress_callback:
            progress_callback(100, "Import completed successfully!")
        elif existing_zone and existing_records_mode == 'merge':
            message = f"Matching records merged. {message}"
        elif existing_zone and existing_records_mode == 'append':
            message = f"Records appended to existing zone. {message}"
        
        return True, message
    
    def export_zones_bulk(self, zone_names: List[str], format_type: str, file_path: str, 
                         include_metadata: bool = True, progress_callback=None) -> Tuple[bool, str]:
        """Export multiple zones to a ZIP archive.
        
        Args:
            zone_names: List of zone names to export
            format_type: Export format ('json', 'yaml', 'bind', 'djbdns')
            file_path: Output ZIP file path
            include_metadata: Include timestamps and metadata
            progress_callback: Optional callback for progress updates
            
        Returns:
            Tuple of (success, message)
        """
        try:
            if progress_callback:
                progress_callback(0, "Starting bulk export...")
            
            # Create temporary directory for individual zone files
            with tempfile.TemporaryDirectory() as temp_dir:
                exported_files = []
                total_zones = len(zone_names)
                
                # Export each zone to temporary files
                for i, zone_name in enumerate(zone_names):
                    if progress_callback:
                        progress = int((i / total_zones) * 80)  # Use 80% for individual exports
                        progress_callback(progress, f"Exporting zone {i+1}/{total_zones}: {zone_name}")
                    
                    # Get zone data from cache
                    zone_data = self.cache_manager.get_zone_by_name(zone_name)
                    if not zone_data:
                        logger.warning(f"Zone {zone_name} not found in cache, skipping")
                        continue
                    
                    # Get records from cache
                    records, _ = self.cache_manager.get_cached_records(zone_name)
                    if records is None:
                        logger.warning(f"Records for zone {zone_name} not found in cache, skipping")
                        continue
                    
                    # Generate filename for this zone
                    zone_filename = self.generate_export_filename(zone_name, format_type)
                    temp_file_path = os.path.join(temp_dir, zone_filename)
                    
                    # Export zone to temporary file
                    try:
                        if format_type == 'json':
                            self._export_json(zone_data, records, temp_file_path, include_metadata)
                        elif format_type == 'yaml':
                            self._export_yaml(zone_data, records, temp_file_path, include_metadata)
                        elif format_type == 'bind':
                            self._export_bind(zone_data, records, temp_file_path)
                        elif format_type == 'djbdns':
                            self._export_djbdns(zone_data, records, temp_file_path)
                        else:
                            return False, f"Unsupported export format: {format_type}"
                        
                        exported_files.append((zone_filename, temp_file_path))
                        
                    except Exception as e:
                        logger.error(f"Failed to export zone {zone_name}: {e}")
                        # Continue with other zones instead of failing completely
                        continue
                
                if not exported_files:
                    return False, "No zones were successfully exported"
                
                if progress_callback:
                    progress_callback(85, "Creating ZIP archive...")
                
                # Create ZIP archive
                with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for zone_filename, temp_file_path in exported_files:
                        zip_file.write(temp_file_path, zone_filename)
                        if progress_callback:
                            current_progress = 85 + int((len([f for f in exported_files if f[0] <= zone_filename]) / len(exported_files)) * 10)
                            progress_callback(current_progress, f"Adding {zone_filename} to ZIP...")
                
                if progress_callback:
                    progress_callback(100, "Bulk export completed successfully!")
                
                successful_count = len(exported_files)
                failed_count = total_zones - successful_count
                
                message = f"Bulk export completed: {successful_count} zones exported to {file_path}"
                if failed_count > 0:
                    message += f" ({failed_count} zones failed to export)"
                
                logger.info(f"Bulk export completed: {successful_count}/{total_zones} zones exported")
                return True, message
                
        except Exception as e:
            logger.error(f"Bulk export failed: {e}")
            return False, f"Bulk export failed: {str(e)}"
