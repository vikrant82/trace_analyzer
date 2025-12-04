import pytest
from unittest.mock import Mock
from trace_analyzer.processors.aggregator import NodeAggregator

class TestParallelism:
    def test_calculate_effective_time_no_overlap(self):
        aggregator = NodeAggregator(Mock(), Mock())
        nodes = [
            {'start_time_ns': 0, 'end_time_ns': 10_000_000}, # 10ms
            {'start_time_ns': 20_000_000, 'end_time_ns': 30_000_000} # 10ms
        ]
        # Total duration: 20ms. Effective: 20ms.
        effective_ms = aggregator._calculate_effective_time(nodes)
        assert effective_ms == 20.0

    def test_calculate_effective_time_overlap(self):
        aggregator = NodeAggregator(Mock(), Mock())
        nodes = [
            {'start_time_ns': 0, 'end_time_ns': 20_000_000}, # 20ms
            {'start_time_ns': 10_000_000, 'end_time_ns': 30_000_000} # 20ms
        ]
        # Overlap: 0-30ms. Effective: 30ms.
        effective_ms = aggregator._calculate_effective_time(nodes)
        assert effective_ms == 30.0

    def test_calculate_effective_time_nested(self):
        aggregator = NodeAggregator(Mock(), Mock())
        nodes = [
            {'start_time_ns': 0, 'end_time_ns': 50_000_000}, # 50ms
            {'start_time_ns': 10_000_000, 'end_time_ns': 40_000_000} # 30ms
        ]
        # Nested: 0-50ms. Effective: 50ms.
        effective_ms = aggregator._calculate_effective_time(nodes)
        assert effective_ms == 50.0

    def test_calculate_effective_time_complex(self):
        aggregator = NodeAggregator(Mock(), Mock())
        nodes = [
            {'start_time_ns': 0, 'end_time_ns': 10_000_000},
            {'start_time_ns': 5_000_000, 'end_time_ns': 15_000_000},
            {'start_time_ns': 20_000_000, 'end_time_ns': 30_000_000}
        ]
        # 0-15ms (15ms) + 20-30ms (10ms) = 25ms
        effective_ms = aggregator._calculate_effective_time(nodes)
        assert effective_ms == 25.0
