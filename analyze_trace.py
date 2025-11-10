#!/usr/bin/env python3
"""
Trace Endpoint Analyzer
Parses OpenTelemetry trace JSON files and analyzes HTTP endpoints and Kafka/messaging operations.
"""

import ijson
import re
from collections import defaultdict
from typing import Dict, Tuple, List, TypedDict, DefaultDict
import sys
from urllib.parse import urlparse


class EndpointStats(TypedDict):
    count: int
    total_time_ms: float
    total_self_time_ms: float
    error_count: int
    error_messages: DefaultDict[str, int]

class KafkaStats(TypedDict):
    count: int
    total_time_ms: float
    error_count: int
    error_messages: DefaultDict[str, int]


class TraceAnalyzer:
    def __init__(self, strip_query_params=True, include_gateway_services=False, include_service_mesh=False):
        """
        Initialize the TraceAnalyzer.
        
        Args:
            strip_query_params (bool): If True, removes query parameters from URLs before analysis.
                                      Default: True (recommended for cleaner grouping)
            
            include_gateway_services (bool): If True, includes services that only have CLIENT spans
                                            or act as pure proxies/gateways in service counts.
                                            Default: False (excludes pure gateway/proxy services)
                                            
                                            When False: Counts only services with SERVER spans.
                                            When True: Also counts services with only CLIENT spans
                                            (e.g., load balancers, API gateways that only forward requests).
            
            include_service_mesh (bool): If True, includes service mesh sidecar spans (Istio/Envoy)
                                        in the analysis, showing duplicate entries for each logical
                                        operation (both application and sidecar spans).
                                        Default: False (filters out sidecar duplicates)
                                        
                                        When False: Filters SERVER→SERVER and CLIENT→CLIENT chains
                                        (typical Istio/Envoy sidecar patterns), showing only application spans.
                                        
                                        When True: Includes all spans, showing complete request path
                                        through service mesh infrastructure. Useful for diagnosing
                                        service mesh overhead and configuration issues.
        """
        self.strip_query_params = strip_query_params
        self.include_gateway_services = include_gateway_services
        self.include_service_mesh = include_service_mesh
        
        # Data structures for flat analysis
        self.endpoint_params: DefaultDict[Tuple, EndpointStats] = defaultdict(lambda: {'count': 0, 'total_time_ms': 0.0, 'total_self_time_ms': 0.0, 'error_count': 0, 'error_messages': defaultdict(int)})
        self.service_calls: DefaultDict[Tuple, EndpointStats] = defaultdict(lambda: {'count': 0, 'total_time_ms': 0.0, 'total_self_time_ms': 0.0, 'error_count': 0, 'error_messages': defaultdict(int)})
        self.kafka_messages: DefaultDict[Tuple, KafkaStats] = defaultdict(lambda: {'count': 0, 'total_time_ms': 0.0, 'error_count': 0, 'error_messages': defaultdict(int)})
        
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

        total_errors = sum(e['error_count'] for e in self.endpoint_params.values()) + \
                       sum(e['error_count'] for e in self.service_calls.values()) + \
                       sum(e['error_count'] for e in self.kafka_messages.values())
        total_error_endpoints = len([k for k, v in self.endpoint_params.items() if v['error_count'] > 0]) + \
                                len([k for k, v in self.service_calls.items() if v['error_count'] > 0]) + \
                                len([k for k, v in self.kafka_messages.items() if v['error_count'] > 0])
        print(f"Found {total_errors} total errors across {total_error_endpoints} unique endpoints/operations")

    def _process_collected_traces(self):
        """
        Iterate through each collected trace, build its hierarchy, calculate
        timings, and then populate the flat metrics for the summary tables.
        """
        for trace_id, spans in self.traces.items():
            # Pass 1 & 2: Build the raw hierarchy and a flat map of all nodes.
            raw_hierarchy, span_nodes = self._build_raw_hierarchy(spans)
            
            # Pass 3: Recursively calculate timings for the entire hierarchy.
            # This is the single source of truth for all self-time calculations.
            if raw_hierarchy:
                self._calculate_hierarchy_timings(raw_hierarchy)

            # Pass 4: Populate the flat summary tables using the now-correct
            # values that were calculated in the hierarchy.
            self._populate_flat_metrics(span_nodes)

            # Pass 5: Normalize and aggregate the raw hierarchy
            # This keeps the correct parent-child relationships but normalizes endpoints
            # and aggregates sibling nodes with the same normalized endpoint
            normalized_hierarchy = self._normalize_and_aggregate_hierarchy(raw_hierarchy)

            # Store the normalized hierarchy for the UI
            self.trace_hierarchies[trace_id] = normalized_hierarchy
            
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

    def _build_raw_hierarchy(self, spans: List[Dict]) -> Tuple[Dict, Dict]:
        """
        Build a raw tree structure from a flat list of spans, intelligently
        re-parenting orphaned spans to their logical service entry points.
        """
        span_nodes = {}
        service_server_spans = {}

        # First pass: create nodes and identify the primary SERVER span for each service.
        for span in spans:
            span_id = span.get('spanId')
            if not span_id: continue
            
            duration_ms = (span.get('endTimeUnixNano', 0) - span.get('startTimeUnixNano', 0)) / 1_000_000.0
            service_name = self.extract_service_name(span.get('resource', {}).get('attributes', []))
            
            span_nodes[span_id] = {
                'span': span, 'service_name': service_name, 'children': [],
                'total_time_ms': duration_ms, 'self_time_ms': duration_ms,
            }

            if span.get('kind') == 'SPAN_KIND_SERVER' and service_name not in service_server_spans:
                 service_server_spans[service_name] = span_id

        # Second pass: link children, adopting orphans to their service's SERVER span.
        root_spans = []
        for span_id, node in span_nodes.items():
            parent_span_id = node['span'].get('parentSpanId')
            
            if parent_span_id and parent_span_id in span_nodes:
                span_nodes[parent_span_id]['children'].append(node)
            elif node['service_name'] in service_server_spans and span_id != service_server_spans[node['service_name']]:
                # This is an orphan. Adopt it.
                parent_id = service_server_spans[node['service_name']]
                span_nodes[parent_id]['children'].append(node)
            else:
                # This is a true root span.
                root_spans.append(node)
        
        root = {
            'span': {'name': 'Trace Root'}, 'service_name': 'Trace', 'children': root_spans,
            'total_time_ms': sum(s['total_time_ms'] for s in root_spans), 'self_time_ms': 0
        }
        return root, span_nodes

    def _populate_flat_metrics(self, span_nodes: Dict):
        """
        Pass 4: Populate the flat summary tables. This function reads the
        final, correct values from the nodes after the hierarchy has been fully processed.
        
        Service Filtering Logic:
        
        include_gateway_services (controls CLIENT-only services):
        - False (default): Only counts services with SERVER spans
        - True: Also counts services with only CLIENT spans (API gateways, proxies)
        
        include_service_mesh (controls sidecar duplicates):
        - False (default): Filters out SERVER→SERVER and CLIENT→CLIENT chains
          (Istio/Envoy sidecar patterns), showing only application spans
        - True: Includes all spans, showing both application and sidecar spans
          (useful for diagnosing service mesh overhead)
        
        Combined behavior:
        - Both False: Business logic only, cleanest view
        - Gateway True, Mesh False: Includes API gateways, excludes sidecar duplicates
        - Gateway False, Mesh True: Includes sidecar duplicates, excludes pure gateways
        - Both True: Complete infrastructure view, all spans included
        """
        # Pre-pass: When include_gateway_services is True, collect all services that have SERVER spans
        # This prevents us from double-counting CLIENT spans from services that also have SERVER spans
        services_with_server_spans = set()
        if self.include_gateway_services:
            for span_id, node in span_nodes.items():
                span = node['span']
                span_kind = span.get('kind', '')
                if span_kind == 'SPAN_KIND_SERVER':
                    services_with_server_spans.add(node['service_name'])
        
        for span_id, node in span_nodes.items():
            span = node['span']
            attributes = span.get('attributes', [])
            span_kind = span.get('kind', '')
            
            parent_span_id = span.get('parentSpanId')
            parent_node = span_nodes.get(parent_span_id)
            parent_kind = parent_node['span'].get('kind') if parent_node else None

            # Read the final, correct time values from the node.
            total_time = node['total_time_ms']
            self_time = node['self_time_ms']

            # Check for errors
            span_status = span.get('status', {})
            is_error = span_status.get('code') == 'STATUS_CODE_ERROR'
            error_message = span_status.get('message', 'Unknown Error') if is_error else None

            http_path = self.extract_http_path(attributes)
            if http_path:
                http_method = self.extract_http_method(attributes)
                # If method is missing, try to extract from span name or default to UNKNOWN
                if not http_method:
                    span_name = span.get('name', '')
                    # Common HTTP methods that might appear in span names
                    for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
                        if span_name.startswith(method + ' ') or span_name == method:
                            http_method = method
                            break
                    # If still no method found, use UNKNOWN to avoid empty strings
                    if not http_method:
                        http_method = 'UNKNOWN'
                
                normalized_path, params = self.normalize_path(http_path)
                param_str = params[0] if params else '[no-params]'
                
                # Apply filtering logic for SERVER spans based on configuration
                should_include_server = False
                if span_kind == 'SPAN_KIND_SERVER':
                    # Step 1: Check if we should filter out service mesh sidecar duplicates
                    if self.include_service_mesh:
                        # Include ALL SERVER spans when service mesh is enabled
                        should_include_server = True
                    else:
                        # Filter out SERVER→SERVER hops (Envoy sidecar → app pattern)
                        # Include: CLIENT parent (normal call), None (root), INTERNAL (app logic)
                        # Exclude: SERVER parent (sidecar duplicate)
                        should_include_server = (parent_kind != 'SPAN_KIND_SERVER')
                    
                    # Step 2: Further filter based on gateway_services setting
                    # This only matters when include_service_mesh=False
                    if not self.include_service_mesh and not self.include_gateway_services:
                        # Strictest mode: Only CLIENT parent or root (no parent)
                        should_include_server = (parent_kind == 'SPAN_KIND_CLIENT' or parent_kind is None)
                
                if should_include_server:
                    key = (node['service_name'], http_method, normalized_path, param_str)
                    self.endpoint_params[key]['count'] += 1
                    self.endpoint_params[key]['total_time_ms'] += total_time
                    self.endpoint_params[key]['total_self_time_ms'] += self_time
                    if is_error and error_message:
                        self.endpoint_params[key]['error_count'] += 1
                        self.endpoint_params[key]['error_messages'][error_message] += 1
                
                # Apply filtering logic for CLIENT spans based on configuration
                elif span_kind == 'SPAN_KIND_CLIENT':
                    # When include_gateway_services is True, we need to capture services
                    # that ONLY have CLIENT spans (pure gateways/proxies)
                    if self.include_gateway_services:
                        # Only add CLIENT span as incoming request if service has NO SERVER spans AT ALL
                        # This captures pure gateway services like 'gateway-service' or 'gs:prod:/dx'
                        # Use the pre-collected set for efficient lookup
                        if node['service_name'] not in services_with_server_spans:
                            # Treat this CLIENT span as if it's an incoming request to the gateway
                            key = (node['service_name'], http_method, normalized_path, param_str)
                            self.endpoint_params[key]['count'] += 1
                            self.endpoint_params[key]['total_time_ms'] += total_time
                            self.endpoint_params[key]['total_self_time_ms'] += self_time
                            if is_error and error_message:
                                self.endpoint_params[key]['error_count'] += 1
                                self.endpoint_params[key]['error_messages'][error_message] += 1
                    
                    # Always track service-to-service calls (for the service calls table)
                    # Apply filtering based on service mesh setting
                    if self.include_service_mesh:
                        # Include ALL CLIENT spans when service mesh is enabled
                        should_include_client = True
                    else:
                        # Filter out CLIENT→CLIENT chains (app → Envoy sidecar pattern)
                        should_include_client = (parent_kind != 'SPAN_KIND_CLIENT')
                    
                    if should_include_client:
                        target_service = self.extract_target_service_from_url(http_path)
                        key = (node['service_name'], target_service, http_method, normalized_path, param_str)
                        self.service_calls[key]['count'] += 1
                        self.service_calls[key]['total_time_ms'] += total_time
                        self.service_calls[key]['total_self_time_ms'] += self_time
                        if is_error and error_message:
                            self.service_calls[key]['error_count'] += 1
                            self.service_calls[key]['error_messages'][error_message] += 1
            else:
                op_type, msg_type, details = self.extract_kafka_info(span, attributes)
                if op_type in ['consumer', 'producer']:
                    key = (node['service_name'], op_type, msg_type, details)
                    self.kafka_messages[key]['count'] += 1
                    self.kafka_messages[key]['total_time_ms'] += total_time
                    if is_error and error_message:
                        self.kafka_messages[key]['error_count'] += 1
                        self.kafka_messages[key]['error_messages'][error_message] += 1

    def _calculate_hierarchy_timings(self, node: Dict):
        """
        Pass 3: Recursively traverse the hierarchy to aggregate children and calculate self-time.
        This works bottom-up.
        """
        if not node or not node.get('children'):
            return

        # 1. Recurse to the bottom of the tree for all children.
        #    This ensures that everything below the current node is fully processed.
        for child in node['children']:
            self._calculate_hierarchy_timings(child)

        # 2. Now that all children have been processed (including their own self-time
        #    and aggregation), aggregate the immediate children of the current node.
        aggregated_children = self._aggregate_list_of_nodes(node['children'])
        node['children'] = aggregated_children
        
        # 3. Finally, calculate the self-time of the current node by subtracting the
        #    total time of its now-aggregated children.
        child_total_time = sum(child['total_time_ms'] for child in node['children'])
        node['self_time_ms'] = max(0, node['total_time_ms'] - child_total_time)

    def _aggregate_list_of_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """
        Aggregates a list of nodes based on a composite key.
        This function is NOT recursive; it relies on the main recursive loop
        in _calculate_hierarchy_timings to have already processed child nodes.
        """
        if not nodes:
            return []

        aggregated_nodes = defaultdict(list)
        for node in nodes:
            span = node.get('span', {})
            service = node.get('service_name', 'Unknown')
            
            # First, check if the node already has display info (from earlier processing)
            if '_display_method' in node and '_display_path' in node:
                http_method = node['_display_method']
                normalized_path = node['_display_path']
                aggregation_key = f"{service}:{http_method}:{normalized_path}"
            else:
                # Extract from span attributes
                http_path = self.extract_http_path(span.get('attributes', []))
                
                if http_path:
                    http_method = self.extract_http_method(span.get('attributes', []))
                    # Default to method from span name if missing
                    if not http_method:
                        span_name = span.get('name', '')
                        for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
                            if span_name.startswith(method + ' ') or span_name == method:
                                http_method = method
                                break
                        if not http_method:
                            http_method = 'POST'  # Default to POST instead of UNKNOWN
                    
                    normalized_path, _ = self.normalize_path(http_path)
                    aggregation_key = f"{service}:{http_method}:{normalized_path}"
                    # Store method and path for display
                    node['_display_method'] = http_method
                    node['_display_path'] = normalized_path
                else:
                    # Non-HTTP span (Kafka, database, internal)
                    aggregation_key = f"{service}:{span.get('name', 'Unknown Span')}"
            
            aggregated_nodes[aggregation_key].append(node)

        final_list = []
        for key, group in aggregated_nodes.items():
            if len(group) == 1:
                # Single node - enhance display name if HTTP
                node = group[0]
                if '_display_method' in node and '_display_path' in node:
                    # Create a clean display name
                    display_name = f"{node['_display_method']} {node['_display_path']}"
                    # Only update if it's not already formatted
                    if not node['span'].get('name', '').startswith(node['_display_method']):
                        node['span']['name'] = display_name
                    node['http_method'] = node['_display_method']
                final_list.append(node)
            else:
                total_time = sum(c['total_time_ms'] for c in group)
                self_time = sum(c['self_time_ms'] for c in group)
                
                # Grandchildren are simply concatenated. They have already been correctly
                # aggregated by the main recursive calls in _calculate_hierarchy_timings.
                all_grandchildren = [grandchild for child in group for grandchild in child.get('children', [])]
                
                # Create a clean display name for aggregated nodes
                if '_display_method' in group[0] and '_display_path' in group[0]:
                    display_name = f"{group[0]['_display_method']} {group[0]['_display_path']}"
                    http_method = group[0]['_display_method']
                else:
                    display_name = key
                    http_method = None
                
                agg_node = {
                    'span': {
                        'name': display_name,
                        # Keep attributes from the first span for the template to extract the HTTP method.
                        'attributes': group[0]['span'].get('attributes', [])
                    },
                    'service_name': group[0]['service_name'],
                    'http_method': http_method,
                    'children': all_grandchildren,
                    'total_time_ms': total_time,
                    'self_time_ms': self_time,
                    'aggregated': True,
                    'count': sum(c.get('count', 1) for c in group),
                    'avg_time_ms': total_time / sum(c.get('count', 1) for c in group)
                }
                final_list.append(agg_node)
        
        return final_list

    def _build_aggregated_hierarchy(self, trace_id: str, span_nodes: Dict):
        """
        Build an aggregated hierarchy view using the already-aggregated flat metrics.
        This creates a tree that shows service call relationships with proper aggregation
        by (service, method, path, parameter), matching the flat tables.
        
        Returns a root node with the trace entry point as the starting point.
        """
        # If no span nodes, return None
        if not span_nodes:
            return None
        
        # Find the root span (no parent or smallest startTime)
        root_span_node = None
        min_start_time = float('inf')
        
        for span_id, node in span_nodes.items():
            span = node['span']
            parent_id = span.get('parentSpanId')
            start_time = span.get('startTimeUnixNano', 0)
            
            # Root is span with no parent, or earliest span if all have parents
            if not parent_id or parent_id not in span_nodes:
                if start_time < min_start_time:
                    min_start_time = start_time
                    root_span_node = node
        
        if not root_span_node:
            # Fallback: use first span
            root_span_node = list(span_nodes.values())[0]
        
        # Build a map of service calls: caller -> [(target, endpoint_info)]
        service_children = defaultdict(list)
        
        # Add service-to-service calls
        for key, stats in self.service_calls.items():
            caller_service, target_service, http_method, normalized_path, param_str = key
            
            display_name = f"{http_method} {normalized_path}"
            if param_str and param_str != '[no-params]':
                display_name += f" ({param_str})"
            
            child_node = {
                'span': {
                    'name': display_name,
                    'attributes': []
                },
                'service_name': target_service,
                'http_method': http_method,
                'total_time_ms': stats['total_time_ms'],
                'self_time_ms': stats['total_self_time_ms'],
                'aggregated': stats['count'] > 1,
                'count': stats['count'],
                'avg_time_ms': stats['total_time_ms'] / stats['count'] if stats['count'] > 0 else 0,
                'children': []
            }
            
            service_children[caller_service].append(child_node)
        
        # Also add incoming requests (endpoint_params) for services
        service_endpoints = defaultdict(list)
        for key, stats in self.endpoint_params.items():
            service_name, http_method, normalized_path, param_str = key
            
            display_name = f"{http_method} {normalized_path}"
            if param_str and param_str != '[no-params]':
                display_name += f" ({param_str})"
            
            endpoint_info = {
                'span': {
                    'name': display_name,
                    'attributes': []
                },
                'service_name': service_name,
                'http_method': http_method,
                'total_time_ms': stats['total_time_ms'],
                'self_time_ms': stats['total_self_time_ms'],
                'aggregated': stats['count'] > 1,
                'count': stats['count'],
                'avg_time_ms': stats['total_time_ms'] / stats['count'] if stats['count'] > 0 else 0,
                'children': []
            }
            
            service_endpoints[service_name].append(endpoint_info)
        
        # Build the tree recursively - NO aggregation, show each unique call
        def build_tree(service_name, visited=None, depth=0):
            if visited is None:
                visited = set()
            
            # Prevent infinite recursion
            if service_name in visited or depth > 10:
                return []
            
            visited.add(service_name)
            children = []
            
            # Add all outgoing calls from this service (already aggregated by service_calls keys)
            for child in service_children.get(service_name, []):
                # Recursively build children for this child's target service
                child['children'] = build_tree(child['service_name'], visited.copy(), depth + 1)
                children.append(child)
            
            return children
        
        # Create root node
        root_service = root_span_node['service_name']
        
        # Get display name for root
        root_display_name = root_span_node['span'].get('name', 'Trace Entry')
        
        # Extract HTTP info if available
        root_http_path = self.extract_http_path(root_span_node['span'].get('attributes', []))
        if root_http_path:
            root_http_method = self.extract_http_method(root_span_node['span'].get('attributes', []))
            if not root_http_method:
                root_http_method = 'POST'
            root_normalized_path, _ = self.normalize_path(root_http_path)
            root_display_name = f"{root_http_method} {root_normalized_path}"
        
        # Build children - if root service has no calls, find all top-level services
        root_children = build_tree(root_service)
        
        # If root has no children, it might be a gateway/proxy with no recorded calls
        # Find services that aren't called by anyone (top-level entry points)
        if not root_children:
            all_callers = set(key[0] for key in self.service_calls.keys())  # caller services
            all_targets = set(key[1] for key in self.service_calls.keys())  # target services
            
            # Services that make calls but aren't called by others are entry points
            entry_services = all_callers - all_targets
            
            for entry_service in entry_services:
                root_children.extend(build_tree(entry_service))
        
        root_node = {
            'span': {
                'name': root_display_name,
                'attributes': root_span_node['span'].get('attributes', [])
            },
            'service_name': root_service,
            'total_time_ms': root_span_node['total_time_ms'],
            'self_time_ms': root_span_node['self_time_ms'],
            'aggregated': False,
            'count': 1,
            'children': root_children
        }
        
        return root_node

    def _normalize_and_aggregate_hierarchy(self, root_node: Dict) -> Dict:
        """
        Recursively normalize span names and aggregate sibling nodes that have
        the same normalized endpoint. This keeps the correct parent-child relationships
        from the raw hierarchy while providing clean, aggregated display.
        
        Also filters out service mesh sidecar duplicates when include_service_mesh is False.
        """
        if not root_node:
            return None
        
        def normalize_node(node):
            """Normalize a single node's display name."""
            span = node['span']
            attributes = span.get('attributes', [])
            
            # Extract HTTP information
            http_path = self.extract_http_path(attributes)
            if http_path:
                http_method = self.extract_http_method(attributes)
                if not http_method:
                    # Try to extract from span name
                    span_name = span.get('name', '')
                    if span_name.startswith(('GET ', 'POST ', 'PUT ', 'DELETE ', 'PATCH ')):
                        http_method = span_name.split()[0]
                    else:
                        http_method = 'POST'  # Default
                
                normalized_path, param_values = self.normalize_path(http_path)
                
                # Convert param_values list to string
                param_str = ', '.join(param_values) if param_values else ''
                
                # Create display name
                display_name = f"{http_method} {normalized_path}"
                if param_str:
                    display_name += f" ({param_str})"
                
                node['span']['name'] = display_name
                node['http_method'] = http_method
                node['normalized_path'] = normalized_path
                node['parameter_value'] = param_str
            
            return node
        
        def should_skip_node(node, parent_node=None):
            """
            Determine if a node is a service mesh sidecar duplicate that should be skipped.
            Returns True if the node should be skipped (and its children lifted to parent).
            """
            if self.include_service_mesh:
                return False  # Don't skip anything when mesh spans are included
            
            # Check for same-service duplicates (service calling itself)
            if parent_node:
                parent_service = parent_node.get('service_name', '')
                node_service = node.get('service_name', '')
                
                # Skip if same service (sidecar duplicate)
                if node_service and parent_service and node_service == parent_service:
                    # Same service calling itself is a sidecar duplicate
                    return True
            
            return False
        
        def filter_duplicates_and_lift(children, parent_node):
            """
            Recursively filter out same-service duplicates and lift their children.
            Keep lifting until we find nodes from different services.
            """
            if not children:
                return []
            
            result = []
            for child in children:
                normalize_node(child)
                
                if should_skip_node(child, parent_node):
                    # Skip this duplicate and recursively process its children
                    result.extend(filter_duplicates_and_lift(child.get('children', []), parent_node))
                else:
                    result.append(child)
            
            return result
        
        def aggregate_siblings(children, parent_node=None):
            """Aggregate sibling nodes with the same normalized endpoint."""
            if not children:
                return []
            
            # First pass: filter out sidecar duplicates and lift their children
            filtered_children = filter_duplicates_and_lift(children, parent_node)
            
            # Second pass: group by (service_name, http_method, normalized_path, parameter_value)
            groups = {}
            for child in filtered_children:
                # Normalize again (in case we lifted unnormalized children)
                normalize_node(child)
                
                # Create aggregation key
                service = child.get('service_name', '')
                method = child.get('http_method', '')
                path = child.get('normalized_path', '')
                param = child.get('parameter_value', '')
                
                # Include parameter in key to keep separate calls separate
                key = (service, method, path, param)
                
                if key not in groups:
                    groups[key] = []
                groups[key].append(child)
            
            # Aggregate each group
            aggregated = []
            for group_children in groups.values():
                if len(group_children) == 1:
                    # Single node - just recursively process children
                    node = group_children[0]
                    node['children'] = aggregate_siblings(node.get('children', []), node)
                    node['aggregated'] = False
                    node['count'] = 1
                    aggregated.append(node)
                else:
                    # Multiple nodes - aggregate them
                    first = group_children[0]
                    total_time = sum(c.get('total_time_ms', 0) for c in group_children)
                    self_time = sum(c.get('self_time_ms', 0) for c in group_children)
                    count = len(group_children)
                    
                    # Collect all grandchildren
                    all_grandchildren = []
                    for c in group_children:
                        all_grandchildren.extend(c.get('children', []))
                    
                    # Recursively aggregate grandchildren (pass first as parent node)
                    aggregated_grandchildren = aggregate_siblings(all_grandchildren, first)
                    
                    agg_node = {
                        'span': first['span'].copy(),
                        'service_name': first.get('service_name', ''),
                        'http_method': first.get('http_method', ''),
                        'normalized_path': first.get('normalized_path', ''),
                        'parameter_value': first.get('parameter_value', ''),
                        'total_time_ms': total_time,
                        'self_time_ms': self_time,
                        'children': aggregated_grandchildren,
                        'aggregated': True,
                        'count': count,
                        'avg_time_ms': total_time / count if count > 0 else 0
                    }
                    aggregated.append(agg_node)
            
            return aggregated
        
        # Normalize and process the root
        root_copy = root_node.copy()
        normalize_node(root_copy)
        root_copy['children'] = aggregate_siblings(root_copy.get('children', []), root_copy)
        root_copy['aggregated'] = False
        root_copy['count'] = 1
        
        return root_copy
    
    def _filter_hierarchy(self, node: Dict, span_nodes: Dict):
        """
        Filter the hierarchy tree to remove only sidecar duplicates based on service mesh settings.
        The hierarchy should show the actual call flow, so we only filter out infrastructure duplicates.
        
        Args:
            node: The current hierarchy node to filter
            span_nodes: Flat map of all span nodes for looking up parents
            
        Returns:
            Filtered node dict or None if it should be excluded
        """
        if not node:
            return None
        
        span = node.get('span', {})
        span_kind = span.get('kind', '')
        
        # Get parent information
        parent_span_id = span.get('parentSpanId')
        parent_node = span_nodes.get(parent_span_id)
        parent_kind = parent_node['span'].get('kind') if parent_node else None
        
        # For hierarchy view, we want to show the actual trace flow
        # Only filter out clear service mesh duplicates when service mesh filtering is OFF
        should_include = True
        
        if not self.include_service_mesh:
            # Filter only obvious sidecar duplicates
            if span_kind == 'SPAN_KIND_SERVER' and parent_kind == 'SPAN_KIND_SERVER':
                # This is likely a sidecar→app hop, filter it out
                should_include = False
            elif span_kind == 'SPAN_KIND_CLIENT' and parent_kind == 'SPAN_KIND_CLIENT':
                # This is likely an app→sidecar hop, filter it out
                should_include = False
        
        # If this node should be excluded, return None
        if not should_include:
            return None
        
        # Recursively filter children
        if 'children' in node and node['children']:
            filtered_children = []
            for child in node['children']:
                filtered_child = self._filter_hierarchy(child, span_nodes)
                if filtered_child is not None:
                    filtered_children.append(filtered_child)
            node['children'] = filtered_children
        
        return node

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
  python analyze_trace.py trace.json --include-gateways
  python analyze_trace.py trace.json --include-service-mesh
  python analyze_trace.py trace.json --include-gateways --include-service-mesh
        """
    )
    parser.add_argument('input_file', help='Path to the trace JSON file')
    parser.add_argument('-o', '--output', dest='output_file', default='trace_analysis.md', help='Output markdown file')
    parser.add_argument('--keep-query-params', action='store_true', help='Keep query parameters in URLs')
    parser.add_argument('--include-gateways', action='store_true', 
                       help='Include gateway/proxy services with only CLIENT spans (default: exclude them)')
    parser.add_argument('--include-service-mesh', action='store_true',
                       help='Include service mesh sidecar spans (Istio/Envoy), showing duplicates (default: filter them out)')
    args = parser.parse_args()
    
    analyzer = TraceAnalyzer(
        strip_query_params=not args.keep_query_params,
        include_gateway_services=args.include_gateways,
        include_service_mesh=args.include_service_mesh
    )
    
    try:
        print(f"\nConfiguration:")
        print(f"  Input file: {args.input_file}")
        print(f"  Output file: {args.output_file}")
        print(f"  Strip query params: {not args.keep_query_params}")
        print(f"  Include gateway services: {args.include_gateways}")
        print(f"  Include service mesh: {args.include_service_mesh}\n")
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
