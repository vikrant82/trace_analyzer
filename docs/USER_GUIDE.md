# Trace Analyzer User Guide

**Last Updated:** January 20, 2026

This guide covers how to use the Trace Analyzer for analyzing OpenTelemetry traces.

---

## Table of Contents

- [Web Application](#web-application)
- [Command Line Interface](#command-line-interface)
- [REST API](#rest-api)
- [Sharing Analysis Results](#sharing-analysis-results)
- [Filtering Options](#filtering-options)
- [Parameter Detection](#parameter-detection)
- [Query Parameter Handling](#query-parameter-handling)
- [Output Format](#output-format)

---

## Web Application

The web interface is the recommended way to use Trace Analyzer.

### Starting the Server

```bash
python app.py
```

Then open `http://localhost:5001` in your browser.

### Using the Interface

1. **Upload:** Drag and drop or select your trace JSON file
2. **Configure:** Set filtering options (see [Filtering Options](#filtering-options))
3. **Analyze:** Click "Analyze Trace File"
4. **Explore:** View interactive results with sortable tables and trace hierarchy

### Features

- 📊 Interactive HTML interface
- 📈 Visual statistics dashboard
- 🔍 Sortable tables (click column headers)
- 🌳 Interactive trace hierarchy with expand/collapse
- 📱 Responsive design

---

## Command Line Interface

For scripting and automation, use the CLI tool.

### Basic Usage

```bash
python analyze_trace.py trace_file.json
```

### Options

| Option | Description |
|--------|-------------|
| `-o, --output` | Custom output file path |
| `--keep-query-params` | Keep query parameters (default: stripped) |
| `--include-gateways` | Include gateway/proxy services |
| `--include-service-mesh` | Include Istio/Envoy sidecars |

### Examples

```bash
# Basic analysis
python analyze_trace.py trace.json

# Custom output file
python analyze_trace.py trace.json -o my_report.md

# Include all service types
python analyze_trace.py trace.json --include-gateways --include-service-mesh
```

**Output:** Generates a Markdown file with analysis results.

---

## REST API

For programmatic access, use the REST API.

### Analyze Endpoint

```
POST /api/analyze
```

### Request

- **Content-Type:** `multipart/form-data`
- **Body:**
  - `file` (required): JSON trace file
  - `strip_query_params`: "true" (default) or "false"
  - `include_gateway_services`: "true" or "false"
  - `include_service_mesh`: "true" or "false"

### Example

```bash
curl -X POST http://localhost:5001/api/analyze \
  -F "file=@trace.json" \
  -F "include_gateway_services=true"
```

### Response

```json
{
  "summary": {
    "total_requests": 150,
    "total_time_ms": 45300,
    "total_time_formatted": "45.30 s",
    "unique_services": 2,
    "unique_endpoints": 5
  },
  "services": { ... },
  "service_calls": [ ... ],
  "trace_hierarchies": [ ... ]
}
```

---

## Sharing Analysis Results

Share your analysis results with teammates using shareable links with configurable expiration.

### How to Share

1. **Analyze** your trace file through the web interface
2. **Click** the "🔗 Share" button in the results header
3. **Select** expiration time (24 hours, 7 days, or 1 month)
4. **Copy** the generated short URL

### Expiration Options

| Option | Duration | Use Case |
|--------|----------|----------|
| **24 Hours** | 1 day | Quick reviews, daily standups |
| **7 Days** | 1 week | Sprint analysis, incident reviews |
| **1 Month** | 30 days | Documentation, long-term reference |

### Shared Link Format

```
https://your-domain.com/s/abc12def
```

- 8-character short code
- Full analysis results (including trace hierarchy)
- Read-only view for recipients

### Privacy Considerations

- **Opt-in only**: Sharing is never automatic
- **Processed results only**: Original trace file is not stored
- **Auto-cleanup**: Expired shares are automatically deleted
- **No authentication**: Anyone with the link can view (use judiciously)

### Share API

Create shares programmatically:

```bash
# Create a share
curl -X POST http://localhost:5001/api/share \
  -H "Content-Type: application/json" \
  -d '{
    "results": {...},
    "filename": "trace.json",
    "ttl": "7d"
  }'

# Response
{
  "share_id": "abc12def",
  "share_url": "http://localhost:5001/s/abc12def",
  "expires_at": 1738000000,
  "ttl_label": "7d"
}
```

Retrieve a share:

```bash
# Get share as JSON
curl http://localhost:5001/api/share/abc12def

# View share in browser
open http://localhost:5001/s/abc12def
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SHARE_STORAGE_DIR` | `shares/` | Directory for share files |

---

## Filtering Options

### Include Gateway Services

**Default:** OFF

Controls whether CLIENT-only services (API gateways, load balancers, proxies) appear in results.

| Setting | Behavior |
|---------|----------|
| OFF | Only services with SERVER spans (business logic) |
| ON | Include gateways and proxies |

**Use Case:** Enable when you need full service topology including forwarding infrastructure.

### Include Service Mesh

**Default:** OFF

Controls whether Istio/Envoy sidecar spans appear in results.

| Setting | Behavior |
|---------|----------|
| OFF | Filters out sidecar duplicates (cleanest view) |
| ON | Shows both application AND sidecar spans |

**Use Case:** Enable when diagnosing service mesh overhead or configuration issues.

### Combined Behavior

| Gateway | Mesh | Result |
|---------|------|--------|
| OFF | OFF | **Business logic only** (recommended) |
| ON | OFF | Business logic + gateways |
| OFF | ON | Business logic + sidecar duplicates |
| ON | ON | **Complete infrastructure** |

---

## Parameter Detection

The analyzer automatically detects and normalizes URL parameters:

### Detection Rules

| Type | Pattern | Normalized | Tracked? |
|------|---------|------------|----------|
| UUID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` | `{uuid}` | ❌ Ignored |
| Rule ID | `AppName__ResourceName` | `{rule_id}` | ✅ Yes |
| Encoded | Base64-like (30+ chars) | `{encoded_id}` | ✅ Yes |
| Semver | `4.3.8`, `1.0.0.1` | `{version}` | ✅ Yes |
| Numeric | `/123`, `/456` | `{id}` | ✅ Yes |

### Example

```
Input:  /v1/a21a1909-c664-41be-bfc5-9a3ce0dae52c/users/123
Output: /v1/{uuid}/users/{id}
Tracked: {id} = 123 (UUID ignored)
```

### Detection Order

1. UUIDs (ignored)
2. Rule IDs (tracked)
3. Long encoded strings (tracked)
4. Semantic versions (tracked)
5. Numeric IDs (tracked)

### Fuzzy Path Matching

When your system uses a framework like Micronaut that provides pre-parameterized route templates (via `http.route`), the analyzer will merge those with raw URL paths from proxy/sidecar spans. For example:

- **SERVER span** (`http.route`): `/v1/{isolationID}/bundles/{bundleID}/versions/{versionID}`
- **CLIENT span** (`http.url`): `/v1/abc123/bundles/data-model/versions/4.3.8`

These are recognized as the same endpoint and merged, with concrete values like `data-model` and `4.3.8` shown as parameter values in the display.

---

## Query Parameter Handling

**Default:** Query parameters are stripped.

### Example

```
Before: /data-pages/App__Resource?param1=abc&param2=xyz
After:  /data-pages/{rule_id}
```

### When to Keep Query Parameters

- Query parameters represent different endpoints (rare)
- Debugging specific parameter combinations

### How to Disable Stripping

- **CLI:** `--keep-query-params`
- **Web UI:** Uncheck "Strip query parameters"
- **API:** `strip_query_params=false`

---

## Output Format

### Report Sections

1. **Summary Statistics**
   - Total requests, time, services, endpoints

2. **Trace Hierarchy** (Web only)
   - Interactive tree visualization
   - See [Visualization Guide](VISUALIZATION_GUIDE.md) for details

3. **Services Overview**
   - Incoming requests by service
   - Sorted by total time (descending)

4. **Service-to-Service Calls**
   - Outgoing HTTP calls between services
   - Grouped by caller → callee pairs

5. **Kafka/Messaging Operations**
   - Consumer and producer operations
   - Performance metrics

### Timing Display

| Duration | Format |
|----------|--------|
| < 1s | `245.50 ms` |
| < 1m | `12.45 s` |
| ≥ 1m | `2m 15.30s` |

---

## Related Documentation

- [Quick Start Guide](QUICKSTART.md) - Get started in 3 steps
- [Visualization Guide](VISUALIZATION_GUIDE.md) - Understanding the trace hierarchy
- [Architecture](ARCHITECTURE.md) - System design and modules
- [Analysis](ANALYSIS.md) - Trace processing algorithms
