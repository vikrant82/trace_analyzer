# Trace Analyzer - Project Overview

## Purpose
Trace Analyzer is a powerful OpenTelemetry trace analysis tool that processes trace JSON files to extract HTTP endpoint performance metrics, Kafka/messaging operations, and service dependencies in distributed systems.

## Key Differentiators
- **Offline aggregated analysis** of captured traces (vs real-time monitoring in Jaeger/Grafana)
- **Intelligent endpoint normalization** - groups similar endpoints (e.g., `/api/users/123` → `/api/users/{id}`)
- **Accurate self-time calculation** - calculates time spent in each function excluding downstream calls
- **Portable and lightweight** - runs on a single JSON file, no infrastructure required
- **Post-incident analysis** - analyze snapshots from incidents without needing live system access

## Deployment Options
1. **CLI tool** - Command-line analysis with markdown output
2. **Web Application** - Flask-based interactive dashboard
3. **REST API** - Programmatic access for automation
4. **Docker** - Containerized deployment

## Tech Stack
- **Language**: Python 3
- **Web Framework**: Flask 3.0+
- **JSON Parser**: ijson (streaming parser for large files)
- **Templating**: Jinja2
- **Web Server**: Werkzeug
- **Containerization**: Docker, Docker Compose

## Core Features
- Interactive trace hierarchy with visual tree and dynamic highlighting (5-95% threshold slider)
- Smart URL normalization (UUIDs, IDs, encoded strings, rule identifiers)
- Service mesh filtering (eliminates Istio/Envoy duplicates)
- Incoming vs Outgoing requests detection
- Kafka/messaging operations tracking
- Accurate timing calculations (Total Time + Self Time per endpoint)
- Error tracking with counts and messages

## Project Structure
```
Trace_Analyser/
├── analyze_trace.py      # Core analysis engine (TraceAnalyzer class)
├── app.py                # Flask web application
├── requirements.txt      # Python dependencies
├── templates/            # Jinja2 HTML templates
│   ├── index.html       # Upload page
│   └── results.html     # Results page with trace hierarchy
├── static/              # CSS styling
│   └── style.css
├── README.md            # Full documentation
├── QUICKSTART.md        # Quick start guide
├── architecture_summary.md  # Architecture deep-dive
├── improvements.md      # Proposed enhancements
├── Dockerfile           # Docker image definition
├── docker-compose.yml   # Docker Compose configuration
└── .github/             # GitHub workflows (if any)
```
