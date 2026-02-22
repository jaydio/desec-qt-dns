#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
API Client for interacting with deSEC DNS API.
Provides methods for managing DNS zones and records.
"""

import json
import logging
import requests
from datetime import datetime
import time
from threading import Lock

logger = logging.getLogger(__name__)

class APIClient:
    """Client for the deSEC API that handles requests and responses."""
    
    def __init__(self, config_manager):
        """
        Initialize the API client.
        
        Args:
            config_manager: ConfigManager instance that provides API URL and auth token
        """
        self.config_manager = config_manager
        self.last_error = None
        self.is_online = False
        
        # Rate limiting
        self._rate_limit_lock = Lock()
        self._last_request_time = 0
        
        self.check_connectivity()
    
    def _get_headers(self):
        """
        Create headers for API requests including authentication.
        
        Returns:
            dict: Headers for API requests
        """
        return {
            'Authorization': f'Token {self.config_manager.get_auth_token()}',
            'Content-Type': 'application/json'
        }
    
    def _apply_rate_limit(self):
        """
        Apply rate limiting to prevent API throttling.
        Waits if necessary to maintain the configured rate limit.
        """
        with self._rate_limit_lock:
            # Get rate limit from config (requests per second, default 2)
            rate_limit = self.config_manager.get_setting('api_rate_limit', 2.0)
            
            if rate_limit <= 0:
                return  # No rate limiting
            
            # Calculate minimum time between requests
            min_interval = 1.0 / rate_limit
            
            # Calculate time since last request
            current_time = time.time()
            time_since_last = current_time - self._last_request_time
            
            # Wait if we need to throttle
            if time_since_last < min_interval:
                sleep_time = min_interval - time_since_last
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.3f}s")
                time.sleep(sleep_time)
            
            # Update last request time
            self._last_request_time = time.time()
    
    def _make_request(self, method, endpoint, data=None, params=None):
        """
        Make a request to the deSEC API.
        
        Args:
            method (str): HTTP method (GET, POST, PUT, PATCH, DELETE)
            endpoint (str): API endpoint
            data (dict, optional): Request payload
            params (dict, optional): Query parameters
            
        Returns:
            tuple: (success, response_data or error_message)
        """
        # Apply rate limiting before making the request
        self._apply_rate_limit()
        
        url = f"{self.config_manager.get_api_url()}{endpoint}"
        headers = self._get_headers()
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=10)
            elif method == 'PATCH':
                response = requests.patch(url, headers=headers, json=data, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)
            else:
                return False, f"Unsupported HTTP method: {method}"
            
            # Check if request was successful
            response.raise_for_status()
            
            # Update online status
            self.is_online = True
            
            # Return parsed JSON if there's content, otherwise return empty dict
            if response.content:
                return True, response.json()
            return True, {}
            
        except requests.exceptions.ConnectionError as e:
            self.is_online = False
            self.last_error = f"Connection error: {str(e)}"
            logger.error(self.last_error)
            return False, "Connection error. Please check your internet connection."
        
        except requests.exceptions.Timeout:
            self.last_error = "Request timed out"
            logger.error(self.last_error)
            return False, "Request timed out. Please try again later."
        
        except requests.exceptions.HTTPError as e:
            self.last_error = f"HTTP error {e.response.status_code}: {e.response.text}"
            logger.error(self.last_error)
            
            # Try to parse error response
            error_message = "An error occurred"
            parsed_response = {}
            
            try:
                error_data = e.response.json()
                parsed_response = error_data  # Store parsed response for returning
                
                # Handle various error formats from deSEC API
                if isinstance(error_data, dict):
                    # Case: Detailed error with field-specific messages
                    if 'non_field_errors' in error_data:
                        error_message = "; ".join(error_data['non_field_errors'])
                    # Case: Duplicate record error
                    elif 'detail' in error_data and 'already exists' in error_data['detail']:
                        error_message = f"Duplicate record: {error_data['detail']}"
                    # Case: Other field errors
                    elif any(k for k in error_data.keys() if k not in ['detail']):
                        field_errors = []
                        for field, msgs in error_data.items():
                            if isinstance(msgs, list):
                                field_errors.append(f"{field}: {'; '.join(msgs)}")
                            else:
                                field_errors.append(f"{field}: {msgs}")
                        error_message = " | ".join(field_errors)
                    # Case: Simple detail message
                    elif 'detail' in error_data:
                        error_message = error_data['detail']
                elif isinstance(error_data, list) and error_data:
                    error_message = "; ".join(str(err) for err in error_data)
            except ValueError:
                error_message = e.response.text
            
            # Return both a human-readable message and the parsed response    
            return False, {"message": f"Error {e.response.status_code}: {error_message}", "raw_response": parsed_response}
        
        except Exception as e:
            self.last_error = f"Unexpected error: {str(e)}"
            logger.error(self.last_error)
            return False, f"An unexpected error occurred: {str(e)}"
    
    def check_connectivity(self):
        """
        Check if the API is reachable and authentication is valid.
        
        Returns:
            bool: True if API is accessible and auth token is valid
        """
        if not self.config_manager.get_auth_token():
            self.is_online = False
            return False
        
        # Try to retrieve domains as a connectivity test
        success, _ = self._make_request('GET', '/domains/')
        return success
    
    def get_account_info(self):
        """
        Get account information including domain limit.

        Returns:
            tuple: (success, account data dict or error message)
        """
        return self._make_request('GET', '/auth/account/')

    def get_zones(self):
        """
        Get all domains (zones) for the authenticated user.
        
        Returns:
            tuple: (success, list of domains or error message)
        """
        return self._make_request('GET', '/domains/')
    
    def create_zone(self, name):
        """
        Create a new domain (zone).
        
        Args:
            name (str): Domain name
            
        Returns:
            tuple: (success, zone data or error message)
        """
        data = {'name': name}
        return self._make_request('POST', '/domains/', data)
    
    def delete_zone(self, name):
        """
        Delete a domain (zone).
        
        Args:
            name (str): Domain name
            
        Returns:
            tuple: (success, empty dict or error message)
        """
        return self._make_request('DELETE', f'/domains/{name}/')
    
    def get_records(self, domain_name, subname=None, type=None):
        """
        Get DNS records for a domain.
        
        Args:
            domain_name (str): Domain name
            subname (str, optional): Filter by subname
            type (str, optional): Filter by record type
            
        Returns:
            tuple: (success, list of records or error message)
        """
        params = {}
        if subname is not None:
            params['subname'] = subname
        if type is not None:
            params['type'] = type
            
        return self._make_request('GET', f'/domains/{domain_name}/rrsets/', params=params)
    
    def create_record(self, domain_name, subname, type, ttl, records):
        """
        Create a new DNS record.
        
        Args:
            domain_name (str): Domain name
            subname (str): Subdomain (or empty string for apex)
            type (str): Record type (A, CNAME, MX, TXT, etc.)
            ttl (int): Time to live in seconds
            records (list): List of record content strings
            
        Returns:
            tuple: (success, record data or error message)
        """
        data = {
            'subname': subname,
            'type': type,
            'ttl': ttl,
            'records': records
        }
        return self._make_request('POST', f'/domains/{domain_name}/rrsets/', data)
    
    def update_record(self, domain_name, subname, type, ttl, records):
        """
        Update an existing DNS record.
        
        Args:
            domain_name (str): Domain name
            subname (str): Subdomain (or empty string for apex)
            type (str): Record type (A, CNAME, MX, TXT, etc.)
            ttl (int): Time to live in seconds
            records (list): List of record content strings
            
        Returns:
            tuple: (success, record data or error message)
        """
        data = {
            'ttl': ttl,
            'records': records
        }
        
        # Handle apex (@) records
        if subname == "@" or not subname:
            endpoint = f'/domains/{domain_name}/rrsets/@/{type}/'
        else:
            endpoint = f'/domains/{domain_name}/rrsets/{subname}/{type}/'
            
        return self._make_request('PATCH', endpoint, data)
    
    def delete_record(self, domain_name, subname, type):
        """
        Delete a DNS record.

        Args:
            domain_name (str): Domain name
            subname (str): Subdomain (or empty string for apex)
            type (str): Record type (A, CNAME, MX, TXT, etc.)

        Returns:
            tuple: (success, empty dict or error message)
        """
        # Handle apex (@) records
        if subname == "@" or not subname:
            endpoint = f'/domains/{domain_name}/rrsets/@/{type}/'
        else:
            endpoint = f'/domains/{domain_name}/rrsets/{subname}/{type}/'

        return self._make_request('DELETE', endpoint)

    # -------------------------------------------------------------------------
    # Token management
    # -------------------------------------------------------------------------

    def list_tokens(self):
        """
        List all API tokens for the authenticated account.
        Requires perm_manage_tokens on the current token.

        Returns:
            tuple: (success, list of token dicts or error message)
        """
        return self._make_request('GET', '/auth/tokens/')

    def create_token(self, name, perm_create_domain=True, perm_delete_domain=True,
                     perm_manage_tokens=False, max_age=None, max_unused_period=None,
                     allowed_subnets=None, auto_policy=False):
        """
        Create a new API token.

        Args:
            name (str): Human-readable label for the token
            perm_create_domain (bool): Allow creating domains
            perm_delete_domain (bool): Allow deleting domains
            perm_manage_tokens (bool): Allow managing tokens
            max_age (str or None): Age-based expiration e.g. '30 00:00:00'
            max_unused_period (str or None): Inactivity expiration e.g. '7 00:00:00'
            allowed_subnets (list or None): List of CIDR strings; None = unrestricted
            auto_policy (bool): Auto-create permissive policy on domain creation

        Returns:
            tuple: (success, token dict including one-time secret 'token' field)
        """
        data = {
            'name': name,
            'perm_create_domain': perm_create_domain,
            'perm_delete_domain': perm_delete_domain,
            'perm_manage_tokens': perm_manage_tokens,
            'auto_policy': auto_policy,
        }
        if max_age is not None:
            data['max_age'] = max_age
        if max_unused_period is not None:
            data['max_unused_period'] = max_unused_period
        if allowed_subnets is not None:
            data['allowed_subnets'] = allowed_subnets
        return self._make_request('POST', '/auth/tokens/', data)

    def get_token(self, token_id):
        """
        Retrieve a specific API token by ID.

        Args:
            token_id (str): Token UUID

        Returns:
            tuple: (success, token dict or error message)
        """
        return self._make_request('GET', f'/auth/tokens/{token_id}/')

    def update_token(self, token_id, **fields):
        """
        Update an existing API token (partial update).

        Args:
            token_id (str): Token UUID
            **fields: Fields to update (name, perm_*, max_age, max_unused_period,
                      allowed_subnets, auto_policy)

        Returns:
            tuple: (success, updated token dict or error message)
        """
        return self._make_request('PATCH', f'/auth/tokens/{token_id}/', fields)

    def delete_token(self, token_id):
        """
        Delete an API token.

        Args:
            token_id (str): Token UUID

        Returns:
            tuple: (success, empty dict or error message)
        """
        return self._make_request('DELETE', f'/auth/tokens/{token_id}/')

    # -------------------------------------------------------------------------
    # Token policy management
    # -------------------------------------------------------------------------

    def list_token_policies(self, token_id):
        """
        List all RRset policies for a token.

        Args:
            token_id (str): Token UUID

        Returns:
            tuple: (success, list of policy dicts or error message)
        """
        return self._make_request('GET', f'/auth/tokens/{token_id}/policies/rrsets/')

    def create_token_policy(self, token_id, domain=None, subname=None,
                            type_=None, perm_write=False):
        """
        Create an RRset policy for a token.

        Args:
            token_id (str): Token UUID
            domain (str or None): Domain name; None = default policy
            subname (str or None): Subname; None = match all
            type_ (str or None): Record type; None = match all
            perm_write (bool): Grant write permission

        Returns:
            tuple: (success, policy dict or error message)
        """
        # Always include domain, subname, and type — even when None.
        # The API requires these fields to be present (as JSON null means "match all").
        data = {
            'perm_write': perm_write,
            'domain': domain,
            'subname': subname,
            'type': type_,
        }
        return self._make_request('POST', f'/auth/tokens/{token_id}/policies/rrsets/', data)

    def update_token_policy(self, token_id, policy_id, **fields):
        """
        Update an existing RRset policy (partial update).

        Args:
            token_id (str): Token UUID
            policy_id (str): Policy UUID
            **fields: Fields to update (domain, subname, type, perm_write)

        Returns:
            tuple: (success, updated policy dict or error message)
        """
        return self._make_request(
            'PATCH', f'/auth/tokens/{token_id}/policies/rrsets/{policy_id}/', fields
        )

    def delete_token_policy(self, token_id, policy_id):
        """
        Delete an RRset policy from a token.

        Args:
            token_id (str): Token UUID
            policy_id (str): Policy UUID

        Returns:
            tuple: (success, empty dict or error message)
        """
        return self._make_request(
            'DELETE', f'/auth/tokens/{token_id}/policies/rrsets/{policy_id}/'
        )
