"""Unit tests for ShareStorage module."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from trace_analyzer.storage import ShareStorage, ShareData, TTL_OPTIONS


class TestShareData:
    """Tests for ShareData dataclass."""
    
    def test_is_expired_returns_false_for_future_expiry(self):
        """ShareData with future expiry time should not be expired."""
        share = ShareData(
            share_id='abc12345',
            created_at=int(time.time()),
            expires_at=int(time.time()) + 3600,  # 1 hour from now
            ttl_label='24h',
            filename='test.json',
            results={'summary': {}}
        )
        assert share.is_expired() is False
    
    def test_is_expired_returns_true_for_past_expiry(self):
        """ShareData with past expiry time should be expired."""
        share = ShareData(
            share_id='abc12345',
            created_at=int(time.time()) - 7200,
            expires_at=int(time.time()) - 3600,  # 1 hour ago
            ttl_label='24h',
            filename='test.json',
            results={'summary': {}}
        )
        assert share.is_expired() is True
    
    def test_to_dict_returns_all_fields(self):
        """to_dict should return all fields."""
        share = ShareData(
            share_id='abc12345',
            created_at=1000,
            expires_at=2000,
            ttl_label='7d',
            filename='test.json',
            results={'key': 'value'}
        )
        d = share.to_dict()
        
        assert d['share_id'] == 'abc12345'
        assert d['created_at'] == 1000
        assert d['expires_at'] == 2000
        assert d['ttl_label'] == '7d'
        assert d['filename'] == 'test.json'
        assert d['results'] == {'key': 'value'}
    
    def test_from_dict_creates_share_data(self):
        """from_dict should create ShareData from dictionary."""
        data = {
            'share_id': 'xyz98765',
            'created_at': 1000,
            'expires_at': 2000,
            'ttl_label': '1m',
            'filename': 'trace.json',
            'results': {'summary': {'total': 100}}
        }
        share = ShareData.from_dict(data)
        
        assert share.share_id == 'xyz98765'
        assert share.created_at == 1000
        assert share.expires_at == 2000
        assert share.ttl_label == '1m'
        assert share.filename == 'trace.json'
        assert share.results == {'summary': {'total': 100}}


class TestShareStorage:
    """Tests for ShareStorage class."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def storage(self, temp_storage_dir):
        """Create a ShareStorage instance with temp directory."""
        return ShareStorage(storage_dir=temp_storage_dir)
    
    def test_init_creates_storage_directory(self, temp_storage_dir):
        """Storage should create directory if it doesn't exist."""
        storage_path = os.path.join(temp_storage_dir, 'nested', 'shares')
        storage = ShareStorage(storage_dir=storage_path)
        
        assert os.path.exists(storage_path)
        assert os.path.isdir(storage_path)
    
    def test_init_creates_gitkeep(self, temp_storage_dir):
        """Storage should create .gitkeep file."""
        storage = ShareStorage(storage_dir=temp_storage_dir)
        gitkeep = os.path.join(temp_storage_dir, '.gitkeep')
        
        assert os.path.exists(gitkeep)
    
    def test_create_share_returns_share_id_and_data(self, storage):
        """create_share should return share_id and ShareData."""
        results = {'summary': {'total_requests': 10}}
        
        share_id, share_data = storage.create_share(
            results=results,
            filename='test.json',
            ttl='24h'
        )
        
        assert isinstance(share_id, str)
        assert len(share_id) == 8
        assert isinstance(share_data, ShareData)
        assert share_data.share_id == share_id
        assert share_data.filename == 'test.json'
        assert share_data.ttl_label == '24h'
        assert share_data.results == results
    
    def test_create_share_generates_unique_ids(self, storage):
        """create_share should generate unique IDs."""
        ids = set()
        for _ in range(10):
            share_id, _ = storage.create_share(
                results={},
                filename='test.json',
                ttl='24h'
            )
            ids.add(share_id)
        
        assert len(ids) == 10  # All IDs should be unique
    
    def test_create_share_with_different_ttls(self, storage):
        """create_share should accept all valid TTL options."""
        for ttl in TTL_OPTIONS.keys():
            share_id, share_data = storage.create_share(
                results={},
                filename='test.json',
                ttl=ttl
            )
            
            assert share_data.ttl_label == ttl
            expected_duration = TTL_OPTIONS[ttl]
            actual_duration = share_data.expires_at - share_data.created_at
            assert actual_duration == expected_duration
    
    def test_create_share_raises_for_invalid_ttl(self, storage):
        """create_share should raise ValueError for invalid TTL."""
        with pytest.raises(ValueError, match="Invalid TTL"):
            storage.create_share(
                results={},
                filename='test.json',
                ttl='invalid'
            )
    
    def test_create_share_writes_file(self, storage, temp_storage_dir):
        """create_share should write JSON file."""
        share_id, _ = storage.create_share(
            results={'key': 'value'},
            filename='test.json',
            ttl='7d'
        )
        
        filepath = os.path.join(temp_storage_dir, f'{share_id}.json')
        assert os.path.exists(filepath)
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        assert data['share_id'] == share_id
        assert data['filename'] == 'test.json'
        assert data['results'] == {'key': 'value'}
    
    def test_get_share_returns_share_data(self, storage):
        """get_share should return ShareData for valid share."""
        share_id, original = storage.create_share(
            results={'test': 'data'},
            filename='trace.json',
            ttl='24h'
        )
        
        retrieved = storage.get_share(share_id)
        
        assert retrieved is not None
        assert retrieved.share_id == original.share_id
        assert retrieved.filename == original.filename
        assert retrieved.results == original.results
    
    def test_get_share_returns_none_for_nonexistent(self, storage):
        """get_share should return None for nonexistent share."""
        result = storage.get_share('nonexistent')
        assert result is None
    
    def test_get_share_returns_none_for_expired(self, storage, temp_storage_dir):
        """get_share should return None for expired share."""
        # Create an expired share manually
        share_id = 'expired1'
        expired_data = {
            'share_id': share_id,
            'created_at': int(time.time()) - 7200,
            'expires_at': int(time.time()) - 3600,  # Expired 1 hour ago
            'ttl_label': '24h',
            'filename': 'old.json',
            'results': {}
        }
        
        filepath = os.path.join(temp_storage_dir, f'{share_id}.json')
        with open(filepath, 'w') as f:
            json.dump(expired_data, f)
        
        result = storage.get_share(share_id)
        
        assert result is None
        assert not os.path.exists(filepath)  # File should be deleted
    
    def test_get_share_handles_corrupted_file(self, storage, temp_storage_dir):
        """get_share should return None for corrupted file."""
        share_id = 'corrupt1'
        filepath = os.path.join(temp_storage_dir, f'{share_id}.json')
        
        with open(filepath, 'w') as f:
            f.write('not valid json {{{')
        
        result = storage.get_share(share_id)
        
        assert result is None
        assert not os.path.exists(filepath)  # File should be deleted
    
    def test_cleanup_expired_removes_old_files(self, storage, temp_storage_dir):
        """cleanup_expired should remove expired files."""
        # Create an expired share
        expired_data = {
            'share_id': 'expired1',
            'created_at': int(time.time()) - 7200,
            'expires_at': int(time.time()) - 3600,
            'ttl_label': '24h',
            'filename': 'old.json',
            'results': {}
        }
        filepath1 = os.path.join(temp_storage_dir, 'expired1.json')
        with open(filepath1, 'w') as f:
            json.dump(expired_data, f)
        
        # Create a valid share
        share_id, _ = storage.create_share(
            results={},
            filename='new.json',
            ttl='24h'
        )
        filepath2 = os.path.join(temp_storage_dir, f'{share_id}.json')
        
        deleted_count = storage.cleanup_expired()
        
        assert deleted_count == 1
        assert not os.path.exists(filepath1)
        assert os.path.exists(filepath2)
    
    def test_list_shares_returns_active_shares(self, storage):
        """list_shares should return only active shares."""
        # Create some shares
        storage.create_share(results={}, filename='file1.json', ttl='24h')
        storage.create_share(results={}, filename='file2.json', ttl='7d')
        
        shares = storage.list_shares()
        
        assert len(shares) == 2
        assert all('share_id' in s for s in shares)
        assert all('filename' in s for s in shares)
        assert all('results' not in s for s in shares)  # Should not include full results
    
    def test_list_shares_sorted_by_created_at_descending(self, storage):
        """list_shares should be sorted newest first."""
        # Create shares with slight delay
        storage.create_share(results={}, filename='first.json', ttl='24h')
        time.sleep(0.1)
        storage.create_share(results={}, filename='second.json', ttl='24h')
        
        shares = storage.list_shares()
        
        assert shares[0]['filename'] == 'second.json'
        assert shares[1]['filename'] == 'first.json'
    
    def test_get_stats_returns_storage_statistics(self, storage):
        """get_stats should return storage statistics."""
        storage.create_share(results={'data': 'x' * 1000}, filename='f1.json', ttl='24h')
        storage.create_share(results={'data': 'y' * 1000}, filename='f2.json', ttl='7d')
        
        stats = storage.get_stats()
        
        assert stats['total_shares'] == 2
        assert stats['total_size_bytes'] > 0
        assert stats['active_count'] == 2
        assert stats['expired_count'] == 0


class TestTTLOptions:
    """Tests for TTL configuration."""
    
    def test_ttl_options_has_required_keys(self):
        """TTL_OPTIONS should have all required keys."""
        assert '24h' in TTL_OPTIONS
        assert '7d' in TTL_OPTIONS
        assert '1m' in TTL_OPTIONS
    
    def test_ttl_values_are_correct(self):
        """TTL values should be correct in seconds."""
        assert TTL_OPTIONS['24h'] == 86400
        assert TTL_OPTIONS['7d'] == 604800
        assert TTL_OPTIONS['1m'] == 2592000
