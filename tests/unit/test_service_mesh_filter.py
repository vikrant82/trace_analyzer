"""
Unit tests for trace_analyzer.filters.service_mesh_filter module.
"""
import pytest
from trace_analyzer.core.types import TraceConfig
from trace_analyzer.filters.service_mesh_filter import ServiceMeshFilter


def make_attributes(**kwargs):
    """Helper to create OpenTelemetry-format attributes."""
    return [{"key": k, "value": {"stringValue": v}} for k, v in kwargs.items()]


class TestServiceMeshFilter:
    """Tests for the ServiceMeshFilter class."""
    
    def test_should_include_server_span_mesh_disabled(self):
        """Test including server span when service mesh filtering is disabled."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        # Test SERVER span with SERVER parent (should be excluded - sidecar pattern)
        assert filter_obj.should_include_server_span('SPAN_KIND_SERVER', 'SPAN_KIND_SERVER') == False
        
        # Test SERVER span with CLIENT parent (should be included - normal call)
        assert filter_obj.should_include_server_span('SPAN_KIND_SERVER', 'SPAN_KIND_CLIENT') == True
        
        # Test SERVER span with no parent (should be included - root span)
        assert filter_obj.should_include_server_span('SPAN_KIND_SERVER', None) == True
    
    def test_should_include_server_span_mesh_enabled(self):
        """Test including server span when service mesh filtering is enabled."""
        config = TraceConfig(include_service_mesh=True)
        filter_obj = ServiceMeshFilter(config)
        
        # When mesh is enabled, all SERVER spans should be included
        assert filter_obj.should_include_server_span('SPAN_KIND_SERVER', 'SPAN_KIND_SERVER') == True
        assert filter_obj.should_include_server_span('SPAN_KIND_SERVER', 'SPAN_KIND_CLIENT') == True
        assert filter_obj.should_include_server_span('SPAN_KIND_SERVER', None) == True
    
    def test_should_include_regular_service(self):
        """Test filtering based on span kind, not service name."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        # Non-SERVER spans should return False
        assert filter_obj.should_include_server_span('SPAN_KIND_CLIENT', None) == False
        assert filter_obj.should_include_server_span('SPAN_KIND_INTERNAL', None) == False
    
    def test_should_include_client_span_envoy(self):
        """Test filtering CLIENT→CLIENT chain (sidecar pattern)."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        # CLIENT span with CLIENT parent should be excluded (app→sidecar pattern)
        assert filter_obj.should_include_client_span('SPAN_KIND_CLIENT', 'SPAN_KIND_CLIENT') == False
        
        # CLIENT span with SERVER parent should be included (normal outbound call)
        assert filter_obj.should_include_client_span('SPAN_KIND_CLIENT', 'SPAN_KIND_SERVER') == True
    
    def test_should_include_client_span_regular(self):
        """Test CLIENT span with mesh enabled includes all."""
        config = TraceConfig(include_service_mesh=True)
        filter_obj = ServiceMeshFilter(config)
        
        # All CLIENT spans included when mesh enabled
        assert filter_obj.should_include_client_span('SPAN_KIND_CLIENT', 'SPAN_KIND_CLIENT') == True
        assert filter_obj.should_include_client_span('SPAN_KIND_CLIENT', 'SPAN_KIND_SERVER') == True
    
    def test_detect_istio_services(self):
        """Test span kind filtering with gateway services config."""
        config = TraceConfig(include_service_mesh=False, include_gateway_services=False)
        filter_obj = ServiceMeshFilter(config)
        
        # Strictest mode: only CLIENT parent or root (None) allowed
        assert filter_obj.should_include_server_span('SPAN_KIND_SERVER', 'SPAN_KIND_CLIENT') == True
        assert filter_obj.should_include_server_span('SPAN_KIND_SERVER', None) == True
        assert filter_obj.should_include_server_span('SPAN_KIND_SERVER', 'SPAN_KIND_INTERNAL') == False
        assert filter_obj.should_include_server_span('SPAN_KIND_SERVER', 'SPAN_KIND_SERVER') == False
    
    def test_detect_envoy_sidecar(self):
        """Test non-CLIENT spans return False from should_include_client_span."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        # Non-CLIENT spans should return False
        assert filter_obj.should_include_client_span('SPAN_KIND_SERVER', None) == False
        assert filter_obj.should_include_client_span('SPAN_KIND_INTERNAL', None) == False
    
    def test_should_skip_node_mesh_service(self):
        """Test skipping nodes with same service name (sidecar duplicate)."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        parent_node = {"service_name": "user-service"}
        node = {"service_name": "user-service"}
        
        # Same service calling itself indicates sidecar duplicate
        assert filter_obj.should_skip_node(node, parent_node) == True
    
    def test_should_not_skip_regular_node(self):
        """Test not skipping regular service nodes."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        node = {
            "service": "user-service",
            "method": "GET",
            "path": "/api/users"
        }
        
        # Regular service nodes should not be skipped
        assert filter_obj.should_skip_node(node) == False
    
    def test_include_mesh_keeps_all_nodes(self):
        """Test that enabling mesh inclusion keeps all nodes."""
        config = TraceConfig(include_service_mesh=True)
        filter_obj = ServiceMeshFilter(config)
        
        mesh_node = {
            "service": "istio-proxy",
            "method": "GET",
            "path": "/api/users"
        }
        
        regular_node = {
            "service": "user-service",
            "method": "GET",
            "path": "/api/users"
        }
        
        assert filter_obj.should_skip_node(mesh_node) == False
        assert filter_obj.should_skip_node(regular_node) == False
    
    def test_empty_service_name(self):
        """Test should_skip_node with missing service names."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        parent_node = {}  # No service_name
        node = {"service_name": "user-service"}
        
        # Should not skip when parent has no service_name
        assert filter_obj.should_skip_node(node, parent_node) == False
