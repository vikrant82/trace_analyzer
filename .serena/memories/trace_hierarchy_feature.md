# Trace Hierarchy Feature - Technical Reference

## Overview
The Trace Hierarchy feature is the centerpiece of the visualization, providing an interactive tree view of distributed traces with accurate timing breakdowns and dynamic highlighting.

## Five-Pass Analysis Pipeline

### Pass 1 & 2: `_build_raw_hierarchy(spans)`
**Location**: `analyze_trace.py` line ~290
**Purpose**: Build initial tree structure from flat span lists

**Algorithm**:
1. Create node for each span with timing data
2. Identify primary `SPAN_KIND_SERVER` span per service (entry point)
3. Link children to parents via `parentSpanId`
4. **Orphan Adoption**: Attach orphaned spans (missing parent) to their service's SERVER span
5. Create artificial root node for multi-root traces

**Node Structure**:
```python
{
    'span': {...},              # Original span data
    'service_name': str,        # Extracted service name
    'children': [],             # Child nodes list
    'total_time_ms': float,     # Duration from nano timestamps
    'self_time_ms': float       # Initially = total_time
}
```

### Pass 3: `_calculate_hierarchy_timings(node)`
**Location**: `analyze_trace.py` line ~480
**Purpose**: Calculate accurate self-times recursively (bottom-up)

**Algorithm**:
1. Recurse to leaf nodes first
2. Aggregate sibling nodes with identical calls via `_aggregate_list_of_nodes()`
3. Calculate: `self_time = max(0, total_time - sum(children's total_time))`

**Key**: Self-time calculation uses aggregated children, not raw children

### Pass 4: `_populate_flat_metrics(span_nodes)`
**Location**: `analyze_trace.py` line ~340
**Purpose**: Populate flat summary tables

**Operations**:
- Read final timing values from hierarchy nodes
- Populate `endpoint_params` (incoming requests)
- Populate `service_calls` (service-to-service calls)
- Populate `kafka_messages` (messaging operations)
- Apply filtering based on:
  - `include_gateway_services`: Controls CLIENT-only services
  - `include_service_mesh`: Filters SERVER→SERVER and CLIENT→CLIENT chains

### Pass 5: `_normalize_and_aggregate_hierarchy(root_node)`
**Location**: `analyze_trace.py` line ~760
**Purpose**: Create clean display hierarchy

**Operations**:
1. **Normalize span names**: Extract HTTP method/path, normalize parameters
2. **Filter sidecar duplicates**: Remove same-service calls (Envoy/Istio)
3. **Aggregate siblings**: Group nodes with same (service, method, path, param)
4. **Recalculate self-times**: After tree modifications via `_recalculate_self_times()`

## Key Algorithms

### Orphan Adoption
**Problem**: Fragmented traces with missing parent spans
**Solution**: Attach orphans to their service's designated SERVER span

```python
if parent_span_id not in span_nodes:
    if service_name in service_server_spans:
        parent_id = service_server_spans[service_name]
        span_nodes[parent_id]['children'].append(node)
```

### Self-Time Calculation
**Formula**: `self_time = max(0, total_time - sum(children's total_time))`
**Timing**: Calculated recursively bottom-up after aggregation

### Sidecar Duplicate Filtering
**Pattern Detection**:
- Same service calling itself → sidecar duplicate
- Lift children to parent, skip duplicate node

```python
if node_service == parent_service:
    # Skip and lift children
    result.extend(filter_duplicates_and_lift(child.children, parent_node))
```

### Sibling Aggregation
**Grouping Key**: `(service_name, http_method, normalized_path, parameter_value)`
**Merge Operations**:
- Sum total_time and self_time
- Concatenate all grandchildren
- Calculate average: `avg_time = total_time / count`

## Frontend Integration

### Jinja2 Macro: `render_trace_node()`
**Location**: `templates/results.html` line ~10

**Parameters**:
- `node`: Current node to render
- `loop_index`: Position in list
- `total_trace_time`: Wall-clock duration of entire trace
- `parent_total_time`: Parent node's total time

**Calculations**:
- `total_perc = (node.total_time_ms / total_trace_time * 100)`
- `self_perc = (node.self_time_ms / total_trace_time * 100)`

**Data Attributes** (for JavaScript):
- `data-state`: "expanded" | "collapsed"
- `data-total-time`: Numeric milliseconds
- `data-trace-percent`: Percentage of total trace time

