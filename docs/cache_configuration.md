# Cache Configuration Guide

WBORM provides a powerful and flexible caching system for query results, supporting multiple storage backends, configurable TTL, and detailed statistics.

## Table of Contents

- [Quick Start](#quick-start)
- [Global Configuration](#global-configuration)
- [Per-Query Configuration](#per-query-configuration)
- [Cache Backends](#cache-backends)
- [Cache Statistics](#cache-statistics)
- [Cache Invalidation](#cache-invalidation)
- [Advanced Usage](#advanced-usage)

---

## Quick Start

By default, WBORM caches query results for 60 seconds using an in-memory backend:

```python
from wbjdbc import connect_to_db
from wborm import generate_model

conn = connect_to_db(...)
Cliente = generate_model("clientes", conn)

# First call - queries database
clientes = Cliente.filter(status="ATIVO").all()

# Second call (within 60s) - uses cache
clientes = Cliente.filter(status="ATIVO").all()  # Cached!
```

---

## Global Configuration

### Change Cache TTL

```python
from wborm import configure_cache

# Set TTL to 5 minutes
configure_cache(ttl=300)

# Disable TTL (cache never expires)
configure_cache(ttl=None)
```

### Disable Caching Globally

```python
from wborm import configure_cache

# Disable all caching
configure_cache(enabled=False)

# Re-enable caching
configure_cache(enabled=True)
```

### Set Maximum Cache Size

```python
from wborm import configure_cache

# Limit cache to 100 entries (oldest evicted when full)
configure_cache(max_size=100)
```

---

## Per-Query Configuration

### Bypass Cache with `.live()`

```python
# Force fresh query (ignore cache)
clientes = Cliente.filter(status="ATIVO").live().all()
```

### Custom TTL per Query

```python
# Cache this query for 10 minutes
clientes = Cliente.filter(status="ATIVO").cache(ttl=600).all()
```

### Disable Cache for Specific Query

```python
# Equivalent to .live()
clientes = Cliente.filter(status="ATIVO").cache(enabled=False).all()
```

---

## Cache Backends

WBORM supports multiple cache storage backends:

### 1. Memory Cache (Default)

Simple dictionary-based in-memory cache:

```python
from wborm import configure_cache, MemoryCacheBackend

# Unlimited size
configure_cache(backend=MemoryCacheBackend())

# With max size (oldest evicted)
configure_cache(backend=MemoryCacheBackend(max_size=500))
```

**Pros:**
- Fast access
- Simple

**Cons:**
- Lost on process restart
- No LRU eviction

### 2. LRU Cache

Least Recently Used cache with smart eviction:

```python
from wborm import configure_cache, LRUCacheBackend

# LRU cache with 100 entries
configure_cache(backend=LRUCacheBackend(max_size=100))
```

**Pros:**
- Keeps frequently accessed queries
- Automatic eviction of unused entries

**Cons:**
- Lost on process restart
- Slightly slower than memory cache

### 3. Disk Cache

Persistent file-based cache:

```python
from wborm import configure_cache, DiskCacheBackend

# Use system temp directory
configure_cache(backend=DiskCacheBackend())

# Custom cache directory
configure_cache(backend=DiskCacheBackend(
    cache_dir="/var/cache/wborm",
    max_size=1000
))
```

**Pros:**
- Persists across restarts
- Can handle very large caches

**Cons:**
- Slower than memory cache
- Requires disk I/O

---

## Cache Statistics

Track cache performance with built-in statistics:

```python
from wborm import cache_stats

# Get statistics
stats = cache_stats()

print(f"Cache Hits: {stats['hits']}")
print(f"Cache Misses: {stats['misses']}")
print(f"Hit Rate: {stats['hit_rate']:.1%}")
print(f"Cache Size: {stats['size']} entries")
print(f"Total Sets: {stats['sets']}")
print(f"Invalidations: {stats['invalidations']}")
```

Example output:
```
Cache Hits: 1,234
Cache Misses: 156
Hit Rate: 88.8%
Cache Size: 42 entries
Total Sets: 156
Invalidations: 12
```

### Reset Statistics

```python
from wborm import get_cache_config

config = get_cache_config()
config.reset_stats()
```

---

## Cache Invalidation

### Clear All Cache

```python
from wborm import clear_cache

# Remove all cached queries
clear_cache()
```

### Invalidate Specific Query

```python
from wborm import invalidate_cache

# Invalidate by SQL pattern
invalidate_cache("SELECT * FROM clientes WHERE status = 'ATIVO'")
```

### Manual Invalidation

```python
from wborm import get_cache_config

config = get_cache_config()

# Invalidate specific cache key
cache_key = "your_cache_key_here"
config.invalidate(cache_key)
```

---

## Advanced Usage

### Custom Cache Configuration Object

```python
from wborm import CacheConfig, LRUCacheBackend

# Create custom configuration
custom_config = CacheConfig(
    enabled=True,
    ttl=300,  # 5 minutes
    backend=LRUCacheBackend(max_size=200),
    stats_enabled=True
)

# Use in QuerySet (requires internal access)
# This is typically done internally by WBORM
```

### Conditional Caching

```python
import os

# Disable cache in development
if os.getenv("ENV") == "development":
    configure_cache(enabled=False)
else:
    configure_cache(enabled=True, ttl=600)
```

### Cache Warming

```python
# Pre-populate cache with common queries
def warm_cache():
    Cliente.filter(status="ATIVO").all()
    Cliente.filter(tipo="VIP").all()
    Pedido.filter(data_criacao__gt="2024-01-01").all()

# Call on application startup
warm_cache()
```

### Monitoring Cache Performance

```python
import time
from wborm import cache_stats

def monitor_cache():
    while True:
        stats = cache_stats()
        if stats['hit_rate'] < 0.7:  # Below 70%
            print(f"⚠️  Low cache hit rate: {stats['hit_rate']:.1%}")

        time.sleep(60)  # Check every minute
```

### Dynamic TTL Based on Query Complexity

```python
def smart_cache_ttl(queryset):
    """Adjust TTL based on query complexity"""
    if queryset._joins:
        # Complex queries with joins: cache longer
        return queryset.cache(ttl=600)  # 10 minutes
    else:
        # Simple queries: cache shorter
        return queryset.cache(ttl=60)  # 1 minute

# Usage
clientes = smart_cache_ttl(Cliente.filter(status="ATIVO")).all()
```

---

## Best Practices

### 1. **Choose the Right Backend**

- **Development**: Memory cache (simple, fast)
- **Production with restarts**: Disk cache (persistent)
- **High-traffic APIs**: LRU cache (smart eviction)

### 2. **Set Appropriate TTL**

```python
# Fast-changing data: short TTL
configure_cache(ttl=30)  # 30 seconds

# Reference data: long TTL
configure_cache(ttl=3600)  # 1 hour

# Static data: no expiration
configure_cache(ttl=None)
```

### 3. **Use `.live()` for Critical Queries**

```python
# Always get fresh data for financial calculations
saldo = Conta.filter(id=conta_id).live().sum("saldo")
```

### 4. **Monitor Cache Statistics**

```python
# Periodically check cache performance
stats = cache_stats()
if stats['hit_rate'] < 0.5:
    print("Consider increasing cache size or TTL")
```

### 5. **Clear Cache After Bulk Operations**

```python
# After bulk insert/update/delete
Cliente.bulk_update(...)
clear_cache()  # Invalidate all cached queries
```

---

## Examples

### Example 1: Production Configuration

```python
from wborm import configure_cache, LRUCacheBackend

# LRU cache with 5-minute TTL
configure_cache(
    enabled=True,
    ttl=300,
    backend=LRUCacheBackend(max_size=500)
)
```

### Example 2: Development Configuration

```python
from wborm import configure_cache

# Short TTL for development
configure_cache(
    enabled=True,
    ttl=10,  # 10 seconds only
    max_size=50
)
```

### Example 3: Persistent Cache

```python
from wborm import configure_cache, DiskCacheBackend

# Disk cache for microservices (survives restarts)
configure_cache(
    backend=DiskCacheBackend(
        cache_dir="/app/cache",
        max_size=1000
    ),
    ttl=600
)
```

### Example 4: Mixed Caching Strategy

```python
# Global configuration with moderate TTL
configure_cache(ttl=120)

# Critical queries: always fresh
saldo = Conta.live().sum("saldo")

# Heavy queries: cache longer
relatorio = (
    Vendas.select("categoria", "COUNT(*)", "SUM(valor)")
          .group_by("categoria")
          .cache(ttl=1800)  # 30 minutes
          .all()
)

# Real-time data: no cache
usuarios_online = Usuario.filter(online=True).live().count()
```

---

## Migration from Old Cache System

If you're upgrading from WBORM < 0.4.0, the cache system now uses the new configuration:

**Old (deprecated):**
```python
# TTL was hardcoded to 60 seconds
# Cache used global _query_result_cache dict
```

**New:**
```python
from wborm import configure_cache

# Explicit configuration
configure_cache(ttl=60)  # Same as before

# Or customize
configure_cache(ttl=300, backend=LRUCacheBackend(100))
```

**All existing code continues to work** - the new system is backward compatible.

---

## API Reference

### `configure_cache(enabled=None, ttl=None, backend=None, max_size=None, stats_enabled=None)`

Configure global cache settings.

**Parameters:**
- `enabled` (bool): Enable/disable caching globally
- `ttl` (int): Time-to-live in seconds (None = no expiration)
- `backend` (CacheBackend): Cache storage backend instance
- `max_size` (int): Maximum cache entries (for MemoryCacheBackend)
- `stats_enabled` (bool): Enable statistics tracking

### `clear_cache()`

Clear all cached query results.

### `cache_stats()`

Get cache statistics dictionary.

**Returns:**
```python
{
    'hits': int,
    'misses': int,
    'hit_rate': float,
    'size': int,
    'sets': int,
    'evictions': int,
    'invalidations': int
}
```

### `invalidate_cache(pattern=None)`

Invalidate cache entries matching pattern.

**Parameters:**
- `pattern` (str, optional): SQL pattern to match (None = clear all)

**Returns:** Number of entries invalidated

### `get_cache_config()`

Get global cache configuration object.

**Returns:** `CacheConfig` instance

---

## Troubleshooting

### Cache Not Working

```python
from wborm import get_cache_config

config = get_cache_config()
print(f"Cache enabled: {config.enabled}")
print(f"Cache TTL: {config.ttl}")
```

### Low Hit Rate

- Increase `max_size` if evictions are high
- Increase `ttl` if misses are high
- Consider using `LRUCacheBackend`

### Memory Usage Too High

- Reduce `max_size`
- Use `LRUCacheBackend` with smaller size
- Switch to `DiskCacheBackend`

---

**Note:** Cache configuration is global per Python process. If using multiple processes (e.g., Gunicorn workers), each process has its own cache.
