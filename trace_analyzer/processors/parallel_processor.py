"""
Parallel trace processor for improved performance on multi-trace files.
"""

import multiprocessing as mp
from multiprocessing import Pool
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional, Callable
import os

from ..core.types import TraceConfig
from ..extractors import HttpExtractor, KafkaExtractor, PathNormalizer
from ..formatters import format_time
from .hierarchy_builder import HierarchyBuilder
from .timing_calculator import TimingCalculator
from .aggregator import NodeAggregator
from .metrics_populator import MetricsPopulator
from .normalizer import HierarchyNormalizer


def _process_single_trace(args: Tuple[str, List[Dict], dict]) -> Tuple[str, Dict, Dict, Dict, Dict, Dict]:
    """
    Process a single trace independently. Designed to run in a worker process.
    
    Args:
        args: Tuple of (trace_id, spans, config_dict)
        
    Returns:
        Tuple of (trace_id, hierarchy, summary, endpoint_params, service_calls, kafka_messages, effective_times)
    """
    trace_id, spans, config_dict = args
    
    config = TraceConfig(
        strip_query_params=config_dict['strip_query_params'],
        include_gateway_services=config_dict['include_gateway_services'],
        include_service_mesh=config_dict['include_service_mesh']
    )
    
    http_extractor = HttpExtractor()
    kafka_extractor = KafkaExtractor()
    path_normalizer = PathNormalizer()
    
    hierarchy_builder = HierarchyBuilder(http_extractor)
    aggregator = NodeAggregator(http_extractor, path_normalizer)
    timing_calculator = TimingCalculator(aggregator)
    metrics_populator = MetricsPopulator(config, http_extractor, kafka_extractor, path_normalizer)
    hierarchy_normalizer = HierarchyNormalizer(config, http_extractor, path_normalizer, timing_calculator)
    
    raw_hierarchy, span_nodes = hierarchy_builder.build_raw_hierarchy(spans)
    
    if raw_hierarchy:
        timing_calculator.calculate_hierarchy_timings(raw_hierarchy)
    
    ep, sc, km, eff = metrics_populator.populate_flat_metrics(span_nodes)
    
    normalized_hierarchy = hierarchy_normalizer.normalize_and_aggregate_hierarchy(raw_hierarchy)
    
    trace_summary = {}
    if spans:
        start_times = [s.get('startTimeUnixNano', 0) for s in spans]
        end_times = [s.get('endTimeUnixNano', 0) for s in spans]
        min_start_time = min(start_times) if start_times else 0
        max_end_time = max(end_times) if end_times else 0
        wall_clock_duration = (max_end_time - min_start_time) / 1_000_000.0
        
        trace_summary = {
            'start_time_unix_nano': min_start_time,
            'end_time_unix_nano': max_end_time,
            'wall_clock_duration_ms': wall_clock_duration,
            'wall_clock_duration_formatted': format_time(wall_clock_duration),
            'span_count': len(spans)
        }
    
    def convert_defaultdicts(d):
        if isinstance(d, defaultdict):
            d = dict(d)
        if isinstance(d, dict):
            return {k: convert_defaultdicts(v) for k, v in d.items()}
        return d
    
    ep = convert_defaultdicts(ep)
    sc = convert_defaultdicts(sc)
    km = convert_defaultdicts(km)
    eff = convert_defaultdicts(eff)
    
    return (trace_id, normalized_hierarchy, trace_summary, ep, sc, km, eff)


