# Parallelism Detection - Technical Guide

## Overview
The parallelism detection feature identifies and visualizes when distributed trace spans execute concurrently, calculating effective wall-clock time vs cumulative time and displaying visual indicators.

---

## Core Algorithm: Interval Merging

### Purpose
Calculate actual wall-clock time from overlapping time spans, distinguishing cumulative time (sum of all children) from effective time (actual duration due to parallelism).

### Location
`trace_analyzer/processors/timing_calculator.py`

### Implementation

#### Method 1: `merge_time_intervals(intervals)`
**Signature:**
```python
@staticmethod
def merge_time_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]
```

**Algorithm:**
1. Filter out invalid intervals where `start >= end`
2. Sort intervals by start time (ascending)
3. Iterate through sorted intervals:
   - If current interval overlaps with last merged interval (`start <= last_end`):
     - **Merge:** Extend last interval to `max(last_end, current_end)`
   - Else:
     - **Append:** Add as new non-overlapping interval

**Example:**
```python
intervals = [(10, 110), (30, 110), (50, 110)]  # 3 overlapping spans
merged = merge_time_intervals(intervals)
# Result: [(10, 110)]  # Single merged interval
```

**Edge Cases:**
- Empty input → empty output
- All intervals identical → single merged interval
- No overlaps → all intervals preserved
- Nested intervals (e.g., `(10, 100)` within `(0, 150)`) → outer interval only

#### Method 2: `calculate_wall_clock_ms(intervals)`
**Signature:**
```python
@staticmethod
def calculate_wall_clock_ms(intervals: List[Tuple[int, int]]) -> float
```

**Algorithm:**
1. Call `merge_time_intervals()` to get non-overlapping intervals
2. Sum the duration of each merged interval: `sum(end - start)`
3. Convert nanoseconds to milliseconds: `total_ns / 1_000_000.0`

**Example:**
```python
intervals = [(10, 110), (30, 110), (50, 110)]  # Cumulative: 300ms
wall_clock = calculate_wall_clock_ms(intervals)
# Result: 100.0 ms (merged 10-110 ns → 100 ns → 0.1 ms... wait, example uses ms units!)
```

**Note:** Input intervals are expected in **nanoseconds** (from `startTimeUnixNano`/`endTimeUnixNano`), output is **milliseconds**.

---

## Parallelism Detection: Real vs Inherited

### Concept

**Problem:** Not all aggregated node groups represent true parallelism.

**Scenario 1 (Real Parallelism - Fan-out):**
```
serviceA (count=1) ⊗
  └─ serviceB (count=88) ⚡2.8×  ← Real parallelism: 88 calls from 1 parent
       └─ serviceC (count=88)   ← Inherited: 1:1 mapping with parent
```

**Scenario 2 (Inherited Parallelism - 1:1 Chain):**
```
serviceA (count=5)
  └─ serviceB (count=5)  ← No indicator: each serviceA call → 1 serviceB call
       └─ serviceC (count=5)  ← No indicator: linear chain, no fan-out
```

### Detection Logic

**Location:** `trace_analyzer/processors/normalizer.py` → `aggregate_siblings()` function

**Parameters:**
- `children`: List of nodes to aggregate
- `parent_node`: Parent node reference (for marking fan-out)
- `parent_count`: Aggregation count of parent (default: 1)
- `is_root_level`: If True, first-level children always considered real parallelism

**Formula:**
```python
is_real_parallelism = is_root_level or count > parent_count
```

**Rules:**
1. **Root level children:** Always real (no parent to compare against)
2. **Fan-out:** `count > parent_count` → parent initiated parallel calls
3. **Linear chain:** `count == parent_count` → 1:1 mapping, inherited count
4. **Impossible:** `count < parent_count` → should never occur (would indicate merging branches)

**Recursive Propagation:**
When aggregating children, pass `parent_count=count` to grandchildren:
```python
aggregated_grandchildren = aggregate_siblings(
    all_grandchildren,
    first,  # parent_node for sidecar filtering
    parent_count=count,  # Propagate current node's count
    is_root_level=False
)
```

