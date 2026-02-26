#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cache Manager for deSEC Qt DNS Manager.
Handles caching of API responses for offline access.
"""

import os
import stat
import json
import logging
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Union

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages caching of API data for offline access.
    
    Implements a multi-layered caching system with memory cache
    and file-based storage for persistent data across sessions.
    """
    
    CACHE_DIR = os.path.expanduser("~/.config/desecqt/cache")
    ZONES_CACHE_FILE = os.path.join(CACHE_DIR, "zones.json")
    
    def __init__(self) -> None:
        """Initialize the cache manager with optimized data structures."""
        self._ensure_cache_dir_exists()
        self.last_sync_time: Optional[datetime] = None
        
        # Optimized in-memory cache with indexed access
        self.memory_cache: Dict[str, Any] = {
            'zones': None,             # List of zone objects
            'zones_timestamp': None,   # When zones were last fetched
            'zones_index': {},         # Quick lookup by zone name -> zone object
            'records': {},             # Domain name -> records mapping
            'tokens': None,            # List of token objects
            'tokens_timestamp': None,  # When tokens were last fetched
            'token_policies': {},      # token_id -> {policies, timestamp}
        }
        
    def _ensure_cache_dir_exists(self) -> None:
        """Create cache directory with restrictive permissions and clean up stale pickle files."""
        try:
            os.makedirs(self.CACHE_DIR, exist_ok=True)
            os.chmod(self.CACHE_DIR, stat.S_IRWXU)  # 0700
        except OSError as e:
            logger.error(f"Failed to create/secure cache directory: {e}")
        # Remove stale pickle files from previous versions
        try:
            for fname in os.listdir(self.CACHE_DIR):
                if fname.endswith('.pkl'):
                    pkl_path = os.path.join(self.CACHE_DIR, fname)
                    os.remove(pkl_path)
                    logger.info(f"Removed stale pickle file: {fname}")
        except OSError as e:
            logger.warning(f"Failed to clean up pickle files: {e}")

    @staticmethod
    def _atomic_json_write(file_path: str, data: Any, indent: int = 2) -> None:
        """Write JSON data atomically: temp file + os.replace."""
        dir_path = os.path.dirname(file_path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f, indent=indent)
            os.replace(tmp_path, file_path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    
    def get_record_cache_file(self, domain_name: str) -> str:
        """
        Get the cache file path for a specific domain's records.
        
        Args:
            domain_name: The domain name
            
        Returns:
            Path to the cache file
        """
        # Sanitize domain name for use in filenames
        sanitized = domain_name.replace('.', '_').replace('/', '_')
        return os.path.join(self.CACHE_DIR, f"records_{sanitized}.json")
    
    def cache_zones(self, zones_data: List[Dict[str, Any]]) -> bool:
        """
        Cache the list of zones in both memory and file formats.
        
        Args:
            zones_data: List of zone objects
            
        Returns:
            True if successful, False otherwise
        """
        timestamp = datetime.now()
        cache_data = {
            'timestamp': timestamp.isoformat(),
            'zones': zones_data
        }
        
        # Update memory cache immediately with indexing for faster lookups
        self.memory_cache['zones'] = zones_data
        self.memory_cache['zones_timestamp'] = timestamp
        self.last_sync_time = timestamp
        
        # Build zone name index for O(1) lookups
        zone_index = {}
        for zone in zones_data:
            zone_name = zone.get('name', '')
            if zone_name:
                zone_index[zone_name] = zone
                
        # Store the index for future rapid lookups
        self.memory_cache['zones_index'] = zone_index
        
        # Atomic JSON write
        try:
            self._atomic_json_write(self.ZONES_CACHE_FILE, cache_data)
            logger.info(f"Cached {len(zones_data)} zones with indexed access")
            return True
        except Exception as e:
            logger.error(f"Failed to cache zones: {e}")
            return False
    
    def get_cached_zones(self) -> Tuple[Optional[List[Dict[str, Any]]], Optional[datetime]]:
        """
        Get the cached zones with optimized performance.
        Checks memory cache first, then falls back to file.
        
        Returns:
            A tuple containing:
                - List of zone objects or None if no cache exists
                - Timestamp of when zones were cached or None if no cache
        """
        # First check memory cache - fastest retrieval method (O(1) access)
        if self.memory_cache['zones'] is not None:
            return self.memory_cache['zones'], self.memory_cache['zones_timestamp']
        
        start_time = datetime.now()

        # JSON file cache
        if not os.path.exists(self.ZONES_CACHE_FILE):
            logger.warning("No zones cache file found")
            return None, None
            
        try:
            with open(self.ZONES_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
            
            timestamp = datetime.fromisoformat(cache_data['timestamp'])
            zones = cache_data['zones']
            
            # Build zone index for O(1) lookups
            zone_index = {}
            for zone in zones:
                zone_name = zone.get('name', '')
                if zone_name:
                    zone_index[zone_name] = zone
            
            # Store in memory cache with index for future rapid access
            self.memory_cache['zones'] = zones
            self.memory_cache['zones_timestamp'] = timestamp 
            self.memory_cache['zones_index'] = zone_index
            self.last_sync_time = timestamp
            
            load_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"Loaded {len(zones)} zones from JSON cache in {load_time:.1f}ms")
            return zones, timestamp
        except Exception as e:
            logger.error(f"Failed to read zones cache: {e}")
            return None, None
    
    def cache_records(self, domain_name: str, records_data: List[Dict[str, Any]]) -> bool:
        """
        Cache the records for a specific domain with optimized performance.
        Stores in both memory cache and on disk in multiple formats.
        
        Args:
            domain_name: Domain name to cache records for
            records_data: List of record objects to cache
            
        Returns:
            True if successful, False otherwise
        """
        timestamp = datetime.now()
        cache_data = {
            'timestamp': timestamp.isoformat(),
            'records': records_data
        }
        
        # Update memory cache immediately with index
        self.memory_cache['records'][domain_name] = {
            'records': records_data,
            'timestamp': timestamp,
            # Create index by record ID for faster lookups
            'index': {record.get('id'): i for i, record in enumerate(records_data) if 'id' in record}
        }
        
        # Atomic JSON write
        try:
            cache_file = self.get_record_cache_file(domain_name)
            self._atomic_json_write(cache_file, cache_data)
            logger.info(f"Cached {len(records_data)} records for {domain_name} with indexed access")
            return True
        except Exception as e:
            logger.error(f"Failed to cache records for {domain_name}: {e}")
            return False
    
    def get_cached_records(self, domain_name: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[datetime]]:
        """
        Get the cached records for a specific domain with optimized performance.
        Checks memory cache first for immediate access.
        
        Args:
            domain_name: Domain name to retrieve records for
            
        Returns:
            A tuple containing:
                - List of record objects or None if no cache exists
                - Timestamp of when records were cached or None if no cache
        """
        # First check memory cache for O(1) access
        if domain_name in self.memory_cache['records']:
            cache_entry = self.memory_cache['records'][domain_name]
            return cache_entry['records'], cache_entry['timestamp']
        
        start_time = datetime.now()

        # JSON file cache
        cache_file = self.get_record_cache_file(domain_name)
        
        if not os.path.exists(cache_file):
            return None, None
            
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            timestamp = datetime.fromisoformat(cache_data['timestamp'])
            records = cache_data['records']
            
            # Create index by record ID for faster lookups
            record_index = {record.get('id'): i for i, record in enumerate(records) if 'id' in record}
            
            # Store in memory cache with index for future rapid access
            self.memory_cache['records'][domain_name] = {
                'records': records,
                'timestamp': timestamp,
                'index': record_index
            }
            
            load_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"Loaded {len(records)} records for {domain_name} from JSON cache in {load_time:.1f}ms")
            return records, timestamp
        except Exception as e:
            logger.error(f"Failed to read records cache for {domain_name}: {e}")
            return None, None
    
    # ------------------------------------------------------------------
    # Token caching
    # ------------------------------------------------------------------

    def cache_tokens(self, tokens_data: List[Dict[str, Any]]) -> bool:
        """Cache the list of API tokens in memory and JSON on disk."""
        timestamp = datetime.now()
        self.memory_cache['tokens'] = tokens_data
        self.memory_cache['tokens_timestamp'] = timestamp
        try:
            cache_file = os.path.join(self.CACHE_DIR, "tokens.json")
            self._atomic_json_write(cache_file, {'timestamp': timestamp.isoformat(), 'data': tokens_data})
            logger.info(f"Cached {len(tokens_data)} tokens")
            return True
        except Exception as e:
            logger.error(f"Failed to cache tokens: {e}")
            return False

    def get_cached_tokens(self) -> Tuple[Optional[List[Dict[str, Any]]], Optional[datetime]]:
        """Return cached tokens (memory-first, JSON fallback)."""
        if self.memory_cache['tokens'] is not None:
            return self.memory_cache['tokens'], self.memory_cache['tokens_timestamp']
        cache_file = os.path.join(self.CACHE_DIR, "tokens.json")
        if not os.path.exists(cache_file):
            return None, None
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            timestamp = datetime.fromisoformat(cache_data['timestamp'])
            tokens = cache_data['data']
            self.memory_cache['tokens'] = tokens
            self.memory_cache['tokens_timestamp'] = timestamp
            logger.info(f"Loaded {len(tokens)} tokens from JSON cache")
            return tokens, timestamp
        except Exception as e:
            logger.error(f"Failed to read tokens cache: {e}")
            return None, None

    def cache_token_policies(self, token_id: str, policies_data: List[Dict[str, Any]]) -> bool:
        """Cache RRset policies for a specific token."""
        timestamp = datetime.now()
        self.memory_cache['token_policies'][token_id] = {
            'policies': policies_data,
            'timestamp': timestamp,
        }
        try:
            cache_file = os.path.join(self.CACHE_DIR, f"token_policies_{token_id}.json")
            self._atomic_json_write(cache_file, {'timestamp': timestamp.isoformat(), 'data': policies_data})
            logger.info(f"Cached {len(policies_data)} policies for token {token_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache policies for token {token_id}: {e}")
            return False

    def get_cached_token_policies(self, token_id: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[datetime]]:
        """Return cached policies for a token (memory-first, JSON fallback)."""
        if token_id in self.memory_cache['token_policies']:
            entry = self.memory_cache['token_policies'][token_id]
            return entry['policies'], entry['timestamp']
        cache_file = os.path.join(self.CACHE_DIR, f"token_policies_{token_id}.json")
        if not os.path.exists(cache_file):
            return None, None
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            timestamp = datetime.fromisoformat(cache_data['timestamp'])
            policies = cache_data['data']
            self.memory_cache['token_policies'][token_id] = {
                'policies': policies,
                'timestamp': timestamp,
            }
            logger.info(f"Loaded {len(policies)} policies for token {token_id} from JSON cache")
            return policies, timestamp
        except Exception as e:
            logger.error(f"Failed to read policies cache for token {token_id}: {e}")
            return None, None

    def clear_domain_cache(self, domain_name: str) -> bool:
        """
        Clear the cache for a specific domain.
        Removes from both memory cache and disk storage.
        
        Args:
            domain_name: Domain name to clear cache for
            
        Returns:
            True if successful, False otherwise
        """
        # Clear from memory cache
        if domain_name in self.memory_cache['records']:
            del self.memory_cache['records'][domain_name]
        
        try:
            # Remove JSON cache file
            cache_file = self.get_record_cache_file(domain_name)
            if os.path.exists(cache_file):
                os.remove(cache_file)

            logger.info(f"Cleared cache for {domain_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache for {domain_name}: {e}")
            return False
    
    def clear_all_cache(self) -> bool:
        """
        Clear all cached data from both memory and disk.
        
        Returns:
            True if successful, False otherwise
        """
        # Clear memory cache
        self.memory_cache = {
            'zones': None,
            'zones_timestamp': None,
            'zones_index': {},
            'records': {},
            'tokens': None,
            'tokens_timestamp': None,
            'token_policies': {},
        }
        
        try:
            # Remove all files in the cache directory
            for filename in os.listdir(self.CACHE_DIR):
                file_path = os.path.join(self.CACHE_DIR, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            
            logger.info("All cache cleared (memory and disk)")
            return True
        except Exception as e:
            logger.error(f"Failed to clear all cache: {e}")
            return False
    
    def is_cache_stale(self, timestamp: Optional[datetime], sync_interval_minutes: int) -> bool:
        """
        Check if cached data is stale based on sync interval.
        
        Args:
            timestamp: Timestamp of cached data
            sync_interval_minutes: Sync interval in minutes
            
        Returns:
            True if cache is stale, False otherwise
        """
        if timestamp is None:
            return True
            
        # Calculate expiration time
        expiration_time = timestamp + timedelta(minutes=sync_interval_minutes)
        
        # Check if current time is past expiration
        return datetime.now() > expiration_time
    
    def get_last_sync_time(self) -> Optional[datetime]:
        """
        Get the timestamp of last synchronization.
        
        Returns:
            Last sync time or None if never synced
        """
        return self.last_sync_time
        
    def get_zone_by_name(self, zone_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a zone object by name using the optimized index.
        
        Args:
            zone_name: Zone name to search for
            
        Returns:
            Zone object or None if not found
        """
        # If we have an index, this is an O(1) operation
        if self.memory_cache['zones_index'] and zone_name in self.memory_cache['zones_index']:
            return self.memory_cache['zones_index'][zone_name]
            
        # Fallback to O(n) search if index not available
        if self.memory_cache['zones']:
            for zone in self.memory_cache['zones']:
                if zone.get('name') == zone_name:
                    return zone
                    
        return None
