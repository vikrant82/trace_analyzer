"""
URL path normalization and parameter extraction.
"""

import re
from typing import Tuple, List
from urllib.parse import urlparse


class PathNormalizer:
    """Normalizes URL paths by replacing dynamic parameters with placeholders."""
    
    def __init__(self):
        """Initialize regex patterns for various parameter types."""
        self.uuid_pattern = re.compile(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            re.IGNORECASE
        )
        self.numeric_id_pattern = re.compile(r'/\d+(?=/|\?|$)')
        self.rule_identifier_pattern = re.compile(
            r'/[A-Z][A-Za-z0-9-]*__[A-Za-z0-9_]+(?=/|\?|$)'
        )
        self.long_encoded_pattern = re.compile(r'/[A-Za-z0-9_-]{30,}(?=/|\?|$)')
        self.semver_pattern = re.compile(r'/\d+\.\d+\.\d+(?:\.\d+)?(?=/|\?|$)')
    
    def normalize_path(self, path: str, strip_query_params: bool = True) -> Tuple[str, List[str]]:
        """
        Normalize a path by replacing parameter values with placeholders.
        Handles both full URLs and relative paths, extracting only the path component.
        
        Args:
            path: URL or path string to normalize
            strip_query_params: If True, removes query parameters from the path
            
        Returns:
            Tuple of (normalized_path, non_uuid_params)
            - normalized_path: Path with parameters replaced by placeholders
            - non_uuid_params: List of non-UUID parameter values extracted
        """
        if not path:
            return path, []
        
        # If it's a full URL, parse it to get only the path
        if '://' in path:
            path = urlparse(path).path
        
        # Strip query parameters if requested
        if strip_query_params and '?' in path:
            path = path.split('?')[0]
        
        non_uuid_params = []
        normalized = path
        
        # Replace UUIDs with {uuid}
        uuid_matches = list(self.uuid_pattern.finditer(path))
        for match in uuid_matches:
            normalized = normalized.replace(match.group(0), '{uuid}', 1)
        
        # Replace rule identifiers with {rule_id}
        rule_matches = list(self.rule_identifier_pattern.finditer(path))
        for match in rule_matches:
            param_value = match.group(0)[1:]  # Remove leading slash
            non_uuid_params.append(param_value)
            normalized = normalized.replace(match.group(0), '/{rule_id}', 1)
        
        # Replace long encoded strings with {encoded_id}
        long_encoded_matches = list(self.long_encoded_pattern.finditer(path))
        for match in long_encoded_matches:
            param_value = match.group(0)[1:]  # Remove leading slash
            
            # Check if this match overlaps with UUID or rule matches
            is_already_matched = False
            for uuid_match in uuid_matches:
                if (match.start() <= uuid_match.start() < match.end() or
                        uuid_match.start() <= match.start() < uuid_match.end()):
                    is_already_matched = True
                    break
            
            if not is_already_matched:
                for rule_match in rule_matches:
                    if (match.start() <= rule_match.start() < match.end() or
                            rule_match.start() <= match.start() < rule_match.end()):
                        is_already_matched = True
                        break
            
            if not is_already_matched:
                non_uuid_params.append(param_value)
                normalized = normalized.replace(match.group(0), '/{encoded_id}', 1)
        
        # Replace semantic version strings (e.g., 4.3.8, 1.0.0.1) with {version}
        for match in self.semver_pattern.finditer(path):
            param_value = match.group(0)[1:]  # Remove leading slash
            if param_value not in non_uuid_params:
                non_uuid_params.append(param_value)
                normalized = normalized.replace(match.group(0), '/{version}', 1)
        
        # Replace numeric IDs with {id}
        for match in self.numeric_id_pattern.finditer(path):
            param_value = match.group(0)[1:]  # Remove leading slash
            if param_value not in non_uuid_params:
                non_uuid_params.append(param_value)
                normalized = normalized.replace(match.group(0), '/{id}', 1)
        
        return normalized, non_uuid_params
