"""
Timing calculator for hierarchy nodes.
"""

from typing import Dict


class TimingCalculator:
    """Calculates timing metrics for hierarchy nodes."""
    
    def __init__(self, aggregator):
        """
        Initialize with node aggregator.
        
        Args:
            aggregator: NodeAggregator instance
        """
        self.aggregator = aggregator
    
    def calculate_hierarchy_timings(self, node: Dict) -> None:
        """
        Pass 3: Recursively traverse the hierarchy to aggregate children and calculate self-time.
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
        
        # 3. Finally, calculate the self-time of the current node by subtracting the
        #    total time of its now-aggregated children
        child_total_time = sum(child['total_time_ms'] for child in node['children'])
        node['self_time_ms'] = max(0, node['total_time_ms'] - child_total_time)
    
    @staticmethod
    def recalculate_self_times(node: Dict) -> None:
        """
        Recursively recalculate self-times after hierarchy modifications.
        Self-time = total_time - sum(children's total_time)
        
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
            child_total = sum(c.get('total_time_ms', 0) for c in children)
            node['self_time_ms'] = max(0.0, node.get('total_time_ms', 0) - child_total)
        else:
            # Leaf node: self-time equals total time
            node['self_time_ms'] = node.get('total_time_ms', 0)
