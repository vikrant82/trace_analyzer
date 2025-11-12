"""
Main trace analyzer orchestrator.
"""

from collections import defaultdict
from typing import DefaultDict, Tuple

from ..core.types import TraceConfig, EndpointStats, KafkaStats
from ..extractors import HttpExtractor, KafkaExtractor, PathNormalizer
from ..processors import (
    TraceFileProcessor,
    HierarchyBuilder,
    TimingCalculator,
    NodeAggregator,
    MetricsPopulator,
    HierarchyNormalizer
)
from ..formatters import format_time


class TraceAnalyzer:
    """Main orchestrator for trace analysis."""
    
    def __init__(
        self,
        strip_query_params: bool = True,
        include_gateway_services: bool = False,
        include_service_mesh: bool = False
    ):
        """
        Initialize the TraceAnalyzer.
        
        Args:
            strip_query_params: If True, removes query parameters from URLs before analysis
            include_gateway_services: If True, includes services that only have CLIENT spans
            include_service_mesh: If True, includes service mesh sidecar spans
        """
        # Configuration
        self.config = TraceConfig(
            strip_query_params=strip_query_params,
            include_gateway_services=include_gateway_services,
            include_service_mesh=include_service_mesh
        )
        
        # Data structures for flat analysis
        self.endpoint_params: DefaultDict[Tuple, EndpointStats] = defaultdict(
            lambda: {
                'count': 0,
                'total_time_ms': 0.0,
                'total_self_time_ms': 0.0,
                'error_count': 0,
                'error_messages': defaultdict(int)
            }
        )
        self.service_calls: DefaultDict[Tuple, EndpointStats] = defaultdict(
            lambda: {
                'count': 0,
                'total_time_ms': 0.0,
                'total_self_time_ms': 0.0,
                'error_count': 0,
                'error_messages': defaultdict(int)
            }
        )
        self.kafka_messages: DefaultDict[Tuple, KafkaStats] = defaultdict(
            lambda: {
                'count': 0,
                'total_time_ms': 0.0,
                'error_count': 0,
                'error_messages': defaultdict(int)
            }
        )
        
        # Data structures for hierarchical analysis
        self.traces = {}
        self.trace_hierarchies = {}
        self.trace_summary = {}
        
        # Initialize components
        self.http_extractor = HttpExtractor()
        self.kafka_extractor = KafkaExtractor()
        self.path_normalizer = PathNormalizer()
        
        self.file_processor = TraceFileProcessor()
        self.hierarchy_builder = HierarchyBuilder(self.http_extractor)
        
        self.aggregator = NodeAggregator(self.http_extractor, self.path_normalizer)
        self.timing_calculator = TimingCalculator(self.aggregator)
        
        self.metrics_populator = MetricsPopulator(
            self.config,
            self.http_extractor,
            self.kafka_extractor,
            self.path_normalizer
        )
        
        self.hierarchy_normalizer = HierarchyNormalizer(
            self.config,
            self.http_extractor,
            self.path_normalizer,
            self.timing_calculator
        )
    
    def process_trace_file(self, file_path: str):
        """
        Process the trace JSON file by first grouping all spans by traceId,
        then building a hierarchy for each trace.
        
        Args:
            file_path: Path to the trace JSON file
        """
        # Step 1: Read and group spans by trace ID
        self.traces = self.file_processor.process_file(file_path)
        
        # Step 2: Process each trace
        self._process_collected_traces()
        
        # Step 3: Report summary
        print(f"\nFound {len(self.endpoint_params)} unique incoming request combinations (SERVER spans)")
        print(f"Found {len(self.service_calls)} unique outgoing call combinations (CLIENT spans)")
        print(f"Found {len(self.kafka_messages)} unique Kafka/messaging operations")
        
        total_errors = (sum(e['error_count'] for e in self.endpoint_params.values()) +
                       sum(e['error_count'] for e in self.service_calls.values()) +
                       sum(e['error_count'] for e in self.kafka_messages.values()))
        total_error_endpoints = (len([k for k, v in self.endpoint_params.items() if v['error_count'] > 0]) +
                                len([k for k, v in self.service_calls.items() if v['error_count'] > 0]) +
                                len([k for k, v in self.kafka_messages.items() if v['error_count'] > 0]))
        print(f"Found {total_errors} total errors across {total_error_endpoints} unique endpoints/operations")
    
    def _process_collected_traces(self):
        """
        Iterate through each collected trace, build its hierarchy, calculate
        timings, and then populate the flat metrics for the summary tables.
        """
        for trace_id, spans in self.traces.items():
            # Pass 1 & 2: Build the raw hierarchy and a flat map of all nodes
            raw_hierarchy, span_nodes = self.hierarchy_builder.build_raw_hierarchy(spans)
            
            # Pass 3: Recursively calculate timings for the entire hierarchy
            if raw_hierarchy:
                self.timing_calculator.calculate_hierarchy_timings(raw_hierarchy)
            
            # Pass 4: Populate the flat summary tables
            ep, sc, km = self.metrics_populator.populate_flat_metrics(span_nodes)
            
            # Merge results into analyzer's collections
            for key, stats in ep.items():
                self.endpoint_params[key]['count'] += stats['count']
                self.endpoint_params[key]['total_time_ms'] += stats['total_time_ms']
                self.endpoint_params[key]['total_self_time_ms'] += stats['total_self_time_ms']
                self.endpoint_params[key]['error_count'] += stats['error_count']
                for msg, count in stats['error_messages'].items():
                    self.endpoint_params[key]['error_messages'][msg] += count
            
            for key, stats in sc.items():
                self.service_calls[key]['count'] += stats['count']
                self.service_calls[key]['total_time_ms'] += stats['total_time_ms']
                self.service_calls[key]['total_self_time_ms'] += stats['total_self_time_ms']
                self.service_calls[key]['error_count'] += stats['error_count']
                for msg, count in stats['error_messages'].items():
                    self.service_calls[key]['error_messages'][msg] += count
            
            for key, stats in km.items():
                self.kafka_messages[key]['count'] += stats['count']
                self.kafka_messages[key]['total_time_ms'] += stats['total_time_ms']
                self.kafka_messages[key]['error_count'] += stats['error_count']
                for msg, count in stats['error_messages'].items():
                    self.kafka_messages[key]['error_messages'][msg] += count
            
            # Pass 5: Normalize and aggregate the raw hierarchy
            normalized_hierarchy = self.hierarchy_normalizer.normalize_and_aggregate_hierarchy(raw_hierarchy)
            
            # Store the normalized hierarchy for the UI
            self.trace_hierarchies[trace_id] = normalized_hierarchy
            
            # Store trace summary
            if spans:
                start_times = [s.get('startTimeUnixNano', 0) for s in spans]
                end_times = [s.get('endTimeUnixNano', 0) for s in spans]
                min_start_time = min(start_times) if start_times else 0
                max_end_time = max(end_times) if end_times else 0
                wall_clock_duration = (max_end_time - min_start_time) / 1_000_000.0
                
                self.trace_summary[trace_id] = {
                    'start_time_unix_nano': min_start_time,
                    'end_time_unix_nano': max_end_time,
                    'wall_clock_duration_ms': wall_clock_duration,
                    'wall_clock_duration_formatted': format_time(wall_clock_duration),
                    'span_count': len(spans)
                }
    
    def format_time(self, ms: float) -> str:
        """
        Format time in milliseconds to a human-readable string.
        
        Args:
            ms: Time in milliseconds
            
        Returns:
            Formatted time string
        """
        return format_time(ms)
