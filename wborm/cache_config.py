"""
Cache Configuration and Management

This module provides a configurable caching system for query results,
supporting multiple storage backends, TTL configuration, and cache invalidation.

Features:
- Configurable TTL (time-to-live) per cache or globally
- Multiple storage backends (memory, LRU, disk)
- Cache statistics and monitoring
- Manual invalidation and clearing
- Per-query cache overrides
"""

import time
import os
import pickle
import tempfile
from typing import Any, Optional, Dict, Tuple, Callable
from collections import OrderedDict
from hashlib import sha256


class CacheBackend:
    """Base class for cache storage backends"""

    def get(self, key: str) -> Optional[Tuple[Any, float]]:
        """
        Retrieve value and timestamp from cache.

        Args:
            key: Cache key

        Returns:
            Tuple of (value, timestamp) or None if not found
        """
        raise NotImplementedError

    def set(self, key: str, value: Any, timestamp: float) -> None:
        """
        Store value with timestamp in cache.

        Args:
            key: Cache key
            value: Value to cache
            timestamp: Timestamp when cached
        """
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        """
        Remove specific key from cache.

        Args:
            key: Cache key to remove

        Returns:
            True if deleted, False if not found
        """
        raise NotImplementedError

    def clear(self) -> None:
        """Clear all cached entries"""
        raise NotImplementedError

    def size(self) -> int:
        """Return number of cached entries"""
        raise NotImplementedError


class MemoryCacheBackend(CacheBackend):
    """Simple dictionary-based in-memory cache backend"""

    def __init__(self, max_size: Optional[int] = None):
        """
        Initialize memory cache backend.

        Args:
            max_size: Maximum number of entries (None = unlimited)
        """
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self.max_size = max_size

    def get(self, key: str) -> Optional[Tuple[Any, float]]:
        return self._cache.get(key)

    def set(self, key: str, value: Any, timestamp: float) -> None:
        # If max_size reached, remove oldest entry
        if self.max_size and len(self._cache) >= self.max_size:
            if key not in self._cache:  # Only evict if adding new key
                oldest_key = min(self._cache.keys(),
                               key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]

        self._cache[key] = (value, timestamp)

    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)


class LRUCacheBackend(CacheBackend):
    """LRU (Least Recently Used) cache backend"""

    def __init__(self, max_size: int = 100):
        """
        Initialize LRU cache backend.

        Args:
            max_size: Maximum number of entries
        """
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self.max_size = max_size

    def get(self, key: str) -> Optional[Tuple[Any, float]]:
        if key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: Any, timestamp: float) -> None:
        if key in self._cache:
            # Update and move to end
            self._cache.move_to_end(key)
        elif len(self._cache) >= self.max_size:
            # Remove least recently used (first item)
            self._cache.popitem(last=False)

        self._cache[key] = (value, timestamp)

    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)


class DiskCacheBackend(CacheBackend):
    """Disk-based cache backend using temp files"""

    def __init__(self, cache_dir: Optional[str] = None, max_size: int = 1000):
        """
        Initialize disk cache backend.

        Args:
            cache_dir: Directory for cache files (None = system temp)
            max_size: Maximum number of cache files
        """
        self.cache_dir = cache_dir or os.path.join(
            tempfile.gettempdir(),
            "wborm_query_cache"
        )
        self.max_size = max_size
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_path(self, key: str) -> str:
        """Get file path for cache key"""
        return os.path.join(self.cache_dir, f"{key}.cache")

    def get(self, key: str) -> Optional[Tuple[Any, float]]:
        path = self._get_path(key)
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return pickle.load(f)
            except Exception:
                return None
        return None

    def set(self, key: str, value: Any, timestamp: float) -> None:
        # Check size limit and remove oldest if needed
        if self.size() >= self.max_size:
            files = [
                (f, os.path.getmtime(os.path.join(self.cache_dir, f)))
                for f in os.listdir(self.cache_dir)
                if f.endswith(".cache")
            ]
            if files:
                oldest = min(files, key=lambda x: x[1])[0]
                os.remove(os.path.join(self.cache_dir, oldest))

        path = self._get_path(key)
        with open(path, "wb") as f:
            pickle.dump((value, timestamp), f)

    def delete(self, key: str) -> bool:
        path = self._get_path(key)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def clear(self) -> None:
        for filename in os.listdir(self.cache_dir):
            if filename.endswith(".cache"):
                os.remove(os.path.join(self.cache_dir, filename))

    def size(self) -> int:
        return len([
            f for f in os.listdir(self.cache_dir)
            if f.endswith(".cache")
        ])