---

## Parallelism Factor Calculation

### Conditions
Only calculate parallelism when **all** conditions are met:
1. `is_real_parallelism == True` (fan-out detected)
2. `count > 1` (multiple aggregated children)
3. At least 2 valid intervals with timestamps
4. `wall_clock_ms > 0` (merged intervals have duration)

### Formula
```python
parallelism_factor = round(total_time_ms / wall_clock_ms, 2)
```

**Interpretation:**
- `1.0×` → Sequential execution (no overlap)
- `2.4×` → Average 2.4 spans executing concurrently
- `88.0×` → High parallelism (e.g., 88 spans in same timeframe)

**Threshold:**
Only display when `parallelism_factor > 1.05` (filters out rounding noise from near-sequential execution).

### Example Calculation
```python
# 3 child spans:
# - Span 1: 10-110 ns (100 ns duration)
# - Span 2: 30-110 ns (80 ns duration)
# - Span 3: 50-110 ns (60 ns duration)

cumulative_time = 100 + 80 + 60 = 240 ms
wall_clock_time = 100 ms  # Merged interval: 10-110 ns
parallelism_factor = round(240 / 100, 2) = 2.4×
```

---

## Visual Indicators

### Parallelism Display: Effective vs Cumulative

**Display Location:** Aggregated child node (the fan-out target)

**Visual Update (January 2026):**
For parallel nodes, the display now uses Option B visual differentiation:
- **⚡ Effective:** Primary metric (green badge, highlighted) - actual wall-clock time
- **Cumulative:** Secondary metric (gray badge, dimmed) - sum of all call durations

**Template Code:** (`templates/results.html`)
```jinja2
{% if node.aggregated and node.parallelism_factor > 1 and node.wall_clock_ms %}
<span class="metric effective-time-primary">
    <strong>⚡ Effective:</strong> {{ node.wall_clock_ms }} ms ({{ effective_perc }}%)
</span>
<span class="metric cumulative-time-secondary">
    <strong>Cumulative:</strong> {{ node.total_time_ms }} ms (×{{ node.count }} calls, {{ node.parallelism_factor }}× parallel)
</span>
{% endif %}
```

**Tooltip:** Shows cumulative vs effective time comparison

**CSS Class:** `.metric.parallelism-info`

### Parent Badge: `⤵⤵`

**Display Location:** Parent node (the fan-out source)

**Note:** Changed from `⊗` to `⤵⤵` (branching arrows) for better visual intuitiveness.

**Setting Logic:**
```python
if parallelism_factor > 1.05:
    parent_node['has_parallel_children'] = True
```

**Template Code:**
```jinja2
{% if node.has_parallel_children %}
<span class="metric has-parallel-badge" title="This operation initiates fan-out - multiple parallel calls below">⊗</span>
{% endif %}
```

**CSS Class:** `.metric.has-parallel-badge`

**Critical:** Badge is set **inline** during aggregation, not via tree traversal. Only the **direct parent** of parallelized calls gets the badge.

---

## Self-Time Calculation with Parallelism

### Problem
Original implementation:
```python
self_time = max(0, total_time - sum(child.total_time for child in children))
```

**Issue:** When children execute in parallel, their cumulative sum exceeds parent's total time, resulting in `self_time = 0` (or negative, clamped to 0).

### Solution
Use effective wall-clock time instead of cumulative sum:

**Location:** `trace_analyzer/processors/timing_calculator.py` → `calculate_hierarchy_timings()`

**Implementation:**
```python
# Extract child intervals
child_intervals = [
    (c.get('start_time_ns'), c.get('end_time_ns'))
    for c in children
    if c.get('start_time_ns') is not None and c.get('end_time_ns') is not None
]

if child_intervals:
    # Use effective time (handles parallelism)
    child_effective_time = self.calculate_wall_clock_ms(child_intervals)
    node['self_time_ms'] = max(0, node['total_time_ms'] - child_effective_time)
else:
    # Fallback for nodes without timestamps (shouldn't happen in normal traces)
    child_total_time = sum(child['total_time_ms'] for child in children)
    node['self_time_ms'] = max(0, node['total_time_ms'] - child_total_time)
```

