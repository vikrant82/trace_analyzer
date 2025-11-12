"""
Unit tests for trace_analyzer.extractors.path_normalizer module.
"""
import pytest
from trace_analyzer.extractors.path_normalizer import PathNormalizer


class TestPathNormalizer:
    """Tests for the PathNormalizer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.normalizer = PathNormalizer()
    
    def test_normalize_uuid_in_path(self):
        """Test normalizing paths with UUIDs."""
        normalizer = PathNormalizer()
        path = "/api/users/550e8400-e29b-41d4-a716-446655440000/profile"
        normalized, params = normalizer.normalize_path(path)
        
        assert normalized == "/api/users/{uuid}/profile"
        assert "uuid" in params
        assert params["uuid"] == "550e8400-e29b-41d4-a716-446655440000"
    
    def test_normalize_numeric_id(self):
        """Test normalizing paths with numeric IDs."""
        normalizer = PathNormalizer()
        path = "/api/orders/12345/items"
        normalized, params = normalizer.normalize_path(path)
        
        assert normalized == "/api/orders/{id}/items"
        assert "id" in params
        assert params["id"] == "12345"
    
    def test_normalize_multiple_ids(self):
        """Test normalizing paths with multiple IDs."""
        normalizer = PathNormalizer()
        path = "/api/users/123/posts/456/comments"
        normalized, params = normalizer.normalize_path(path)
        
        assert "{id}" in normalized
        assert len(params) >= 2
    
    def test_normalize_long_encoded_string(self):
        """Test normalizing paths with long encoded strings."""
        normalizer = PathNormalizer()
        path = "/api/token/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9/verify"
        normalized, params = normalizer.normalize_path(path)
        
        # Should normalize long encoded strings
        assert "{token}" in normalized or "{id}" in normalized or "{encoded}" in normalized
    
    def test_no_normalization_needed(self):
        """Test paths that don't need normalization."""
        normalizer = PathNormalizer()
        path = "/api/users"
        normalized, params = normalizer.normalize_path(path)
        
        assert normalized == "/api/users"
        assert len(params) == 0
    
    def test_normalize_with_query_params(self):
        """Test normalizing paths with query parameters."""
        normalizer = PathNormalizer()
        path = "/api/search?query=test&limit=10"
        
        # Should handle query params
        result = normalizer.normalize_path(path)
        assert result is not None
    
    def test_normalize_root_path(self):
        """Test normalizing root path."""
        normalizer = PathNormalizer()
        path = "/"
        normalized, params = normalizer.normalize_path(path)
        
        assert normalized == "/"
        assert len(params) == 0
    
    def test_normalize_empty_path(self):
        """Test normalizing empty path."""
        normalizer = PathNormalizer()
        path = ""
        normalized, params = normalizer.normalize_path(path)
        
        assert normalized == ""
        assert len(params) == 0
    
    def test_normalize_hex_id(self):
        """Test normalizing paths with hexadecimal IDs."""
        normalizer = PathNormalizer()
        path = "/api/sessions/a1b2c3d4e5f6/data"
        normalized, params = normalizer.normalize_path(path)
        
        assert "{id}" in normalized or "{hex}" in normalized
    
    def test_preserve_static_segments(self):
        """Test that static path segments are preserved."""
        normalizer = PathNormalizer()
        path = "/api/v2/users/123/profile/settings"
        normalized, params = normalizer.normalize_path(path)
        
        assert "/api/" in normalized
        assert "users" in normalized
        assert "profile" in normalized
        assert "settings" in normalized
    
    def test_mixed_parameters(self):
        """Test paths with mixed parameter types."""
        normalizer = PathNormalizer()
        path = "/api/users/550e8400-e29b-41d4-a716-446655440000/orders/789"
        normalized, params = normalizer.normalize_path(path)
        
        assert "{uuid}" in normalized or "{id}" in normalized
        assert len(params) >= 2
