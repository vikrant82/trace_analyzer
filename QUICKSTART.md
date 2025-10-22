# Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Choose Your Method

#### Method A: Web Application (Easiest)

```bash
# Start the server
python app.py

# Open in browser
# http://localhost:5000
```

Then:
1. Upload your trace JSON file
2. Click "Analyze"
3. View beautiful interactive results!

#### Method B: Command Line

```bash
# Analyze and generate markdown report
python analyze_trace.py your_trace_file.json

# View the report
cat trace_analysis.md
```

### Step 3: Explore Results

The analysis shows:
- 📊 **Incoming Requests**: What endpoints each service receives
- 🔗 **Service Calls**: Which services call each other
- ⏱️ **Performance**: Total time spent on each endpoint
- 📈 **Statistics**: Request counts and timing data

**Everything sorted by total time** - see your slowest endpoints first!

## 🌐 Web Interface Features

- **Interactive Dashboard**: Visual stats and tables
- **Search & Filter**: Find specific endpoints quickly
- **Responsive Design**: Works on desktop and mobile
- **REST API**: Programmatic access for automation

## 📝 CLI Features

- **Markdown Output**: Clean, readable reports
- **Fast Processing**: Streaming JSON parser for large files
- **Flexible**: Customize output filename
- **Lightweight**: No web server needed

## 💡 Pro Tips

1. **Large Files**: The tool uses streaming parsing - no file size limits!
2. **Automation**: Use the REST API to integrate with CI/CD pipelines
3. **Analysis**: Focus on endpoints with highest total time for optimization
4. **Service Dependencies**: Check the Service-to-Service calls section

## 🆘 Need Help?

Check the full [README.md](README.md) for detailed documentation on:
- Feature descriptions
- API endpoints
- Configuration options
- Parameter detection rules
- Performance details

