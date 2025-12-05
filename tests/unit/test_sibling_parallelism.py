"""
Unit tests for sibling parallelism detection in normalizer.
"""
import pytest
from unittest.mock import Mock, MagicMock
from trace_analyzer.processors.normalizer import HierarchyNormalizer
from trace_analyzer.processors.timing_calculator import TimingCalculator


class TestSiblingParallelismDetection:
    """Tests for cross-service sibling parallelism detection."""
    
    @pytest.fixture
    def normalizer(self):
        """Create a normalizer instance with mocked dependencies."""
        config = Mock()
        config.strip_query_params = True
        config.include_service_mesh = False
        
        http_extractor = Mock()
        http_extractor.extract_http_path.return_value = None
        http_extractor.extract_http_method.return_value = None
        
        path_normalizer = Mock()
        path_normalizer.normalize_path.return_value = ('/test', [])
        
        # Use real timing calculator for accurate calculations
        aggregator = Mock()
        timing_calculator = TimingCalculator(aggregator)
        
        return HierarchyNormalizer(config, http_extractor, path_normalizer, timing_calculator)
    
    def test_parallel_siblings_detected(self, normalizer):
        """Test that parallel sibling calls to different services are detected."""
        base = 1_000_000_000_000_000_000  # Base time in nanoseconds
        
        root_node = {
            'span': {'name': 'GET /api/composite', 'attributes': []},
            'service_name': 'api-gateway',
            'total_time_ms': 150.0,
            'self_time_ms': 150.0,
            'start_time_ns': base,
            'end_time_ns': base + 150_000_000,  # 150ms
            'children': [
                {
                    'span': {'name': 'POST /validate', 'attributes': []},
                    'service_name': 'auth-service',
                    'total_time_ms': 50.0,
                    'self_time_ms': 50.0,
                    'start_time_ns': base + 10_000_000,   # 10-60ms
                    'end_time_ns': base + 60_000_000,
                    'children': []
                },
                {
                    'span': {'name': 'GET /profile', 'attributes': []},
                    'service_name': 'user-service',
                    'total_time_ms': 60.0,
                    'self_time_ms': 60.0,
                    'start_time_ns': base + 20_000_000,   # 20-80ms (overlaps)
                    'end_time_ns': base + 80_000_000,
                    'children': []
                },
                {
                    'span': {'name': 'GET /history', 'attributes': []},
                    'service_name': 'order-service',
                    'total_time_ms': 70.0,
                    'self_time_ms': 70.0,
                    'start_time_ns': base + 30_000_000,   # 30-100ms (overlaps)
                    'end_time_ns': base + 100_000_000,
                    'children': []
                }
            ]
        }
        
        result = normalizer.normalize_and_aggregate_hierarchy(root_node)
        
        # Parent should have sibling parallelism markers
        assert result.get('sibling_parallelism') is True
        assert result.get('parallel_sibling_count') == 3
        
        # Parallelism factor: cumulative (180ms) / effective (90ms) = 2.0
        assert result.get('sibling_parallelism_factor') == pytest.approx(2.0, abs=0.1)
        assert result.get('sibling_effective_time_ms') == pytest.approx(90.0, abs=0.1)
        assert result.get('sibling_cumulative_time_ms') == pytest.approx(180.0, abs=0.1)
        
        # Each child should be marked as parallel sibling
        for child in result['children']:
            assert child.get('is_parallel_sibling') is True
    
    def test_sequential_siblings_not_marked(self, normalizer):
        """Test that sequential (non-overlapping) siblings are NOT marked as parallel."""
        base = 1_000_000_000_000_000_000
        
        root_node = {
            'span': {'name': 'GET /api/sequential', 'attributes': []},
            'service_name': 'api-gateway',
            'total_time_ms': 300.0,
            'self_time_ms': 300.0,
            'start_time_ns': base,
            'end_time_ns': base + 300_000_000,
            'children': [
                {
                    'span': {'name': 'POST /validate', 'attributes': []},
                    'service_name': 'auth-service',
                    'total_time_ms': 100.0,
                    'self_time_ms': 100.0,
                    'start_time_ns': base,                    # 0-100ms
                    'end_time_ns': base + 100_000_000,
                    'children': []
                },
                {
                    'span': {'name': 'GET /profile', 'attributes': []},
                    'service_name': 'user-service',
                    'total_time_ms': 100.0,
                    'self_time_ms': 100.0,
                    'start_time_ns': base + 100_000_000,      # 100-200ms (sequential)
                    'end_time_ns': base + 200_000_000,
                    'children': []
                },
                {
                    'span': {'name': 'GET /history', 'attributes': []},
                    'service_name': 'order-service',
                    'total_time_ms': 100.0,
                    'self_time_ms': 100.0,
                    'start_time_ns': base + 200_000_000,      # 200-300ms (sequential)
                    'end_time_ns': base + 300_000_000,
                    'children': []
                }
            ]
        }
        
        result = normalizer.normalize_and_aggregate_hierarchy(root_node)
        
        # Parent should NOT have sibling parallelism (factor would be ~1.0)
        assert result.get('sibling_parallelism') is not True
        
        # Children should NOT be marked
        for child in result['children']:
            assert child.get('is_parallel_sibling') is not True
    
    def test_single_child_not_marked(self, normalizer):
        """Test that a single child does not trigger sibling parallelism."""
        base = 1_000_000_000_000_000_000
        
        root_node = {
            'span': {'name': 'GET /api/single', 'attributes': []},
            'service_name': 'api-gateway',
            'total_time_ms': 100.0,
            'self_time_ms': 100.0,
            'start_time_ns': base,
            'end_time_ns': base + 100_000_000,
            'children': [
                {
                    'span': {'name': 'POST /validate', 'attributes': []},
                    'service_name': 'auth-service',
                    'total_time_ms': 50.0,
                    'self_time_ms': 50.0,
                    'start_time_ns': base + 10_000_000,
                    'end_time_ns': base + 60_000_000,
                    'children': []
                }
            ]
        }
        
        result = normalizer.normalize_and_aggregate_hierarchy(root_node)
        
        # Should NOT have sibling parallelism
        assert result.get('sibling_parallelism') is not True
        assert result['children'][0].get('is_parallel_sibling') is not True
    
    def test_partially_overlapping_siblings(self, normalizer):
        """Test with only partial overlap - should still detect parallelism."""
        base = 1_000_000_000_000_000_000
        
        root_node = {
            'span': {'name': 'GET /api/partial', 'attributes': []},
            'service_name': 'api-gateway',
            'total_time_ms': 200.0,
            'self_time_ms': 200.0,
            'start_time_ns': base,
            'end_time_ns': base + 200_000_000,
            'children': [
                {
                    'span': {'name': 'service-a', 'attributes': []},
                    'service_name': 'service-a',
                    'total_time_ms': 100.0,
                    'self_time_ms': 100.0,
                    'start_time_ns': base,                    # 0-100ms
                    'end_time_ns': base + 100_000_000,
                    'children': []
                },
                {
                    'span': {'name': 'service-b', 'attributes': []},
                    'service_name': 'service-b',
                    'total_time_ms': 100.0,
                    'self_time_ms': 100.0,
                    'start_time_ns': base + 50_000_000,       # 50-150ms (50ms overlap)
                    'end_time_ns': base + 150_000_000,
                    'children': []
                }
            ]
        }
        
        result = normalizer.normalize_and_aggregate_hierarchy(root_node)
        
        # Should detect sibling parallelism
        # Cumulative: 200ms, Effective: 150ms (0-150ms merged), Factor: ~1.33
        assert result.get('sibling_parallelism') is True
        assert result.get('parallel_sibling_count') == 2
        assert result.get('sibling_parallelism_factor') == pytest.approx(1.33, abs=0.1)
    
    def test_mixed_aggregated_and_siblings(self, normalizer):
        """Test with mixed scenario: some nodes aggregate, others don't."""
        base = 1_000_000_000_000_000_000
        
        # Mock http_extractor to return paths for aggregation
        normalizer.http_extractor.extract_http_path.side_effect = lambda attrs: '/items/{id}' if any(
            a.get('key') == 'http.url' and '/items/' in a.get('value', {}).get('stringValue', '')
            for a in attrs
        ) else None
        
        root_node = {
            'span': {'name': 'GET /api/mixed', 'attributes': []},
            'service_name': 'api-gateway',
            'total_time_ms': 200.0,
            'self_time_ms': 200.0,
            'start_time_ns': base,
            'end_time_ns': base + 200_000_000,
            'children': [
                {
                    'span': {'name': 'auth-check', 'attributes': []},
                    'service_name': 'auth-service',
                    'total_time_ms': 50.0,
                    'self_time_ms': 50.0,
                    'start_time_ns': base + 10_000_000,       # 10-60ms
                    'end_time_ns': base + 60_000_000,
                    'children': []
                },
                {
                    'span': {'name': 'get-user', 'attributes': []},
                    'service_name': 'user-service',
                    'total_time_ms': 60.0,
                    'self_time_ms': 60.0,
                    'start_time_ns': base + 20_000_000,       # 20-80ms (overlaps with auth)
                    'end_time_ns': base + 80_000_000,
                    'children': []
                }
            ]
        }
        
        result = normalizer.normalize_and_aggregate_hierarchy(root_node)
        
        # Should still detect sibling parallelism for the two services
        assert result.get('sibling_parallelism') is True
        assert result.get('parallel_sibling_count') == 2


