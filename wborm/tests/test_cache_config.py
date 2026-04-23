"""
Tests for cache_config module

Tests the configurable cache system including multiple backends,
TTL configuration, statistics, and invalidation.
"""

import time
import os
import tempfile
from wborm.cache_config import (
    CacheConfig,
    MemoryCacheBackend,
    LRUCacheBackend,
    DiskCacheBackend,
    configure_cache,
    clear_cache,
    cache_stats,
    get_cache_config,
)


def test_memory_cache_backend():
    """Test MemoryCacheBackend basic operations"""
    backend = MemoryCacheBackend()

    # Test set and get
    backend.set("key1", "value1", time.time())
    result = backend.get("key1")
    assert result is not None
    assert result[0] == "value1"

    # Test delete
    assert backend.delete("key1") is True
    assert backend.get("key1") is None
    assert backend.delete("key1") is False  # Already deleted

    # Test clear
    backend.set("key2", "value2", time.time())
    backend.set("key3", "value3", time.time())
    assert backend.size() == 2
    backend.clear()
    assert backend.size() == 0


def test_memory_cache_max_size():
    """Test MemoryCacheBackend with max_size limit"""
    backend = MemoryCacheBackend(max_size=3)

    # Add 3 entries
    backend.set("key1", "value1", time.time())
    backend.set("key2", "value2", time.time())
    backend.set("key3", "value3", time.time())
    assert backend.size() == 3

    # Adding 4th should evict oldest
    time.sleep(0.01)  # Ensure different timestamps
    backend.set("key4", "value4", time.time())
    assert backend.size() == 3
    assert backend.get("key1") is None  # Oldest evicted


def test_lru_cache_backend():
    """Test LRUCacheBackend operations"""
    backend = LRUCacheBackend(max_size=3)

    # Add 3 entries
    backend.set("key1", "value1", time.time())
    backend.set("key2", "value2", time.time())
    backend.set("key3", "value3", time.time())

    # Access key1 to make it recently used
    backend.get("key1")

    # Add key4, should evict key2 (least recently used)
    backend.set("key4", "value4", time.time())
    assert backend.size() == 3
    assert backend.get("key2") is None  # LRU evicted
    assert backend.get("key1") is not None  # Still present (recently accessed)


def test_disk_cache_backend():
    """Test DiskCacheBackend operations"""
    # Use temporary directory
    cache_dir = os.path.join(tempfile.gettempdir(), "test_wborm_cache")
    backend = DiskCacheBackend(cache_dir=cache_dir, max_size=100)

    try:
        # Test set and get
        backend.set("key1", {"data": "value1"}, time.time())
        result = backend.get("key1")
        assert result is not None
        assert result[0]["data"] == "value1"

        # Test persistence
        backend2 = DiskCacheBackend(cache_dir=cache_dir)
        result2 = backend2.get("key1")
        assert result2 is not None
        assert result2[0]["data"] == "value1"

        # Test delete
        assert backend.delete("key1") is True
        assert backend.get("key1") is None

        # Test clear
        backend.set("key2", "value2", time.time())
        backend.set("key3", "value3", time.time())
        assert backend.size() >= 2
        backend.clear()
        assert backend.size() == 0

    finally:
        # Cleanup
        backend.clear()
        if os.path.exists(cache_dir):
            os.rmdir(cache_dir)


def test_cache_config_basic():
    """Test CacheConfig basic operations"""
    config = CacheConfig(ttl=60)

    # Test set and get
    config.set("test_key", "test_value")
    value = config.get("test_key")
    assert value == "test_value"

    # Test invalidate
    assert config.invalidate("test_key") is True
    assert config.get("test_key") is None
    assert config.invalidate("test_key") is False  # Already invalidated


def test_cache_config_ttl():
    """Test CacheConfig TTL expiration"""
    config = CacheConfig(ttl=1)  # 1 second TTL

    config.set("expiring_key", "expiring_value")
    assert config.get("expiring_key") == "expiring_value"

    # Wait for expiration
    time.sleep(1.1)
    assert config.get("expiring_key") is None  # Expired


def test_cache_config_disabled():
    """Test CacheConfig when disabled"""
    config = CacheConfig(enabled=False)

    config.set("key", "value")
    # Should not cache when disabled
    assert config.get("key") is None