**Example:**
```
Parent: 150ms total
Children: 100ms, 80ms, 60ms (cumulative: 240ms, effective: 100ms)
Old calculation: max(0, 150 - 240) = 0ms ❌
New calculation: max(0, 150 - 100) = 50ms ✅
```

**Fallback:** Preserved for backward compatibility with traces missing timestamps (e.g., synthetic test data).

---

## Data Flow: Timestamps Through Pipeline

### Stage 1: Hierarchy Builder
**File:** `trace_analyzer/processors/hierarchy_builder.py`

**Extraction:**
```python
start_time_ns = span.get('startTimeUnixNano', 0)
end_time_ns = span.get('endTimeUnixNano', 0)

span_nodes[span_id] = {
    'start_time_ns': start_time_ns,
    'end_time_ns': end_time_ns,
    # ... other fields
}
```

**Root Node:** Calculate bounds as `min(start_times)` to `max(end_times)` of all descendants.

### Stage 2: Timing Calculator
**File:** `trace_analyzer/processors/timing_calculator.py`

**Usage:**
- Calculate parent self-time using `calculate_wall_clock_ms(child_intervals)`
- Preserve `start_time_ns` and `end_time_ns` in node dict (pass-through)

### Stage 3: Normalizer (Aggregation)
**File:** `trace_analyzer/processors/normalizer.py`

**Aggregated Node Timestamps:**
```python
start_times = [c.get('start_time_ns', 0) for c in group_children if c.get('start_time_ns')]
end_times = [c.get('end_time_ns', 0) for c in group_children if c.get('end_time_ns')]
agg_start = min(start_times) if start_times else 0
agg_end = max(end_times) if end_times else 0
```

**Parallelism Calculation:**
```python
child_intervals = [
    (c.get('start_time_ns', 0), c.get('end_time_ns', 0))
    for c in group_children
    if c.get('start_time_ns') is not None and c.get('end_time_ns') is not None
       and c.get('start_time_ns') < c.get('end_time_ns')
]
wall_clock_ms = self.timing_calculator.calculate_wall_clock_ms(child_intervals)
```

---

## Testing Approach

### Test Files
- **Unit tests:** `tests/unit/test_timing_calculator.py`
- **Sample traces:** `sample-trace-parallel.json`, `sample-trace-parallel-siblings.json`

### Test Scenarios

#### 1. Aggregated Parallelism (Fan-out)
**File:** `sample-trace-parallel.json`

**Structure:**
```
api-gateway GET /api/aggregate (0-150ms) ⊗
  └─ data-service GET /items/{id} (count=3) ⚡2.4×
       (3 parallel calls: 10-110ms, 30-110ms, 50-110ms)
```

**Validation:**
- Parent self-time: 50ms (150 - 100 effective)
- Aggregated child: parallelism_factor=2.4, wall_clock_ms=100
- Parent has `⊗` badge
- Child has `⚡` indicator

#### 2. Sibling Parallelism (Non-aggregated)
**File:** `sample-trace-parallel-siblings.json`

**Structure:**
```
api-gateway GET /api/composite (0-150ms) ⊗
  ├─ auth-service POST /validate (10-60ms)
  ├─ user-service GET /profile (20-80ms)
  └─ order-service GET /history (30-100ms)
```

**Validation:**
- Parent self-time: 60ms (150 - 90 effective)
- Parent has `⊗` badge
- Children appear separately (no aggregation)
- NO `⚡` indicators (no aggregated nodes)

#### 3. Unit Test: Parallel Children
**Class:** `TestSelfTimeWithParallelism`

**Test:** `test_self_time_with_parallel_children`
```python
# Parent: 0-150ms
# Child 1: 10-110ms
# Child 2: 30-110ms
# Child 3: 50-110ms
# Expected: self_time=50ms (150 - 100 effective)
```

