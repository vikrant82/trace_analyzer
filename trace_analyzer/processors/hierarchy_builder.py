"""
Hierarchy builder for trace spans.
"""

from typing import Dict, List, Tuple


class HierarchyBuilder:
    """Builds tree structure from flat list of spans."""
    
    def __init__(self, http_extractor):
        """
        Initialize with HTTP extractor for service name extraction.
        
        Args:
            http_extractor: HttpExtractor instance
        """
        self.http_extractor = http_extractor
    
    def build_raw_hierarchy(self, spans: List[Dict]) -> Tuple[Dict, Dict]:
        """
        Build a raw tree structure from a flat list of spans, intelligently
        re-parenting orphaned spans to their logical service entry points.
        
        Args:
            spans: List of span dictionaries
            
        Returns:
            Tuple of (root_node, span_nodes_dict)
            - root_node: Root of the hierarchy tree
            - span_nodes_dict: Flat mapping of span_id -> node for lookups
        """
        span_nodes = {}
        service_server_spans = {}
        
        # First pass: create nodes and identify the primary SERVER span for each service
        for span in spans:
            span_id = span.get('spanId')
            if not span_id:
                continue
            
            duration_ms = (span.get('endTimeUnixNano', 0) - 
                          span.get('startTimeUnixNano', 0)) / 1_000_000.0
            service_name = self.http_extractor.extract_service_name(
                span.get('resource', {}).get('attributes', [])
            )
            
            span_nodes[span_id] = {
                'span': span,
                'service_name': service_name,
                'children': [],
                'total_time_ms': duration_ms,
                'self_time_ms': duration_ms,
            }
            
            if (span.get('kind') == 'SPAN_KIND_SERVER' and 
                    service_name not in service_server_spans):
                service_server_spans[service_name] = span_id
        
        # Second pass: link children, adopting orphans to their service's SERVER span
        root_spans = []
        for span_id, node in span_nodes.items():
            parent_span_id = node['span'].get('parentSpanId')
            
            if parent_span_id and parent_span_id in span_nodes:
                # Normal case: parent exists
                span_nodes[parent_span_id]['children'].append(node)
            elif (node['service_name'] in service_server_spans and 
                  span_id != service_server_spans[node['service_name']]):
                # Orphan: adopt it to the service's SERVER span
                parent_id = service_server_spans[node['service_name']]
                span_nodes[parent_id]['children'].append(node)
            else:
                # True root span
                root_spans.append(node)
        
        # Create artificial root if multiple root spans exist
        root = {
            'span': {'name': 'Trace Root'},
            'service_name': 'Trace',
            'children': root_spans,
            'total_time_ms': sum(s['total_time_ms'] for s in root_spans),
            'self_time_ms': 0
        }
        
        return root, span_nodes
