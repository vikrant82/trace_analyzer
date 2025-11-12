"""
Service mesh filtering for trace spans.
"""

from typing import Dict, Optional


class ServiceMeshFilter:
    """Filters service mesh sidecar duplicate spans."""
    
    def __init__(self, config):
        """
        Initialize with trace configuration.
        
        Args:
            config: TraceConfig instance
        """
        self.config = config
    
    def should_include_server_span(self, span_kind: str, parent_kind: Optional[str]) -> bool:
        """
        Determine if a SERVER span should be included based on configuration.
        
        Args:
            span_kind: Kind of the current span
            parent_kind: Kind of the parent span (or None)
            
        Returns:
            True if span should be included
        """
        if span_kind != 'SPAN_KIND_SERVER':
            return False
        
        if self.config.include_service_mesh:
            # Include ALL SERVER spans when service mesh is enabled
            return True
        else:
            # Filter out SERVER→SERVER hops (Envoy sidecar → app pattern)
            # Include: CLIENT parent (normal call), None (root), INTERNAL (app logic)
            # Exclude: SERVER parent (sidecar duplicate)
            should_include = (parent_kind != 'SPAN_KIND_SERVER')
            
            # Further filter based on gateway_services setting
            if not self.config.include_gateway_services:
                # Strictest mode: Only CLIENT parent or root (no parent)
                should_include = (parent_kind == 'SPAN_KIND_CLIENT' or parent_kind is None)
            
            return should_include
    
    def should_include_client_span(self, span_kind: str, parent_kind: Optional[str]) -> bool:
        """
        Determine if a CLIENT span should be included based on configuration.
        
        Args:
            span_kind: Kind of the current span
            parent_kind: Kind of the parent span (or None)
            
        Returns:
            True if span should be included
        """
        if span_kind != 'SPAN_KIND_CLIENT':
            return False
        
        if self.config.include_service_mesh:
            # Include ALL CLIENT spans when service mesh is enabled
            return True
        else:
            # Filter out CLIENT→CLIENT chains (app → Envoy sidecar pattern)
            return (parent_kind != 'SPAN_KIND_CLIENT')
    
    def should_skip_node(self, node: Dict, parent_node: Optional[Dict] = None) -> bool:
        """
        Determine if a node is a service mesh sidecar duplicate that should be skipped.
        
        Args:
            node: Current hierarchy node
            parent_node: Parent hierarchy node (or None)
            
        Returns:
            True if the node should be skipped (and its children lifted to parent)
        """
        if self.config.include_service_mesh:
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
