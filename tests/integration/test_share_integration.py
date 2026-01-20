"""Integration tests for Share API endpoints."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

# Import the Flask app
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app import app, share_storage


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_share_storage():
    """Create a temporary storage for shares and cleanup after."""
    original_storage_dir = share_storage.storage_dir
    with tempfile.TemporaryDirectory() as tmpdir:
        share_storage.storage_dir = Path(tmpdir)
        share_storage._ensure_storage_dir()
        yield tmpdir
        share_storage.storage_dir = original_storage_dir


@pytest.fixture
def sample_results():
    """Sample analysis results for testing."""
    return {
        'summary': {
            'total_requests': 100,
            'total_time_ms': 5000,
            'total_time_formatted': '5.00s',
            'unique_services': 5,
            'unique_endpoints': 10,
            'unique_combinations': 15,
            'total_kafka_operations': 0,
            'total_kafka_time_ms': 0,
            'total_kafka_time_formatted': '0ms',
            'total_traces': 1,
            'total_errors': 2
        },
        'services': {
            'summary': [],
            'details': {}
        },
        'service_calls': [],
        'kafka_operations': [],
        'error_analysis': {},
        'trace_hierarchies': {},
        'trace_summary': {}
    }


class TestCreateShareEndpoint:
    """Tests for POST /api/share endpoint."""
    
    def test_create_share_success(self, client, temp_share_storage, sample_results):
        """Should create a share and return share URL."""
        response = client.post('/api/share',
            data=json.dumps({
                'results': sample_results,
                'filename': 'test-trace.json',
                'ttl': '24h'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'share_id' in data
        assert 'share_url' in data
        assert 'expires_at' in data
        assert data['ttl_label'] == '24h'
        assert len(data['share_id']) == 8
        assert '/s/' in data['share_url']
    
    def test_create_share_with_7d_ttl(self, client, temp_share_storage, sample_results):
        """Should accept 7d TTL option."""
        response = client.post('/api/share',
            data=json.dumps({
                'results': sample_results,
                'filename': 'test.json',
                'ttl': '7d'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ttl_label'] == '7d'
    
    def test_create_share_with_1m_ttl(self, client, temp_share_storage, sample_results):
        """Should accept 1m TTL option."""
        response = client.post('/api/share',
            data=json.dumps({
                'results': sample_results,
                'filename': 'test.json',
                'ttl': '1m'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ttl_label'] == '1m'
    
    def test_create_share_default_ttl(self, client, temp_share_storage, sample_results):
        """Should use 24h as default TTL when not specified."""
        response = client.post('/api/share',
            data=json.dumps({
                'results': sample_results,
                'filename': 'test.json'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ttl_label'] == '24h'
    
    def test_create_share_invalid_ttl(self, client, temp_share_storage, sample_results):
        """Should reject invalid TTL values."""
        response = client.post('/api/share',
            data=json.dumps({
                'results': sample_results,
                'filename': 'test.json',
                'ttl': 'invalid'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'Invalid TTL' in data['error']
    
    def test_create_share_no_json(self, client, temp_share_storage):
        """Should reject request without JSON data."""
        response = client.post('/api/share',
            data='not json',
            content_type='text/plain'
        )
        
        # Should return 400 or 415 (unsupported media type) or 500
        assert response.status_code in (400, 415, 500)
    
    def test_create_share_no_results(self, client, temp_share_storage):
        """Should reject request without results."""
        response = client.post('/api/share',
            data=json.dumps({
                'filename': 'test.json',
                'ttl': '24h'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'No results provided' in data['error']


class TestViewShareEndpoint:
    """Tests for GET /s/<share_id> endpoint."""
    
    def test_view_share_success(self, client, temp_share_storage, sample_results):
        """Should render results page for valid share."""
        # First create a share
        create_response = client.post('/api/share',
            data=json.dumps({
                'results': sample_results,
                'filename': 'test-trace.json',
                'ttl': '24h'
            }),
            content_type='application/json'
        )
        share_id = create_response.get_json()['share_id']
        
        # Then view it
        response = client.get(f'/s/{share_id}')
        
        assert response.status_code == 200
        assert b'Analysis Results' in response.data
        assert b'(Shared)' in response.data
    
    def test_view_share_not_found(self, client, temp_share_storage):
        """Should return 404 for nonexistent share."""
        response = client.get('/s/nonexist')
        
        assert response.status_code == 404
        assert b'Share not found' in response.data or b'expired' in response.data


class TestGetShareAPIEndpoint:
    """Tests for GET /api/share/<share_id> endpoint."""
    
    def test_get_share_api_success(self, client, temp_share_storage, sample_results):
        """Should return JSON for valid share."""
        # Create a share
        create_response = client.post('/api/share',
            data=json.dumps({
                'results': sample_results,
                'filename': 'test-trace.json',
                'ttl': '7d'
            }),
            content_type='application/json'
        )
        share_id = create_response.get_json()['share_id']
        
        # Get it via API
        response = client.get(f'/api/share/{share_id}')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['share_id'] == share_id
        assert data['filename'] == 'test-trace.json'
        assert data['ttl_label'] == '7d'
        assert 'results' in data
        assert data['results']['summary']['total_requests'] == 100
    
    def test_get_share_api_not_found(self, client, temp_share_storage):
        """Should return 404 for nonexistent share."""
        response = client.get('/api/share/nonexist')
        
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data


class TestTTLOptionsEndpoint:
    """Tests for GET /api/ttl-options endpoint."""
    
    def test_get_ttl_options(self, client):
        """Should return available TTL options."""
        response = client.get('/api/ttl-options')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'options' in data
        assert len(data['options']) == 3
        
        values = [opt['value'] for opt in data['options']]
        assert '24h' in values
        assert '7d' in values
        assert '1m' in values
        
        # Check structure
        for opt in data['options']:
            assert 'value' in opt
            assert 'label' in opt
            assert 'seconds' in opt


class TestShareIntegration:
    """End-to-end integration tests for share feature."""
    
    def test_full_share_flow(self, client, temp_share_storage, sample_results):
        """Test complete share flow: create -> retrieve -> view."""
        # Step 1: Create share
        create_response = client.post('/api/share',
            data=json.dumps({
                'results': sample_results,
                'filename': 'production-trace.json',
                'ttl': '7d'
            }),
            content_type='application/json'
        )
        assert create_response.status_code == 200
        share_data = create_response.get_json()
        share_id = share_data['share_id']
        
        # Step 2: Retrieve via API
        api_response = client.get(f'/api/share/{share_id}')
        assert api_response.status_code == 200
        api_data = api_response.get_json()
        assert api_data['results'] == sample_results
        
        # Step 3: View in browser
        view_response = client.get(f'/s/{share_id}')
        assert view_response.status_code == 200
        assert b'production-trace.json' in view_response.data
    
    def test_multiple_shares_independent(self, client, temp_share_storage):
        """Multiple shares should be independent."""
        results1 = {'summary': {'total_requests': 100}}
        results2 = {'summary': {'total_requests': 200}}
        
        # Create two shares
        resp1 = client.post('/api/share',
            data=json.dumps({'results': results1, 'filename': 'trace1.json', 'ttl': '24h'}),
            content_type='application/json'
        )
        resp2 = client.post('/api/share',
            data=json.dumps({'results': results2, 'filename': 'trace2.json', 'ttl': '7d'}),
            content_type='application/json'
        )
        
        id1 = resp1.get_json()['share_id']
        id2 = resp2.get_json()['share_id']
        
        # Verify they're independent
        assert id1 != id2
        
        data1 = client.get(f'/api/share/{id1}').get_json()
        data2 = client.get(f'/api/share/{id2}').get_json()
        
        assert data1['results']['summary']['total_requests'] == 100
        assert data2['results']['summary']['total_requests'] == 200
