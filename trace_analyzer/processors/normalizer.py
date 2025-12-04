"""
Hierarchy normalizer for display aggregation.
"""

from typing import Dict, List, Optional


class HierarchyNormalizer:
    """Normalizes and aggregates hierarchy for clean display."""
    
    def __init__(self, config, http_extractor, path_normalizer, timing_calculator):
        """
        Initialize with configuration and utilities.
        
        Args:
            config: TraceConfig instance
            http_extractor: HttpExtractor instance
            path_normalizer: PathNormalizer instance
            timing_calculator: TimingCalculator instance
        """
        self.config = config
        self.http_extractor = http_extractor
        self.path_normalizer = path_normalizer
        self.timing_calculator = timing_calculator
    
    def _calculate_effective_time(self, nodes: List[Dict]) -> float:
        """
        Calculate effective wall-clock time by merging overlapping intervals.
        """
        intervals = []
        for node in nodes:
            start = node.get('start_time_ns')
            end = node.get('end_time_ns')
            if start is not None and end is not None and end > start:
                intervals.append((start, end))
        
        if not intervals:
            return 0.0
            
        # Sort by start time
        intervals.sort(key=lambda x: x[0])
        
        merged = []
        if intervals:
            curr_start, curr_end = intervals[0]
            for next_start, next_end in intervals[1:]:
                if next_start < curr_end:
                    curr_end = max(curr_end, next_end)
                else:
                    merged.append((curr_start, curr_end))
                    curr_start, curr_end = next_start, next_end
            merged.append((curr_start, curr_end))
            
        total_ns = sum(end - start for start, end in merged)
        return total_ns / 1_000_000.0

    def normalize_and_aggregate_hierarchy(self, root_node: Dict) -> Optional[Dict]:
        """
        Recursively normalize span names and aggregate sibling nodes that have
        the same normalized endpoint. This keeps the correct parent-child relationships
        from the raw hierarchy while providing clean, aggregated display.
        
        Also filters out service mesh sidecar duplicates when include_service_mesh is False.
        
        Args:
            root_node: Root of the hierarchy tree
            
        Returns:
            Normalized and aggregated root node
        """
        if not root_node:
            return None
        
        def normalize_node(node):
            """Normalize a single node's display name."""
            span = node['span']
            attributes = span.get('attributes', [])
            
            # Extract HTTP information
            http_path = self.http_extractor.extract_http_path(attributes)
            if http_path:
                http_method = self.http_extractor.extract_http_method(attributes)
                if not http_method:
                    # Try to extract from span name
                    span_name = span.get('name', '')
                    if span_name.startswith(('GET ', 'POST ', 'PUT ', 'DELETE ', 'PATCH ')):
                        http_method = span_name.split()[0]
                    else:
                        http_method = 'POST'  # Default
                
                normalized_path, param_values = self.path_normalizer.normalize_path(
                    http_path,
                    self.config.strip_query_params
                )
                
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
            
            IMPORTANT: Never skip error spans - we want to preserve error information
            in the hierarchy for visibility.
            """
            if self.config.include_service_mesh:
                return False  # Don't skip anything when mesh spans are included
            
            # Never skip error spans - preserve them for visibility
            if node.get('is_error', False):
                return False
            
            # Check for same-service duplicates (service calling itself)
            if parent_node:
                parent_service = parent_node.get('service_name', '')
                node_service = node.get('service_name', '')
                
                # Skip if same service (sidecar duplicate)
                if node_service and parent_service and node_service == parent_service:
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
                    # Ensure error information is preserved for single nodes
                    if 'is_error' not in node:
                        node['is_error'] = False
                        node['error_message'] = None
                        node['http_status_code'] = None
                    aggregated.append(node)
                else:
                    # Multiple nodes - aggregate them
                    first = group_children[0]
                    total_time = sum(c.get('total_time_ms', 0) for c in group_children)
                    self_time = sum(c.get('self_time_ms', 0) for c in group_children)
                    count = len(group_children)
                    
                    # Calculate effective time and parallelism
                    effective_time = self._calculate_effective_time(group_children)
                    parallelism_factor = 1.0
                    if effective_time > 0:
                        parallelism_factor = total_time / effective_time
                    
                    # Calculate min start and max end for the aggregated node
                    valid_starts = [c.get('start_time_ns') for c in group_children if c.get('start_time_ns')]
                    valid_ends = [c.get('end_time_ns') for c in group_children if c.get('end_time_ns')]
                    start_time_ns = min(valid_starts) if valid_starts else 0
                    end_time_ns = max(valid_ends) if valid_ends else 0
                    
                    # Collect all grandchildren
                    all_grandchildren = []
                    for c in group_children:
                        all_grandchildren.extend(c.get('children', []))
                    
                    # Recursively aggregate grandchildren (pass first as parent node)
                    aggregated_grandchildren = aggregate_siblings(all_grandchildren, first)
                    
                    # Aggregate error information: if ANY child has an error, mark the aggregated node as error
                    any_errors = any(c.get('is_error', False) for c in group_children)
                    error_count = sum(1 for c in group_children if c.get('is_error', False))
                    
                    # Collect all unique error messages
                    error_messages = set()
                    http_status_codes = set()
                    for c in group_children:
                        if c.get('is_error', False):
                            if c.get('error_message'):
                                error_messages.add(c.get('error_message'))
                            if c.get('http_status_code'):
                                http_status_codes.add(c.get('http_status_code'))
                    
                    # Format error message for aggregated node
                    if any_errors:
                        if len(error_messages) == 1:
                            agg_error_message = list(error_messages)[0]
                        else:
                            agg_error_message = f"Multiple errors ({error_count}/{count})"
                        
                        # Use most common HTTP status code or first one
                        agg_http_status = list(http_status_codes)[0] if http_status_codes else None
                    else:
                        agg_error_message = None
                        agg_http_status = None
                    
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
                        'avg_time_ms': total_time / count if count > 0 else 0,
                        'is_error': any_errors,
                        'error_message': agg_error_message,
                        'http_status_code': agg_http_status,
                        'error_count': error_count,
                        'parallelism_factor': parallelism_factor,
                        'effective_time_ms': effective_time,
                        'start_time_ns': start_time_ns,
                        'end_time_ns': end_time_ns
                    }
                    aggregated.append(agg_node)
            
            return aggregated
        
        # Normalize and process the root
        root_copy = root_node.copy()
        normalize_node(root_copy)
        root_copy['children'] = aggregate_siblings(root_copy.get('children', []), root_copy)
        root_copy['aggregated'] = False
        root_copy['count'] = 1
        
        # Recalculate self-times after filtering and lifting
        self.timing_calculator.recalculate_self_times(root_copy)
        
        return root_copy
