"""
Timing calculator for hierarchy nodes.
"""

from typing import Dict, List, Tuple


class TimingCalculator:
    """Calculates timing metrics for hierarchy nodes."""
    
    def __init__(self, aggregator):
        """
        Initialize with node aggregator.
        
        Args:
            aggregator: NodeAggregator instance
        """
        self.aggregator = aggregator
    
    @staticmethod
    def merge_time_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        Merge overlapping time intervals to calculate actual wall-clock coverage.
        
        Args:
            intervals: List of (start_ns, end_ns) tuples
            
        Returns:
            List of merged non-overlapping intervals
        """
        if not intervals:
            return []
        
        # Filter out invalid intervals and sort by start time
        valid = [(s, e) for s, e in intervals if s < e]
        if not valid:
            return []
        
        sorted_intervals = sorted(valid, key=lambda x: x[0])
        merged = [sorted_intervals[0]]
        
        for start, end in sorted_intervals[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                # Overlapping - extend the current interval
                merged[-1] = (last_start, max(last_end, end))
            else:
                # Non-overlapping - add new interval
                merged.append((start, end))
        
        return merged
    
    @staticmethod
    def calculate_wall_clock_ms(intervals: List[Tuple[int, int]]) -> float:
        """
        Calculate total wall-clock time from merged intervals.
        
        Args:
            intervals: List of (start_ns, end_ns) tuples
            
        Returns:
            Wall-clock time in milliseconds
        """
        merged = TimingCalculator.merge_time_intervals(intervals)
        total_ns = sum(end - start for start, end in merged)
        return total_ns / 1_000_000.0
    
    def calculate_hierarchy_timings(self, node: Dict) -> None:
        """
        Pass 3: Recursively traverse the hierarchy to aggregate children and calculate self-time.
        Also calculates wall-clock time and parallelism factor for children.
        This works bottom-up.
        
        Args:
            node: Hierarchy node dictionary (modified in-place)
        """
        if not node or not node.get('children'):
            return
        
        # 1. Recurse to the bottom of the tree for all children
        #    This ensures that everything below the current node is fully processed
        for child in node['children']:
            self.calculate_hierarchy_timings(child)
        
        # 2. Now that all children have been processed (including their own self-time
        #    and aggregation), aggregate the immediate children of the current node
        aggregated_children = self.aggregator.aggregate_list_of_nodes(node['children'])
        node['children'] = aggregated_children
        
        # 3. Extract child time intervals for wall-clock and self-time calculations
        child_intervals = [
            (child.get('start_time_ns'), child.get('end_time_ns'))
            for child in node['children']
            if child.get('start_time_ns') is not None 
            and child.get('end_time_ns') is not None
            and child.get('start_time_ns') < child.get('end_time_ns')
        ]
        
        # Calculate cumulative child time (sum of individual durations)
        child_total_time = sum(child['total_time_ms'] for child in node['children'])
        
        # 4. Calculate self-time using effective wall-clock time (handles parallelism)
        if child_intervals:
            # Use effective wall-clock time (merged intervals) to handle parallel children
            child_effective_time = self.calculate_wall_clock_ms(child_intervals)
            node['self_time_ms'] = max(0, node['total_time_ms'] - child_effective_time)
            
            # Store wall-clock metrics for parallelism detection
            node['children_wall_clock_ms'] = child_effective_time
            node['children_cumulative_ms'] = child_total_time
            
            # Calculate parallelism factor: cumulative / wall-clock
            # Factor > 1 indicates parallel execution
            if child_effective_time > 0:
                parallelism = child_total_time / child_effective_time
                node['parallelism_factor'] = round(parallelism, 2) if parallelism > 1.05 else 1.0
            else:
                node['parallelism_factor'] = 1.0
        else:
            # Fallback for nodes without timestamps: use cumulative sum
            node['self_time_ms'] = max(0, node['total_time_ms'] - child_total_time)
        
        # Note: has_parallel_children is now set by normalizer.mark_parallel_parents()
        # after the second aggregation pass, which properly detects real parallelism
    
    @staticmethod
    def recalculate_self_times(node: Dict) -> None:
        """
        Recursively recalculate self-times after hierarchy modifications.
        Uses effective wall-clock time to handle parallel children correctly.
        
        Args:
            node: Hierarchy node dictionary (modified in-place)
        """
        if not node:
            return
        
        # Recurse to children first (bottom-up)
        for child in node.get('children', []):
            TimingCalculator.recalculate_self_times(child)
        
        # Calculate self-time for this node
        children = node.get('children', [])
        if children:
            # Extract child intervals for effective time calculation
            child_intervals = [
                (c.get('start_time_ns'), c.get('end_time_ns'))
                for c in children
                if c.get('start_time_ns') is not None 
                and c.get('end_time_ns') is not None
                and c.get('start_time_ns') < c.get('end_time_ns')
            ]
            
            if child_intervals:
                # Use effective wall-clock time (handles parallelism)
                child_effective_time = TimingCalculator.calculate_wall_clock_ms(child_intervals)
                node['self_time_ms'] = max(0.0, node.get('total_time_ms', 0) - child_effective_time)
            else:
                # Fallback: use cumulative sum if timestamps missing
                child_total = sum(c.get('total_time_ms', 0) for c in children)
                node['self_time_ms'] = max(0.0, node.get('total_time_ms', 0) - child_total)
        else:
            # Leaf node: self-time equals total time
            node['self_time_ms'] = node.get('total_time_ms', 0)
