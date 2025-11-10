# Trace Analyzer

A powerful Python tool to analyze OpenTelemetry trace files and extract HTTP endpoint performance metrics and Kafka/messaging operations.

Available as both a **CLI tool** and a **Web Application** with REST API.

Perfect for analyzing distributed systems, microservices architectures, event-driven systems, and identifying performance bottlenecks.

## Features

- Efficiently processes large trace files using streaming JSON parsing
- **Analyzes HTTP requests:**
  - Distinguishes between incoming and outgoing HTTP requests
  - Incoming: relative paths (e.g., `/api/users/123`)
  - Outgoing: full URLs (e.g., `http://service.cluster.local/...`)
  - Tracks service-to-service call relationships
- **Analyzes Kafka/messaging operations:**
  - Detects Kafka consumer and producer operations
  - Tracks message processing spans
  - Extracts message IDs, service IDs, and operation details
- Extracts and groups endpoints by service name
- Detects and normalizes URL parameters (UUIDs, numeric IDs, encoded strings)
- **Tracks timing information** - calculates total time spent per endpoint/operation
- Tracks each unique endpoint-parameter combination per service
- Generates comprehensive reports with:
  - Summary statistics across all services (requests + time)
  - Section 1: Incoming HTTP requests by service
  - Section 2: Service-to-service HTTP calls (caller → callee)
  - Section 3: Kafka/messaging operations by service
  - Table of contents with service links
  - Each table includes: Operation details, Count, **Total Time**
  - **All data sorted by Total Time (descending)** - shows slowest operations first

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for a quick 3-step guide to get started!

## About

This tool analyzes OpenTelemetry trace files exported from observability platforms like Grafana, Jaeger, or similar systems. It provides insights into:
- Service-level performance metrics
- HTTP endpoint call frequencies and latencies
- Service-to-service communication patterns
- Kafka/messaging operation patterns and performance
- Performance bottlenecks in both HTTP and messaging layers

### How is this different from Jaeger/Grafana?

While Jaeger and Grafana excel at real-time monitoring and exploring individual traces, **Trace Analyzer is designed for deep, offline, aggregated analysis** of captured traces. Key differentiators:

- **Intelligent endpoint normalization** - Groups similar endpoints (e.g., `/api/users/123` → `/api/users/{id}`) to reduce noise and identify patterns
- **Accurate self-time calculation** - Calculates time spent in each function excluding downstream calls, aggregated across all traces
- **Portable and lightweight** - Runs on a single JSON file, no infrastructure required
- **Focused reporting** - Quantitative summaries of service interactions and messaging operations
- **Post-incident analysis** - Analyze snapshots from incidents without needing live system access

📖 **See [analysis_summary.md](analysis_summary.md) for a detailed comparison and architectural deep-dive.**

## Project Structure

```
Trace_Analyser/
├── analyze_trace.py      # CLI script for trace analysis
├── app.py                # Flask web application
├── requirements.txt      # Python dependencies
├── templates/            # HTML templates
│   ├── index.html       # Upload page
│   └── results.html     # Results page
├── static/              # Static assets
│   └── style.css        # CSS styling
├── README.md            # Full documentation
├── QUICKSTART.md        # Quick start guide
└── .gitignore          # Git ignore rules
```

## Installation

1. **Clone or download this repository**

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

## Docker Deployment

### Using Docker

1. **Build the image:**
```bash
docker build -t trace-analyzer .
```

2. **Run the container:**
```bash
docker run -p 5000:5000 trace-analyzer
```

Then open `http://localhost:5000` in your browser.

### Using Docker Compose

1. **Start the service:**
```bash
docker-compose up --build
```

2. **Access the application:**
Open `http://localhost:5000` in your browser.

3. **Stop the service:**
```bash
docker-compose down
```

## Usage

### Option 1: Web Application (Recommended)

1. **Start the web server:**
```bash
python app.py
```

2. **Open your browser:**
```
http://localhost:5000
```

3. **Upload and analyze:**
   - Drag and drop or select your trace JSON file
   - Click "Analyze Trace File"
   - View interactive results with sortable tables

**Features:**
- 📊 Interactive HTML interface
- 📈 Visual statistics dashboard
- 🔍 **Sortable tables** - Click column headers to sort (Count, Total Time)
- 📱 Responsive design for mobile
- 🚀 REST API for programmatic access

