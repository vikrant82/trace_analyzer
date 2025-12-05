# Parallelism Detection Feature Specification

## User Story

**As a** developer analyzing distributed traces  
**I want to** see when service calls are executed in parallel  
**So that** I can understand the actual wall-clock time vs cumulative time and identify fan-out patterns

## Problem Statement

When displaying the Trace Hierarchy, the total time shown for a node is the cumulative sum of all child call durations. However, when calls are executed in parallel, the actual wall-clock time is much shorter. This creates confusion because:

1. A parent node might show 1000ms total time when its children sum to 1000ms
2. But if those children ran in parallel, the actual effective time might only be 200ms
3. Users have no visibility into parallelism patterns in their traces

## Solution Overview

Add parallelism detection and display to the Trace Hierarchy feature:

1. **Timestamps in hierarchy nodes**: Store `start_time_ns` and `end_time_ns` for each node
2. **Interval merging algorithm**: Calculate effective wall-clock time from overlapping spans
3. **Real vs inherited parallelism detection**: Distinguish actual fan-out from 1:1 call chains
4. **Visual indicators**: Show `⚡` on parallelized calls and `⊗` on parent nodes that initiate fan-out

---

## Implementation Tasks

### Task 1: Add Timestamps to Hierarchy Nodes

**File**: `trace_analyzer/processors/hierarchy_builder.py`

**Changes**:
- Extract `startTimeUnixNano` and `endTimeUnixNano` from each span
- Store as `start_time_ns` and `end_time_ns` in node dict
- Also add time bounds to root node (min/max of children)

**Code Location**: Lines 39-65 (in `build_raw_hierarchy`)

**Key Code**:
```python
start_time_ns = span.get('startTimeUnixNano', 0)
end_time_ns = span.get('endTimeUnixNano', 0)
duration_ms = (end_time_ns - start_time_ns) / 1_000_000.0

span_nodes[span_id] = {
    ...
    'start_time_ns': start_time_ns,
    'end_time_ns': end_time_ns,
    ...
}
```

---

### Task 2: Implement Interval Merging Algorithm

**File**: `trace_analyzer/processors/timing_calculator.py`

**New Static Methods**:

```python
@staticmethod
def merge_time_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    Merge overlapping time intervals to calculate actual wall-clock coverage.
    
    Algorithm:
    1. Filter out invalid intervals (where start >= end)
    2. Sort intervals by start time
    3. Iterate through sorted intervals, merging overlapping ones
    
    Args:
        intervals: List of (start_ns, end_ns) tuples
        
    Returns:
        List of merged non-overlapping intervals
    """
    if not intervals:
        return []
    
    valid = [(s, e) for s, e in intervals if s < e]
    if not valid:
        return []
    
    sorted_intervals = sorted(valid, key=lambda x: x[0])
    merged = [sorted_intervals[0]]
    
    for start, end in sorted_intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    
    return merged

@staticmethod
def calculate_wall_clock_ms(intervals: List[Tuple[int, int]]) -> float:
    """
    Calculate total wall-clock time from merged intervals.
    
    Args:
        intervals: List of (start_ns, end_ns) tuples
        
    Returns:
        Wall-clock time in milliseconds
    """
    merged = TimingCalculator.merge_time_intervals(intervals)
    total_ns = sum(end - start for start, end in merged)
    return total_ns / 1_000_000.0
```

---

### Task 3: Add Timestamps to Aggregated Nodes

**File**: `trace_analyzer/processors/aggregator.py`

**Changes**:
- When aggregating multiple nodes, calculate time bounds (min start, max end)
- Store `start_time_ns` and `end_time_ns` on aggregated node

**Code Location**: In `aggregate_list_of_nodes`, within the multi-node aggregation block

**Key Code**:
```python
# Calculate time bounds for aggregated node
start_times = [c.get('start_time_ns', 0) for c in group if c.get('start_time_ns')]
end_times = [c.get('end_time_ns', 0) for c in group if c.get('end_time_ns')]
agg_start = min(start_times) if start_times else 0
agg_end = max(end_times) if end_times else 0

agg_node = {
    ...
    'start_time_ns': agg_start,
    'end_time_ns': agg_end,
    ...
}
```

