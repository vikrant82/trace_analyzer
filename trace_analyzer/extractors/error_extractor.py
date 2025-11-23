"""
Error extractor for OpenTelemetry spans.

Provides intelligent error message extraction with multiple fallback sources
to avoid generic "Unknown Error" messages when status.message is empty.
"""

import re
from typing import Dict, Optional, Tuple


class ErrorExtractor:
    """Extracts detailed error information from OpenTelemetry spans."""
    
    # HTTP status code to description mapping
    HTTP_STATUS_MESSAGES = {
        # 4xx Client Errors
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        408: "Request Timeout",
        409: "Conflict",
        410: "Gone",
        413: "Payload Too Large",
        414: "URI Too Long",
        415: "Unsupported Media Type",
        429: "Too Many Requests",
        
        # 5xx Server Errors
        500: "Internal Server Error",
        501: "Not Implemented",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
        505: "HTTP Version Not Supported",
        507: "Insufficient Storage",
        508: "Loop Detected",
        511: "Network Authentication Required"
    }
    
    @staticmethod
    def extract_error_details(span: Dict) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Extract comprehensive error details from a span.
        
        Returns a tuple of (is_error, error_message, http_status_code).
        
        Error message priority:
        1. status.message (if non-empty)
        2. HTTP status code + standard text (e.g., "HTTP 404: Not Found")
        3. exception.message attribute
        4. exception.type attribute
        5. error.message attribute
        6. Span name (e.g., "Error in GET /api/users/{id}")
        7. "Unknown Error" (final fallback)
        
        Args:
            span: OpenTelemetry span dictionary
            
        Returns:
            Tuple of (is_error: bool, error_message: Optional[str], http_status_code: Optional[int])
        """
        span_status = span.get('status', {})
        status_code = span_status.get('code', 0)
        
        # OpenTelemetry status codes: 0=UNSET/OK, 1=ERROR, 2=ERROR
        is_error = status_code in [1, 2]
        
        if not is_error:
            return False, None, None
        
        # Extract HTTP status code from attributes
        http_status_code = ErrorExtractor._extract_http_status_code(span)
        
        # Priority 1: Use status.message if non-empty
        status_message = span_status.get('message', '').strip()
        if status_message:
            return True, status_message, http_status_code
        
        # Priority 2: Use HTTP status code if available
        if http_status_code:
            http_message = ErrorExtractor._format_http_status_message(http_status_code)
            return True, http_message, http_status_code
        
        # Priority 3-5: Check exception and error attributes
        attributes = span.get('attributes', [])
        for attr in attributes:
            key = attr.get('key', '')
            
            # Priority 3: exception.message
            if key == 'exception.message':
                value = ErrorExtractor._extract_attribute_value(attr)
                if value:
                    return True, value, http_status_code
            
            # Priority 4: exception.type
            if key == 'exception.type':
                value = ErrorExtractor._extract_attribute_value(attr)
                if value:
                    return True, value, http_status_code
            
            # Priority 5: error.message
            if key == 'error.message':
                value = ErrorExtractor._extract_attribute_value(attr)
                if value:
                    return True, value, http_status_code
        
        
        # Priority 6: Construct descriptive message from HTTP attributes or span name
        span_name = span.get('name', '').strip()
        
        # If span name is too generic (just HTTP method), try to construct better message
        http_method = ErrorExtractor._extract_http_method(attributes)
        http_url = ErrorExtractor._extract_http_url(attributes)
        
        if http_method and http_url and span_name in [http_method, f'HTTP {http_method}', 'HTTP']:
            # Span name is generic, construct from URL
            # Extract path from URL (remove domain and query params)
            path_match = re.search(r'https?://[^/]+(/[^?]*)', http_url)
            if path_match:
                path = path_match.group(1)
                # Truncate very long paths
                if len(path) > 80:
                    path = path[:77] + '...'
                return True, f"Error in {http_method} {path}", http_status_code
        
        # Fallback to span name if it's descriptive
        if span_name:
            return True, f"Error in {span_name}", http_status_code
        
        # Priority 7: Final fallback
        return True, "Unknown Error", http_status_code
    
    @staticmethod
    def _extract_http_method(attributes: list) -> Optional[str]:
        """Extract HTTP method from attributes."""
        for attr in attributes:
            if attr.get('key') == 'http.method':
                return ErrorExtractor._extract_attribute_value(attr)
        return None
    
    @staticmethod
    def _extract_http_url(attributes: list) -> Optional[str]:
        """Extract HTTP URL from attributes."""
        for attr in attributes:
            if attr.get('key') == 'http.url':
                return ErrorExtractor._extract_attribute_value(attr)
        return None
    
    @staticmethod
    def _extract_http_status_code(span: Dict) -> Optional[int]:
        """
        Extract HTTP status code from span attributes.
        
        Args:
            span: OpenTelemetry span dictionary
            
        Returns:
            HTTP status code as integer, or None if not found
        """
        attributes = span.get('attributes', [])
        for attr in attributes:
            if attr.get('key') == 'http.status_code':
                value = attr.get('value', {})
                status_code = value.get('intValue') or value.get('stringValue')
                if status_code:
                    try:
                        return int(status_code)
                    except (ValueError, TypeError):
                        pass
        return None
    
    @staticmethod
    def _extract_attribute_value(attr: Dict) -> Optional[str]:
        """
        Extract string value from an attribute's value field.
        
        Args:
            attr: Attribute dictionary with 'value' field
            
        Returns:
            String value or None
        """
        value = attr.get('value', {})
        str_value = value.get('stringValue', '').strip()
        if str_value:
            return str_value
        
        # Try intValue as fallback
        int_value = value.get('intValue')
        if int_value is not None:
            return str(int_value)
        
        return None
    
    @staticmethod
    def _format_http_status_message(status_code: int) -> str:
        """
        Format HTTP status code into a human-readable error message.
        
        Args:
            status_code: HTTP status code (e.g., 404, 503)
            
        Returns:
            Formatted message (e.g., "HTTP 404: Not Found")
        """
        description = ErrorExtractor.HTTP_STATUS_MESSAGES.get(
            status_code,
            "Error" if status_code >= 400 else "Unknown Status"
        )
        return f"HTTP {status_code}: {description}"