### JavaScript Features
**Location**: `templates/results.html` line ~390

**Expand/Collapse**:
- Click `.toggle` element
- Toggle `data-state` between "expanded" and "collapsed"
- Buttons: `.btn-expand-all`, `.btn-collapse-all`

**Dynamic Highlighting**:
- Slider: `#highlight-threshold` (range 5-95%, default 10%)
- Function: `updateHighlighting(threshold)`
- Logic: Add `.time-highlighted` class if `tracePercent >= threshold`

## Common Issues & Solutions

### Issue 1: Incorrect Self-Times
**Symptom**: Self-times don't add up correctly
**Cause**: Not recalculating after tree modifications
**Solution**: Call `_recalculate_self_times()` after any tree changes

### Issue 2: Missing Nodes
**Symptom**: Expected nodes don't appear in hierarchy
**Cause**: Over-aggressive sidecar filtering
**Solution**: Check `should_skip_node()` logic, verify service name matching

### Issue 3: Orphaned Spans Not Adopted
**Symptom**: Spans appear as separate roots instead of under service
**Cause**: Service's SERVER span not identified
**Solution**: Verify `service_server_spans` map is populated correctly

### Issue 4: Highlighting Not Working
**Symptom**: Slider moves but highlighting doesn't update
**Cause**: Missing `data-trace-percent` attribute
**Solution**: Verify macro calculates and sets attribute correctly

### Issue 5: Aggregation Not Grouping
**Symptom**: Identical calls show as separate nodes
**Cause**: Aggregation key mismatch
**Solution**: Verify normalization happens before aggregation, check key composition

## Parallelism Detection Feature

### Overview
The Trace Hierarchy now detects and displays parallel execution patterns, showing where fan-out occurs and the effective wall-clock time vs cumulative time.

### Key Components

**TimingCalculator (`timing_calculator.py`)**:
- `merge_time_intervals()`: Merges overlapping time intervals
- `calculate_wall_clock_ms()`: Calculates effective wall-clock duration from merged intervals

**HierarchyNormalizer (`normalizer.py`)**:
- Parallelism detection during sibling aggregation
- Uses `parent_count` parameter to distinguish real vs inherited parallelism:
  - **Real parallelism**: `count > parent_count` (fan-out occurred at this level)
  - **Inherited parallelism**: `count == parent_count` (1:1 mapping with parent)

### Display Logic

**Parallelism Indicator** (`⚡` on aggregated child nodes):
- Shows `parallelism_factor × parallel (wall_clock_ms effective)`
- Only displayed when `is_real_parallelism = True` AND `parallelism_factor > 1.05`

**Parent Badge** (`⤵⤵` on parent nodes):
- Marks the node that **introduces** the fan-out
- Set inline when real parallelism is detected (not via tree traversal)
- Only the direct parent of parallelized calls gets this badge

### Algorithm

1. During `aggregate_siblings()`, track `parent_count` (the aggregated count of the caller)
2. When aggregating children: `is_real_parallelism = is_root_level or count > parent_count`
3. If real parallelism detected and `parallelism_factor > 1.05`:
   - Set `parallelism_factor` and `wall_clock_ms` on the aggregated child node
   - Set `has_parallel_children = True` on the direct parent node

### CSS Classes
- `.metric.parallelism-info`: Styles the `⚡` indicator
- `.metric.has-parallel-badge`: Styles the `⤵⤵` badge
- `.effective-time-primary`: Green badge for effective (wall-clock) time
- `.cumulative-time-secondary`: Gray badge for cumulative time

### Sibling Parallelism (Updated January 2026)
Sibling parallelism detection (`∥` markers) is now **ROOT-LEVEL ONLY** to prevent false positives from sequential parent calls where aggregated child timestamps overlap.

### Example
```
serviceA (count=1) ⤵⤵         ← marked as fan-out source
  └─ serviceB (count=88) ⚡2.8× ← shows parallelism indicator
       └─serviceC (count=88) ← no indicator (inherited)
```

## Testing Scenarios

To verify hierarchy feature:

1. **Fragmented traces** - Test orphan adoption
2. **Service mesh enabled** - Test duplicate filtering
3. **Deep nesting** (10+ levels) - Test recursion
4. **Large aggregations** (100+ calls) - Test performance
5. **Multiple roots** - Test root selection
6. **Concurrent spans** - Test self-time accuracy
7. **Missing HTTP method** - Test defaults