---

### Task 4: Implement Parallelism Detection in Normalizer

**File**: `trace_analyzer/processors/normalizer.py`

**Key Concept**: Real vs Inherited Parallelism

- **Real parallelism**: When `count > parent_count` - a fan-out occurred at this level
- **Inherited parallelism**: When `count == parent_count` - 1:1 mapping with parent (no new fan-out)
- **Root level**: First level children are always considered "real" since their parent is the root

**Changes to `aggregate_siblings` function**:

1. Add parameters: `parent_count=1`, `is_root_level=False`
2. When aggregating multiple nodes, calculate:
   - `is_real_parallelism = is_root_level or count > parent_count`
3. Only calculate and show parallelism when `is_real_parallelism` is True
4. When real parallelism > 1.05 is detected, mark `parent_node['has_parallel_children'] = True`

**Key Code Structure**:
```python
def aggregate_siblings(children, parent_node=None, parent_count=1, is_root_level=False):
    ...
    for group_children in groups.values():
        if len(group_children) > 1:
            count = len(group_children)
            
            # Recursively pass count for parallelism detection
            aggregated_grandchildren = aggregate_siblings(
                all_grandchildren, first, parent_count=count, is_root_level=False
            )
            
            # Calculate parallelism only for real fan-out
            is_real_parallelism = is_root_level or count > parent_count
            parallelism_factor = 1.0
            wall_clock_ms = None
            
            if is_real_parallelism:
                child_intervals = [...]
                if len(child_intervals) > 1:
                    wall_clock_ms = self.timing_calculator.calculate_wall_clock_ms(child_intervals)
                    if wall_clock_ms > 0:
                        parallelism_factor = round(total_time / wall_clock_ms, 2)
                        if parallelism_factor > 1.05:
                            parent_node['has_parallel_children'] = True
                        else:
                            parallelism_factor = 1.0
                            wall_clock_ms = None
            
            agg_node = {
                ...
                'parallelism_factor': parallelism_factor,
                'wall_clock_ms': wall_clock_ms,
            }
```

---

### Task 5: Update Template for Parallelism Display

**File**: `templates/results.html`

**Changes**:
- Add parallelism indicator (`⚡`) on aggregated child nodes
- Add parent badge (`⊗`) on nodes with parallel children

**Template Code** (inside `render_trace_node` macro):
```jinja2
{# Parallelism indicator on aggregated child nodes #}
{% if node.aggregated and node.parallelism_factor is defined and node.parallelism_factor > 1 and node.wall_clock_ms %}
<span class="metric parallelism-info" title="These {{ node.count }} calls ran in parallel: {{ '%.2f'|format(node.total_time_ms) }}ms cumulative / {{ '%.2f'|format(node.wall_clock_ms) }}ms effective">
    <strong>⚡ {{ "%.1f"|format(node.parallelism_factor) }}× parallel</strong>
    <span class="effective-time">({{ "%.2f"|format(node.wall_clock_ms) }}ms effective)</span>
</span>
{% endif %}

{# Parent badge for nodes with parallel children #}
{% if node.has_parallel_children %}
<span class="metric has-parallel-badge" title="This node has children running in parallel">
    ⊗
</span>
{% endif %}
```

---

### Task 6: Add CSS Styling

**File**: `static/style.css`

**New CSS Classes**:
```css
/* Parallelism indicator styling */
.metric.parallelism-info {
    background-color: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.3);
    color: #1e40af;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.85em;
}

.metric.parallelism-info strong {
    color: #1e40af;
}

.metric.parallelism-info .effective-time {
    color: #3b82f6;
    font-size: 0.9em;
    margin-left: 4px;
}

/* Parent node with parallel children indicator */
.metric.has-parallel-badge {
    background-color: rgba(139, 92, 246, 0.1);
    border: 1px solid rgba(139, 92, 246, 0.3);
    color: #6d28d9;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.9em;
    cursor: help;
}
```

---

### Task 7: HTTP Route Preference

