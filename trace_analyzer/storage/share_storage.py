"""
Share storage module for persisting and retrieving shared analysis results.

This module provides file-based storage for shared trace analysis results,
with configurable TTL (time-to-live) and automatic cleanup of expired shares.
"""

import json
import os
import secrets
import string
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# TTL options in seconds
TTL_OPTIONS: Dict[str, int] = {
    '24h': 86400,       # 24 hours
    '7d': 604800,       # 7 days
    '1m': 2592000,      # 30 days (1 month)
}

# Short ID character set (alphanumeric, no ambiguous chars like 0/O, 1/l)
ID_CHARS = string.ascii_lowercase + string.digits
ID_CHARS = ID_CHARS.replace('0', '').replace('o', '').replace('l', '').replace('1', '')
ID_LENGTH = 8


@dataclass
class ShareData:
    """Data structure for a shared analysis result."""
    share_id: str
    created_at: int
    expires_at: int
    ttl_label: str
    filename: str
    results: Dict[str, Any]
    
    def is_expired(self) -> bool:
        """Check if this share has expired."""
        return time.time() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'share_id': self.share_id,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'ttl_label': self.ttl_label,
            'filename': self.filename,
            'results': self.results,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShareData':
        """Create ShareData from dictionary."""
        return cls(
            share_id=data['share_id'],
            created_at=data['created_at'],
            expires_at=data['expires_at'],
            ttl_label=data['ttl_label'],
            filename=data['filename'],
            results=data['results'],
        )


class ShareStorage:
    """
    File-based storage for shared analysis results.
    
    Files are stored as: shares/{share_id}.json
    Each file contains metadata (timestamps, TTL) and the full results JSON.
    
    Args:
        storage_dir: Directory path for storing share files
    """
    
    def __init__(self, storage_dir: str = 'shares'):
        self.storage_dir = Path(storage_dir)
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self) -> None:
        """Create storage directory if it doesn't exist."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Create .gitkeep to ensure directory is tracked
        gitkeep = self.storage_dir / '.gitkeep'
        if not gitkeep.exists():
            gitkeep.touch()
    
    def _generate_share_id(self) -> str:
        """Generate a unique 8-character alphanumeric share ID."""
        while True:
            share_id = ''.join(secrets.choice(ID_CHARS) for _ in range(ID_LENGTH))
            if not self._get_share_path(share_id).exists():
                return share_id
    
    def _get_share_path(self, share_id: str) -> Path:
        """Get the file path for a share ID."""
        return self.storage_dir / f'{share_id}.json'
    
    def create_share(
        self, 
        results: Dict[str, Any], 
        filename: str, 
        ttl: str = '24h'
    ) -> Tuple[str, ShareData]:
        """
        Create a new share from analysis results.
        
        Args:
            results: The analysis results dictionary from prepare_results()
            filename: Original filename that was analyzed
            ttl: TTL label ('24h', '7d', or '1m')
            
        Returns:
            Tuple of (share_id, ShareData)
            
        Raises:
            ValueError: If TTL is invalid
        """
        if ttl not in TTL_OPTIONS:
            raise ValueError(f"Invalid TTL '{ttl}'. Must be one of: {list(TTL_OPTIONS.keys())}")
        
        share_id = self._generate_share_id()
        created_at = int(time.time())
        expires_at = created_at + TTL_OPTIONS[ttl]
        
        share_data = ShareData(
            share_id=share_id,
            created_at=created_at,
            expires_at=expires_at,
            ttl_label=ttl,
            filename=filename,
            results=results,
        )
        
        # Write to file
        share_path = self._get_share_path(share_id)
        with open(share_path, 'w', encoding='utf-8') as f:
            json.dump(share_data.to_dict(), f, indent=2)
        
        return share_id, share_data
    
    def get_share(self, share_id: str) -> Optional[ShareData]:
        """
        Retrieve a share by ID.
        
        Args:
            share_id: The share ID to retrieve
            
        Returns:
            ShareData if found and not expired, None otherwise
        """
        share_path = self._get_share_path(share_id)
        
        if not share_path.exists():
            return None
        
        try:
            with open(share_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            share_data = ShareData.from_dict(data)
            
            # Check if expired
            if share_data.is_expired():
                # Clean up expired file
                self._delete_share_file(share_id)
                return None
            
            return share_data
            
        except (json.JSONDecodeError, KeyError):
            # Corrupted file, delete it
            self._delete_share_file(share_id)
            return None
    
    def _delete_share_file(self, share_id: str) -> bool:
        """Delete a share file."""
        share_path = self._get_share_path(share_id)
        try:
            if share_path.exists():
                share_path.unlink()
                return True
        except OSError:
            pass
        return False
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired share files.
        
        Returns:
            Number of files deleted
        """
        deleted_count = 0
        current_time = time.time()
        
        for share_file in self.storage_dir.glob('*.json'):
            try:
                with open(share_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                expires_at = data.get('expires_at', 0)
                if current_time > expires_at:
                    share_file.unlink()
                    deleted_count += 1
                    
            except (json.JSONDecodeError, KeyError, OSError):
                # Corrupted file, delete it
                try:
                    share_file.unlink()
                    deleted_count += 1
                except OSError:
                    pass
        
        return deleted_count
    
    def list_shares(self) -> List[Dict[str, Any]]:
        """
        List all active (non-expired) shares.
        
        Returns:
            List of share metadata (without full results)
        """
        shares = []
        current_time = time.time()
        
        for share_file in self.storage_dir.glob('*.json'):
            try:
                with open(share_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                expires_at = data.get('expires_at', 0)
                if current_time <= expires_at:
                    shares.append({
                        'share_id': data.get('share_id'),
                        'created_at': data.get('created_at'),
                        'expires_at': expires_at,
                        'ttl_label': data.get('ttl_label'),
                        'filename': data.get('filename'),
                    })
            except (json.JSONDecodeError, KeyError, OSError):
                pass
        
        return sorted(shares, key=lambda x: x.get('created_at', 0), reverse=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Dictionary with storage stats
        """
        total_files = 0
        total_size = 0
        expired_count = 0
        current_time = time.time()
        
        for share_file in self.storage_dir.glob('*.json'):
            total_files += 1
            total_size += share_file.stat().st_size
            
            try:
                with open(share_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if current_time > data.get('expires_at', 0):
                    expired_count += 1
            except:
                expired_count += 1
        
        return {
            'total_shares': total_files,
            'total_size_bytes': total_size,
            'expired_count': expired_count,
            'active_count': total_files - expired_count,
        }
