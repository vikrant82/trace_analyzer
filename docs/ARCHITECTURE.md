# Trace Analyzer: Architecture and Code Summary

## 1. Project Overview

The Trace Analyzer is a web-based utility designed to parse and analyze OpenTelemetry trace JSON files. It provides a detailed, hierarchical view of distributed traces, offering insights into performance bottlenecks, service dependencies, and overall system behavior. The application is built with a Python backend using Flask and a simple, dynamic frontend using Jinja2 templates.

## 2. Core Architecture

The application is composed of four main components:

1.  **`trace_analyzer/` (The Backend Engine):** This package contains the core analysis logic, organized into extractors, processors, formatters, filters, storage, and web modules.
2.  **`app.py` (The Web Application):** A lightweight Flask application that serves the web UI and provides REST API endpoints for analyzing and sharing trace files.
3.  **`analyze_trace.py` (CLI Interface):** Command-line interface for scripted analysis.
4.  **`templates/` (The Frontend):** Jinja2 HTML templates that define the structure and appearance of the web UI.

## 3. The Backend Engine: `analyze_trace.py`

The `TraceAnalyzer` class is where the core logic of the application resides. It is designed to be a stateful processor that can be instantiated and then used to analyze a trace file.

### Key Data Structures

*   **`self.traces`:** A `defaultdict(list)` that stores all the spans from the trace file, grouped by their `traceId`. This is the primary data structure used to build the trace hierarchies.
*   **`self.trace_hierarchies`:** A dictionary that stores the final, processed hierarchy for each trace. The key is the `traceId`, and the value is the root node of the hierarchy.
*   **`self.trace_summary`:** A dictionary that stores high-level summary information for each trace, such as the total wall-clock duration and the number of spans.
*   **`self.endpoint_params` & `self.service_calls`:** These are `defaultdict` structures that store the flat-list data for the summary tables in the UI. They are populated *after* the hierarchy has been fully processed, ensuring that all timing metrics are based on the final, correct `self_time` values.

### The Analysis Process: A Four-Pass System

The analysis is performed in a sophisticated four-pass system within the `_process_collected_traces` method. This is crucial for correctly handling fragmented trace data and calculating an accurate `Self Time`.

1.  **Pass 1 & 2 (`_build_raw_hierarchy`):** This is the most critical step for data integrity.
    *   **Node Creation & `SERVER` Span Identification:** The method first iterates through all spans to create a node for each one. Crucially, it also identifies the primary `SPAN_KIND_SERVER` span for each service and stores it in a `service_server_spans` map. This `SERVER` span acts as the designated "head" of that service.
    *   **Hierarchy Linking & Orphan Adoption:** In the second pass, it links children to their parents. If a span's `parentSpanId` is not found in the trace data (making it an "orphan"), the logic now intelligently adopts it. It attaches the orphan span as a child of the designated `SERVER` span for its own service. This programmatically repairs the broken call graph caused by fragmented trace data.

2.  **Pass 3 (`_calculate_hierarchy_timings`):** This recursive, bottom-up pass traverses the now-corrected hierarchy.
    *   It first ensures all children of a node are processed.
    *   It then aggregates the direct children of the current node to group identical calls.
    *   Finally, it calculates the `self_time` for the current node using the formula: `self_time = max(0, total_time - sum_of_aggregated_children_total_time)`. Because the hierarchy is correct, this calculation is now accurate.

3.  **Pass 4 (`_populate_flat_metrics`):** With a fully correct and calculated hierarchy, this final pass iterates through all the nodes one last time. It reads the now-accurate `total_time_ms` and `self_time_ms` values from each node and populates the flat data structures (`endpoint_params`, `service_calls`) used to generate the summary tables in the UI.

### Recursive Aggregation

*   **`_aggregate_list_of_nodes(nodes)`:** This helper function is responsible for grouping nodes that represent identical calls. It uses a composite key (service, method, and normalized path) to ensure that only truly identical operations are merged. Fuzzy path matching allows raw URL paths (from proxy/sidecar CLIENT spans) to merge with pre-parameterized framework routes (from SERVER spans using `http.route`). When nodes are merged, their `count` is summed, a new `avg_time_ms` is calculated, and absorbed concrete values (e.g., `data-model`, `4.3.8`) are tracked as parameter values. This is what provides the clean, aggregated view in the final hierarchy display.

## 4. The Web Application: `app.py`

The Flask application is straightforward. It has two main routes:

*   **`/`:** Renders the main page with the file upload form.
*   **`/analyze`:** This is the workhorse of the web UI. It handles the file upload, creates an instance of the `TraceAnalyzer`, calls the `process_trace_file` method, and then passes the results to the `prepare_results` function before rendering the `results.html` template.

The `prepare_results` function acts as a bridge between the backend and the frontend. It takes the raw data from the `TraceAnalyzer` and transforms it into the structured format that the Jinja2 template expects.

## 5. The Frontend: `templates/results.html`

The results page is a dynamic HTML document that is rendered by Jinja2. It is responsible for displaying all the analysis results in a clear and interactive way.

### Key Features

*   **Recursive Macro (`render_trace_node`):** The core of the hierarchy view is a powerful Jinja2 macro that can recursively render each node of the trace. This allows the template to handle traces of any depth and complexity.
*   **Collapsible Hierarchy:** The hierarchy is fully interactive. Each node with children can be collapsed or expanded, and "Collapse All" / "Expand All" buttons provide convenient control over the entire view. This is handled with a small amount of vanilla JavaScript that manipulates the `data-state` attribute of the list items.
*   **Dynamic Styling:** The CSS is designed to visually distinguish between different types of information. For example, the `http-method` has its own style, and the `collapsible` and `expanded`/`collapsed` states are handled with simple CSS rules.

This architecture allows for a clean separation of concerns, with the backend handling the complex analysis and the frontend focusing on providing a clear and interactive user experience.

## 6. Share Storage: `trace_analyzer/storage/`

The storage module provides file-based persistence for shared analysis results.

### ShareStorage Class

The `ShareStorage` class manages the lifecycle of shared analyses:

*   **`create_share(results, filename, ttl)`:** Generates a unique 8-character ID and saves the analysis results as a JSON file with expiration metadata.
*   **`get_share(share_id)`:** Retrieves a share by ID, automatically deleting and returning `None` if expired.
*   **`cleanup_expired()`:** Removes all expired share files (called on server startup).

### Storage Format

Shares are stored as JSON files in the `shares/` directory:

```
shares/
├── abc12def.json    # Share with 8-char ID
├── xyz98765.json
└── .gitkeep
```

Each file contains:

```json
{
  "share_id": "abc12def",
  "created_at": 1737388800,
  "expires_at": 1737993600,
  "ttl_label": "7d",
  "filename": "production-trace.json",
  "results": { /* Full analysis results */ }
}
```

### TTL Options

| Label | Duration | Seconds |
|-------|----------|---------|
| `24h` | 24 Hours | 86,400 |
| `7d` | 7 Days | 604,800 |
| `1m` | 1 Month | 2,592,000 |

### Privacy Model

*   Only processed results are stored (never the original trace file)
*   Sharing is opt-in only (user must explicitly click "Share")
*   Expired files are automatically cleaned up