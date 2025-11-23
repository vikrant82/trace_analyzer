"""
Metrics populator for flat summary tables.
"""

from typing import Dict
from collections import defaultdict


class MetricsPopulator:
    """Populates flat metrics from hierarchy nodes."""
    
    def __init__(self, config, http_extractor, kafka_extractor, path_normalizer):
        """
        Initialize with configuration and extractors.
        
        Args:
            config: TraceConfig instance
            http_extractor: HttpExtractor instance
            kafka_extractor: KafkaExtractor instance
            path_normalizer: PathNormalizer instance
        """
        self.config = config
        self.http_extractor = http_extractor
        self.kafka_extractor = kafka_extractor
        self.path_normalizer = path_normalizer
    
    def populate_flat_metrics(self, span_nodes: Dict) -> tuple:
        """
        Pass 4: Populate the flat summary tables. This function reads the
        final, correct values from the nodes after the hierarchy has been fully processed.
        
        Args:
            span_nodes: Flat mapping of span_id -> node
            
        Returns:
            Tuple of (endpoint_params, service_calls, kafka_messages)
        """
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
        
        # Pre-pass: When include_gateway_services is True, collect all services that have SERVER spans
        services_with_server_spans = set()
        if self.config.include_gateway_services:
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
            
            # Read the final, correct time values from the node
            total_time = node['total_time_ms']
            self_time = node['self_time_ms']
            
            # Use intelligent error extraction
            from ..extractors.error_extractor import ErrorExtractor
            is_error, error_message, _ = ErrorExtractor.extract_error_details(span)

            
            http_path = self.http_extractor.extract_http_path(attributes)
            if http_path:
                http_method = self.http_extractor.extract_http_method(attributes)
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
                
                normalized_path, params = self.path_normalizer.normalize_path(
                    http_path,
                    self.config.strip_query_params
                )
                param_str = params[0] if params else '[no-params]'
                
                # Apply filtering logic for SERVER spans based on configuration
                should_include_server = False
                if span_kind == 'SPAN_KIND_SERVER':
                    # Step 1: Check if we should filter out service mesh sidecar duplicates
                    if self.config.include_service_mesh:
                        # Include ALL SERVER spans when service mesh is enabled
                        should_include_server = True
                    else:
                        # Filter out SERVER→SERVER hops (Envoy sidecar → app pattern)
                        should_include_server = (parent_kind != 'SPAN_KIND_SERVER')
                    
                    # Step 2: Further filter based on gateway_services setting
                    if not self.config.include_service_mesh and not self.config.include_gateway_services:
                        # Strictest mode: Only CLIENT parent or root (no parent)
                        should_include_server = (parent_kind == 'SPAN_KIND_CLIENT' or parent_kind is None)
                
                if should_include_server:
                    key = (node['service_name'], http_method, normalized_path, param_str)
                    endpoint_params[key]['count'] += 1
                    endpoint_params[key]['total_time_ms'] += total_time
                    endpoint_params[key]['total_self_time_ms'] += self_time
                    if is_error and error_message:
                        endpoint_params[key]['error_count'] += 1
                        endpoint_params[key]['error_messages'][error_message] += 1
                
                # Apply filtering logic for CLIENT spans based on configuration
                elif span_kind == 'SPAN_KIND_CLIENT':
                    # When include_gateway_services is True, capture pure gateway services
                    if self.config.include_gateway_services:
                        if node['service_name'] not in services_with_server_spans:
                            # Treat this CLIENT span as incoming request to the gateway
                            key = (node['service_name'], http_method, normalized_path, param_str)
                            endpoint_params[key]['count'] += 1
                            endpoint_params[key]['total_time_ms'] += total_time
                            endpoint_params[key]['total_self_time_ms'] += self_time
                            if is_error and error_message:
                                endpoint_params[key]['error_count'] += 1
                                endpoint_params[key]['error_messages'][error_message] += 1
                    
                    # Always track service-to-service calls
                    if self.config.include_service_mesh:
                        should_include_client = True
                    else:
                        # Filter out CLIENT→CLIENT chains (app → Envoy sidecar pattern)
                        should_include_client = (parent_kind != 'SPAN_KIND_CLIENT')
                    
                    if should_include_client:
                        target_service = self.http_extractor.extract_target_service_from_url(http_path)
                        key = (node['service_name'], target_service, http_method, 
                              normalized_path, param_str)
                        service_calls[key]['count'] += 1
                        service_calls[key]['total_time_ms'] += total_time
                        service_calls[key]['total_self_time_ms'] += self_time
                        if is_error and error_message:
                            service_calls[key]['error_count'] += 1
                            service_calls[key]['error_messages'][error_message] += 1
            else:
                op_type, msg_type, details = self.kafka_extractor.extract_kafka_info(span, attributes)
                if op_type in ['consumer', 'producer']:
                    key = (node['service_name'], op_type, msg_type, details)
                    kafka_messages[key]['count'] += 1
                    kafka_messages[key]['total_time_ms'] += total_time
                    if is_error and error_message:
                        kafka_messages[key]['error_count'] += 1
                        kafka_messages[key]['error_messages'][error_message] += 1
        
        return endpoint_params, service_calls, kafka_messages
