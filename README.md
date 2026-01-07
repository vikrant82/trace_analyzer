# Trace Analyzer

A powerful Python tool to analyze OpenTelemetry trace files and extract HTTP endpoint performance metrics, Kafka/messaging operations, and visualize distributed system behavior.

**Available as CLI tool, Web Application, and REST API.**

---

## ✨ Features

- **Efficient Processing** - Streaming JSON parsing for large trace files
- **HTTP Analysis** - Incoming/outgoing requests, service-to-service calls
- **Kafka/Messaging** - Consumer/producer operations and metrics
- **Visual Trace Hierarchy** - Interactive tree with performance highlighting
- **Parallelism Detection** - Identifies concurrent execution patterns
- **Error Visualization** - Visual indicators for error spans
- **Smart Normalization** - Groups similar endpoints automatically
- **Service Mesh Filtering** - Eliminates Istio/Envoy duplicates

---

## 🚀 Quick Start

### 1. Install

```bash
git clone https://github.com/yourusername/trace-analyzer.git
cd trace-analyzer
pip install -r requirements.txt
```

### 2. Run

**Web Application (recommended):**
```bash
python app.py
# Open http://localhost:5001
```

**Command Line:**
```bash
python analyze_trace.py your-trace.json
```

**Docker:**
```bash
docker-compose up --build
# Open http://localhost:5000
```

### 3. Analyze

Upload a trace file (exported from Jaeger, Grafana, etc.) and explore the results!

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Quick Start](docs/QUICKSTART.md) | Get started in 3 steps |
| [User Guide](docs/USER_GUIDE.md) | CLI, Web, and API usage |
| [Visualization Guide](docs/VISUALIZATION_GUIDE.md) | Understanding visual indicators |
| [Analysis](docs/ANALYSIS.md) | Why this tool vs Jaeger/Grafana |
| [Architecture](docs/ARCHITECTURE.md) | System design and modules |
| [Testing](docs/TESTING.md) | Test suite and coverage |
| [Improvements](docs/improvements.md) | Proposed enhancements |

---

## 🔍 How It's Different

While Jaeger and Grafana excel at real-time monitoring, **Trace Analyzer is designed for deep, offline, aggregated analysis**:

| Feature | Jaeger/Grafana | Trace Analyzer |
|---------|----------------|----------------|
| Endpoint normalization | Manual | Automatic |
| Self-time calculation | Per-span | Aggregated |
| Infrastructure | Required | Single JSON file |
| Post-incident analysis | Needs live system | Works offline |

---

## 📊 Sample Output

```
📈 Summary
Total Requests: 150 | Time: 45.30s | Services: 5 | Endpoints: 12

🌳 Trace Hierarchy
api-gateway (32.4s total, 0.1s self) ⤵⤵
├── data-service → /api/users (×73) ⚡ 9.5× parallel
│   Effective: 7.2s | Cumulative: 68.8s
└── auth-service → /validate (0.5s)
```

---

## 🛠️ Configuration

See [User Guide](docs/USER_GUIDE.md) for:
- Filtering options (gateway services, service mesh)
- Parameter detection rules
- Query parameter handling
- API reference

---

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

## 🤝 Contributing

Contributions welcome! Please read the [Architecture](docs/ARCHITECTURE.md) docs first.