### Option 2: Command Line Interface

**Basic usage (strips query parameters by default):**
```bash
python analyze_trace.py trace_file.json
```

**Custom output file:**
```bash
python analyze_trace.py trace_file.json -o my_report.md
```

**Keep query parameters (not recommended):**
```bash
python analyze_trace.py trace_file.json --keep-query-params
```

**View all options:**
```bash
python analyze_trace.py --help
```

**Output:** Generates a markdown file with analysis results.

### Option 3: REST API

**Analyze a trace file via API (strips query parameters by default):**
```bash
curl -X POST -F "file=@trace_file.json" \
  http://localhost:5000/api/analyze
```

**Keep query parameters:**
```bash
curl -X POST \
  -F "file=@trace_file.json" \
  -F "strip_query_params=false" \
  http://localhost:5000/api/analyze
```

**Response:** JSON with complete analysis results including services, endpoints, and timing data.

## Output

The script generates a markdown file (`trace_analysis.md` by default) with two main sections:

### 1. Incoming Requests by Service
- Shows **only incoming HTTP requests** that each service receives (relative paths)
- Excludes outgoing calls to other services
- Separate table for each service with their received endpoints
- Includes count and **total time spent** per endpoint
- **Sorted by total time (descending)** - slowest endpoints appear first

### 2. Service-to-Service Calls (Outgoing)
- Shows **outgoing HTTP calls** from one service to another
- Extracted from full URLs (e.g., `http://data-service.data-service.svc...`)
- Grouped by caller → callee service pairs
- Each pair shows which endpoints are called with counts and total time
- **Sorted by total time (descending)** per service pair

The report also includes:
- Summary statistics at the top (requests and time)
- Table of contents with links to each service section (includes time per service)
- Console output with service-level statistics and **top 10 slowest endpoints**

### Example Output

```markdown
# Trace Endpoint Analysis Report

**Total Incoming Requests:** 150  
**Total Time (Incoming):** 45.30 s  
**Unique Services:** 2  
**Unique Normalized Endpoints:** 5  
**Unique Endpoint-Parameter Combinations:** 8  

---

## Table of Contents - Incoming Requests by Service

- [api-service](#api-service) (100 requests, 30.50 s)
- [user-service](#user-service) (50 requests, 14.80 s)

---

# Incoming Requests by Service

*This section shows endpoints that each service receives (incoming HTTP requests).*  
*Tables are sorted by Total Time (descending).*

## api-service

**Service Requests:** 100  
**Total Time:** 30.50 s  
**Unique Combinations:** 5  

| Normalized Endpoint | Parameter Value | Count | Total Time |
|---------------------|-----------------|-------|------------|
| /api/posts/{id} | 42 | 45 | 18.50 s |
| /api/posts/{id} | 99 | 30 | 8.20 s |
| /api/users/{uuid} | [no-params] | 25 | 3.80 s |

## user-service

**Service Requests:** 50  
**Total Time:** 14.80 s  
**Unique Combinations:** 3  

| Normalized Endpoint | Parameter Value | Count | Total Time |
|---------------------|-----------------|-------|------------|
| /v1/users/{encoded_id}/profile/{encoded_id} | userProfileView | 30 | 10.20 s |
| /v1/users/{encoded_id}/actions/refresh | [no-params] | 20 | 4.60 s |

---

# Service-to-Service Calls (Outgoing)

*This section shows outgoing HTTP calls from one service to another.*  
*Tables are sorted by Total Time (descending).*

**Total Cross-Service Call Combinations:** 15  
**Total Time (Cross-Service):** 22.40 s  
**Service Pair Relationships:** 2  

## frontend-service → backend-service

**Total Calls:** 50  
**Total Time:** 15.60 s  
**Unique Combinations:** 5  

| Normalized Endpoint | Parameter Value | Count | Total Time |
|---------------------|-----------------|-------|------------|
| http://backend-service.backend.svc.cluster.local/v3/{uuid}/data/App__CurrentUser | [no-params] | 25 | 10.20 s |
| http://backend-service.backend.svc.cluster.local/v3/{uuid}/data/{encoded_id} | App__UserSession | 15 | 5.40 s |
```

## Parameter Detection

The analyzer automatically detects and normalizes different types of parameters:

1. **UUIDs**: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` → `{uuid}` 
   - Normalized but NOT tracked individually (ignored)
   - Example: `/v1/a21a1909-c664-41be-bfc5-9a3ce0dae52c/api` → `/v1/{uuid}/api`

2. **Application identifiers**: `AppName__ResourceName` → `{rule_id}`
   - Resource names, class names, and identifiers with double underscores
   - Tracked separately as parameters
   - Example: `/resources/AppName__UserProfile/execute` → `/resources/{rule_id}/execute`
   - Example: `/data-pages/AppName__Dashboard?param=value` → `/data-pages/{rule_id}?param=value`
   - Tracks: `AppName__UserProfile`, `AppName__Dashboard`, `Service__DataConnector`, etc.

3. **Long encoded strings**: Base64-like strings (30+ chars) → `{encoded_id}`
   - Tracked separately as parameters
   - Example: `/cases/RTE6UGVnYVBsYXRmb3JtX1...` → `/cases/{encoded_id}`

4. **Numeric IDs**: `/123`, `/456` → `/{id}`
   - Tracked separately as parameters
   - Example: `/api/posts/123` → `/api/posts/{id}`

**Detection Order:** UUIDs → Rule IDs → Long encoded → Numeric IDs

**Note:** UUID/GUID parameters are ignored and grouped together. All other parameter types are tracked individually.

### Example:
```
/v1/a21a1909-c664-41be-bfc5-9a3ce0dae52c/api/user/123
/v1/a21a1909-c664-41be-bfc5-9a3ce0dae52c/api/user/345
```

Both normalize to `/v1/{uuid}/api/user/{id}`, but only track:
- `/v1/{uuid}/api/user/{id}`, 123, 1
- `/v1/{uuid}/api/user/{id}`, 345, 1

The UUID value `a21a1909-c664-41be-bfc5-9a3ce0dae52c` is ignored.

## Timing Information

The analyzer calculates duration for each span and aggregates it per endpoint:
- Uses `startTimeUnixNano` and `endTimeUnixNano` from OpenTelemetry spans
- Calculates duration in milliseconds
- **Aggregates total time** for each (endpoint, parameter) combination
- Time is formatted for readability:
  - `< 1s`: Shows in milliseconds (e.g., `245.50 ms`)
  - `< 1m`: Shows in seconds (e.g., `12.45 s`)
  - `>= 1m`: Shows in minutes and seconds (e.g., `2m 15.30s`)

**All tables are sorted by Total Time (descending)**, helping you identify performance bottlenecks quickly.

## Incoming vs Outgoing Request Detection

The analyzer distinguishes between incoming and outgoing HTTP requests:

### Incoming Requests (Section 1)
- Detected by **relative paths** (e.g., `/api/users/123`)
- Represents endpoints that the service **receives**
- Tracked per service in the first section

### Outgoing Requests (Section 2)
- Detected by **full URLs** (e.g., `http://service-name.namespace.svc.cluster.local/...`)
- Represents calls the service **makes to other services**
- Target service extracted from the URL hostname
- Tracked as caller → callee relationships in the second section

This separation helps you understand:
- What endpoints each service exposes (incoming)
- What external services each service depends on (outgoing)
- Service communication patterns and dependencies
- The flow of requests across your distributed system
- Microservices architecture and inter-service dependencies

## Understanding Service Counting & Filtering

The analyzer provides two independent filtering options to control what appears in your analysis:

### 1. Include Gateway Services (Controls CLIENT-only services)

**Default (OFF):** Only counts services with `SPAN_KIND_SERVER` spans
- Excludes: API gateways, load balancers, proxies that only forward requests (CLIENT-only)
- **Use case:** Focus on services with business logic

**When enabled (ON):** Also counts services with only CLIENT spans
- Includes: API gateways, load balancers, proxies
- **Use case:** Full service topology including forwarding infrastructure

**Example:** `gateway-service` (only has CLIENT spans) → Excluded by default, included when enabled

### 2. Include Service Mesh (Controls Istio/Envoy sidecar spans)

**Default (OFF):** Filters out service mesh sidecar duplicates
- Excludes: SERVER→SERVER chains (Envoy→App)
- Excludes: CLIENT→CLIENT chains (App→Envoy)
- Shows: Only application-level spans (cleanest view)
- **Use case:** Normal analysis without infrastructure noise