def test_cache_config_no_ttl():
    """Test CacheConfig with no TTL (never expires)"""
    config = CacheConfig(ttl=None)

    config.set("permanent_key", "permanent_value")
    time.sleep(0.5)

    # Should still be cached (no TTL)
    assert config.get("permanent_key") == "permanent_value"


def test_cache_config_statistics():
    """Test cache statistics tracking"""
    config = CacheConfig(stats_enabled=True)

    # Initial stats
    stats = config.stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0

    # Miss
    config.get("nonexistent")
    stats = config.stats()
    assert stats["misses"] == 1

    # Set and hit
    config.set("key1", "value1")
    config.get("key1")
    stats = config.stats()
    assert stats["hits"] == 1
    assert stats["sets"] == 1

    # Another miss
    config.get("key2")
    stats = config.stats()
    assert stats["misses"] == 2

    # Check hit rate
    assert stats["hit_rate"] == 1 / 3  # 1 hit, 2 misses

    # Reset stats
    config.reset_stats()
    stats = config.stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0


def test_cache_config_different_backends():
    """Test CacheConfig with different backends"""
    # Memory backend
    config_mem = CacheConfig(backend=MemoryCacheBackend())
    config_mem.set("key1", "value1")
    assert config_mem.get("key1") == "value1"

    # LRU backend
    config_lru = CacheConfig(backend=LRUCacheBackend(max_size=10))
    config_lru.set("key2", "value2")
    assert config_lru.get("key2") == "value2"

    # Disk backend
    cache_dir = os.path.join(tempfile.gettempdir(), "test_wborm_cache2")
    config_disk = CacheConfig(backend=DiskCacheBackend(cache_dir=cache_dir))
    try:
        config_disk.set("key3", "value3")
        assert config_disk.get("key3") == "value3"
    finally:
        config_disk.clear()
        if os.path.exists(cache_dir):
            os.rmdir(cache_dir)


def test_global_cache_configuration():
    """Test global cache configuration functions"""
    # Get current config
    config = get_cache_config()
    assert config is not None

    # Configure cache
    configure_cache(ttl=120)
    config = get_cache_config()
    assert config.ttl == 120

    # Disable cache
    configure_cache(enabled=False)
    config = get_cache_config()
    assert config.enabled is False

    # Re-enable
    configure_cache(enabled=True, ttl=60)
    config = get_cache_config()
    assert config.enabled is True
    assert config.ttl == 60


def test_clear_cache_function():
    """Test clear_cache utility function"""
    config = get_cache_config()

    # Add some entries
    config.set("key1", "value1")
    config.set("key2", "value2")
    assert config.backend.size() >= 2

    # Clear all
    clear_cache()
    assert config.backend.size() == 0


def test_cache_stats_function():
    """Test cache_stats utility function"""
    configure_cache(enabled=True, stats_enabled=True)
    config = get_cache_config()
    config.reset_stats()

    # Generate some activity
    config.set("key1", "value1")
    config.get("key1")  # Hit
    config.get("key2")  # Miss

    stats = cache_stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1
    assert "hit_rate" in stats


def test_cache_config_clear():
    """Test CacheConfig clear operation"""
    config = CacheConfig()

    # Add multiple entries
    for i in range(5):
        config.set(f"key{i}", f"value{i}")

    assert config.backend.size() >= 5

    # Clear all
    config.clear()
    assert config.backend.size() == 0


def run_all_tests():
    """Run all cache configuration tests"""
    print("Running cache_config tests...")

    test_memory_cache_backend()
    print("✓ Memory cache backend")

    test_memory_cache_max_size()
    print("✓ Memory cache max size")

    test_lru_cache_backend()
    print("✓ LRU cache backend")

    test_disk_cache_backend()
    print("✓ Disk cache backend")

    test_cache_config_basic()
    print("✓ Cache config basic")

    test_cache_config_ttl()
    print("✓ Cache config TTL")

    test_cache_config_disabled()
    print("✓ Cache config disabled")

    test_cache_config_no_ttl()
    print("✓ Cache config no TTL")

    test_cache_config_statistics()
    print("✓ Cache statistics")

    test_cache_config_different_backends()
    print("✓ Different backends")

    test_global_cache_configuration()
    print("✓ Global configuration")

    test_clear_cache_function()
    print("✓ Clear cache function")

    test_cache_stats_function()
    print("✓ Cache stats function")

    test_cache_config_clear()
    print("✓ Cache config clear")

    print("\nAll cache_config tests passed! ✅")


if __name__ == "__main__":
    run_all_tests()
