"""
Time formatting utilities for human-readable output.
"""


def format_time(ms: float) -> str:
    """
    Format time in milliseconds to a human-readable string.
    
    Args:
        ms: Time in milliseconds
        
    Returns:
        Formatted time string (e.g., "123.45 ms", "2.34 s", "1m 30.50s")
    """
    if ms < 1000:
        return f"{ms:.2f} ms"
    elif ms < 60000:
        return f"{ms/1000:.2f} s"
    else:
        minutes = int(ms / 60000)
        seconds = (ms % 60000) / 1000
        return f"{minutes}m {seconds:.2f}s"
