#!/usr/bin/env python3
"""
Flask Web Application for Trace Endpoint Analyzer
Provides both a web UI and REST API endpoints for analyzing HTTP and Kafka trace operations.
"""

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import tempfile
import json
import logging
import time
from trace_analyzer import TraceAnalyzer
from trace_analyzer.web import prepare_results
from collections import defaultdict

# Configure logger
logger = logging.getLogger('trace_analyzer')
logger.setLevel(os.environ.get('TRACE_ANALYZER_LOG_LEVEL', 'INFO').upper())
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-5s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(handler)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

ALLOWED_EXTENSIONS = {'json'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def get_analysis_summary(analyzer: TraceAnalyzer) -> dict:
    """Extract summary metrics from analyzer for logging."""
    trace_count = len(analyzer.traces) if analyzer.traces else 0
    span_count = sum(len(spans) for spans in analyzer.traces.values()) if analyzer.traces else 0
    service_count = len(set(
        v.get('service', 'unknown') 
        for d in [analyzer.endpoint_params, analyzer.service_calls, analyzer.kafka_messages]
        for v in d.values()
    ))
    endpoint_count = len(analyzer.endpoint_params) + len(analyzer.service_calls) + len(analyzer.kafka_messages)
    error_count = sum(
        v['error_count'] 
        for d in [analyzer.endpoint_params, analyzer.service_calls, analyzer.kafka_messages]
        for v in d.values()
    )
    return {
        'traces': trace_count,
        'spans': span_count,
        'services': service_count,
        'endpoints': endpoint_count,
        'errors': error_count
    }


SAMPLE_TRACES = {
    'basic': {
        'file': 'sample-trace.json',
        'name': 'Basic Trace',
        'description': 'Simple service-to-service call chain'
    },
    'parallel': {
        'file': 'sample-trace-parallel.json',
        'name': 'Parallel Calls',
        'description': 'Trace with parallel downstream calls'
    },
    'parallel-siblings': {
        'file': 'sample-trace-parallel-siblings.json',
        'name': 'Parallel Siblings',
        'description': 'Trace with parallel sibling spans'
    }
}


@app.route('/')
def index():
    """Main page with file upload form."""
    return render_template('index.html', sample_traces=SAMPLE_TRACES)


@app.route('/analyze/sample/<sample_name>', methods=['GET', 'POST'])
def analyze_sample(sample_name: str):
    """
    Analyze a pre-loaded sample trace file.
    
    Args:
        sample_name: Key identifying the sample trace (basic, parallel, parallel-siblings)
    
    Returns:
        HTML results page or error
    """
    if sample_name not in SAMPLE_TRACES:
        return render_template('index.html', 
                             sample_traces=SAMPLE_TRACES,
                             error=f'Unknown sample trace: {sample_name}')
    
    sample = SAMPLE_TRACES[sample_name]
    filepath = os.path.join(os.path.dirname(__file__), sample['file'])
    
    if not os.path.exists(filepath):
        return render_template('index.html',
                             sample_traces=SAMPLE_TRACES,
                             error=f'Sample file not found: {sample["file"]}')
    
    strip_query_params = request.args.get('strip_query_params', 'true').lower() == 'true'
    include_gateway_services = request.args.get('include_gateway_services', 'false').lower() == 'true'
    include_service_mesh = request.args.get('include_service_mesh', 'false').lower() == 'true'
    
    file_size = os.path.getsize(filepath)
    start_time = time.perf_counter()
    
    logger.info(
        f"TRACE_REQUEST_START | file={sample['file']} | size={format_file_size(file_size)} | "
        f"type=sample | client={request.remote_addr}"
    )
    
    try:
        analyzer = TraceAnalyzer(
            strip_query_params=strip_query_params,
            include_gateway_services=include_gateway_services,
            include_service_mesh=include_service_mesh
        )
        analyzer.process_trace_file(filepath)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        summary = get_analysis_summary(analyzer)
        logger.info(
            f"TRACE_REQUEST_END | file={sample['file']} | duration={duration_ms:,.0f}ms | "
            f"traces={summary['traces']} | spans={summary['spans']} | "
            f"services={summary['services']} | endpoints={summary['endpoints']} | errors={summary['errors']}"
        )
        
        results = prepare_results(analyzer)
        
        return render_template('results.html',
                             filename=f"{sample['name']} ({sample['file']})",
                             results=results)
    
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            f"TRACE_REQUEST_FAIL | file={sample['file']} | duration={duration_ms:,.0f}ms | "
            f"error={type(e).__name__}: {str(e)}"
        )
        return render_template('index.html',
                             sample_traces=SAMPLE_TRACES,
                             error=f'Error analyzing sample: {str(e)}')