class ParallelTraceProcessor:
    """Process traces in parallel using multiprocessing."""
    
    def __init__(self, config: TraceConfig, num_workers: Optional[int] = None):
        """
        Initialize parallel processor.
        
        Args:
            config: TraceConfig instance
            num_workers: Number of worker processes (default: CPU count)
        """
        self.config = config
        self.num_workers = num_workers or os.cpu_count() or 4
        
        self.config_dict = {
            'strip_query_params': config.strip_query_params,
            'include_gateway_services': config.include_gateway_services,
            'include_service_mesh': config.include_service_mesh
        }
    
    def process_traces(self, traces: Dict[str, List[Dict]], progress_callback=None) -> Tuple[Dict, Dict, Dict, Dict, Dict, Dict]:
        """
        Process multiple traces in parallel.
        
        Args:
            traces: Dictionary mapping trace_id -> list of spans
            progress_callback: Optional callback(completed, total) for progress updates
            
        Returns:
            Tuple of (trace_hierarchies, trace_summaries, endpoint_params, service_calls, kafka_messages, effective_times)
        """
        trace_count = len(traces)
        
        if trace_count <= 1 or self.num_workers <= 1:
            return self._process_sequential(traces, progress_callback)
        
        work_items = [
            (trace_id, spans, self.config_dict)
            for trace_id, spans in traces.items()
        ]
        
        trace_hierarchies = {}
        trace_summaries = {}
        endpoint_params = defaultdict(lambda: {
            'count': 0, 'total_time_ms': 0.0, 'total_self_time_ms': 0.0,
            'error_count': 0, 'error_messages': defaultdict(int)
        })
        service_calls = defaultdict(lambda: {
            'count': 0, 'total_time_ms': 0.0, 'total_self_time_ms': 0.0,
            'error_count': 0, 'error_messages': defaultdict(int)
        })
        kafka_messages = defaultdict(lambda: {
            'count': 0, 'total_time_ms': 0.0,
            'error_count': 0, 'error_messages': defaultdict(int)
        })
        effective_times = {
            'endpoints': {},
            'service_calls': {},
            'kafka': {},
            'services': {}
        }
        
        completed = 0
        
        effective_workers = min(self.num_workers, trace_count)
        
        with Pool(processes=effective_workers) as pool:
            for result in pool.imap_unordered(_process_single_trace, work_items, chunksize=1):
                trace_id, hierarchy, summary, ep, sc, km, eff = result
                
                trace_hierarchies[trace_id] = hierarchy
                trace_summaries[trace_id] = summary
                
                for key, stats in ep.items():
                    endpoint_params[key]['count'] += stats['count']
                    endpoint_params[key]['total_time_ms'] += stats['total_time_ms']
                    endpoint_params[key]['total_self_time_ms'] += stats.get('total_self_time_ms', 0.0)
                    endpoint_params[key]['error_count'] += stats.get('error_count', 0)
                    for msg, count in stats.get('error_messages', {}).items():
                        endpoint_params[key]['error_messages'][msg] += count
                
                for key, stats in sc.items():
                    service_calls[key]['count'] += stats['count']
                    service_calls[key]['total_time_ms'] += stats['total_time_ms']
                    service_calls[key]['total_self_time_ms'] += stats.get('total_self_time_ms', 0.0)
                    service_calls[key]['error_count'] += stats.get('error_count', 0)
                    for msg, count in stats.get('error_messages', {}).items():
                        service_calls[key]['error_messages'][msg] += count
                
                for key, stats in km.items():
                    kafka_messages[key]['count'] += stats['count']
                    kafka_messages[key]['total_time_ms'] += stats['total_time_ms']
                    kafka_messages[key]['error_count'] += stats.get('error_count', 0)
                    for msg, count in stats.get('error_messages', {}).items():
                        kafka_messages[key]['error_messages'][msg] += count
                
                for category in ['endpoints', 'service_calls', 'kafka', 'services']:
                    for key, eff_time in eff.get(category, {}).items():
                        if key not in effective_times[category]:
                            effective_times[category][key] = eff_time
                        else:
                            effective_times[category][key] += eff_time
                
                completed += 1
                if progress_callback:
                    progress_callback(completed, trace_count)
        
        return trace_hierarchies, trace_summaries, endpoint_params, service_calls, kafka_messages, effective_times
    
    def _process_sequential(self, traces: Dict[str, List[Dict]], progress_callback=None) -> Tuple[Dict, Dict, Dict, Dict, Dict, Dict]:
        """
        Fallback sequential processing for single trace or single worker.
        """
        from .hierarchy_builder import HierarchyBuilder
        from .timing_calculator import TimingCalculator
        from .aggregator import NodeAggregator
        from .metrics_populator import MetricsPopulator
        from .normalizer import HierarchyNormalizer
        from ..extractors import HttpExtractor, KafkaExtractor, PathNormalizer
        
        http_extractor = HttpExtractor()
        kafka_extractor = KafkaExtractor()
        path_normalizer = PathNormalizer()
        
        hierarchy_builder = HierarchyBuilder(http_extractor)
        aggregator = NodeAggregator(http_extractor, path_normalizer)
        timing_calculator = TimingCalculator(aggregator)
        metrics_populator = MetricsPopulator(self.config, http_extractor, kafka_extractor, path_normalizer)
        hierarchy_normalizer = HierarchyNormalizer(self.config, http_extractor, path_normalizer, timing_calculator)
        
        trace_hierarchies = {}
        trace_summaries = {}
        endpoint_params = defaultdict(lambda: {
            'count': 0, 'total_time_ms': 0.0, 'total_self_time_ms': 0.0,
            'error_count': 0, 'error_messages': defaultdict(int)
        })
        service_calls = defaultdict(lambda: {
            'count': 0, 'total_time_ms': 0.0, 'total_self_time_ms': 0.0,
            'error_count': 0, 'error_messages': defaultdict(int)
        })
        kafka_messages = defaultdict(lambda: {
            'count': 0, 'total_time_ms': 0.0,
            'error_count': 0, 'error_messages': defaultdict(int)
        })
        effective_times = {
            'endpoints': {},
            'service_calls': {},
            'kafka': {},
            'services': {}
        }
        
        total = len(traces)
        completed = 0
        
        for trace_id, spans in traces.items():
            raw_hierarchy, span_nodes = hierarchy_builder.build_raw_hierarchy(spans)
            
            if raw_hierarchy:
                timing_calculator.calculate_hierarchy_timings(raw_hierarchy)
            
            ep, sc, km, eff = metrics_populator.populate_flat_metrics(span_nodes)
            
            for key, stats in ep.items():
                endpoint_params[key]['count'] += stats['count']
                endpoint_params[key]['total_time_ms'] += stats['total_time_ms']
                endpoint_params[key]['total_self_time_ms'] += stats.get('total_self_time_ms', 0.0)
                endpoint_params[key]['error_count'] += stats.get('error_count', 0)
                for msg, count in stats.get('error_messages', {}).items():
                    endpoint_params[key]['error_messages'][msg] += count
            
            for key, stats in sc.items():
                service_calls[key]['count'] += stats['count']
                service_calls[key]['total_time_ms'] += stats['total_time_ms']
                service_calls[key]['total_self_time_ms'] += stats.get('total_self_time_ms', 0.0)
                service_calls[key]['error_count'] += stats.get('error_count', 0)
                for msg, count in stats.get('error_messages', {}).items():
                    service_calls[key]['error_messages'][msg] += count
            
            for key, stats in km.items():
                kafka_messages[key]['count'] += stats['count']
                kafka_messages[key]['total_time_ms'] += stats['total_time_ms']
                kafka_messages[key]['error_count'] += stats.get('error_count', 0)
                for msg, count in stats.get('error_messages', {}).items():
                    kafka_messages[key]['error_messages'][msg] += count
            
            for category in ['endpoints', 'service_calls', 'kafka', 'services']:
                for key, eff_time in eff.get(category, {}).items():
                    if key not in effective_times[category]:
                        effective_times[category][key] = eff_time
                    else:
                        effective_times[category][key] += eff_time
            
            normalized_hierarchy = hierarchy_normalizer.normalize_and_aggregate_hierarchy(raw_hierarchy)
            trace_hierarchies[trace_id] = normalized_hierarchy
            
            if spans:
                start_times = [s.get('startTimeUnixNano', 0) for s in spans]
                end_times = [s.get('endTimeUnixNano', 0) for s in spans]
                min_start_time = min(start_times) if start_times else 0
                max_end_time = max(end_times) if end_times else 0
                wall_clock_duration = (max_end_time - min_start_time) / 1_000_000.0
                
                trace_summaries[trace_id] = {
                    'start_time_unix_nano': min_start_time,
                    'end_time_unix_nano': max_end_time,
                    'wall_clock_duration_ms': wall_clock_duration,
                    'wall_clock_duration_formatted': format_time(wall_clock_duration),
                    'span_count': len(spans)
                }
            
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
        
        return trace_hierarchies, trace_summaries, endpoint_params, service_calls, kafka_messages, effective_times