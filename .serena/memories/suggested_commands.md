# Suggested Commands

## Development Setup

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Create Virtual Environment (Recommended)
```bash
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
pip install -r requirements.txt
```

## Running the Application

### Web Application (Development Mode)
```bash
python3 app.py
# Access at http://localhost:5001
```

### CLI Analysis
```bash
# Basic usage (strips query parameters by default)
python3 analyze_trace.py trace_file.json

# Custom output file
python3 analyze_trace.py trace_file.json -o my_report.md

# Keep query parameters
python3 analyze_trace.py trace_file.json --keep-query-params

# Include gateway services
python3 analyze_trace.py trace_file.json --include-gateways

# Include service mesh spans
python3 analyze_trace.py trace_file.json --include-service-mesh

# All options
python3 analyze_trace.py trace_file.json --include-gateways --include-service-mesh -o report.md

# View help
python3 analyze_trace.py --help
```

## Docker Deployment

### Build and Run with Docker
```bash
# Build image
docker build -t trace-analyzer .

# Run container
docker run -p 5000:5000 trace-analyzer
# Access at http://localhost:5000
```

### Docker Compose
```bash
# Start service
docker-compose up --build

# Stop service
docker-compose down
```

## Testing

### Manual Testing
```bash
# Test CLI with sample file
python3 analyze_trace.py bug-archanata.json

# Test web app
python3 app.py
# Open browser to http://localhost:5001 and upload trace file
```

### API Testing
```bash
# Test REST API endpoint
curl -X POST -F "file=@trace_file.json" http://localhost:5001/api/analyze

# With options
curl -X POST \
  -F "file=@trace_file.json" \
  -F "strip_query_params=false" \
  -F "include_gateway_services=true" \
  -F "include_service_mesh=true" \
  http://localhost:5001/api/analyze
```

## Code Quality

### Check Python Syntax
```bash
python3 -m py_compile analyze_trace.py
python3 -m py_compile app.py
```

### Format Code (if using Black - not currently in requirements)
```bash
# To add Black to project:
pip install black
black analyze_trace.py app.py
```

### Lint Code (if using pylint/flake8 - not currently in requirements)
```bash
# To add linting:
pip install pylint
pylint analyze_trace.py app.py
```

## Git Commands (macOS)

### Common Git Operations
```bash
# Check status
git status

# Stage changes
git add analyze_trace.py app.py

# Commit changes
git commit -m "Description of changes"

# Push to remote
git push origin main

# Pull latest changes
git pull origin main

# View commit history
git log --oneline

# View current branch
git branch

# Create new branch
git checkout -b feature/new-feature
```

## macOS System Utilities

### File Operations
```bash
# List files
ls -la

# Find files
find . -name "*.py"

# Search in files
grep -r "TraceAnalyzer" .

# View file content
cat analyze_trace.py
head -n 20 analyze_trace.py
tail -n 20 analyze_trace.py

# File size
du -sh trace_file.json
```

### Process Management
```bash
# Find process
ps aux | grep python

# Kill process
kill <PID>
kill -9 <PID>  # Force kill

# Check port usage
lsof -i :5001
```

## Debugging

### Python Debugging
```bash
# Run with verbose output
python3 -u analyze_trace.py trace_file.json

# Interactive Python shell
python3
>>> from analyze_trace import TraceAnalyzer
>>> analyzer = TraceAnalyzer()
```

### View Logs
```bash
# Follow Flask logs
python3 app.py 2>&1 | tee app.log

# Docker logs
docker logs -f <container_id>
docker-compose logs -f
```