class CacheConfig:
    """
    Global cache configuration for WBORM query caching.

    Attributes:
        enabled: Enable/disable caching globally
        ttl: Default TTL in seconds (None = no expiration)
        backend: Cache storage backend instance
        stats_enabled: Enable cache statistics collection
    """

    def __init__(
        self,
        enabled: bool = True,
        ttl: Optional[int] = 60,
        backend: Optional[CacheBackend] = None,
        max_size: Optional[int] = None,
        stats_enabled: bool = True
    ):
        """
        Initialize cache configuration.

        Args:
            enabled: Enable caching (default: True)
            ttl: Time-to-live in seconds (default: 60, None = no expiration)
            backend: Cache backend instance (default: MemoryCacheBackend)
            max_size: Maximum cache entries (default: None = unlimited)
            stats_enabled: Enable statistics tracking (default: True)

        Examples:
            >>> # Default configuration (60s TTL, memory cache)
            >>> config = CacheConfig()

            >>> # Disable caching
            >>> config = CacheConfig(enabled=False)

            >>> # 5-minute TTL with LRU cache
            >>> config = CacheConfig(ttl=300, backend=LRUCacheBackend(100))

            >>> # Disk-based cache
            >>> config = CacheConfig(backend=DiskCacheBackend())
        """
        self.enabled = enabled
        self.ttl = ttl
        self.backend = backend or MemoryCacheBackend(max_size=max_size)
        self.stats_enabled = stats_enabled

        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
            "invalidations": 0,
        }

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if not self.enabled:
            return None

        result = self.backend.get(key)
        if result is None:
            if self.stats_enabled:
                self._stats["misses"] += 1
            return None

        value, timestamp = result

        # Check TTL
        if self.ttl is not None and time.time() - timestamp > self.ttl:
            self.backend.delete(key)
            if self.stats_enabled:
                self._stats["misses"] += 1
            return None

        if self.stats_enabled:
            self._stats["hits"] += 1

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        if not self.enabled:
            return

        self.backend.set(key, value, time.time())

        if self.stats_enabled:
            self._stats["sets"] += 1

    def invalidate(self, key: str) -> bool:
        """
        Remove specific key from cache.

        Args:
            key: Cache key to invalidate

        Returns:
            True if key was found and removed
        """
        result = self.backend.delete(key)
        if result and self.stats_enabled:
            self._stats["invalidations"] += 1
        return result

    def clear(self) -> None:
        """Clear all cached entries"""
        self.backend.clear()
        if self.stats_enabled:
            self._stats["evictions"] += self.backend.size()

    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics

        Examples:
            >>> config.stats()
            {
                'hits': 150,
                'misses': 23,
                'hit_rate': 0.867,
                'size': 42,
                'sets': 23,
                'invalidations': 5
            }
        """
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate,
            "size": self.backend.size(),
            "sets": self._stats["sets"],
            "evictions": self._stats["evictions"],
            "invalidations": self._stats["invalidations"],
        }

    def reset_stats(self) -> None:
        """Reset cache statistics to zero"""
        for key in self._stats:
            self._stats[key] = 0


# Global cache configuration instance
_global_cache_config = CacheConfig()


def get_cache_config() -> CacheConfig:
    """
    Get global cache configuration.

    Returns:
        Global CacheConfig instance

    Examples:
        >>> config = get_cache_config()
        >>> config.ttl = 120  # Change TTL to 2 minutes
    """
    return _global_cache_config


def configure_cache(
    enabled: Optional[bool] = None,
    ttl: Optional[int] = None,
    backend: Optional[CacheBackend] = None,
    max_size: Optional[int] = None,
    stats_enabled: Optional[bool] = None
) -> None:
    """
    Configure global cache settings.

    Args:
        enabled: Enable/disable caching
        ttl: Time-to-live in seconds
        backend: Cache backend instance
        max_size: Maximum cache entries
        stats_enabled: Enable statistics

    Examples:
        >>> # Disable caching globally
        >>> configure_cache(enabled=False)

        >>> # Change TTL to 5 minutes
        >>> configure_cache(ttl=300)

        >>> # Use LRU cache with 100 entries
        >>> configure_cache(backend=LRUCacheBackend(100))

        >>> # Use disk cache
        >>> configure_cache(backend=DiskCacheBackend())
    """
    global _global_cache_config

    if enabled is not None:
        _global_cache_config.enabled = enabled

    if ttl is not None:
        _global_cache_config.ttl = ttl

    if backend is not None:
        _global_cache_config.backend = backend
    elif max_size is not None:
        # Update max_size of current backend if it's MemoryCacheBackend
        if isinstance(_global_cache_config.backend, MemoryCacheBackend):
            _global_cache_config.backend.max_size = max_size

    if stats_enabled is not None:
        _global_cache_config.stats_enabled = stats_enabled


def clear_cache() -> None:
    """
    Clear all cached query results.

    Examples:
        >>> clear_cache()  # Remove all cached queries
    """
    _global_cache_config.clear()


def cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dictionary with cache statistics

    Examples:
        >>> stats = cache_stats()
        >>> print(f"Hit rate: {stats['hit_rate']:.1%}")
    """
    return _global_cache_config.stats()


def invalidate_cache(pattern: Optional[str] = None) -> int:
    """
    Invalidate cache entries matching pattern.

    Args:
        pattern: SQL pattern to match (None = clear all)

    Returns:
        Number of entries invalidated

    Examples:
        >>> # Clear cache for specific table
        >>> invalidate_cache("SELECT * FROM clientes")

        >>> # Clear all cache
        >>> invalidate_cache()
    """
    if pattern is None:
        _global_cache_config.clear()
        return _global_cache_config.backend.size()

    # For pattern matching, we'd need to iterate through keys
    # For now, just generate the key and invalidate it
    key = sha256(pattern.encode()).hexdigest()
    return 1 if _global_cache_config.invalidate(key) else 0
