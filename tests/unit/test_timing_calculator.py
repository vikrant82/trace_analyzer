"""
Unit tests for trace_analyzer.processors.timing_calculator module.
"""
import pytest
from trace_analyzer.processors.timing_calculator import TimingCalculator


class TestMergeTimeIntervals:
    """Tests for the merge_time_intervals static method."""
    
    def test_non_overlapping_intervals(self):
        """Test that non-overlapping intervals are preserved."""
        intervals = [
            (100, 200),  # 100ms
            (300, 400),  # 100ms
            (500, 600),  # 100ms
        ]
        merged = TimingCalculator.merge_time_intervals(intervals)
        assert merged == [(100, 200), (300, 400), (500, 600)]
    
    def test_fully_overlapping_intervals(self):
        """Test that fully overlapping intervals are merged."""
        intervals = [
            (100, 500),  # Parent interval
            (150, 300),  # Fully inside
            (200, 400),  # Fully inside
        ]
        merged = TimingCalculator.merge_time_intervals(intervals)
        assert merged == [(100, 500)]
    
    def test_partially_overlapping_intervals(self):
        """Test that partially overlapping intervals are merged."""
        intervals = [
            (100, 300),
            (200, 400),
            (350, 500),
        ]
        merged = TimingCalculator.merge_time_intervals(intervals)
        # Should merge into single interval from 100 to 500
        assert merged == [(100, 500)]
    
    def test_adjacent_intervals(self):
        """Test that adjacent intervals remain separate."""
        intervals = [
            (100, 200),
            (200, 300),  # Starts exactly where previous ends
        ]
        merged = TimingCalculator.merge_time_intervals(intervals)
        # Adjacent but not overlapping, should merge
        assert merged == [(100, 300)]
    
    def test_empty_intervals(self):
        """Test handling of empty interval list."""
        merged = TimingCalculator.merge_time_intervals([])
        assert merged == []
    
    def test_single_interval(self):
        """Test handling of single interval."""
        intervals = [(100, 500)]
        merged = TimingCalculator.merge_time_intervals(intervals)
        assert merged == [(100, 500)]
    
    def test_unsorted_intervals(self):
        """Test that unsorted intervals are handled correctly."""
        intervals = [
            (500, 600),
            (100, 200),
            (300, 400),
        ]
        merged = TimingCalculator.merge_time_intervals(intervals)
        assert merged == [(100, 200), (300, 400), (500, 600)]
    
    def test_complex_parallel_scenario(self):
        """Test realistic parallel call scenario with overlapping spans."""
        # 5 parallel calls that mostly overlap
        intervals = [
            (1000, 1100),  # Call 1: 100ns
            (1010, 1095),  # Call 2: 85ns, overlaps with 1
            (1020, 1110),  # Call 3: 90ns, overlaps with 1,2
            (1030, 1105),  # Call 4: 75ns, overlaps with 1,2,3
            (1040, 1115),  # Call 5: 75ns, overlaps with 3,4
        ]
        merged = TimingCalculator.merge_time_intervals(intervals)
        # Should merge into single interval from 1000 to 1115
        assert len(merged) == 1
        assert merged[0] == (1000, 1115)