**File**: `trace_analyzer/extractors/http_extractor.py`

**Change**: Prefer `http.route` (normalized template path like `/users/{id}`) over `http.target` (actual path like `/users/12345`)

**Why**: Enables aggregation of calls with different parameter values but same route template

**Key Code**:
```python
@staticmethod
def extract_http_path(attributes: List[Dict]) -> str:
    # First check for http.route (normalized template path)
    for attr in attributes:
        if attr.get('key') == 'http.route':
            value = attr.get('value', {})
            route = value.get('stringValue', '')
            if route:
                return route
    
    # Fall back to actual path attributes
    for attr in attributes:
        if attr.get('key') in ['http.url', 'http.target', 'http.path']:
            ...
```

---

### Task 8: Sample Trace Update

**File**: `sample-trace.json`

**Add**: New trace demonstrating parallel calls

**Structure**:
- `batch-service` receives `POST /api/batch/process`
- Fans out to 5 parallel `GET /items/{id}` calls to `data-service`
- Each call has `http.route` set to `/items/{id}` for aggregation
- Calls have overlapping timestamps to demonstrate parallelism

---

### Task 9: Unit Tests

**File**: `tests/unit/test_timing_calculator.py` (new file)

**Test Classes**:

1. `TestMergeTimeIntervals`
   - `test_non_overlapping_intervals`
   - `test_fully_overlapping_intervals`
   - `test_partially_overlapping_intervals`
   - `test_adjacent_intervals`
   - `test_empty_intervals`
   - `test_single_interval`
   - `test_unsorted_intervals`
   - `test_complex_parallel_scenario`

2. `TestCalculateWallClockMs`
   - `test_sequential_intervals`
   - `test_parallel_intervals`
   - `test_empty_intervals`
   - `test_single_interval`

3. `TestParallelismFactor`
   - `test_sequential_calls_no_parallelism`
   - `test_parallel_calls_high_parallelism`

**File**: `tests/unit/test_http_extractor.py` (update existing)

**New Tests**:
- `test_http_route_preferred_over_target`
- `test_http_route_preferred_over_url`
- `test_fallback_to_target_when_no_route`
- `test_empty_http_route_falls_back`

---

## Expected Display Behavior

### Example Trace Hierarchy

```
dx-case-service GET /api/cases/{id} ⊗    ← Parent shows ⊗ badge
  └─ data-service GET /items/{id}        ← Shows ⚡ indicator
       Count: 88
       Avg: 664.12 ms
       Total: 58442.69 ms (258.9%)
       Self: 641.59 ms (2.8%)
       ⚡ 2.8× parallel (21168.82ms effective)
       
       └─ rule-service POST /rules/{id}/execute  ← NO indicator (inherited)
            Count: 88
            ...
```

### Rules

1. `⚡ X.X× parallel` shows ONLY when:
   - Node is aggregated (`aggregated: true`)
   - `parallelism_factor > 1`
   - `wall_clock_ms` is calculated
   - Parallelism is "real" (count > parent_count)

2. `⊗` badge shows ONLY on:
   - The direct parent that introduces the fan-out
   - Set when we detect real parallelism in children

3. Inherited parallelism (1:1 mapping) shows NO indicator

---

## Integration Tests to Update

**File**: `tests/integration/test_analyzer_integration.py`

**Change**: Update references from `test-trace.json` to `sample-trace.json`

---

## Acceptance Criteria

1. ✅ Timestamps are preserved through hierarchy building and aggregation
2. ✅ Interval merging correctly calculates wall-clock time for overlapping spans
3. ✅ Parallelism factor is calculated only for real fan-out scenarios
4. ✅ `⚡` indicator appears on aggregated nodes with parallelism > 1
5. ✅ `⊗` badge appears only on direct parent of parallel children
6. ✅ Inherited parallelism (1:1 chains) shows no indicators
7. ✅ `http.route` is preferred for path extraction when available
8. ✅ Sample trace demonstrates parallelism feature
9. ✅ All existing tests pass
10. ✅ New unit tests cover interval merging and parallelism calculation
