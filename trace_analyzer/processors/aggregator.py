"""
Node aggregator for hierarchy siblings.
"""

from typing import List, Dict, Tuple
from collections import defaultdict


class NodeAggregator:
    """Aggregates sibling nodes with identical endpoints."""
    
    def __init__(self, http_extractor, path_normalizer):
        """
        Initialize with extractors.
        
        Args:
            http_extractor: HttpExtractor instance
            path_normalizer: PathNormalizer instance
        """
        self.http_extractor = http_extractor
        self.path_normalizer = path_normalizer
    
    def aggregate_list_of_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """
        Aggregates a list of nodes based on a composite key.
        This function is NOT recursive; it relies on the main recursive loop
        in _calculate_hierarchy_timings to have already processed child nodes.
        
        Args:
            nodes: List of sibling nodes to aggregate
            
        Returns:
            List of aggregated nodes
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
                http_path = self.http_extractor.extract_http_path(span.get('attributes', []))
                
                if http_path:
                    http_method = self.http_extractor.extract_http_method(span.get('attributes', []))
                    # Default to method from span name if missing
                    if not http_method:
                        span_name = span.get('name', '')
                        for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
                            if span_name.startswith(method + ' ') or span_name == method:
                                http_method = method
                                break
                        if not http_method:
                            http_method = 'POST'  # Default to POST instead of UNKNOWN
                    
                    normalized_path, _ = self.path_normalizer.normalize_path(http_path)
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
                
                # Calculate time bounds for aggregated node (min start, max end)
                start_times = [c.get('start_time_ns', 0) for c in group if c.get('start_time_ns')]
                end_times = [c.get('end_time_ns', 0) for c in group if c.get('end_time_ns')]
                agg_start = min(start_times) if start_times else 0
                agg_end = max(end_times) if end_times else 0
                
                # Grandchildren are simply concatenated. They have already been correctly
                # aggregated by the main recursive calls in _calculate_hierarchy_timings.
                all_grandchildren = [grandchild for child in group 
                                    for grandchild in child.get('children', [])]
                
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
                        # Keep attributes from the first span for the template to extract the HTTP method
                        'attributes': group[0]['span'].get('attributes', [])
                    },
                    'service_name': group[0]['service_name'],
                    'http_method': http_method,
                    'children': all_grandchildren,
                    'total_time_ms': total_time,
                    'self_time_ms': self_time,
                    'start_time_ns': agg_start,
                    'end_time_ns': agg_end,
                    'aggregated': True,
                    'count': sum(c.get('count', 1) for c in group),
                    'avg_time_ms': total_time / sum(c.get('count', 1) for c in group),
                }
                final_list.append(agg_node)
        
        return final_list