class TestCalculateWallClockMs:
    """Tests for the calculate_wall_clock_ms static method."""
    
    def test_sequential_intervals(self):
        """Test wall clock time for sequential (non-overlapping) intervals."""
        intervals = [
            (1_000_000_000, 1_100_000_000),  # 100ms
            (1_200_000_000, 1_300_000_000),  # 100ms
            (1_400_000_000, 1_500_000_000),  # 100ms
        ]
        wall_clock = TimingCalculator.calculate_wall_clock_ms(intervals)
        # Sequential calls: wall clock = sum of durations = 300ms
        assert wall_clock == pytest.approx(300.0, rel=0.01)
    
    def test_parallel_intervals(self):
        """Test wall clock time for parallel (overlapping) intervals."""
        # 5 parallel calls starting at slightly different times
        # Each call takes ~100ms, but they overlap significantly
        base = 1_609_459_500_000_000_000  # Base timestamp
        intervals = [
            (base + 10_000_000, base + 110_000_000),   # 10ms to 110ms = 100ms
            (base + 15_000_000, base + 105_000_000),   # 15ms to 105ms = 90ms
            (base + 20_000_000, base + 120_000_000),   # 20ms to 120ms = 100ms
            (base + 25_000_000, base + 115_000_000),   # 25ms to 115ms = 90ms
            (base + 30_000_000, base + 125_000_000),   # 30ms to 125ms = 95ms
        ]
        wall_clock = TimingCalculator.calculate_wall_clock_ms(intervals)
        # Wall clock should be from earliest start (10ms) to latest end (125ms) = 115ms
        # Not the sum of individual durations (475ms)
        assert wall_clock == pytest.approx(115.0, rel=0.01)
    
    def test_empty_intervals(self):
        """Test wall clock time for empty interval list."""
        wall_clock = TimingCalculator.calculate_wall_clock_ms([])
        assert wall_clock == 0.0
    
    def test_single_interval(self):
        """Test wall clock time for single interval."""
        intervals = [(1_000_000_000, 1_100_000_000)]  # 100ms
        wall_clock = TimingCalculator.calculate_wall_clock_ms(intervals)
        assert wall_clock == pytest.approx(100.0, rel=0.01)


class TestParallelismFactor:
    """Integration tests for parallelism factor calculation."""
    
    def test_sequential_calls_no_parallelism(self):
        """Test that sequential calls show parallelism factor ~1."""
        # Sequential calls: cumulative = wall clock, factor = 1
        intervals = [
            (1_000_000_000, 1_100_000_000),  # 100ms
            (1_200_000_000, 1_300_000_000),  # 100ms
            (1_400_000_000, 1_500_000_000),  # 100ms
        ]
        wall_clock = TimingCalculator.calculate_wall_clock_ms(intervals)
        cumulative = 300.0  # Sum of individual durations
        
        # Sequential: wall clock ≈ cumulative
        assert wall_clock == pytest.approx(300.0, rel=0.01)
        parallelism = cumulative / wall_clock
        assert parallelism == pytest.approx(1.0, rel=0.05)
    
    def test_parallel_calls_high_parallelism(self):
        """Test that highly parallel calls show high parallelism factor."""
        # 5 calls each taking ~90ms, all overlapping in ~100ms window
        base = 1_609_459_500_000_000_000
        intervals = [
            (base + 10_000_000, base + 100_000_000),   # 90ms
            (base + 15_000_000, base + 105_000_000),   # 90ms
            (base + 20_000_000, base + 110_000_000),   # 90ms
            (base + 25_000_000, base + 115_000_000),   # 90ms
            (base + 30_000_000, base + 120_000_000),   # 90ms
        ]
        wall_clock = TimingCalculator.calculate_wall_clock_ms(intervals)
        cumulative = 450.0  # 5 * 90ms
        
        # Wall clock should be ~110ms (from 10ms to 120ms)
        assert wall_clock == pytest.approx(110.0, rel=0.05)
        
        # Parallelism factor should be ~4 (450/110)
        parallelism = cumulative / wall_clock
        assert parallelism >= 3.5
        assert parallelism <= 5.0


