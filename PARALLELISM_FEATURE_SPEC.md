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

### Task 8: Sample Trace Update

**File**: `sample-trace.json`

**Add**: New trace demonstrating parallel calls

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