class TestSiblingParallelismThreshold:
    """Tests for the 1.05 threshold for sibling parallelism."""
    
    @pytest.fixture
    def normalizer(self):
        """Create a normalizer instance."""
        config = Mock()
        config.strip_query_params = True
        config.include_service_mesh = False
        
        http_extractor = Mock()
        http_extractor.extract_http_path.return_value = None
        http_extractor.extract_http_method.return_value = None
        
        path_normalizer = Mock()
        
        aggregator = Mock()
        timing_calculator = TimingCalculator(aggregator)
        
        return HierarchyNormalizer(config, http_extractor, path_normalizer, timing_calculator)
    
    def test_below_threshold_not_marked(self, normalizer):
        """Test that near-sequential siblings (factor < 1.05) are not marked."""
        base = 1_000_000_000_000_000_000
        
        # Two siblings with minimal overlap (factor ~1.02)
        root_node = {
            'span': {'name': 'test', 'attributes': []},
            'service_name': 'gateway',
            'total_time_ms': 200.0,
            'self_time_ms': 200.0,
            'start_time_ns': base,
            'end_time_ns': base + 200_000_000,
            'children': [
                {
                    'span': {'name': 'a', 'attributes': []},
                    'service_name': 'service-a',
                    'total_time_ms': 100.0,
                    'self_time_ms': 100.0,
                    'start_time_ns': base,                    # 0-100ms
                    'end_time_ns': base + 100_000_000,
                    'children': []
                },
                {
                    'span': {'name': 'b', 'attributes': []},
                    'service_name': 'service-b',
                    'total_time_ms': 100.0,
                    'self_time_ms': 100.0,
                    'start_time_ns': base + 98_000_000,       # 98-198ms (2ms overlap)
                    'end_time_ns': base + 198_000_000,
                    'children': []
                }
            ]
        }
        
        result = normalizer.normalize_and_aggregate_hierarchy(root_node)
        
        # Factor ~1.01, below threshold
        # Should NOT mark as sibling parallelism
        assert result.get('sibling_parallelism') is not True
