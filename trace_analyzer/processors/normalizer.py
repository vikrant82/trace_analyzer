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
        
        def aggregate_siblings(children, parent_node=None, parent_count=1, is_root_level=False):
            """Aggregate sibling nodes with the same normalized endpoint.
            
            Args:
                children: List of child nodes to aggregate
                parent_node: Parent node (for sidecar filtering)
                parent_count: Count of parent's aggregation (for parallelism detection)
                is_root_level: If True, calculate parallelism for aggregated groups
            """
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
                    # Pass this node for filtering, count=1 for parallelism
                    node['children'] = aggregate_siblings(node.get('children', []), node, parent_count=1, is_root_level=False)
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
                    
                    # Collect all grandchildren
                    all_grandchildren = []
                    for c in group_children:
                        all_grandchildren.extend(c.get('children', []))
                    
                    # Recursively aggregate grandchildren
                    # Use first for filtering, count for parallelism detection
                    aggregated_grandchildren = aggregate_siblings(all_grandchildren, first, parent_count=count, is_root_level=False)
                    
                    # Calculate parallelism for ALL aggregated nodes (count > 1)
                    # This shows effective wall-clock time vs cumulative time for any parallel execution
                    # 
                    # "Real" parallelism (for ⤵⤵ badge on parent) is only when fan-out occurs:
                    # - count > parent_count: This node has MORE calls than its parent (fan-out)
                    # - is_root_level: Direct children of root
                    parallelism_factor = 1.0
                    wall_clock_ms = None
                    is_real_parallelism = is_root_level or count > parent_count
                    
                    # Always calculate wall_clock for aggregated nodes to show effective time
                    child_intervals = [
                        (c.get('start_time_ns', 0), c.get('end_time_ns', 0))
                        for c in group_children
                        if c.get('start_time_ns') is not None and c.get('end_time_ns') is not None
                           and c.get('start_time_ns') < c.get('end_time_ns')
                    ]
                    if len(child_intervals) > 1:
                        wall_clock_ms = self.timing_calculator.calculate_wall_clock_ms(child_intervals)
                        if wall_clock_ms > 0:
                            parallelism_factor = round(total_time / wall_clock_ms, 2)
                            if parallelism_factor <= 1.15:
                                parallelism_factor = 1.0
                                wall_clock_ms = None
                            elif is_real_parallelism:
                                # Mark the DIRECT parent as having parallel children
                                # Only for "real" fan-out (not inherited parallelism)
                                parent_node['has_parallel_children'] = True
                    
                    # Calculate time bounds for aggregated node (min start, max end)
                    start_times = [c.get('start_time_ns', 0) for c in group_children if c.get('start_time_ns')]
                    end_times = [c.get('end_time_ns', 0) for c in group_children if c.get('end_time_ns')]
                    agg_start = min(start_times) if start_times else 0
                    agg_end = max(end_times) if end_times else 0
                    
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
                        'start_time_ns': agg_start,
                        'end_time_ns': agg_end,
                        'parallelism_factor': parallelism_factor,
                        'wall_clock_ms': wall_clock_ms,
                    }
                    aggregated.append(agg_node)
            
            # Detect sibling parallelism when:
            # 1. At root level (direct children of trace root), OR
            # 2. Parent is NOT aggregated (count=1) - single parent with multiple different children
            # 
            # This avoids false positives from sequential aggregated calls (e.g., 61 calls to serviceA
            # each with one child call to serviceB - the 61 serviceB calls are NOT parallel siblings)
            if is_root_level or parent_count == 1:
                detect_sibling_parallelism(aggregated, parent_node)
            
            return aggregated
        
        def detect_sibling_parallelism(all_final_children: List[Dict], parent_node: Optional[Dict]) -> None:
            """
            Detect parallelism across siblings (different services running concurrently).
            This detects cross-service parallel calls (e.g., an API gateway calling auth,
            user, and order services concurrently).
            
            Called when:
            - Root level (direct children of trace root), OR
            - Parent is NOT aggregated (count=1)
            
            This avoids false positives from sequential aggregated calls where children's
            aggregated timestamps overlap due to parent aggregation.
            
            Sets attributes on parent_node and marks ONLY children that overlap with others.
            
            Args:
                all_final_children: List of final aggregated/non-aggregated sibling nodes
                parent_node: The parent node that initiated these parallel calls
            """
            if not parent_node or len(all_final_children) < 2:
                return
            
            # Collect valid intervals from ALL children with their indices
            children_with_intervals = []
            
            for i, child in enumerate(all_final_children):
                start_ns = child.get('start_time_ns')
                end_ns = child.get('end_time_ns')
                if start_ns and end_ns and start_ns < end_ns:
                    children_with_intervals.append((i, child, start_ns, end_ns))
            
            if len(children_with_intervals) < 2:
                return
            
            # Find which children actually overlap with at least one other child
            overlapping_indices = set()
            
            for i, (idx_a, child_a, start_a, end_a) in enumerate(children_with_intervals):
                for idx_b, child_b, start_b, end_b in children_with_intervals[i + 1:]:
                    # Check if intervals overlap: A.start < B.end AND B.start < A.end
                    if start_a < end_b and start_b < end_a:
                        overlapping_indices.add(idx_a)
                        overlapping_indices.add(idx_b)
            
            if len(overlapping_indices) < 2:
                return
            
            # Calculate metrics only for overlapping children
            overlapping_intervals = [
                (start_ns, end_ns) 
                for idx, child, start_ns, end_ns in children_with_intervals 
                if idx in overlapping_indices
            ]
            
            cumulative_ms = sum(
                (end - start) / 1_000_000.0 
                for start, end in overlapping_intervals
            )
            
            effective_ms = self.timing_calculator.calculate_wall_clock_ms(overlapping_intervals)
            
            if effective_ms <= 0:
                return
            
            factor = round(cumulative_ms / effective_ms, 2)
            
            # Only mark as sibling parallelism if meaningful (threshold: 1.15)
            if factor > 1.15:
                parent_node['sibling_parallelism'] = True
                parent_node['sibling_parallelism_factor'] = factor
                parent_node['sibling_effective_time_ms'] = effective_ms
                parent_node['sibling_cumulative_time_ms'] = cumulative_ms
                parent_node['parallel_sibling_count'] = len(overlapping_indices)
                parent_node['has_parallel_children'] = True
                
                # Mark ONLY children that actually overlap with others
                for idx, child, _, _ in children_with_intervals:
                    if idx in overlapping_indices:
                        child['is_parallel_sibling'] = True
        
        def calculate_timeline_positions(node: Dict) -> None:
            """
            Calculate relative timeline positions for children within parent's time window.
            This enables visual timeline bars showing where each child falls.
            
            Adds to each child:
            - timeline_start_pct: Start position as % of parent's effective time (0-100)
            - timeline_end_pct: End position as % of parent's effective time (0-100)
            """
            children = node.get('children', [])
            if not children:
                return
            
            # Get parent's time window
            parent_start = node.get('start_time_ns', 0)
            parent_end = node.get('end_time_ns', 0)
            parent_duration = parent_end - parent_start if parent_end > parent_start else 0
            
            if parent_duration <= 0:
                # Recurse anyway
                for child in children:
                    calculate_timeline_positions(child)
                return
            
            # Calculate relative positions for each child
            for child in children:
                child_start = child.get('start_time_ns', parent_start)
                child_end = child.get('end_time_ns', parent_end)
                
                # Clamp to parent's window
                child_start = max(child_start, parent_start)
                child_end = min(child_end, parent_end)
                
                # Calculate percentages
                start_pct = (child_start - parent_start) / parent_duration * 100
                end_pct = (child_end - parent_start) / parent_duration * 100
                
                child['timeline_start_pct'] = round(start_pct, 1)
                child['timeline_end_pct'] = round(end_pct, 1)
                child['timeline_width_pct'] = round(end_pct - start_pct, 1)
                
                # Recurse
                calculate_timeline_positions(child)
        
        # Normalize and process the root
        root_copy = root_node.copy()
        normalize_node(root_copy)
        # Process root's children with is_root_level=True and parent_count=1
        root_copy['children'] = aggregate_siblings(root_copy.get('children', []), root_copy, parent_count=1, is_root_level=True)
        root_copy['aggregated'] = False
        root_copy['count'] = 1
        
        # Note: has_parallel_children is now set inline within aggregate_siblings
        # when we detect real parallelism (count > parent_count and parallelism_factor > 1)
        
        # Recalculate self-times after filtering and lifting
        self.timing_calculator.recalculate_self_times(root_copy)
        
        # Calculate timeline positions for visualization
        calculate_timeline_positions(root_copy)
        
        return root_copy
