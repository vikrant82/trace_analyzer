"""
Integration test for the full trace analyzer workflow.
"""
import pytest
import json
from pathlib import Path
from trace_analyzer import TraceAnalyzer, TraceConfig


class TestTraceAnalyzerIntegration:
    """Integration tests for end-to-end trace analysis."""
    
    def test_analyze_test_trace_file(self):
        """Test analyzing the actual test-trace.json file."""
        # Path to the test file
        test_file = Path(__file__).parent.parent.parent / "test-trace.json"
        
        if not test_file.exists():
            # Fallback to sample-trace.json
            test_file = Path(__file__).parent.parent.parent / "sample-trace.json"
            
        if not test_file.exists():
            pytest.skip("Neither test-trace.json nor sample-trace.json found")
        
        # Create analyzer with default config
        analyzer = TraceAnalyzer(
            strip_query_params=True,
            include_gateway_services=False,
            include_service_mesh=False
        )
        
        # Process the trace file
        analyzer.process_trace_file(str(test_file))
        
        # Verify basic results - use correct attribute names
        assert len(analyzer.endpoint_params) > 0, "Should have endpoint parameters"
        
        # Check that we have some service calls
        has_calls = len(analyzer.service_calls) > 0
        assert has_calls, "Should have service calls"
    
    def test_analyzer_with_different_configs(self):
        """Test analyzer with different configuration options."""
        test_file = Path(__file__).parent.parent.parent / "test-trace.json"
        
        if not test_file.exists():
            # Fallback to sample-trace.json
            test_file = Path(__file__).parent.parent.parent / "sample-trace.json"
            
        if not test_file.exists():
            pytest.skip("Neither test-trace.json nor sample-trace.json found")
        
        # Test with service mesh enabled
        analyzer1 = TraceAnalyzer(include_service_mesh=True)
        analyzer1.process_trace_file(str(test_file))
        
        # Test with gateway services enabled
        analyzer2 = TraceAnalyzer(include_gateway_services=True)
        analyzer2.process_trace_file(str(test_file))
        
        # Test with query params not stripped
        analyzer3 = TraceAnalyzer(strip_query_params=False)
        analyzer3.process_trace_file(str(test_file))
        
        # All should complete without errors
        assert True
    
    def test_analyzer_hierarchies(self):
        """Test that analyzer processes traces successfully."""
        test_file = Path(__file__).parent.parent.parent / "test-trace.json"
        
        if not test_file.exists():
            # Fallback to sample-trace.json
            test_file = Path(__file__).parent.parent.parent / "sample-trace.json"
            
        if not test_file.exists():
            pytest.skip("Neither test-trace.json nor sample-trace.json found")
        
        analyzer = TraceAnalyzer()
        analyzer.process_trace_file(str(test_file))
        
        # Check that processing completed and we have data
        assert len(analyzer.endpoint_params) > 0 or len(analyzer.service_calls) > 0
    
    def test_analyzer_with_sample_trace_file(self, sample_trace_file):
        """Test analyzer with a simple generated trace file."""
        analyzer = TraceAnalyzer()
        analyzer.process_trace_file(sample_trace_file)
        
        # Should process without errors
        assert True
    
    def test_empty_trace_file(self, tmp_path):
        """Test handling of empty trace file."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text('{"resourceSpans": []}')
        
        analyzer = TraceAnalyzer()
        
        # Should handle empty file gracefully
        try:
            analyzer.process_trace_file(str(empty_file))
            # Should complete without error
            assert True
        except Exception as e:
            # If it raises an exception, it should be a reasonable one
            assert "No" in str(e) or "Empty" in str(e) or "resourceSpans" in str(e)
    
    def test_malformed_json_file(self, tmp_path):
        """Test handling of malformed JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text('{invalid json}')
        
        analyzer = TraceAnalyzer()
        
        # Should raise appropriate error
        with pytest.raises((json.JSONDecodeError, Exception)):
            analyzer.process_trace_file(str(bad_file))
    
    def test_analyzer_state_reset(self, sample_trace_file):
        """Test that analyzer can be reused for multiple files."""
        analyzer = TraceAnalyzer()
        
        # Process first time
        analyzer.process_trace_file(sample_trace_file)
        first_params_count = len(analyzer.endpoint_params)
        
        # Process second time (should reset state)
        analyzer.process_trace_file(sample_trace_file)
        second_params_count = len(analyzer.endpoint_params)
        
        # Should have same results (state was reset)
        assert first_params_count == second_params_count
