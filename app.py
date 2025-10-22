#!/usr/bin/env python3
"""
Flask Web Application for Trace Endpoint Analyzer
Provides both a web UI and REST API endpoints for analyzing trace files.
"""

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import tempfile
import json
from analyze_trace import TraceAnalyzer
from collections import defaultdict

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

ALLOWED_EXTENSIONS = {'json'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Main page with file upload form."""
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze_api():
    """
    API endpoint to analyze a trace file.
    Accepts: multipart/form-data with 'file' field and optional 'strip_query_params' field
    Returns: JSON with analysis results
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only JSON files are allowed.'}), 400
    
    strip_query_params = request.form.get('strip_query_params', 'true').lower() == 'true'
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        analyzer = TraceAnalyzer(strip_query_params=strip_query_params)
        analyzer.process_trace_file(filepath)
        
        os.remove(filepath)
        
        results = prepare_results(analyzer)
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/analyze', methods=['POST'])
def analyze_web():
    """
    Web endpoint to analyze a trace file.
    Accepts: multipart/form-data with 'file' field and optional 'strip_query_params' checkbox
    Returns: HTML results page
    """
    if 'file' not in request.files:
        return render_template('index.html', error='No file provided')
    
    file = request.files['file']
    
    if file.filename == '':
        return render_template('index.html', error='No file selected')
    
    if not allowed_file(file.filename):
        return render_template('index.html', error='Invalid file type. Only JSON files are allowed.')
    
    strip_query_params = 'strip_query_params' in request.form
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        analyzer = TraceAnalyzer(strip_query_params=strip_query_params)
        analyzer.process_trace_file(filepath)
        
        os.remove(filepath)
        
        results = prepare_results(analyzer)
        
        return render_template('results.html', 
                             filename=filename,
                             results=results)
    
    except Exception as e:
        return render_template('index.html', error=f'Error analyzing file: {str(e)}')


def prepare_results(analyzer):
    """Convert analyzer results to a structured format for JSON/HTML output."""
    services_data = defaultdict(list)
    for (service, endpoint, param), stats in analyzer.endpoint_params.items():
        services_data[service].append({
            'endpoint': endpoint,
            'parameter': param,
            'count': stats['count'],
            'total_time_ms': stats['total_time_ms'],
            'total_time_formatted': analyzer.format_time(stats['total_time_ms'])
        })
    
    for service in services_data:
        services_data[service].sort(key=lambda x: -x['total_time_ms'])
    
    services_summary = []
    for service, endpoints in services_data.items():
        total_count = sum(e['count'] for e in endpoints)
        total_time = sum(e['total_time_ms'] for e in endpoints)
        services_summary.append({
            'name': service,
            'request_count': total_count,
            'total_time_ms': total_time,
            'total_time_formatted': analyzer.format_time(total_time),
            'unique_combinations': len(endpoints)
        })
    
    services_summary.sort(key=lambda x: -x['total_time_ms'])
    
    service_calls = defaultdict(list)
    for (caller, callee, endpoint, param), stats in analyzer.service_calls.items():
        service_calls[(caller, callee)].append({
            'endpoint': endpoint,
            'parameter': param,
            'count': stats['count'],
            'total_time_ms': stats['total_time_ms'],
            'total_time_formatted': analyzer.format_time(stats['total_time_ms'])
        })
    
    service_calls_list = []
    for (caller, callee), calls in service_calls.items():
        calls.sort(key=lambda x: -x['total_time_ms'])
        total_count = sum(c['count'] for c in calls)
        total_time = sum(c['total_time_ms'] for c in calls)
        
        service_calls_list.append({
            'caller': caller,
            'callee': callee,
            'total_calls': total_count,
            'total_time_ms': total_time,
            'total_time_formatted': analyzer.format_time(total_time),
            'calls': calls
        })
    
    service_calls_list.sort(key=lambda x: -x['total_time_ms'])
    
    total_requests = sum(stats['count'] for stats in analyzer.endpoint_params.values())
    total_time_ms = sum(stats['total_time_ms'] for stats in analyzer.endpoint_params.values())
    
    return {
        'summary': {
            'total_requests': total_requests,
            'total_time_ms': total_time_ms,
            'total_time_formatted': analyzer.format_time(total_time_ms),
            'unique_services': len(services_data),
            'unique_endpoints': len(set((k[0], k[1]) for k in analyzer.endpoint_params.keys())),
            'unique_combinations': len(analyzer.endpoint_params)
        },
        'services': {
            'summary': services_summary,
            'details': dict(services_data)
        },
        'service_calls': service_calls_list
    }


if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)

