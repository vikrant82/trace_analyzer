#!/usr/bin/env python3
"""
Trace Endpoint Analyzer
Parses OpenTelemetry trace JSON files and analyzes HTTP endpoints and Kafka/messaging operations.
"""

import ijson
import re
from collections import defaultdict
from typing import Dict, Tuple, List
import sys
from urllib.parse import urlparse


class TraceAnalyzer:
    def __init__(self, strip_query_params=True):
        """
        Initialize the TraceAnalyzer.
        
        Args:
            strip_query_params (bool): If True, removes query parameters from URLs before analysis.
                                      Default: True (recommended for cleaner grouping)
        """
        self.strip_query_params = strip_query_params
        
        # Data structures for flat analysis
        self.endpoint_params = defaultdict(lambda: {'count': 0, 'total_time_ms': 0.0, 'total_self_time_ms': 0.0})
        self.service_calls = defaultdict(lambda: {'count': 0, 'total_time_ms': 0.0, 'total_self_time_ms': 0.0})
        self.kafka_messages = defaultdict(lambda: {'count': 0, 'total_time_ms': 0.0})
        
        # Data structures for hierarchical analysis
        self.traces = defaultdict(list)
        self.trace_hierarchies = {}
        self.trace_summary = {}
        
        self.uuid_pattern = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)
        self.numeric_id_pattern = re.compile(r'/\d+(?=/|\?|$)')
        self.rule_identifier_pattern = re.compile(r'/[A-Z][A-Za-z0-9-]*__[A-Za-z0-9_]+(?=/|\?|$)')
        self.long_encoded_pattern = re.compile(r'/[A-Za-z0-9_-]{30,}(?=/|\?|$)')
        
    def normalize_path(self, path: str) -> Tuple[str, List[str]]:
        """
        Normalize a path by replacing parameter values with placeholders.
        Handles both full URLs and relative paths, extracting only the path component.
        """
        if not path:
            return path, []

        # If it's a full URL, parse it to get only the path.
        if '://' in path:
            path = urlparse(path).path
        
        if self.strip_query_params and '?' in path:
            path = path.split('?')[0]
        
        non_uuid_params = []
        normalized = path
        
        uuid_matches = list(self.uuid_pattern.finditer(path))
        for match in uuid_matches:
            normalized = normalized.replace(match.group(0), '{uuid}', 1)
        
        rule_matches = list(self.rule_identifier_pattern.finditer(path))
        for match in rule_matches:
            param_value = match.group(0)[1:]
            non_uuid_params.append(param_value)
            normalized = normalized.replace(match.group(0), '/{rule_id}', 1)
        
        long_encoded_matches = list(self.long_encoded_pattern.finditer(path))
        for match in long_encoded_matches:
            param_value = match.group(0)[1:]
            
            is_already_matched = False
            for uuid_match in uuid_matches:
                if match.start() <= uuid_match.start() < match.end() or uuid_match.start() <= match.start() < uuid_match.end():
                    is_already_matched = True
                    break
            
            if not is_already_matched:
                for rule_match in rule_matches:
                    if match.start() <= rule_match.start() < match.end() or rule_match.start() <= match.start() < rule_match.end():
                        is_already_matched = True
                        break
            
            if not is_already_matched:
                non_uuid_params.append(param_value)
                normalized = normalized.replace(match.group(0), '/{encoded_id}', 1)
        
        for match in self.numeric_id_pattern.finditer(path):
            param_value = match.group(0)[1:]
            if param_value not in non_uuid_params:
                non_uuid_params.append(param_value)
                normalized = normalized.replace(match.group(0), '/{id}', 1)
        
        return normalized, non_uuid_params
    
    def extract_http_path(self, attributes: List) -> str:
        """
        Extract HTTP path/URL from span attributes.
        Searches for 'http.url', 'http.target', and 'http.path'.
        """
        for attr in attributes:
            if attr.get('key') in ['http.url', 'http.target', 'http.path']:
                value = attr.get('value', {})
                return value.get('stringValue', '')
        return ''
    
    def extract_http_method(self, attributes: List) -> str:
        """Extract HTTP method from span attributes."""
        for attr in attributes:
            if attr.get('key') == 'http.method':
                return attr.get('value', {}).get('stringValue', '')
        return ''

    def extract_service_name(self, resource_attributes: List) -> str:
        """Extract service name from resource attributes."""
        for attr in resource_attributes:
            if attr.get('key') == 'service.name':
                value = attr.get('value', {})
                return value.get('stringValue', 'unknown-service')
        return 'unknown-service'
    
    def extract_target_service_from_url(self, url: str) -> str:
        """Extract target service name from a full URL."""
        if '://' in url:
            host = urlparse(url).hostname
            if host:
                return host.split('.')[0]
        return 'unknown-service'
    
    def extract_kafka_info(self, span: Dict, attributes: List) -> Tuple[str, str, str]:
        """
        Extract Kafka messaging information from span.
        """
        span_kind = span.get('kind', '')
        span_name = span.get('name', '')
        
        operation_type = 'internal'
        if span_kind == 'SPAN_KIND_CONSUMER':
            operation_type = 'consumer'
        elif span_kind == 'SPAN_KIND_PRODUCER':
            operation_type = 'producer'
        
        details_parts = []
        for attr in attributes:
            key = attr.get('key', '')
            value = attr.get('value', {})
            string_value = value.get('stringValue', '')
            
            if key in ['amf-service-id', 'amf-message-id', 'Kafka client', 'Message Uuid']:
                if string_value:
                    details_parts.append(f"{key}={string_value}")
        
        details = ', '.join(details_parts) if details_parts else '[no-details]'
        
        return operation_type, span_name, details
    
    def format_time(self, ms: float) -> str:
        """Format time in milliseconds to a human-readable string."""
        if ms < 1000:
            return f"{ms:.2f} ms"
        elif ms < 60000:
            return f"{ms/1000:.2f} s"
        else:
            minutes = int(ms / 60000)
            seconds = (ms % 60000) / 1000
            return f"{minutes}m {seconds:.2f}s"
    
    def process_trace_file(self, file_path: str):
        """
        Process the trace JSON file by first grouping all spans by traceId,
        then building a hierarchy for each trace.
        """
        print(f"Processing {file_path}...")
        
        with open(file_path, 'rb') as f:
            parser = ijson.items(f, 'batches.item')
            batch_count, span_count = 0, 0
            
            for batch in parser:
                batch_count += 1
                for inst_lib_span in batch.get('instrumentationLibrarySpans', []):
                    for span in inst_lib_span.get('spans', []):
                        span_count += 1
                        trace_id = span.get('traceId')
                        if trace_id:
                            span['resource'] = batch.get('resource', {})
                            self.traces[trace_id].append(span)
                
                if batch_count % 100 == 0:
                    print(f"  Read {batch_count} batches, {span_count} spans...")
        
        print(f"Completed reading file: {batch_count} batches, {span_count} spans found.")
        print(f"Found {len(self.traces)} unique traces.")

        self._process_collected_traces()

        print(f"\nFound {len(self.endpoint_params)} unique incoming request combinations (SERVER spans)")
        print(f"Found {len(self.service_calls)} unique outgoing call combinations (CLIENT spans)")
        print(f"Found {len(self.kafka_messages)} unique Kafka/messaging operations")

    def _process_collected_traces(self):
        """
        Iterate through each collected trace, build its hierarchy, and
        calculate all timing metrics.
        """
        for trace_id, spans in self.traces.items():
            hierarchy = self._build_and_process_hierarchy(spans)
            self.trace_hierarchies[trace_id] = hierarchy
            
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
                    'wall_clock_duration_formatted': self.format_time(wall_clock_duration),
                    'span_count': len(spans)
                }

            if hierarchy:
                self._calculate_hierarchy_timings(hierarchy)

    def _build_and_process_hierarchy(self, spans: List[Dict]) -> Dict:
        """
        Build a tree structure from a flat list of spans for a single trace.
        This version correctly populates the flat metrics to avoid double-counting.
        """
        span_nodes = {}
        root_spans = []

        # First pass: create a node for each span
        for span in spans:
            span_id = span.get('spanId')
            if not span_id: continue
            duration_ms = (span.get('endTimeUnixNano', 0) - span.get('startTimeUnixNano', 0)) / 1_000_000.0
            service_name = self.extract_service_name(span.get('resource', {}).get('attributes', []))
            span_nodes[span_id] = {
                'span': span, 'service_name': service_name, 'children': [],
                'total_time_ms': duration_ms, 'self_time_ms': duration_ms,
            }

        # Second pass: link children to their parents
        for span_id, node in span_nodes.items():
            parent_span_id = node['span'].get('parentSpanId')
            if parent_span_id and parent_span_id in span_nodes:
                span_nodes[parent_span_id]['children'].append(node)
            else:
                root_spans.append(node)

        # Third pass: populate flat metrics now that the hierarchy is fully built
        for span_id, node in span_nodes.items():
            span = node['span']
            attributes = span.get('attributes', [])
            span_kind = span.get('kind', '')
            duration_ms = node['total_time_ms']
            service_name = node['service_name']
            
            parent_span_id = span.get('parentSpanId')
            parent_node = span_nodes.get(parent_span_id)
            parent_kind = parent_node['span'].get('kind') if parent_node else None

            http_path = self.extract_http_path(attributes)
            if http_path:
                http_method = self.extract_http_method(attributes)
                normalized_path, params = self.normalize_path(http_path)
                param_str = params[0] if params else '[no-params]'
                
                # A SERVER span is only a "true" incoming request if its parent is a CLIENT or does not exist.
                if span_kind == 'SPAN_KIND_SERVER' and (parent_kind == 'SPAN_KIND_CLIENT' or parent_kind is None):
                    child_total_time = sum(child['total_time_ms'] for child in node['children'])
                    self_time_ms = max(0, duration_ms - child_total_time)
                    
                    key = (service_name, http_method, normalized_path, param_str)
                    self.endpoint_params[key]['count'] += 1
                    self.endpoint_params[key]['total_time_ms'] += duration_ms
                    self.endpoint_params[key]['total_self_time_ms'] += self_time_ms
                
                # A CLIENT span is only a "true" service-to-service call if its parent is not also a CLIENT span.
                elif span_kind == 'SPAN_KIND_CLIENT' and parent_kind != 'SPAN_KIND_CLIENT':
                    child_total_time = sum(child['total_time_ms'] for child in node['children'])
                    self_time_ms = max(0, duration_ms - child_total_time)

                    target_service = self.extract_target_service_from_url(http_path)
                    key = (service_name, target_service, http_method, normalized_path, param_str)
                    self.service_calls[key]['count'] += 1
                    self.service_calls[key]['total_time_ms'] += duration_ms
                    self.service_calls[key]['total_self_time_ms'] += self_time_ms
            else:
                op_type, msg_type, details = self.extract_kafka_info(span, attributes)
                if op_type in ['consumer', 'producer']:
                    key = (service_name, op_type, msg_type, details)
                    self.kafka_messages[key]['count'] += 1
                    self.kafka_messages[key]['total_time_ms'] += duration_ms
        
        return {
            'span': {'name': 'Trace Root'}, 'service_name': 'Trace', 'children': root_spans,
            'total_time_ms': sum(s['total_time_ms'] for s in root_spans), 'self_time_ms': 0
        }

    def _calculate_hierarchy_timings(self, node: Dict):
        """
        Recursively traverse the hierarchy to aggregate children and calculate self-time.
        """
        if not node or not node.get('children'):
            return

        for child in node['children']:
            self._calculate_hierarchy_timings(child)

        # Aggregate the children of the current node
        node['children'] = self._aggregate_list_of_nodes(node['children'])
        
        # After aggregation, calculate the parent's self-time
        child_total_time = sum(child['total_time_ms'] for child in node['children'])
        node['self_time_ms'] = max(0, node['total_time_ms'] - child_total_time)

    def _aggregate_list_of_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """
        A dedicated helper to recursively aggregate a list of nodes.
        """
        aggregated_nodes = defaultdict(list)
        for node in nodes:
            span = node.get('span', {})
            service = node.get('service_name', 'Unknown')
            http_path = self.extract_http_path(span.get('attributes', []))
            
            if http_path:
                http_method = self.extract_http_method(span.get('attributes', []))
                normalized_path, _ = self.normalize_path(http_path)
                aggregation_key = f"{service}:{http_method}:{normalized_path}"
            else:
                aggregation_key = f"{service}:{span.get('name', 'Unknown Span')}"
            
            aggregated_nodes[aggregation_key].append(node)

        final_children = []
        for key, group in aggregated_nodes.items():
            if len(group) == 1:
                final_children.append(group[0])
            else:
                first_child = group[0]
                total_time = sum(c['total_time_ms'] for c in group)
                self_time = sum(c['self_time_ms'] for c in group)
                
                # Recursively aggregate the children of the group
                all_grandchildren = [grandchild for child in group for grandchild in child.get('children', [])]
                aggregated_grandchildren = self._aggregate_list_of_nodes(all_grandchildren)
                
                agg_node = {
                    'span': {'name': key},
                    'service_name': first_child['service_name'],
                    'children': aggregated_grandchildren,
                    'total_time_ms': total_time,
                    'self_time_ms': self_time,
                    'aggregated': True,
                    'count': sum(c.get('count', 1) for c in group),
                    'avg_time_ms': total_time / sum(c.get('count', 1) for c in group)
                }
                final_children.append(agg_node)
        
        return final_children

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Analyze Grafana trace JSON files and extract HTTP endpoint statistics.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_trace.py trace.json
  python analyze_trace.py trace.json -o custom_report.md
  python analyze_trace.py trace.json --keep-query-params
        """
    )
    parser.add_argument('input_file', help='Path to the trace JSON file')
    parser.add_argument('-o', '--output', dest='output_file', default='trace_analysis.md', help='Output markdown file')
    parser.add_argument('--keep-query-params', action='store_true', help='Keep query parameters in URLs')
    args = parser.parse_args()
    
    analyzer = TraceAnalyzer(strip_query_params=not args.keep_query_params)
    
    try:
        print(f"\nConfiguration:\n  Input file: {args.input_file}\n  Output file: {args.output_file}\n  Strip query params: {not args.keep_query_params}\n")
        analyzer.process_trace_file(args.input_file)
        # The markdown report is not part of the web app, but we keep it for CLI use.
        # analyzer.generate_markdown_report(args.output_file)
        print(f"\n✓ Analysis complete!")
    except FileNotFoundError:
        print(f"Error: File '{args.input_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