**When enabled (ON):** Includes all sidecar spans
- Shows: Both application AND Envoy sidecar spans
- Result: Duplicate entries for each logical operation
- **Use case:** Diagnosing service mesh overhead and configuration

### Combined Behavior Matrix

| Gateway Services | Service Mesh | Result |
|------------------|--------------|--------|
| ❌ OFF | ❌ OFF | **Business logic only** (cleanest view, recommended) |
| ✅ ON | ❌ OFF | Business logic + API gateways (no sidecar duplicates) |
| ❌ OFF | ✅ ON | Business logic + sidecar duplicates (no gateways) |
| ✅ ON | ✅ ON | **Complete infrastructure** (all services, all spans) |

### Service Mesh Example

With **Include Service Mesh OFF** (default):
```
data-service:
  POST /api/users  →  1 request, 50ms  ✅ (application span only)
```

With **Include Service Mesh ON**:
```
data-service:
  POST /api/users  →  1 request, 50ms  ✅ (application span)
  POST /api/users  →  1 request, 52ms  ✅ (Envoy sidecar span)
```

### How to Enable These Options

**CLI:**
```bash
# Default: business logic only
python analyze_trace.py trace.json

# Include gateway services (CLIENT-only)
python analyze_trace.py trace.json --include-gateways

# Include service mesh sidecars (Istio/Envoy)
python analyze_trace.py trace.json --include-service-mesh

# Include everything
python analyze_trace.py trace.json --include-gateways --include-service-mesh
```

**Web UI:**
- Check **"Include Gateway Services"** to include API gateways/proxies
- Check **"Include Service Mesh Spans"** to include Istio/Envoy sidecars

**API:**
```bash
curl -X POST http://localhost:5000/api/analyze \
  -F "file=@trace.json" \
  -F "include_gateway_services=true" \
  -F "include_service_mesh=true"
```

### When to Use Each Mode

**Default (both OFF)** - Most common use case:
- ✅ Clean analysis of business logic
- ✅ No infrastructure noise
- ✅ Accurate application performance

**Gateway Services ON:**
- 🔍 Understanding complete service topology
- 🔍 Debugging gateway/proxy issues
- 🔍 Analyzing load balancer behavior

**Service Mesh ON:**
- 🔧 Diagnosing Istio/Envoy configuration
- 🔧 Measuring service mesh overhead
- 🔧 Debugging sidecar injection issues
- ⚠️ Note: Shows duplicates intentionally

**Both ON:**
- 🛠️ Complete infrastructure visibility
- 🛠️ Full trace analysis including all hops
- 🛠️ Advanced troubleshooting

## Query Parameter Stripping

By default, the analyzer **strips query parameters** from URLs to group similar endpoints together.

**Example:**
```
Before: /data-pages/Application__ResourceName?param1=abc&param2=xyz
After:  /data-pages/{rule_id}
```

This prevents each unique combination of query parameters from creating separate rows.

**When to keep query parameters:**
- If query parameters represent different endpoints (rare)
- For debugging specific parameter combinations

**How to disable:**
- **CLI**: Add `--keep-query-params` flag
- **Web UI**: Uncheck "Strip query parameters" checkbox
- **API**: Set `strip_query_params=false` in form data

## API Endpoints

### `POST /api/analyze`
Analyze a trace file and return JSON results.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: 
  - `file` (required): JSON trace file
  - `strip_query_params` (optional): "true" (default) or "false"

**Response:**
```json
{
  "summary": {
    "total_requests": 150,
    "total_time_ms": 45300,
    "total_time_formatted": "45.30 s",
    "unique_services": 2,
    "unique_endpoints": 5,
    "unique_combinations": 8
  },
  "services": {
    "summary": [...],
    "details": {...}
  },
  "service_calls": [...]
}
```

### `POST /analyze`
Web endpoint that returns HTML results page.

## Configuration

**Web Application Settings (app.py):**
- `MAX_CONTENT_LENGTH`: Maximum file size (default: 500MB)
- `host`: Server host (default: 0.0.0.0)
- `port`: Server port (default: 5000)
- `debug`: Debug mode (default: True)

## Performance

The tool uses streaming JSON parsing (`ijson`) to handle large trace files efficiently without loading the entire file into memory. Both the CLI and web application use the same efficient parsing engine.