class TestSelfTimeWithParallelism:
    """Tests for self-time calculation with parallel child execution."""
    
    def test_self_time_with_parallel_children(self):
        """Test that self-time correctly handles parallel child execution.
        
        Scenario:
          Parent: 0-150ms (150ms total)
          Child 1: 10-110ms (100ms)
          Child 2: 30-110ms (80ms) - overlaps with child 1
          Child 3: 50-110ms (60ms) - overlaps with both
        
        Expected:
          Cumulative child time: 100 + 80 + 60 = 240ms
          Effective child time: 100ms (merged interval 10-110ms)
          Self-time: 150 - 100 = 50ms (NOT 150 - 240 = 0ms!)
        """
        from trace_analyzer.processors.aggregator import NodeAggregator
        from trace_analyzer.extractors.http_extractor import HttpExtractor
        from trace_analyzer.extractors.path_normalizer import PathNormalizer
        
        # Create aggregator with required dependencies
        http_extractor = HttpExtractor()
        path_normalizer = PathNormalizer()
        aggregator = NodeAggregator(http_extractor, path_normalizer)
        calculator = TimingCalculator(aggregator)
        
        base = 1_000_000_000  # 1 second in nanoseconds as base
        
        node = {
            'span': {'name': 'test-parent'},
            'service_name': 'test-service',
            'total_time_ms': 150.0,
            'start_time_ns': base,
            'end_time_ns': base + 150_000_000,
            'children': [
                {
                    'span': {'name': 'child-1'},
                    'service_name': 'test-service',
                    'total_time_ms': 100.0,
                    'self_time_ms': 100.0,  # Leaf nodes: self = total
                    'start_time_ns': base + 10_000_000,  # 10ms
                    'end_time_ns': base + 110_000_000,   # 110ms
                    'children': []
                },
                {
                    'span': {'name': 'child-2'},
                    'service_name': 'test-service',
                    'total_time_ms': 80.0,
                    'self_time_ms': 80.0,  # Leaf nodes: self = total
                    'start_time_ns': base + 30_000_000,  # 30ms (overlap!)
                    'end_time_ns': base + 110_000_000,   # 110ms
                    'children': []
                },
                {
                    'span': {'name': 'child-3'},
                    'service_name': 'test-service',
                    'total_time_ms': 60.0,
                    'self_time_ms': 60.0,  # Leaf nodes: self = total
                    'start_time_ns': base + 50_000_000,  # 50ms (overlap!)
                    'end_time_ns': base + 110_000_000,   # 110ms
                    'children': []
                }
            ]
        }
        
        # Process the node
        calculator.calculate_hierarchy_timings(node)
        
        # Self-time should be 50ms, NOT 0ms
        assert node['self_time_ms'] == pytest.approx(50.0, abs=0.1)
        
        # Should have detected parallelism
        assert 'children_wall_clock_ms' in node
        assert node['children_wall_clock_ms'] == pytest.approx(100.0, abs=0.1)
        assert node['children_cumulative_ms'] == pytest.approx(240.0, abs=0.1)
        
        # Parallelism factor should be ~2.4
        assert 'parallelism_factor' in node
        assert node['parallelism_factor'] == pytest.approx(2.4, abs=0.1)
    
    def test_self_time_without_parallel_execution(self):
        """Test that self-time calculation works correctly for sequential children."""
        from trace_analyzer.processors.aggregator import NodeAggregator
        from trace_analyzer.extractors.http_extractor import HttpExtractor
        from trace_analyzer.extractors.path_normalizer import PathNormalizer
        
        # Create aggregator with required dependencies
        http_extractor = HttpExtractor()
        path_normalizer = PathNormalizer()
        aggregator = NodeAggregator(http_extractor, path_normalizer)
        calculator = TimingCalculator(aggregator)
        
        base = 1_000_000_000
        
        node = {
            'span': {'name': 'sequential-parent'},
            'service_name': 'test-service',
            'total_time_ms': 200.0,
            'start_time_ns': base,
            'end_time_ns': base + 200_000_000,
            'children': [
                {
                    'span': {'name': 'seq-child-1'},
                    'service_name': 'test-service',
                    'total_time_ms': 50.0,
                    'self_time_ms': 50.0,  # Leaf nodes: self = total
                    'start_time_ns': base + 10_000_000,   # 10-60ms
                    'end_time_ns': base + 60_000_000,
                    'children': []
                },
                {
                    'span': {'name': 'seq-child-2'},
                    'service_name': 'test-service',
                    'total_time_ms': 70.0,
                    'self_time_ms': 70.0,  # Leaf nodes: self = total
                    'start_time_ns': base + 70_000_000,   # 70-140ms (no overlap)
                    'end_time_ns': base + 140_000_000,
                    'children': []
                }
            ]
        }
        
        calculator.calculate_hierarchy_timings(node)
        
        # Self-time: 200 - (50 + 70) = 80ms
        assert node['self_time_ms'] == pytest.approx(80.0, abs=0.1)
        
        # Wall clock should equal cumulative (no parallelism)
        assert node['children_wall_clock_ms'] == pytest.approx(120.0, abs=0.1)
        assert node['parallelism_factor'] == 1.0  # No significant parallelism
