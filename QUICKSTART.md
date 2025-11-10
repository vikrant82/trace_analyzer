# Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Choose Your Setup

#### Option A: Traditional Installation

```bash
pip install -r requirements.txt
```

#### Option B: Docker (Recommended)

```bash
docker build -t trace-analyzer .
# or
docker-compose up --build
```

### Step 2: Choose Your Method

#### Method A: Web Application (Easiest)

**With Python:**
```bash
python app.py
# Open http://localhost:5000
```

**With Docker:**
```bash
docker run -p 5000:5000 trace-analyzer
# or
docker-compose up
# Open http://localhost:5000
```

Then:
1. Upload your trace JSON file
2. Click "Analyze"
3. View beautiful interactive results!

#### Method B: Command Line (Python only)

```bash
# Analyze and generate markdown report
python analyze_trace.py your_trace_file.json

# View the report
cat trace_analysis.md
```

### Step 3: Explore Results

The analysis shows:
- 📊 **Summary Statistics**: Overview of total requests, time, services, and endpoints
- 🌲 **Trace Hierarchy**: Interactive visual tree showing complete request flow with dynamic highlighting
  - Adjust the slider (5-95%) to highlight bottlenecks contributing to total trace time
  - Default 10% threshold highlights significant contributors
  - Expand/collapse nodes to explore deep traces
- 📊 **Incoming Requests**: What HTTP endpoints each service receives
- 🔗 **Service Calls**: Which services call each other via HTTP
- 📨 **Kafka Operations**: Message consumer/producer operations and processing
- ⏱️ **Performance**: Total time and self-time spent on each endpoint/operation
- 📈 **Statistics**: Request counts and timing data

**Everything sorted by total time** - see your slowest operations first!

## 🌐 Web Interface Features

- **Interactive Trace Hierarchy**: Visual tree with expand/collapse and dynamic highlighting
- **Adjustable Highlighting**: Slider control (5-95%) to identify bottlenecks in real-time
- **Interactive Dashboard**: Visual stats and tables
- **Search & Filter**: Find specific endpoints quickly
- **Responsive Design**: Works on desktop and mobile
- **REST API**: Programmatic access for automation
- **Sortable Tables**: Click column headers to sort by time or count
- **Smart Filtering**: Optional gateway services and service mesh span controls

## 📝 CLI Features

- **Markdown Output**: Clean, readable reports
- **Fast Processing**: Streaming JSON parser for large files
- **Flexible**: Customize output filename
- **Lightweight**: No web server needed

## 💡 Pro Tips

1. **Large Files**: The tool uses streaming parsing - no file size limits!
2. **Docker**: Use `docker-compose up` for fastest deployment
3. **Automation**: Use the REST API to integrate with CI/CD pipelines
4. **Analysis**: Focus on endpoints with highest total time for optimization
5. **Service Dependencies**: Check the Service-to-Service calls section
6. **Query Parameters**: Use `--keep-query-params` flag to preserve URL query strings

## 🆘 Need Help?

Check the full [README.md](README.md) for detailed documentation on:
- Feature descriptions
- API endpoints
- Configuration options
- Parameter detection rules
- Docker deployment
- Performance details