@app.route('/api/analyze', methods=['POST'])
def analyze_api():
    """
    API endpoint to analyze a trace file.
    Accepts: multipart/form-data with fields:
      - 'file': trace JSON file
      - 'strip_query_params': 'true'|'false' (optional, default: 'true')
      - 'include_gateway_services': 'true'|'false' (optional, default: 'false')
      - 'include_service_mesh': 'true'|'false' (optional, default: 'false')
    Returns: JSON with analysis results
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only JSON files are allowed.'}), 400
    
    strip_query_params = request.form.get('strip_query_params', 'true').lower() == 'true'
    include_gateway_services = request.form.get('include_gateway_services', 'false').lower() == 'true'
    include_service_mesh = request.form.get('include_service_mesh', 'false').lower() == 'true'
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        file_size = os.path.getsize(filepath)
        start_time = time.perf_counter()
        
        logger.info(
            f"TRACE_REQUEST_START | file={filename} | size={format_file_size(file_size)} | "
            f"type=api | client={request.remote_addr}"
        )
        
        analyzer = TraceAnalyzer(
            strip_query_params=strip_query_params,
            include_gateway_services=include_gateway_services,
            include_service_mesh=include_service_mesh
        )
        analyzer.process_trace_file(filepath)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        summary = get_analysis_summary(analyzer)
        logger.info(
            f"TRACE_REQUEST_END | file={filename} | duration={duration_ms:,.0f}ms | "
            f"traces={summary['traces']} | spans={summary['spans']} | "
            f"services={summary['services']} | endpoints={summary['endpoints']} | errors={summary['errors']}"
        )
        
        os.remove(filepath)
        
        results = prepare_results(analyzer)
        
        return jsonify(results)
    
    except Exception as e:
        if 'start_time' in locals():
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"TRACE_REQUEST_FAIL | file={filename} | duration={duration_ms:,.0f}ms | "
                f"error={type(e).__name__}: {str(e)}"
            )
        return jsonify({'error': str(e)}), 500


@app.route('/analyze', methods=['POST'])
def analyze_web():
    """
    Web endpoint to analyze a trace file.
    Accepts: multipart/form-data with 'file' field and optional checkboxes:
      - 'strip_query_params': whether to strip query parameters
      - 'include_gateway_services': whether to include gateway/proxy services in counts
      - 'include_service_mesh': whether to include service mesh sidecar spans
    Returns: HTML results page
    """
    if 'file' not in request.files:
        return render_template('index.html', sample_traces=SAMPLE_TRACES, error='No file provided')
    
    file = request.files['file']
    
    if not file.filename:
        return render_template('index.html', sample_traces=SAMPLE_TRACES, error='No file selected')
    
    if not allowed_file(file.filename):
        return render_template('index.html', sample_traces=SAMPLE_TRACES, error='Invalid file type. Only JSON files are allowed.')
    
    strip_query_params = 'strip_query_params' in request.form
    include_gateway_services = 'include_gateway_services' in request.form
    include_service_mesh = 'include_service_mesh' in request.form
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        file_size = os.path.getsize(filepath)
        start_time = time.perf_counter()
        
        logger.info(
            f"TRACE_REQUEST_START | file={filename} | size={format_file_size(file_size)} | "
            f"type=web | client={request.remote_addr}"
        )
        
        analyzer = TraceAnalyzer(
            strip_query_params=strip_query_params,
            include_gateway_services=include_gateway_services,
            include_service_mesh=include_service_mesh
        )
        analyzer.process_trace_file(filepath)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        summary = get_analysis_summary(analyzer)
        logger.info(
            f"TRACE_REQUEST_END | file={filename} | duration={duration_ms:,.0f}ms | "
            f"traces={summary['traces']} | spans={summary['spans']} | "
            f"services={summary['services']} | endpoints={summary['endpoints']} | errors={summary['errors']}"
        )
        
        os.remove(filepath)
        
        results = prepare_results(analyzer)
        
        return render_template('results.html', 
                             filename=filename,
                             results=results)
    
    except Exception as e:
        if 'start_time' in locals():
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"TRACE_REQUEST_FAIL | file={filename} | duration={duration_ms:,.0f}ms | "
                f"error={type(e).__name__}: {str(e)}"
            )
        return render_template('index.html', sample_traces=SAMPLE_TRACES, error=f'Error analyzing file: {str(e)}')


if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5001)

