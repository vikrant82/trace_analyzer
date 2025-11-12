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
        
        attributes = make_attributes(**{"service.name": "istio-ingressgateway"})
        
        # Should exclude mesh services when disabled
        assert filter_obj.should_include_server_span(attributes) == False
    
    def test_should_include_server_span_mesh_enabled(self):
        """Test including server span when service mesh filtering is enabled."""
        config = TraceConfig(include_service_mesh=True)
        filter_obj = ServiceMeshFilter(config)
        
        attributes = make_attributes(**{"service.name": "istio-ingressgateway"})
        
        # Should include mesh services when enabled
        assert filter_obj.should_include_server_span(attributes) == True
    
    def test_should_include_regular_service(self):
        """Test that regular services are always included."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        attributes = make_attributes(**{"service.name": "user-service"})
        
        # Regular services should always be included
        assert filter_obj.should_include_server_span(attributes) == True
    
    def test_should_include_client_span_envoy(self):
        """Test filtering Envoy sidecar CLIENT spans."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        attributes = make_attributes(**{"service.name": "envoy"})
        
        # Envoy client spans should be excluded when mesh filtering disabled
        assert filter_obj.should_include_client_span(attributes) == False
    
    def test_should_include_client_span_regular(self):
        """Test including regular CLIENT spans."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        attributes = make_attributes(**{"service.name": "user-service"})
        
        # Regular client spans should be included
        assert filter_obj.should_include_client_span(attributes) == True
    
    def test_detect_istio_services(self):
        """Test detecting various Istio service names."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        istio_services = [
            "istio-ingressgateway",
            "istio-egressgateway",
            "istio-proxy",
            "istiod"
        ]
        
        for service in istio_services:
            attributes = make_attributes(**{"service.name": service})
            assert filter_obj.should_include_server_span(attributes) == False
    
    def test_detect_envoy_sidecar(self):
        """Test detecting Envoy sidecar."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        attributes = make_attributes(**{"service.name": "envoy"})
        
        assert filter_obj.should_include_client_span(attributes) == False
    
    def test_should_skip_node_mesh_service(self):
        """Test skipping hierarchy nodes from mesh services."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        node = {
            "service": "istio-ingressgateway",
            "method": "GET",
            "path": "/api/users"
        }
        
        # Mesh service nodes should be skipped
        assert filter_obj.should_skip_node(node) == True
    
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
        """Test handling nodes with empty/missing service names."""
        config = TraceConfig(include_service_mesh=False)
        filter_obj = ServiceMeshFilter(config)
        
        attributes = make_attributes()  # Empty
        
        # Should handle gracefully
        result = filter_obj.should_include_server_span(attributes)
        assert isinstance(result, bool)
