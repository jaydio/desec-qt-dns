#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cache Manager for deSEC Qt DNS Manager.
Handles caching of API responses for offline access.
"""

import os
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Manages caching of API data for offline access.
    Implements a simple file-based cache system.
    """
    
    CACHE_DIR = os.path.expanduser("~/.config/desecqt/cache")
    ZONES_CACHE_FILE = os.path.join(CACHE_DIR, "zones.json")
    
    def __init__(self):
        """Initialize the cache manager and ensure cache directory exists."""
        self._ensure_cache_dir_exists()
        self.last_sync_time = None
        
    def _ensure_cache_dir_exists(self):
        """Create cache directory if it doesn't exist."""
        if not os.path.exists(self.CACHE_DIR):
            try:
                os.makedirs(self.CACHE_DIR)
                logger.info(f"Created cache directory: {self.CACHE_DIR}")
            except OSError as e:
                logger.error(f"Failed to create cache directory: {e}")
    
    def get_record_cache_file(self, domain_name):
        """
        Get the cache file path for a specific domain's records.
        
        Args:
            domain_name (str): The domain name
            
        Returns:
            str: Path to the cache file
        """
        # Sanitize domain name for use in filenames
        sanitized = domain_name.replace('.', '_').replace('/', '_')
        return os.path.join(self.CACHE_DIR, f"records_{sanitized}.json")
    
    def cache_zones(self, zones_data):
        """
        Cache the list of zones.
        
        Args:
            zones_data (list): List of zone objects
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'zones': zones_data
            }
            with open(self.ZONES_CACHE_FILE, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            self.last_sync_time = datetime.now()
            logger.info(f"Cached {len(zones_data)} zones")
            return True
        except Exception as e:
            logger.error(f"Failed to cache zones: {e}")
            return False
    
    def get_cached_zones(self):
        """
        Get the cached zones.
        
        Returns:
            tuple: (zones_list, timestamp) or (None, None) if no cache
        """
        if not os.path.exists(self.ZONES_CACHE_FILE):
            return None, None
            
        try:
            with open(self.ZONES_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
            
            timestamp = datetime.fromisoformat(cache_data['timestamp']) 
            return cache_data['zones'], timestamp
        except Exception as e:
            logger.error(f"Failed to read zones cache: {e}")
            return None, None
    
    def cache_records(self, domain_name, records_data):
        """
        Cache the records for a specific domain.
        
        Args:
            domain_name (str): Domain name
            records_data (list): List of record objects
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cache_file = self.get_record_cache_file(domain_name)
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'domain': domain_name,
                'records': records_data
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
            logger.info(f"Cached {len(records_data)} records for {domain_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache records for {domain_name}: {e}")
            return False
    
    def get_cached_records(self, domain_name):
        """
        Get the cached records for a specific domain.
        
        Args:
            domain_name (str): Domain name
            
        Returns:
            tuple: (records_list, timestamp) or (None, None) if no cache
        """
        cache_file = self.get_record_cache_file(domain_name)
        
        if not os.path.exists(cache_file):
            return None, None
            
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            timestamp = datetime.fromisoformat(cache_data['timestamp'])
            return cache_data['records'], timestamp
        except Exception as e:
            logger.error(f"Failed to read records cache for {domain_name}: {e}")
            return None, None
    
    def clear_domain_cache(self, domain_name):
        """
        Clear the cache for a specific domain.
        
        Args:
            domain_name (str): Domain name
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cache_file = self.get_record_cache_file(domain_name)
            if os.path.exists(cache_file):
                os.remove(cache_file)
                logger.info(f"Cleared cache for {domain_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache for {domain_name}: {e}")
            return False
    
    def clear_all_cache(self):
        """
        Clear all cached data.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Remove all files in the cache directory
            for filename in os.listdir(self.CACHE_DIR):
                file_path = os.path.join(self.CACHE_DIR, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            
            logger.info("All cache cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear all cache: {e}")
            return False
    
    def is_cache_stale(self, timestamp, sync_interval_minutes):
        """
        Check if cached data is stale based on sync interval.
        
        Args:
            timestamp (datetime): Timestamp of cached data
            sync_interval_minutes (int): Sync interval in minutes
            
        Returns:
            bool: True if cache is stale, False otherwise
        """
        if timestamp is None:
            return True
            
        # Calculate expiration time
        expiration_time = timestamp + timedelta(minutes=sync_interval_minutes)
        
        # Check if current time is past expiration
        return datetime.now() > expiration_time
    
    def get_last_sync_time(self):
        """
        Get the timestamp of last synchronization.
        
        Returns:
            datetime: Last sync time or None if never synced
        """
        return self.last_sync_time
