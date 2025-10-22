#!/usr/bin/env python3
"""
Trace Endpoint Analyzer
Parses Grafana trace JSON files and analyzes HTTP endpoints with parameter tracking.
"""

import ijson
import re
from collections import defaultdict
from typing import Dict, Tuple, List
import sys


class TraceAnalyzer:
    def __init__(self, strip_query_params=True):
        """
        Initialize the TraceAnalyzer.
        
        Args:
            strip_query_params (bool): If True, removes query parameters from URLs before analysis.
                                      Default: True (recommended for cleaner grouping)
        """
        self.strip_query_params = strip_query_params
        
        # Dictionary to store (service_name, normalized_endpoint, param_value) -> {'count': int, 'total_time_ms': float}
        self.endpoint_params = defaultdict(lambda: {'count': 0, 'total_time_ms': 0.0})
        
        # Dictionary to store service-to-service calls: (caller_service, callee_service, normalized_endpoint, param) -> {'count': int, 'total_time_ms': float}
        self.service_calls = defaultdict(lambda: {'count': 0, 'total_time_ms': 0.0})
        
        # Map to store spanId -> (service, normalized_endpoint, params)
        self.span_map = {}
        
        # Regex patterns for parameter detection
        self.uuid_pattern = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)
        self.numeric_id_pattern = re.compile(r'/\d+(?=/|\?|$)')
        # Pega-style rule identifiers: PegaPlatform__Something, Data-Portal__Something, etc.
        self.rule_identifier_pattern = re.compile(r'/[A-Z][A-Za-z0-9-]*__[A-Za-z0-9_]+(?=/|\?|$)')
        self.long_encoded_pattern = re.compile(r'/[A-Za-z0-9_-]{30,}(?=/|\?|$)')
        
    def normalize_path(self, path: str) -> Tuple[str, List[str]]:
        """
        Normalize a path by replacing parameter values with placeholders.
        Returns: (normalized_path, list_of_non_uuid_params)
        Note: UUID parameters are normalized but NOT tracked individually.
        """
        if not path:
            return path, []
        
        # Strip query parameters if enabled
        if self.strip_query_params and '?' in path:
            path = path.split('?')[0]
        
        non_uuid_params = []
        normalized = path
        
        # FIRST: Replace UUIDs but DON'T track them (must be done before other checks)
        # UUIDs can match the long encoded pattern, so we need to handle them first
        uuid_matches = list(self.uuid_pattern.finditer(path))
        for match in uuid_matches:
            normalized = normalized.replace(match.group(0), '{uuid}', 1)
        
        # SECOND: Extract and replace Pega-style rule identifiers (e.g., PegaPlatform__ViewLookup)
        rule_matches = list(self.rule_identifier_pattern.finditer(path))
        for match in rule_matches:
            param_value = match.group(0)[1:]  # Remove leading /
            non_uuid_params.append(param_value)
            normalized = normalized.replace(match.group(0), '/{rule_id}', 1)
        
        # THIRD: Extract and replace long encoded strings (non-UUID, non-Pega)
        # Re-search in the original path to find long encoded strings
        long_encoded_matches = list(self.long_encoded_pattern.finditer(path))
        for match in long_encoded_matches:
            param_value = match.group(0)[1:]  # Remove leading /
            
            # Check if this match overlaps with UUID or rule matches - if so, skip it
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
        
        # FOURTH: Extract and replace numeric IDs
        for match in self.numeric_id_pattern.finditer(path):
            param_value = match.group(0)[1:]  # Remove leading /
            if param_value not in non_uuid_params:  # Avoid duplicates
                non_uuid_params.append(param_value)
                normalized = normalized.replace(match.group(0), '/{id}', 1)
        
        return normalized, non_uuid_params
    
    def extract_http_path(self, attributes: List) -> Tuple[str, bool]:
        """
        Extract HTTP path from span attributes.
        Returns: (path, is_incoming)
        - is_incoming=True: relative path (incoming request to this service)
        - is_incoming=False: full URL (outgoing request to another service)
        """
        for attr in attributes:
            if attr.get('key') in ['http.path', 'http.url']:
                value = attr.get('value', {})
                path = value.get('stringValue', '')
                # If path starts with http:// or https://, it's an outgoing call
                is_outgoing = path.startswith('http://') or path.startswith('https://')
                return path, not is_outgoing
        return '', False
    
    def extract_service_name(self, resource_attributes: List) -> str:
        """Extract service name from resource attributes."""
        for attr in resource_attributes:
            if attr.get('key') == 'service.name':
                value = attr.get('value', {})
                return value.get('stringValue', 'unknown-service')
        return 'unknown-service'
    
    def extract_target_service_from_url(self, url: str) -> str:
        """
        Extract target service name from a full URL.
        E.g., http://data-service.data-service.svc.cluster.local/... -> data-service
        """
        if url.startswith('http://') or url.startswith('https://'):
            # Remove protocol
            without_protocol = url.split('://', 1)[1] if '://' in url else url
            # Get the host part
            host = without_protocol.split('/', 1)[0]
            # Extract service name (first part before the first dot)
            service = host.split('.')[0]
            return service
        return 'unknown-service'
    
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
        """Process the trace JSON file using streaming parser."""
        print(f"Processing {file_path}...")
        
        with open(file_path, 'rb') as f:
            # Stream through batches
            parser = ijson.items(f, 'batches.item')
            
            batch_count = 0
            span_count = 0
            
            for batch in parser:
                batch_count += 1
                
                # Extract service name from batch resource
                resource = batch.get('resource', {})
                resource_attributes = resource.get('attributes', [])
                service_name = self.extract_service_name(resource_attributes)
                
                # Navigate through instrumentationLibrarySpans
                inst_lib_spans = batch.get('instrumentationLibrarySpans', [])
                
                for inst_lib_span in inst_lib_spans:
                    spans = inst_lib_span.get('spans', [])
                    
                    for span in spans:
                        span_count += 1
                        attributes = span.get('attributes', [])
                        
                        span_id = span.get('spanId', '')
                        parent_span_id = span.get('parentSpanId', '')
                        
                        # Calculate span duration in milliseconds
                        start_time_nano = span.get('startTimeUnixNano', 0)
                        end_time_nano = span.get('endTimeUnixNano', 0)
                        duration_ms = (end_time_nano - start_time_nano) / 1_000_000.0  # Convert nanoseconds to milliseconds
                        
                        # Extract HTTP path and determine if it's incoming or outgoing
                        http_path, is_incoming = self.extract_http_path(attributes)
                        
                        if http_path:
                            # Normalize the path and extract non-UUID parameters
                            normalized_path, non_uuid_params = self.normalize_path(http_path)
                            
                            # Store span information for parent-child relationship tracking
                            if non_uuid_params:
                                for param in non_uuid_params:
                                    self.span_map[span_id] = (service_name, normalized_path, param)
                                    
                                    # Track endpoint calls by service (ONLY for incoming requests)
                                    if is_incoming:
                                        key = (service_name, normalized_path, param)
                                        self.endpoint_params[key]['count'] += 1
                                        self.endpoint_params[key]['total_time_ms'] += duration_ms
                                    else:
                                        # For outgoing calls, track as service-to-service call
                                        target_service = self.extract_target_service_from_url(http_path)
                                        call_key = (service_name, target_service, normalized_path, param)
                                        self.service_calls[call_key]['count'] += 1
                                        self.service_calls[call_key]['total_time_ms'] += duration_ms
                            else:
                                # No non-UUID parameters found, track the endpoint pattern only
                                self.span_map[span_id] = (service_name, normalized_path, '[no-params]')
                                
                                # Track endpoint calls by service (ONLY for incoming requests)
                                if is_incoming:
                                    key = (service_name, normalized_path, '[no-params]')
                                    self.endpoint_params[key]['count'] += 1
                                    self.endpoint_params[key]['total_time_ms'] += duration_ms
                                else:
                                    # For outgoing calls, track as service-to-service call
                                    target_service = self.extract_target_service_from_url(http_path)
                                    call_key = (service_name, target_service, normalized_path, '[no-params]')
                                    self.service_calls[call_key]['count'] += 1
                                    self.service_calls[call_key]['total_time_ms'] += duration_ms
                
                if batch_count % 100 == 0:
                    print(f"  Processed {batch_count} batches, {span_count} spans...")
        
        print(f"Completed: {batch_count} batches, {span_count} spans processed")
        print(f"Found {len(self.endpoint_params)} unique endpoint-parameter combinations")
        print(f"Found {len(self.service_calls)} unique service-to-service call combinations")
    
    def generate_markdown_report(self, output_file: str):
        """Generate a markdown file with the analysis results."""
        print(f"\nGenerating report: {output_file}")
        
        # Group data by service
        services_data = defaultdict(list)
        for (service, endpoint, param), stats in self.endpoint_params.items():
            services_data[service].append((endpoint, param, stats['count'], stats['total_time_ms']))
        
        # Sort services alphabetically
        sorted_services = sorted(services_data.keys())
        
        with open(output_file, 'w') as f:
            f.write("# Trace Endpoint Analysis Report\n\n")
            
            total_requests = sum(stats['count'] for stats in self.endpoint_params.values())
            total_time_ms = sum(stats['total_time_ms'] for stats in self.endpoint_params.values())
            unique_services = len(services_data)
            unique_endpoints = len(set((k[0], k[1]) for k in self.endpoint_params.keys()))
            
            f.write(f"**Total Incoming Requests:** {total_requests}  \n")
            f.write(f"**Total Time (Incoming):** {self.format_time(total_time_ms)}  \n")
            f.write(f"**Unique Services:** {unique_services}  \n")
            f.write(f"**Unique Normalized Endpoints:** {unique_endpoints}  \n")
            f.write(f"**Unique Endpoint-Parameter Combinations:** {len(self.endpoint_params)}  \n\n")
            
            f.write("---\n\n")
            
            # Generate table of contents
            f.write("## Table of Contents - Incoming Requests by Service\n\n")
            for service in sorted_services:
                service_count = sum(count for _, _, count, _ in services_data[service])
                service_time = sum(time_ms for _, _, _, time_ms in services_data[service])
                # Create anchor-friendly service name
                anchor = service.lower().replace(':', '').replace('/', '').replace(' ', '-')
                f.write(f"- [{service}](#{anchor}) ({service_count} requests, {self.format_time(service_time)})\n")
            f.write("\n---\n\n")
            
            f.write("# Incoming Requests by Service\n\n")
            f.write("*This section shows endpoints that each service receives (incoming HTTP requests).*  \n")
            f.write("*Tables are sorted by Total Time (descending).*\n\n")
            
            # Generate separate table for each service
            for service in sorted_services:
                service_data = services_data[service]
                
                # Sort by total time (descending), then by endpoint, then by parameter
                sorted_service_data = sorted(
                    service_data,
                    key=lambda x: (-x[3], x[0], x[1])
                )
                
                service_count = sum(count for _, _, count, _ in service_data)
                service_time = sum(time_ms for _, _, _, time_ms in service_data)
                unique_combos = len(service_data)
                
                f.write(f"## {service}\n\n")
                f.write(f"**Service Requests:** {service_count}  \n")
                f.write(f"**Total Time:** {self.format_time(service_time)}  \n")
                f.write(f"**Unique Combinations:** {unique_combos}  \n\n")
                
                f.write("| Normalized Endpoint | Parameter Value | Count | Total Time |\n")
                f.write("|---------------------|-----------------|-------|------------|\n")
                
                for endpoint, param, count, time_ms in sorted_service_data:
                    # Truncate long parameter values for readability
                    display_param = param if len(param) <= 50 else f"{param[:47]}..."
                    f.write(f"| {endpoint} | {display_param} | {count} | {self.format_time(time_ms)} |\n")
                
                f.write("\n")
            
            # Generate Service-to-Service Call section
            if self.service_calls:
                f.write("---\n\n")
                f.write("# Service-to-Service Calls (Outgoing)\n\n")
                f.write("*This section shows outgoing HTTP calls from one service to another.*  \n")
                f.write("*Tables are sorted by Total Time (descending).*\n\n")
                
                # Group service calls by (caller, callee)
                service_pairs = defaultdict(list)
                for (caller, callee, endpoint, param), stats in self.service_calls.items():
                    service_pairs[(caller, callee)].append((endpoint, param, stats['count'], stats['total_time_ms']))
                
                # Sort service pairs
                sorted_pairs = sorted(service_pairs.keys())
                
                total_call_time = sum(stats['total_time_ms'] for stats in self.service_calls.values())
                
                f.write(f"**Total Cross-Service Call Combinations:** {len(self.service_calls)}  \n")
                f.write(f"**Total Time (Cross-Service):** {self.format_time(total_call_time)}  \n")
                f.write(f"**Service Pair Relationships:** {len(sorted_pairs)}  \n\n")
                
                for caller, callee in sorted_pairs:
                    pair_data = service_pairs[(caller, callee)]
                    
                    # Sort by total time (descending)
                    sorted_pair_data = sorted(pair_data, key=lambda x: (-x[3], x[0], x[1]))
                    
                    pair_count = sum(count for _, _, count, _ in pair_data)
                    pair_time = sum(time_ms for _, _, _, time_ms in pair_data)
                    
                    f.write(f"## {caller} → {callee}\n\n")
                    f.write(f"**Total Calls:** {pair_count}  \n")
                    f.write(f"**Total Time:** {self.format_time(pair_time)}  \n")
                    f.write(f"**Unique Combinations:** {len(pair_data)}  \n\n")
                    
                    f.write("| Normalized Endpoint | Parameter Value | Count | Total Time |\n")
                    f.write("|---------------------|-----------------|-------|------------|\n")
                    
                    for endpoint, param, count, time_ms in sorted_pair_data:
                        # Truncate long parameter values for readability
                        display_param = param if len(param) <= 50 else f"{param[:47]}..."
                        f.write(f"| {endpoint} | {display_param} | {count} | {self.format_time(time_ms)} |\n")
                    
                    f.write("\n")
        
        print(f"Report generated successfully!")
        
        # Print summary statistics
        print("\n=== Summary Statistics ===")
        print(f"Total incoming requests: {total_requests}")
        print(f"Total time (incoming): {self.format_time(total_time_ms)}")
        print(f"Unique services: {unique_services}")
        print(f"Unique normalized endpoints: {unique_endpoints}")
        print(f"Unique endpoint-parameter combinations: {len(self.endpoint_params)}")
        
        print("\n=== Incoming Requests per Service ===")
        for service in sorted_services:
            service_count = sum(count for _, _, count, _ in services_data[service])
            service_time = sum(time_ms for _, _, _, time_ms in services_data[service])
            print(f"{service_count:6d} requests ({self.format_time(service_time):>12s})  {service}")
        
        # Service-to-service call statistics
        if self.service_calls:
            print(f"\n=== Service-to-Service Calls ===")
            print(f"Total cross-service call combinations: {len(self.service_calls)}")
            
            service_pairs = defaultdict(lambda: {'count': 0, 'total_time_ms': 0.0})
            for (caller, callee, endpoint, param), stats in self.service_calls.items():
                service_pairs[(caller, callee)]['count'] += stats['count']
                service_pairs[(caller, callee)]['total_time_ms'] += stats['total_time_ms']
            
            print(f"Service pair relationships: {len(service_pairs)}")
            print("\nTop service pair connections (by total time):")
            sorted_pairs = sorted(service_pairs.items(), key=lambda x: -x[1]['total_time_ms'])[:10]
            for (caller, callee), stats in sorted_pairs:
                print(f"{self.format_time(stats['total_time_ms']):>12s} ({stats['count']:4d} calls)  {caller} → {callee}")
        
        # Top 10 slowest incoming requests (by total time)
        print("\n=== Top 10 Slowest Incoming Requests (by Total Time) ===")
        top_10 = sorted(self.endpoint_params.items(), key=lambda x: -x[1]['total_time_ms'])[:10]
        for (service, endpoint, param), stats in top_10:
            display_param = param if len(param) <= 30 else f"{param[:27]}..."
            print(f"{self.format_time(stats['total_time_ms']):>12s} ({stats['count']:4d}x)  [{service}] {endpoint} | {display_param}")


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
    parser.add_argument('-o', '--output', dest='output_file', 
                       default='trace_analysis.md',
                       help='Output markdown file (default: trace_analysis.md)')
    parser.add_argument('--keep-query-params', action='store_true',
                       help='Keep query parameters in URLs (default: strip them)')
    
    args = parser.parse_args()
    
    input_file = args.input_file
    output_file = args.output_file
    strip_query_params = not args.keep_query_params
    
    analyzer = TraceAnalyzer(strip_query_params=strip_query_params)
    
    try:
        print(f"\nConfiguration:")
        print(f"  Input file: {input_file}")
        print(f"  Output file: {output_file}")
        print(f"  Strip query params: {strip_query_params}")
        print()
        
        analyzer.process_trace_file(input_file)
        analyzer.generate_markdown_report(output_file)
        print(f"\n✓ Analysis complete! Report saved to: {output_file}")
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

