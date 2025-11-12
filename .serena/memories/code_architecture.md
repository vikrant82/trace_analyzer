# Code Architecture

## Core Components

### 1. `analyze_trace.py` - The Analysis Engine
**Main Class**: `TraceAnalyzer`

**Initialization Parameters**:
- `strip_query_params` (bool): Remove query parameters from URLs (default: True)
- `include_gateway_services` (bool): Include CLIENT-only services (default: False)
- `include_service_mesh` (bool): Include Istio/Envoy sidecar spans (default: False)

**Key Data Structures**:
- `traces`: Dict[trace_id, List[spans]] - Raw spans grouped by trace
- `trace_hierarchies`: Dict[trace_id, hierarchy_tree] - Processed display trees
- `trace_summary`: Dict[trace_id, summary_stats] - Wall-clock duration, span count
- `endpoint_params`: Flat dict of incoming requests per service
- `service_calls`: Flat dict of service-to-service calls
- `kafka_messages`: Flat dict of Kafka operations

**Five-Pass Analysis Pipeline**:
1. **Ingest & Group** - Read file, group spans by traceId
2. **Build Hierarchy** (`_build_raw_hierarchy`) - Create tree, adopt orphans
3. **Calculate Timings** (`_calculate_hierarchy_timings`) - Recursive bottom-up self-time calculation
4. **Populate Flat Metrics** (`_populate_flat_metrics`) - Fill summary tables with filtering
5. **Normalize & Aggregate** (`_normalize_and_aggregate_hierarchy`) - Clean display tree

**Key Methods**:
- `process_trace_file()` - Main entry point
- `normalize_path()` - URL normalization with regex patterns
- `extract_http_path()`, `extract_http_method()`, `extract_service_name()` - Attribute extraction
- `format_time()` - Human-readable time formatting

### 2. `app.py` - Flask Web Application
**Routes**:
- `GET /` - Upload page (index.html)
- `POST /analyze` - Web form submission → HTML results
- `POST /api/analyze` - REST API → JSON results

**Key Functions**:
- `analyze_web()` - Handles web form uploads
- `analyze_api()` - Handles API requests
- `prepare_results()` - Transforms TraceAnalyzer output to UI-friendly format
- `allowed_file()` - File validation

**Configuration**:
- `MAX_CONTENT_LENGTH`: 500MB file size limit
- `UPLOAD_FOLDER`: temp directory for uploads
- Server: 0.0.0.0:5001 (development)

### 3. `templates/results.html` - Frontend
**Jinja2 Macro**: `render_trace_node(node, loop_index, total_trace_time, parent_total_time)`
- Recursively renders trace hierarchy tree
- Displays metrics: Count, Avg Time, Total Time, Self Time
- Interactive expand/collapse with JavaScript
- Dynamic highlighting slider (5-95% threshold)

**JavaScript Features**:
- Table sorting (click column headers)
- Hierarchy expand/collapse
- Dynamic highlighting based on slider value
- Time parsing for sorting (ms, s, m formats)

## Data Flow
1. User uploads trace JSON file
2. Flask saves to temp directory
3. TraceAnalyzer processes file (5-pass pipeline)
4. `prepare_results()` transforms to UI format
5. Template renders interactive results
6. User interacts with hierarchy, tables, slider
