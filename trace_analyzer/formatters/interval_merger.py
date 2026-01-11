"""
Interval merging utility for calculating effective (wall-clock) time
from overlapping execution intervals.
"""
from typing import List, Tuple, Dict
from collections import defaultdict


def merge_intervals(intervals: List[Tuple[int, int]]) -> int:
    """
    Merge overlapping intervals and return total effective duration.
    
    This function takes a list of (start_ns, end_ns) tuples representing
    span execution intervals and merges overlapping ones to calculate
    the actual wall-clock time consumed.
    
    Example:
        Input: [(0, 100), (50, 150), (200, 300)]
        After merge: [(0, 150), (200, 300)]
        Effective: 150 + 100 = 250 nanoseconds
    
    Args:
        intervals: List of (start_ns, end_ns) tuples in nanoseconds
        
    Returns:
        Total effective duration in nanoseconds (merged, non-overlapping)
    """
    if not intervals:
        return 0
    
    # Filter out invalid intervals and sort by start time
    valid = [(s, e) for s, e in intervals if s > 0 and e > s]
    if not valid:
        return 0
    
    valid.sort(key=lambda x: x[0])
    
    # Merge overlapping intervals
    merged = [valid[0]]
    for start, end in valid[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            # Overlapping - extend the last interval
            merged[-1] = (last_start, max(last_end, end))
        else:
            # Non-overlapping - add new interval
            merged.append((start, end))
    
    # Sum durations of merged intervals
    total_ns = sum(end - start for start, end in merged)
    return total_ns


def calculate_effective_times(
    intervals_by_key: Dict[tuple, List[Tuple[int, int]]]
) -> Dict[tuple, float]:
    """
    Calculate effective time in milliseconds for each grouping key.
    
    Args:
        intervals_by_key: Dict mapping grouping key -> list of (start_ns, end_ns)
        
    Returns:
        Dict mapping grouping key -> effective_time_ms
    """
    result = {}
    for key, intervals in intervals_by_key.items():
        effective_ns = merge_intervals(intervals)
        result[key] = effective_ns / 1_000_000.0  # Convert ns to ms
    return result


def calculate_parallelism_factor(
    cumulative_ms: float, 
    effective_ms: float
) -> float:
    """
    Calculate the parallelism factor (how much parallelism was achieved).
    
    Args:
        cumulative_ms: Sum of all individual call durations
        effective_ms: Actual wall-clock time (merged intervals)
        
    Returns:
        Parallelism factor (>1 means parallel execution occurred)
    """
    if effective_ms <= 0:
        return 1.0
    return cumulative_ms / effective_ms
