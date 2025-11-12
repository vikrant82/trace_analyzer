"""
HTTP information extraction from OpenTelemetry span attributes.
"""

from typing import List, Dict
from urllib.parse import urlparse


class HttpExtractor:
    """Extracts HTTP-related information from span attributes."""
    
    @staticmethod
    def extract_http_path(attributes: List[Dict]) -> str:
        """
        Extract HTTP path/URL from span attributes.
        Searches for 'http.url', 'http.target', and 'http.path'.
        
        Args:
            attributes: List of span attribute dictionaries
            
        Returns:
            HTTP path/URL string or empty string if not found
        """
        for attr in attributes:
            if attr.get('key') in ['http.url', 'http.target', 'http.path']:
                value = attr.get('value', {})
                return value.get('stringValue', '')
        return ''
    
    @staticmethod
    def extract_http_method(attributes: List[Dict]) -> str:
        """
        Extract HTTP method from span attributes.
        
        Args:
            attributes: List of span attribute dictionaries
            
        Returns:
            HTTP method (GET, POST, etc.) or empty string if not found
        """
        for attr in attributes:
            if attr.get('key') == 'http.method':
                return attr.get('value', {}).get('stringValue', '')
        return ''
    
    @staticmethod
    def extract_service_name(resource_attributes: List[Dict]) -> str:
        """
        Extract service name from resource attributes.
        
        Args:
            resource_attributes: List of resource attribute dictionaries
            
        Returns:
            Service name or 'unknown-service' if not found
        """
        for attr in resource_attributes:
            if attr.get('key') == 'service.name':
                value = attr.get('value', {})
                return value.get('stringValue', 'unknown-service')
        return 'unknown-service'
    
    @staticmethod
    def extract_target_service_from_url(url: str) -> str:
        """
        Extract target service name from a full URL.
        
        Args:
            url: Full URL string
            
        Returns:
            Service name extracted from hostname or 'unknown-service'
        """
        if '://' in url:
            host = urlparse(url).hostname
            if host:
                return host.split('.')[0]
        return 'unknown-service'
