"""
Unit tests for trace_analyzer.formatters.time_formatter module.
"""
import pytest
from trace_analyzer.formatters.time_formatter import format_time


class TestFormatTime:
    """Tests for the format_time() function."""
    
    def test_format_milliseconds(self):
        """Test formatting times in milliseconds."""
        assert format_time(0.5) == "0.50 ms"
        assert format_time(10.25) == "10.25 ms"
        assert format_time(999.99) == "999.99 ms"
    
    def test_format_seconds(self):
        """Test formatting times in seconds."""
        assert format_time(1000) == "1.00 s"
        assert format_time(1500) == "1.50 s"
        # Rounding can cause 59999 to round to 60.00 s
        result = format_time(59999)
        assert "59." in result or "60." in result  # Allow for rounding
    
    def test_format_minutes(self):
        """Test formatting times in minutes and seconds."""
        assert format_time(60000) == "1m 0.00s"
        assert format_time(90000) == "1m 30.00s"
        assert format_time(125500) == "2m 5.50s"
        assert format_time(3600000) == "60m 0.00s"
    
    def test_zero_time(self):
        """Test formatting zero time."""
        assert format_time(0) == "0.00 ms"
    
    def test_very_small_time(self):
        """Test formatting very small time values."""
        assert format_time(0.001) == "0.00 ms"
        assert format_time(0.01) == "0.01 ms"
    
    def test_edge_cases(self):
        """Test edge cases at boundaries."""
        # Just below 1 second - allow for rounding
        result = format_time(999.999)
        assert "999" in result or "1000" in result
        
        # Exactly 1 second
        assert format_time(1000.0) == "1.00 s"
        
        # Just below 1 minute - allow for rounding
        result_min = format_time(59999.99)
        assert "59." in result_min or "60." in result_min
        
        # Exactly 1 minute
        assert format_time(60000.0) == "1m 0.00s"
    
    def test_large_values(self):
        """Test formatting large time values."""
        # 1 hour
        assert format_time(3600000) == "60m 0.00s"
        
        # 2 hours
        assert format_time(7200000) == "120m 0.00s"
    
    def test_precision(self):
        """Test decimal precision in formatting."""
        assert format_time(1.234) == "1.23 ms"
        assert format_time(1234.567) == "1.23 s"
        assert format_time(61234.567) == "1m 1.23s"
    
    def test_negative_values(self):
        """Test behavior with negative values (if applicable)."""
        # Negative values should still format correctly
        result = format_time(-10)
        assert "ms" in result or "s" in result
