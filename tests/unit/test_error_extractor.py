"""
Unit tests for ErrorExtractor.

Tests the intelligent error message extraction logic with various
fallback scenarios.
"""
import pytest
from trace_analyzer.extractors.error_extractor import ErrorExtractor


class TestErrorExtractor:
    """Test suite for ErrorExtractor class."""
    
    def test_no_error_status(self):
        """Test span with no error status (code 0)."""
        span = {
            'status': {'code': 0, 'message': 'OK'},
            'attributes': []
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is False
        assert error_message is None
        assert http_status_code is None
    
    def test_error_with_message(self):
        """Test error span with explicit status message."""
        span = {
            'status': {'code': 2, 'message': 'Connection timeout'},
            'attributes': [
                {'key': 'http.status_code', 'value': {'intValue': 504}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'Connection timeout'
        assert http_status_code == 504
    
    def test_error_empty_message_with_http_status(self):
        """Test error span with empty message but HTTP status code."""
        span = {
            'status': {'code': 2, 'message': ''},
            'attributes': [
                {'key': 'http.status_code', 'value': {'intValue': 404}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'HTTP 404: Not Found'
        assert http_status_code == 404
    
    def test_error_empty_message_with_http_503(self):
        """Test error span with HTTP 503 Service Unavailable."""
        span = {
            'status': {'code': 2, 'message': ''},
            'attributes': [
                {'key': 'http.status_code', 'value': {'intValue': 503}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'HTTP 503: Service Unavailable'
        assert http_status_code == 503
    
    def test_error_empty_message_with_http_500(self):
        """Test error span with HTTP 500 Internal Server Error."""
        span = {
            'status': {'code': 2, 'message': ''},
            'attributes': [
                {'key': 'http.status_code', 'value': {'intValue': 500}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'HTTP 500: Internal Server Error'
        assert http_status_code == 500
    
    def test_error_with_exception_message(self):
        """Test error span with exception.message attribute."""
        span = {
            'status': {'code': 2, 'message': ''},
            'attributes': [
                {'key': 'exception.message', 'value': {'stringValue': 'NullPointerException'}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'NullPointerException'
        assert http_status_code is None
    
    def test_error_with_exception_type(self):
        """Test error span with exception.type attribute."""
        span = {
            'status': {'code': 2, 'message': ''},
            'attributes': [
                {'key': 'exception.type', 'value': {'stringValue': 'java.sql.SQLException'}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'java.sql.SQLException'
        assert http_status_code is None
    
    def test_error_with_error_message_attribute(self):
        """Test error span with error.message attribute."""
        span = {
            'status': {'code': 2, 'message': ''},
            'attributes': [
                {'key': 'error.message', 'value': {'stringValue': 'Validation failed'}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'Validation failed'
        assert http_status_code is None
    
    def test_error_with_span_name_fallback(self):
        """Test error span falling back to span name."""
        span = {
            'name': 'GET /api/users/{id}',
            'status': {'code': 2, 'message': ''},
            'attributes': []
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'Error in GET /api/users/{id}'
        assert http_status_code is None
    
    def test_error_unknown_fallback(self):
        """Test error span with no information (final fallback)."""
        span = {
            'status': {'code': 2, 'message': ''},
            'attributes': []
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'Unknown Error'
        assert http_status_code is None
    
    def test_http_status_string_value(self):
        """Test HTTP status code extraction from stringValue."""
        span = {
            'status': {'code': 2, 'message': ''},
            'attributes': [
                {'key': 'http.status_code', 'value': {'stringValue': '404'}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'HTTP 404: Not Found'
        assert http_status_code == 404
    
    def test_priority_status_message_over_http_code(self):
        """Test that status.message takes priority over HTTP status code."""
        span = {
            'status': {'code': 2, 'message': 'Custom error message'},
            'attributes': [
                {'key': 'http.status_code', 'value': {'intValue': 500}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'Custom error message'
        assert http_status_code == 500  # Still extracted but not used for message
    
    def test_priority_http_code_over_exception(self):
        """Test that HTTP status code takes priority over exception attributes."""
        span = {
            'status': {'code': 2, 'message': ''},
            'attributes': [
                {'key': 'http.status_code', 'value': {'intValue': 404}},
                {'key': 'exception.message', 'value': {'stringValue': 'Some exception'}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'HTTP 404: Not Found'
        assert http_status_code == 404
    
    def test_http_status_unknown_code(self):
        """Test HTTP status code not in the standard mapping."""
        span = {
            'status': {'code': 2, 'message': ''},
            'attributes': [
                {'key': 'http.status_code', 'value': {'intValue': 499}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'HTTP 499: Error'
        assert http_status_code == 499
    
    def test_whitespace_trimming(self):
        """Test that whitespace in status message is trimmed."""
        span = {
            'status': {'code': 2, 'message': '  Whitespace error  '},
            'attributes': []
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'Whitespace error'
        assert http_status_code is None
    
    def test_error_code_1(self):
        """Test that status code 1 is also treated as error."""
        span = {
            'status': {'code': 1, 'message': 'Error code 1'},
            'attributes': []
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'Error code 1'
        assert http_status_code is None
    
    def test_generic_span_name_with_http_url(self):
        """Test that generic span names like 'GET' are enhanced with URL path."""
        span = {
            'name': 'GET',
            'status': {'code': 2, 'message': ''},
            'attributes': [
                {'key': 'http.method', 'value': {'stringValue': 'GET'}},
                {'key': 'http.url', 'value': {'stringValue': 'http://mss-service.example.com/v2/cache/data'}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'Error in GET /v2/cache/data'
        assert http_status_code is None
    
    def test_generic_span_name_post(self):
        """Test generic 'POST' span name."""
        span = {
            'name': 'POST',
            'status': {'code': 2, 'message': ''},
            'attributes': [
                {'key': 'http.method', 'value': {'stringValue': 'POST'}},
                {'key': 'http.url', 'value': {'stringValue': 'http://api.example.com/api/orders'}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message == 'Error in POST /api/orders'
        assert http_status_code is None
    
    def test_generic_span_name_long_path(self):
        """Test that very long paths are truncated."""
        long_path = '/api/very/long/path/that/exceeds/eighty/characters/and/should/be/truncated/for/readability'
        span = {
            'name': 'GET',
            'status': {'code': 2, 'message': ''},
            'attributes': [
                {'key': 'http.method', 'value': {'stringValue': 'GET'}},
                {'key': 'http.url', 'value': {'stringValue': f'http://example.com{long_path}'}}
            ]
        }
        
        is_error, error_message, http_status_code = ErrorExtractor.extract_error_details(span)
        
        assert is_error is True
        assert error_message.startswith('Error in GET /api/very/long/path/')
        assert error_message.endswith('...')
        assert len(error_message) <= 100  # "Error in GET " + 80 chars + "..." = ~93 chars
