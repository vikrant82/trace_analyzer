"""
Pytest configuration and shared fixtures for trace analyzer tests.
"""
import json
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def sample_span():
    """Sample OpenTelemetry span for testing."""
    return {
        "traceId": "abc123",
        "spanId": "span1",
        "parentSpanId": None,
        "name": "GET /api/users",
        "kind": 2,  # SERVER
        "startTimeUnixNano": 1000000000,
        "endTimeUnixNano": 2000000000,
        "attributes": {
            "http.method": "GET",
            "http.target": "/api/users",
            "http.route": "/api/users",
            "service.name": "user-service"
        }
    }


@pytest.fixture
def sample_client_span():
    """Sample CLIENT span for testing."""
    return {
        "traceId": "abc123",
        "spanId": "span2",
        "parentSpanId": "span1",
        "name": "HTTP GET",
        "kind": 3,  # CLIENT
        "startTimeUnixNano": 1500000000,
        "endTimeUnixNano": 1800000000,
        "attributes": {
            "http.method": "GET",
            "http.url": "http://database-service:8080/api/data/123",
            "service.name": "user-service"
        }
    }


@pytest.fixture
def sample_kafka_span():
    """Sample Kafka span for testing."""
    return {
        "traceId": "abc123",
        "spanId": "span3",
        "parentSpanId": "span1",
        "name": "user-events send",
        "kind": 4,  # PRODUCER
        "startTimeUnixNano": 1600000000,
        "endTimeUnixNano": 1700000000,
        "attributes": {
            "messaging.system": "kafka",
            "messaging.operation": "send",
            "messaging.destination": "user-events",
            "service.name": "user-service"
        }
    }


@pytest.fixture
def sample_trace():
    """Sample complete trace with hierarchy."""
    return {
        "traceId": "trace-001",
        "spans": [
            {
                "traceId": "trace-001",
                "spanId": "root",
                "parentSpanId": None,
                "name": "GET /api/users",
                "kind": 2,  # SERVER
                "startTimeUnixNano": 1000000000,
                "endTimeUnixNano": 5000000000,
                "attributes": {
                    "http.method": "GET",
                    "http.target": "/api/users",
                    "service.name": "gateway"
                }
            },
            {
                "traceId": "trace-001",
                "spanId": "child1",
                "parentSpanId": "root",
                "name": "HTTP GET",
                "kind": 3,  # CLIENT
                "startTimeUnixNano": 1500000000,
                "endTimeUnixNano": 4000000000,
                "attributes": {
                    "http.method": "GET",
                    "http.url": "http://user-service:8080/users",
                    "service.name": "gateway"
                }
            },
            {
                "traceId": "trace-001",
                "spanId": "child2",
                "parentSpanId": "child1",
                "name": "GET /users",
                "kind": 2,  # SERVER
                "startTimeUnixNano": 2000000000,
                "endTimeUnixNano": 3500000000,
                "attributes": {
                    "http.method": "GET",
                    "http.target": "/users",
                    "service.name": "user-service"
                }
            }
        ]
    }


@pytest.fixture
def sample_trace_file(tmp_path):
    """Create a temporary trace JSON file for testing."""
    trace_data = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "abc123",
                                "spanId": "span1",
                                "parentSpanId": "",
                                "name": "GET /api/users",
                                "kind": 2,
                                "startTimeUnixNano": "1000000000",
                                "endTimeUnixNano": "2000000000",
                                "attributes": [
                                    {"key": "http.method", "value": {"stringValue": "GET"}},
                                    {"key": "http.target", "value": {"stringValue": "/api/users"}},
                                    {"key": "service.name", "value": {"stringValue": "user-service"}}
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }
    
    trace_file = tmp_path / "test_trace.json"
    with open(trace_file, "w") as f:
        json.dump(trace_data, f)
    
    return str(trace_file)


@pytest.fixture
def sample_hierarchy_node():
    """Sample hierarchy node for testing."""
    return {
        "service": "user-service",
        "method": "GET",
        "path": "/api/users",
        "count": 1,
        "avg_time": 1.0,
        "total_time": 1.0,
        "self_time": 0.5,
        "children": []
    }


@pytest.fixture
def sample_endpoint_stats():
    """Sample endpoint statistics for testing."""
    return {
        "service": "user-service",
        "method": "GET",
        "path": "/api/users",
        "count": 5,
        "avg_time": 100.5,
        "min_time": 50.0,
        "max_time": 150.0,
        "error_count": 0
    }


@pytest.fixture
def sample_service_mesh_span():
    """Sample Istio/Envoy service mesh span."""
    return {
        "traceId": "mesh123",
        "spanId": "envoy1",
        "parentSpanId": None,
        "name": "ingress",
        "kind": 2,
        "startTimeUnixNano": 1000000000,
        "endTimeUnixNano": 2000000000,
        "attributes": {
            "service.name": "istio-ingressgateway",
            "http.method": "GET",
            "http.target": "/api/users"
        }
    }


@pytest.fixture
def temp_json_file(tmp_path):
    """Create a temporary JSON file and return a helper function."""
    def _create_file(data):
        file_path = tmp_path / f"test_{id(data)}.json"
        with open(file_path, "w") as f:
            json.dump(data, f)
        return str(file_path)
    
    return _create_file
