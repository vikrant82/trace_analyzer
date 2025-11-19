# Trace Visualization Guide

**Last Updated:** November 19, 2025

## Overview
The Trace Analyzer provides a hierarchical view of trace spans to help identify performance bottlenecks. This guide explains the visualization logic, specifically the "Dual-Highlighting" system used to distinguish between slow paths and actual bottlenecks.

---

## The "Dual-Highlighting" System

In distributed tracing, a "slow" span can be slow for two reasons:
1.  **It is waiting for children:** The span itself does little work, but its children take a long time. (e.g., A Controller waiting for a Database call).
2.  **It is doing the work:** The span itself consumes CPU or I/O time. (e.g., The Database call itself).

To visualize this effectively, we use two distinct highlighting styles based on a configurable threshold (default 10%).

### 1. 🔴 Bottleneck (High Self-Time)
**Visual:** Red Border + Red Text + Red Background Tint  
**Logic:** `Self Time % > Threshold`

These nodes are the **root cause** of latency.
-   **Self Time:** The time spent in *this specific span*, excluding its children.
-   **Meaning:** "This specific operation is slow."
-   **Action:** Optimize the code or query within this span.

### 2. 🟠 Hot Path (High Total-Time)
**Visual:** Orange/Amber Border + Normal Text + Amber Background Tint  
**Logic:** `Total Time % > Threshold` AND `Self Time % < Threshold`

These nodes represent the **path** to the bottleneck.
-   **Total Time:** The duration of the span *including* all its children.
-   **Meaning:** "This operation is slow because it is waiting for something else."
-   **Action:** Follow the orange path down the tree until you find the red bottleneck.

---

## Interactive Controls

### Threshold Slider
The slider at the top of the hierarchy view controls the sensitivity of the highlighting.
-   **Range:** 5% to 95%
-   **Default:** 10%
-   **Usage:**
    -   **Lower Threshold (e.g., 5%):** Highlights more nodes, useful for finding minor contributors.
    -   **Higher Threshold (e.g., 20%):** Highlights only the most critical bottlenecks, useful for large traces.

### Collapsible Tree
-   **Expand/Collapse:** Click the arrow (▶) or the node itself to toggle visibility of children.
-   **Expand All / Collapse All:** Use the buttons to control the entire tree.
-   **Default View:** By default, the tree automatically expands only the **Hot Zones** (nodes contributing > 10% to the total time). This allows you to immediately focus on the critical path without manual navigation.

---

## Metrics Explained

Each node in the tree displays the following metrics:

-   **Total:** The wall-clock time from start to finish of this span.
-   **Self:** The time spent *only* in this span (Total - Sum of Children).
-   **Count:** How many times this specific operation occurred (if aggregated).
-   **Avg:** Average duration (if aggregated).

### Example
```
[Controller] Total: 100ms | Self: 5ms  (Orange - Hot Path)
  └── [Service A] Total: 95ms | Self: 5ms (Orange - Hot Path)
        └── [DB Query] Total: 90ms | Self: 90ms (Red - Bottleneck)
```

In this example:
-   The **Controller** and **Service A** are highlighted in **Orange** because they are part of the slow path (Total > 10%).
-   The **DB Query** is highlighted in **Red** because it is doing the actual work (Self > 10%).