**Test:** `test_self_time_without_parallel_execution`
```python
# Parent: 0-300ms
# Child 1: 0-100ms
# Child 2: 100-200ms
# Child 3: 200-300ms
# Expected: self_time=0ms (sequential, no overlap)
```

---

## Common Pitfalls & Solutions

### Pitfall 1: Inherited Parallelism Shows Indicators
**Symptom:** Every node in a deep chain shows `⚡` indicator.

**Cause:** Not tracking `parent_count` or always setting `is_root_level=True`.

**Solution:** Pass `parent_count=count` recursively and set `is_root_level=False` for non-root calls.

### Pitfall 2: Missing Timestamps
**Symptom:** Self-time calculation falls back to cumulative sum, shows 0ms for parallel parents.

**Cause:** Timestamps not extracted or not propagated through pipeline.

**Solution:** Verify `start_time_ns` and `end_time_ns` exist in node dict at every stage.

### Pitfall 3: Parent Badge on Wrong Node
**Symptom:** Grandparent shows `⊗` instead of direct parent.

**Cause:** Setting flag on wrong node reference or via tree traversal.

**Solution:** Only set `parent_node['has_parallel_children'] = True` when `parallelism_factor > 1.05` in `aggregate_siblings()`.

### Pitfall 4: Parallelism Factor = 1.0 Displayed
**Symptom:** UI shows `⚡ 1.0× parallel` (meaningless).

**Cause:** Not applying 1.05 threshold.

**Solution:** Set `parallelism_factor = 1.0` and `wall_clock_ms = None` when factor ≤ 1.05.

### Pitfall 5: Negative Self-Time (Debugging)
**Symptom:** Self-time shows as 0 but should be positive.

**Cause:** Using cumulative sum instead of effective time.

**Solution:** Check `calculate_hierarchy_timings()` uses `calculate_wall_clock_ms()` for child intervals.

---

## Sibling Parallelism Detection

### Status Update (January 2026)
**Sibling parallelism detection is now ROOT-LEVEL ONLY.**

The `∥` markers and sibling parallelism badges are only detected at the root level of the trace hierarchy. This prevents false positives from sequential parent calls where child timestamps overlap due to aggregation.

### Why This Change?
When sequential parent calls (e.g., 61 calls to `ViewLookupByReferenceKeys`) are aggregated, their children's timestamps span the entire time range of all 61 calls. This made it appear like children were running in parallel, even though within each parent call they ran sequentially.

### Current Behavior
- **Root level:** Sibling parallelism is detected and shown with `∥` markers
- **Nested levels:** No sibling parallelism detection (rely on `⚡` indicators instead)

### Code Location
`trace_analyzer/processors/normalizer.py` → `aggregate_siblings()` and `detect_sibling_parallelism()`

### Timeline Visualization

For sibling parallelism visualization, timeline bars show position and work density.

## Table-Level Effective Time Calculation

For summary tables (Services Overview, Incoming Requests, Service Calls, Kafka), effective time accounts for parallel execution using interval merging.

### Interval Merging Algorithm (`interval_merger.py`)

```python
def merge_intervals(intervals: List[Tuple[int, int]]) -> int:
    """
    1. Sort intervals by start time
    2. Merge overlapping intervals
    3. Sum durations of merged intervals
    """
```

### Data Flow

1. **metrics_populator.py**: Collects `(start_ns, end_ns)` intervals per grouping key
2. **analyzer.py**: Stores `effective_times` dict with categories: `endpoints`, `service_calls`, `kafka`, `services`
3. **result_builder.py**: Calculates parallelism factor = cumulative/effective, flags `has_parallelism` if >1.15

### Display Format

When `has_parallelism` is true:
- **Effective**: `⚡ 4.2s` (green badge) - actual wall-clock time
- **Cumulative**: `Σ 36.44s (8.7×)` (gray) - sum of all call durations