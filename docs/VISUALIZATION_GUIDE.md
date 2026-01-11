# Trace Visualization Guide

**Last Updated:** January 7, 2026

This guide explains all visual elements in the Trace Analyzer's interactive trace hierarchy.

---

## Table of Contents

- [Overview](#overview)
- [Performance Highlighting](#performance-highlighting)
- [Parallelism Indicators](#parallelism-indicators)
- [Error Indicators](#error-indicators)
- [Metrics Display](#metrics-display)
- [Interactive Controls](#interactive-controls)

---

## Overview

The Trace Analyzer displays a hierarchical tree view of your trace spans with multiple visual indicators to help identify:

1. **Performance bottlenecks** (where time is spent)
2. **Parallel execution** (concurrent operations)
3. **Errors** (failed operations)

---

## Performance Highlighting

### The Dual-Highlighting System

A span can be "slow" for two reasons:
1. **Waiting for children** - The span does little work, but children take long
2. **Doing the work** - The span itself consumes time

We use two distinct highlighting styles:

### 🔴 Bottleneck (High Self-Time)

**Visual:** Red border + Red text + Red background tint

**Logic:** `Self Time % > Threshold`

**Meaning:** This specific operation is the root cause of latency.

**Action:** Optimize the code or query within this span.

### 🟠 Hot Path (High Total-Time)

**Visual:** Orange/Amber border + Amber background tint

**Logic:** `Total Time % > Threshold` AND `Self Time % < Threshold`

**Meaning:** This operation is slow because it's waiting for something else.

**Action:** Follow the orange path down the tree until you find the red bottleneck.

### Example

```
[Controller] Total: 100ms | Self: 5ms   🟠 Hot Path
  └── [Service A] Total: 95ms | Self: 5ms   🟠 Hot Path
        └── [DB Query] Total: 90ms | Self: 90ms   🔴 Bottleneck
```

The Controller and Service A are part of the slow path, but the DB Query is doing the actual work.

---

## Parallelism Indicators

### ⤵⤵ Has Parallel Children

**Visual:** Purple badge with branching arrows

**Location:** Parent node that initiated parallel calls

**Meaning:** This node's children executed concurrently.

**Tooltip:** "This node has children running in parallel"

### ⚡ Effective (Parallel Execution)

**Visual:** Green badge showing effective wall-clock time

**Location:** Aggregated nodes with detected parallelism

**Display:**
```
⚡ Effective: 7,231.74 ms (22.3%)
Cumulative: 68,871.85 ms (×73 calls, 9.5× parallel)
```

**Metrics:**
- **Effective:** Actual wall-clock time (what you waited)
- **Cumulative:** Sum of all individual call durations
- **Parallelism factor:** How many calls ran concurrently on average

**Example:**
- 73 calls with 943ms average each
- Cumulative: 68,872ms (if sequential)
- Effective: 7,232ms (due to 9.5× parallelism)

### Understanding Parallelism Factor

| Factor | Meaning |
|--------|---------|
| 1.0× | Sequential (no overlap) |
| 2.0× | Average 2 calls concurrent |
| 9.5× | Average 9.5 calls concurrent |

### ∥ Sibling Parallelism Marker

**Visual:** Blue badge with parallel bars symbol

**Location:** On individual child spans that run concurrently with siblings

**Meaning:** This child overlaps in time with other children of the same parent.

**When shown:**
- Multiple different children (different services/endpoints) run concurrently
- Only marked on children that actually overlap with at least one sibling

### Timeline Bars

**Visual:** Horizontal bar below each span's metrics

**Components:**
- **Light span (border):** Shows when the span happened (start % - end %)
- **Solid fill:** Shows work density (effective time / span duration)

**Example:**
```
CurrentUser (×73): Effective 275ms across 3500ms span
[░░░█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]
     ↑ 8% filled (275/3500 = scattered, lightweight)

BasicRuleLookup (×73): Effective 3333ms across 3400ms span  
[    ████████████████████████████████████████████████████████░]
     ↑ 98% filled (3333/3400 = concentrated, heavyweight)
```

**Tooltip:** Shows timeline range and density percentage

**Interpretation:**
- **Full span, thin fill:** Calls are scattered but lightweight
- **Partial span, full fill:** Calls are concentrated and heavyweight
- **Orange color:** For parallel siblings (marked with ∥)

---

## Error Indicators

### 🔴 Error Dot (Pulsing)

**Visual:** Red pulsing circle

**Location:** Before the service name on error spans

**Meaning:** This span has an error status (OpenTelemetry status code 1 or 2)

**Tooltip:** Shows the error message

### ❌ Error Badge

**Visual:** Red badge with error details

**Location:** In the metrics area of error spans

**Display variants:**
- Single span: `❌ Error (502)` - Shows HTTP status code
- Aggregated: `❌ Error (4/73)` - Shows error count / total count

**Tooltip:** Full error message

### Error Span Background

**Visual:** Subtle red gradient background with red left border

**Applied to:** The entire node row for error spans

---

## Metrics Display

Each node shows the following metrics:

### Standard Metrics

| Metric | Description |
|--------|-------------|
| **Count** | Number of calls (for aggregated nodes) |
| **Avg** | Average duration (for aggregated nodes) |
| **Total** | Wall-clock time from start to finish |
| **Self** | Time spent only in this span (Total - Children) |

### Parallel Node Metrics

For nodes with detected parallelism, the display changes:

| Metric | Description |
|--------|-------------|
| **⚡ Effective** | Actual wall-clock time (primary, green) |
| **Cumulative** | Sum of all call durations (secondary, gray) |

### Time Formatting

| Duration | Format |
|----------|--------|
| < 1s | `245.50 ms` |
| < 1m | `12.45 s` |
| ≥ 1m | `2m 15.30s` |

### Percentage Calculation

All percentages are relative to **total trace wall-clock time**.

**Note:** For parallel nodes, cumulative percentages can exceed 100% because multiple calls overlap in time.

---

## Interactive Controls

### Threshold Slider

**Location:** Top of the trace hierarchy section

**Range:** 5% to 95%

**Default:** 10%

**Usage:**
- **Lower (5%):** Highlights more nodes, finds minor contributors
- **Higher (20%+):** Only shows critical bottlenecks

### Expand/Collapse

**Arrow Toggle (▶/▼):** Click to expand or collapse children

**Buttons:**
- **Expand All:** Opens entire tree
- **Collapse All:** Closes entire tree
- **Expand Hot Zones:** Opens only nodes > threshold (default view)

### Default Expansion

By default, the tree automatically expands nodes contributing > 10% to total trace time, allowing immediate focus on the critical path.

### Show Performance Issues Only

**Checkbox:** Filters to show only nodes with performance issues

When enabled, hides nodes that are:
- Below the threshold percentage
- Not part of the hot path
- Not bottlenecks

---

## Quick Reference

| Indicator | Visual | Meaning |
|-----------|--------|---------|
| 🟠 Orange border | High total time | Hot path (slow due to children) |
| 🔴 Red border | High self time | Bottleneck (actually slow) |
| ⤵⤵ | Purple badge | Has parallel children below |
| ⚡ Effective | Green badge | Parallel execution metrics |
| ∥ | Blue badge | Part of sibling parallel group |
| Timeline bar | Horizontal bar | Position and density within parent |
| 🔴 Pulsing dot | Red circle | Error span indicator |
| ❌ Error | Red badge | Error with details/count |

---

## Related Documentation

- [User Guide](USER_GUIDE.md) - Using the analyzer
- [Quick Start](QUICKSTART.md) - Getting started
- [Architecture](ARCHITECTURE.md) - How it works internally
- [Analysis](ANALYSIS.md) - Processing algorithms
