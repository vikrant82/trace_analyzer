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
from trace_analyzer import TraceAnalyzer
from trace_analyzer.web import prepare_results
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
        
        analyzer = TraceAnalyzer(
            strip_query_params=strip_query_params,
            include_gateway_services=include_gateway_services,
            include_service_mesh=include_service_mesh
        )
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
    Accepts: multipart/form-data with 'file' field and optional checkboxes:
      - 'strip_query_params': whether to strip query parameters
      - 'include_gateway_services': whether to include gateway/proxy services in counts
      - 'include_service_mesh': whether to include service mesh sidecar spans
    Returns: HTML results page
    """
    if 'file' not in request.files:
        return render_template('index.html', error='No file provided')
    
    file = request.files['file']
    
    if not file.filename:
        return render_template('index.html', error='No file selected')
    
    if not allowed_file(file.filename):
        return render_template('index.html', error='Invalid file type. Only JSON files are allowed.')
    
    strip_query_params = 'strip_query_params' in request.form
    include_gateway_services = 'include_gateway_services' in request.form
    include_service_mesh = 'include_service_mesh' in request.form
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        analyzer = TraceAnalyzer(
            strip_query_params=strip_query_params,
            include_gateway_services=include_gateway_services,
            include_service_mesh=include_service_mesh
        )
        analyzer.process_trace_file(filepath)
        
        os.remove(filepath)
        
        results = prepare_results(analyzer)
        
        return render_template('results.html', 
                             filename=filename,
                             results=results)
    
    except Exception as e:
        return render_template('index.html', error=f'Error analyzing file: {str(e)}')


if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5001)

