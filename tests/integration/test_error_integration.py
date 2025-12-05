"""
Integration tests for error detection and visualization.

Tests the complete error handling workflow from trace file processing
through to hierarchy building and aggregation.
"""
import pytest
import json
from pathlib import Path
from trace_analyzer import TraceAnalyzer


class TestErrorIntegration:
    """Integration tests for error detection workflow."""
    
    def test_sample_trace_error_detection(self):
        """Test error detection with the enhanced sample-trace.json file."""
        sample_file = Path(__file__).parent.parent.parent / "sample-trace.json"
        
        if not sample_file.exists():
            pytest.skip("sample-trace.json not found")
        
        analyzer = TraceAnalyzer()
        analyzer.process_trace_file(str(sample_file))
        
        # Calculate total errors from all metric sources
        total_errors = (sum(e['error_count'] for e in analyzer.endpoint_params.values()) +
                       sum(e['error_count'] for e in analyzer.service_calls.values()) +
                       sum(e['error_count'] for e in analyzer.kafka_messages.values()))
        
        # Should detect errors from our enhanced sample trace
        assert total_errors > 0, "Should detect errors in sample trace"
        
        # Verify error details in endpoint_params (SERVER spans)
        error_endpoints = {k: v for k, v in analyzer.endpoint_params.items() if v['error_count'] > 0}
        assert len(error_endpoints) > 0, "Should have error endpoints"
        
        # Check that error messages are captured
        for endpoint_data in error_endpoints.values():
            assert 'error_messages' in endpoint_data
            assert len(endpoint_data['error_messages']) > 0
    
    # @pytest.mark.skip(reason="Test needs update for batches format - error detection already tested in test_sample_trace_error_detection")
    def test_error_trace_with_empty_messages(self):
        """Test handling of error traces with empty status messages."""
        # Create a minimal trace with error and empty message
        trace_data = {
            "batches": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "test-service"}}
                        ]
                    },
                    "instrumentationLibrarySpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "abc123abc123abc123abc123abc123ab",
                                    "spanId": "span1span1span1",
                                    "parentSpanId": "",
                                    "name": "GET /test",
                                    "kind": "SPAN_KIND_SERVER",
                                    "startTimeUnixNano": 1000000000,
                                    "endTimeUnixNano": 2000000000,
                                    "status": {
                                        "code": 2,
                                        "message": ""
                                    },
                                    "attributes": [
                                        {"key": "http.method", "value": {"stringValue": "GET"}},
                                        {"key": "http.target", "value": {"stringValue": "/test"}},
                                        {"key": "http.status_code", "value": {"intValue": 404}}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Write to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(trace_data, f)
            temp_file = f.name
        
        try:
            analyzer = TraceAnalyzer()
            analyzer.process_trace_file(temp_file)
            
            # Should detect error despite empty message
            total_errors = sum(e['error_count'] for e in analyzer.endpoint_params.values())
            assert total_errors > 0
            
            # Should have error messages captured
            error_endpoint = next((v for v in analyzer.endpoint_params.values() if v['error_count'] > 0), None)
            assert error_endpoint is not None
            assert 'error_messages' in error_endpoint
            assert len(error_endpoint['error_messages']) > 0
            
        finally:
            Path(temp_file).unlink()
    
    def test_mixed_success_and_error_traces(self):
        """Test processing file with both successful and error traces."""
        sample_file = Path(__file__).parent.parent.parent / "sample-trace.json"
        
        if not sample_file.exists():
            pytest.skip("sample-trace.json not found")
        
        analyzer = TraceAnalyzer()
        analyzer.process_trace_file(str(sample_file))
        
        # Should have both successful endpoints and error endpoints
        assert len(analyzer.endpoint_params) > 0, "Should have endpoint data"
        
        # Should have some errors
        total_errors = sum(e['error_count'] for e in analyzer.endpoint_params.values())
        assert total_errors > 0, "Should have errors"
    
    # @pytest.mark.skip(reason="Hierarchy access needs update - error visualization working as shown in UI tests")
    def test_error_hierarchy_visualization_data(self):
        """Test that hierarchy contains error visualization data."""
        sample_file = Path(__file__).parent.parent.parent / "sample-trace.json"
        
        if not sample_file.exists():
            pytest.skip("sample-trace.json not found")
        
        analyzer = TraceAnalyzer()
        analyzer.process_trace_file(str(sample_file))
        
        # Check traces for error information
        assert hasattr(analyzer, 'traces')
        assert len(analyzer.traces) > 0
        
        # Find a hierarchy with errors
        found_error_node = False
        
        def check_node_for_errors(node):
            """Recursively check nodes for error information."""
            nonlocal found_error_node
            
            if node.get('is_error', False):
                found_error_node = True
                # Verify error fields are present
                assert 'error_message' in node
                assert node['error_message'] is not None
                # May or may not have http_status_code
                return True
            
            # Check children
            for child in node.get('children', []):
                if check_node_for_errors(child):
                    return True
            
            return False
        
        # Check all trace hierarchies
        for trace_id, hierarchy in analyzer.trace_hierarchies.items():
            check_node_for_errors(hierarchy)
        
        # Should have found at least one error node in the enhanced sample trace
        assert found_error_node, "Should find error nodes in hierarchy"
    
    # @pytest.mark.skip(reason="Test needs update for batches format - aggregation tested via UI")
    def test_aggregated_error_nodes(self):
        """Test that aggregated nodes preserve error information."""
        # Create trace with multiple identical error calls
        trace_data = {
            "batches": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "api-service"}}
                        ]
                    },
                    "instrumentationLibrarySpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "trace1trace1trace1trace1trace1tr",
                                    "spanId": "rootrootrootroot",
                                    "parentSpanId": "",
                                    "name": "GET /api/users/{id}",
                                    "kind": "SPAN_KIND_SERVER",
                                    "startTimeUnixNano": 1000000000,
                                    "endTimeUnixNano": 1500000000,
                                    "attributes": [
                                        {"key": "http.method", "value": {"stringValue": "GET"}},
                                        {"key": "http.target", "value": {"stringValue": "/api/users/{id}"}}
                                    ]
                                },
                                {
                                    "traceId": "trace1trace1trace1trace1trace1tr",
                                    "spanId": "call1call1call1c",
                                    "parentSpanId": "rootrootrootroot",
                                    "name": "HTTP GET",
                                    "kind": "SPAN_KIND_CLIENT",
                                    "startTimeUnixNano": 1100000000,
                                    "endTimeUnixNano": 1200000000,
                                    "status": {"code": 2, "message": "Timeout"},
                                    "attributes": [
                                        {"key": "http.method", "value": {"stringValue": "GET"}},
                                        {"key": "http.url", "value": {"stringValue": "http://backend:8080/data/123"}},
                                        {"key": "http.status_code", "value": {"intValue": 504}}
                                    ]
                                },
                                {
                                    "traceId": "trace1trace1trace1trace1trace1tr",
                                    "spanId": "call2call2call2c",
                                    "parentSpanId": "rootrootrootroot",
                                    "name": "HTTP GET",
                                    "kind": "SPAN_KIND_CLIENT",
                                    "startTimeUnixNano": 1250000000,
                                    "endTimeUnixNano": 1350000000,
                                    "status": {"code": 2, "message": "Timeout"},
                                    "attributes": [
                                        {"key": "http.method", "value": {"stringValue": "GET"}},
                                        {"key": "http.url", "value": {"stringValue": "http://backend:8080/data/456"}},
                                        {"key": "http.status_code", "value": {"intValue": 504}}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(trace_data, f)
            temp_file = f.name
        
        try:
            analyzer = TraceAnalyzer()
            analyzer.process_trace_file(temp_file)
            
            # Find aggregated node in hierarchy
            hierarchy = list(analyzer.trace_hierarchies.values())[0]
            assert hierarchy is not None, "Should have hierarchy"
            
            def find_aggregated_error_node(node):
                """Find an aggregated node with errors."""
                if node.get('aggregated', False) and node.get('is_error', False):
                    return node
                
                for child in node.get('children', []):
                    result = find_aggregated_error_node(child)
                    if result:
                        return result
                
                return None
            
            agg_node = find_aggregated_error_node(hierarchy)
            
            if agg_node:
                # Verify aggregated error information
                assert agg_node['count'] > 1, "Should be aggregated"
                assert agg_node['is_error'] is True
                assert 'error_count' in agg_node
                assert agg_node['error_count'] > 0
                assert 'error_message' in agg_node
                
        finally:
            Path(temp_file).unlink()
    
    def test_error_count_in_results(self):
        """Test that error counts are correctly reported in results."""
        sample_file = Path(__file__).parent.parent.parent / "sample-trace.json"
        
        if not sample_file.exists():
            pytest.skip("sample-trace.json not found")
        
        analyzer = TraceAnalyzer()
        analyzer.process_trace_file(str(sample_file))
        
        # Count tota        cd /Users/chauv/launchpad/Trace_Analyser && python analyze_trace.py sample-trace-parallel.jsonl errors from all sources
        total_errors = (sum(e['error_count'] for e in analyzer.endpoint_params.values()) +
                       sum(e['error_count'] for e in analyzer.service_calls.values()) +
                       sum(e['error_count'] for e in analyzer.kafka_messages.values()))
        
        assert total_errors > 0, "Should have detected errors"
        
        # Verify error endpoints have proper error messages
        error_endpoints = [e for e in analyzer.endpoint_params.values() if e['error_count'] > 0]
        for endpoint_data in error_endpoints:
            assert 'error_messages' in endpoint_data
            assert len(endpoint_data['error_messages']) > 0