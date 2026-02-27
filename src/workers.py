#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Worker classes for asynchronous operations in deSEC Qt DNS Manager.
"""

import logging
import time
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QRunnable, QObject, Signal

logger = logging.getLogger(__name__)


class LoadRecordsWorker(QRunnable):
    """Worker for asynchronous loading of DNS records with optimized performance."""
    
    class Signals(QObject):
        """Signal wrapper for thread-safe communication with the main thread."""
        finished = Signal(bool, object, str, str)
    
    def __init__(self, api_client, zone_name: str, cache_manager):
        """Initialize the worker.
        
        Args:
            api_client: API client instance
            zone_name: Name of the zone to load records for
            cache_manager: Cache manager instance
        """
        super().__init__()
        self.api_client = api_client
        self.zone_name = zone_name
        self.cache_manager = cache_manager
        self.signals = self.Signals()
    
    def run(self) -> None:
        """Execute the worker to load records from API or cache."""
        start_time = time.time()
        
        if self.api_client.is_online:
            # Online mode - get records from API
            success, response = self.api_client.get_records(self.zone_name)
            
            if success:
                # Cache records with optimized indexing
                self.cache_manager.cache_records(self.zone_name, response)
                elapsed = (time.time() - start_time) * 1000
                logger.debug(f"Retrieved and cached {len(response)} records for {self.zone_name} in {elapsed:.1f}ms")
                self.signals.finished.emit(True, response, self.zone_name, "")
            else:
                error_msg = f"Failed to load records: {response}"
                # Try to load from cache as fallback
                cached_records, _ = self.cache_manager.get_cached_records(self.zone_name)
                
                if cached_records is not None:
                    self.signals.finished.emit(False, cached_records, self.zone_name, error_msg)
                else:
                    self.signals.finished.emit(False, [], self.zone_name, error_msg)
        else:
            # Offline mode - get records from cache
            cached_records, timestamp = self.cache_manager.get_cached_records(self.zone_name)
            
            if cached_records is not None:
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"Loaded {len(cached_records)} records for {self.zone_name} from cache in {elapsed:.1f}ms")
                self.signals.finished.emit(True, cached_records, self.zone_name, f"Loaded {len(cached_records)} records from cache")
            else:
                self.signals.finished.emit(False, [], self.zone_name, "No cached records available")


class LoadZonesWorker(QRunnable):
    """Worker for asynchronous loading of zone data with optimized performance."""
    
    class Signals(QObject):
        """Signal wrapper for thread-safe communication."""
        finished = Signal(bool, object, str)
    
    def __init__(self, api_client, cache_manager):
        """Initialize the worker.
        
        Args:
            api_client: API client instance
            cache_manager: Cache manager instance
        """
        super().__init__()
        self.api_client = api_client
        self.cache_manager = cache_manager
        self.signals = self.Signals()
    
    def run(self) -> None:
        """Execute the worker to load zones from API or cache."""
        start_time = time.time()
        
        if self.api_client.is_online:
            # Online mode - get zones from API
            success, response = self.api_client.get_zones()
            
            if success:
                # Cache zones for future use with optimized indexing
                self.cache_manager.cache_zones(response)
                elapsed = (time.time() - start_time) * 1000
                logger.debug(f"Retrieved and cached {len(response)} zones in {elapsed:.1f}ms")
                self.signals.finished.emit(True, response, "")
            else:
                error_msg = f"Failed to load zones: {response}"
                # Try to load from cache as fallback
                cached_zones, timestamp = self.cache_manager.get_cached_zones()
                
                if cached_zones is not None:
                    self.signals.finished.emit(False, cached_zones, error_msg)
                else:
                    self.signals.finished.emit(False, [], error_msg)
        else:
            # Offline mode - get zones from cache
            cached_zones, timestamp = self.cache_manager.get_cached_zones()
            
            if cached_zones is not None:
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"Loaded {len(cached_zones)} zones from cache in {elapsed:.1f}ms")
                self.signals.finished.emit(True, cached_zones, f"Loaded {len(cached_zones)} zones from cache")
            else:
                self.signals.finished.emit(False, [], "No cached zones available")
