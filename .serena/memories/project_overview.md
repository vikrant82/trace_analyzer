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
- Shareable analysis links with configurable TTL (24h, 7d, 1m)

## Project Structure (Modular Architecture)

### Main Entry Points
- `analyze_trace.py` - CLI facade (59 lines, backward-compatible)
- `app.py` - Flask web application (127 lines)

### Core Package (`trace_analyzer/`)

#### Core (`trace_analyzer/core/`)
- `types.py` - Type definitions and data structures
- `analyzer.py` - Main TraceAnalyzer orchestration class (70 statements, 83% coverage)

#### Extractors (`trace_analyzer/extractors/`)
- `http_extractor.py` - HTTP endpoint extraction and classification
- `kafka_extractor.py` - Kafka/messaging operation detection
- `path_normalizer.py` - URL parameter normalization (96% coverage)

#### Processors (`trace_analyzer/processors/`)
- `file_processor.py` - Streaming JSON file reading (91% coverage)
- `hierarchy_builder.py` - Builds span parent-child relationships (87% coverage)
- `timing_calculator.py` - Calculates total and self-time (94% coverage)
- `normalizer.py` - Normalizes HTTP/Kafka operations (96% coverage)
- `aggregator.py` - Aggregates metrics per endpoint (84% coverage)
- `metrics_populator.py` - Populates final metric structures (85% coverage)

#### Filters (`trace_analyzer/filters/`)
- `service_mesh_filter.py` - Eliminates Istio/Envoy duplicates

#### Formatters (`trace_analyzer/formatters/`)
- `time_formatter.py` - Formats timing values (100% test coverage)

#### Web (`trace_analyzer/web/`)
- `result_builder.py` - Builds web response data structures

#### Storage (`trace_analyzer/storage/`)
- `share_storage.py` - File-based storage for shared analysis results (87% coverage)

### Supporting Files
```
templates/           # Jinja2 HTML templates
static/             # CSS styling
requirements.txt    # Python dependencies
pytest.ini          # Test configuration
sample-trace.json   # Generic example trace (non-proprietary)
test-trace.json     # Real-world trace for testing
```

### Documentation
- `README.md` - Project introduction and quick links
- `docs/QUICKSTART.md` - Quick start guide
- `docs/USER_GUIDE.md` - CLI, Web, and API usage
- `docs/VISUALIZATION_GUIDE.md` - Visual indicators guide
- `docs/TESTING.md` - Comprehensive testing guide
- `docs/ARCHITECTURE.md` - Architecture deep-dive
- `docs/ANALYSIS.md` - Analysis algorithms
- `docs/improvements.md` - Proposed enhancements

### Tests (`tests/`)
```
tests/
├── conftest.py              # 9 shared fixtures
├── unit/                    # 52 unit tests (5 files)
└── integration/             # 7 integration tests (100% passing)
```

## Refactoring Achievement
- **Before**: 1,033-line monolithic analyze_trace.py
- **After**: 14 modular files across 6 subdirectories
- **Backward Compatibility**: Original CLI and web interfaces unchanged
- **Test Coverage**: 79% with comprehensive test suite (145 tests)
- **Lines of Code**: analyze_trace.py: 1,033 → 59 lines

