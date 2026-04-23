# Performance Features - Complete Examples

This guide demonstrates WBORM performance features with practical examples and use cases.

---

## Table of Contents

1. [Cache Configuration](#cache-configuration)
2. [Lazy Loading](#lazy-loading)
3. [Pagination](#pagination)
4. [Performance Monitoring](#performance-monitoring)
5. [Combined Examples](#combined-examples)

---

## Cache Configuration

### Basic Cache Usage

```python
from wbjdbc import connect_to_db
from wborm import generate_model, configure_cache

conn = connect_to_db(...)
Cliente = generate_model("clientes", conn)

# Default behavior - 60s cache
clientes = Cliente.filter(status="ATIVO").all()  # Query DB
clientes = Cliente.filter(status="ATIVO").all()  # From cache!
```

### Configure Global Cache

```python
from wborm import configure_cache, LRUCacheBackend

# Use LRU cache with 5-minute TTL
configure_cache(
    enabled=True,
    ttl=300,
    backend=LRUCacheBackend(max_size=100)
)
```

### Per-Query Cache Control

```python
# Custom TTL for this query
clientes_vip = Cliente.filter(tipo="VIP").cache(ttl=600).all()

# Bypass cache (force fresh query)
saldo_atual = Conta.filter(id=123).live().first()

# Disable cache for specific query
pedidos = Pedido.filter(data__gt="2024-01-01").cache(enabled=False).all()
```

### Multiple Cache Backends

```python
from wborm import (
    configure_cache,
    MemoryCacheBackend,
    LRUCacheBackend,
    DiskCacheBackend
)

# Memory cache (simple, fast)
configure_cache(backend=MemoryCacheBackend(max_size=500))

# LRU cache (smart eviction)
configure_cache(backend=LRUCacheBackend(max_size=100))

# Disk cache (persistent across restarts)
configure_cache(backend=DiskCacheBackend(
    cache_dir="/var/cache/wborm",
    max_size=1000
))
```

### Cache Statistics

```python
from wborm import cache_stats, clear_cache

# Get cache statistics
stats = cache_stats()

print(f"Cache hits: {stats['hits']}")
print(f"Cache misses: {stats['misses']}")
print(f"Hit rate: {stats['hit_rate']:.1%}")
print(f"Cache size: {stats['size']} entries")

# Clear cache
clear_cache()
```

---

## Lazy Loading

### Load Only Specific Columns

```python
# Problem: Produto has large BLOB columns (imagem, descricao_completa)
# Solution: Load only needed columns

# Load only ID and nome
produtos = Produto.only("id", "nome", "preco").all()

# Fast query! Only fetches 3 columns
for produto in produtos:
    print(f"{produto.id}: {produto.nome} - R${produto.preco}")
```

### Defer Heavy Columns

```python
# Load everything EXCEPT large columns
produtos = Produto.defer("imagem_blob", "descricao_completa").all()

# Query fetches all columns except the two deferred ones
for produto in produtos:
    print(produto.nome)  # OK - already loaded
    # produto.imagem_blob would trigger additional query if accessed
```

### Batch Loading to Avoid N+1

```python
from wborm import batch_load_fields

# Get products with only basic info
produtos = Produto.only("id", "nome").limit(100).all()

# Later, batch load descriptions for all at once
batch_load_fields(produtos, ["descricao", "preco"])

# Now all products have descriptions loaded (1 query, not 100!)
for produto in produtos:
    print(f"{produto.nome}: {produto.descricao}")
```

### Real-World Example: Product Listing

```python
def listar_produtos():
    """List products efficiently - load images only when needed"""

    # Initial listing: only show name and price
    produtos = Produto.only("id", "nome", "preco").limit(50).all()

    return [{
        "id": p.id,
        "nome": p.nome,
        "preco": p.preco
    } for p in produtos]

def ver_produto_detalhes(produto_id):
    """Product details: load everything"""

    # Now we need all fields including images
    produto = Produto.filter(id=produto_id).first()

    return {
        "nome": produto.nome,
        "preco": produto.preco,
        "descricao": produto.descricao_completa,
        "imagem": produto.imagem_blob
    }
```

---

## Pagination

### Basic Pagination

```python
# Get page 2 with 20 items per page
page = Cliente.filter(status="ATIVO").paginate(page=2, page_size=20)

# Access items
for cliente in page.items:
    print(cliente.nome)

# Page metadata
print(f"Página {page.page} de {page.pages}")
print(f"Total: {page.total} clientes")
print(f"Mostrando {len(page.items)} de {page.total}")
```

### Navigation

```python
page = Cliente.paginate(page=1, page_size=50)

# Check if there are more pages
if page.has_next:
    next_page = Cliente.paginate(page=page.next_page, page_size=50)

if page.has_prev:
    prev_page = Cliente.paginate(page=page.prev_page, page_size=50)
```

### Build Pagination UI

```python
def render_pagination(queryset, current_page, page_size=20):
    """Render pagination for web UI"""

    page = queryset.paginate(page=current_page, page_size=page_size)

    pagination_html = f"""
    <div class="pagination">
        <span>Página {page.page} de {page.pages} ({page.total} itens)</span>

        {f'<a href="?page={page.prev_page}">← Anterior</a>' if page.has_prev else ''}
        {f'<a href="?page={page.next_page}">Próximo →</a>' if page.has_next else ''}
    </div>
    """

    return {
        "items": [item.to_dict() for item in page.items],
        "pagination": pagination_html
    }
```

### Cursor Pagination (For Huge Datasets)

```python
from wborm import cursor_paginate

# First page (no cursor)
page1 = cursor_paginate(
    Cliente.all(),
    cursor_field="id",
    page_size=1000
)

print(f"Page 1: {len(page1['items'])} items")

# Second page (use cursor from page 1)
page2 = cursor_paginate(
    Cliente.all(),
    cursor=page1['next_cursor'],
    cursor_field="id",
    page_size=1000
)

print(f"Page 2: {len(page2['items'])} items")

# Continue until no more pages
if page2['has_next']:
    page3 = cursor_paginate(
        Cliente.all(),
        cursor=page2['next_cursor'],
        cursor_field="id",
        page_size=1000
    )
```

### Iterate Through All Pages

```python
from wborm import CursorPaginator

# Create paginator
paginator = CursorPaginator(
    Cliente.filter(ativo=True),
    cursor_field="id",
    page_size=1000
)

# Iterate through all items efficiently
for cliente in paginator.iter_all():
    print(cliente.nome)
    # Processes millions of records efficiently!
```

### Real-World Example: Export with Pagination

```python
def export_clientes_to_csv():
    """Export all clients to CSV using cursor pagination"""
    import csv
    from wborm import CursorPaginator

    paginator = CursorPaginator(
        Cliente.all(),
        cursor_field="id",
        page_size=1000
    )

    with open("clientes.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Nome", "Email", "Status"])

        # Process 1000 at a time - memory efficient!
        for cliente in paginator.iter_all():
            writer.writerow([
                cliente.id,
                cliente.nome,
                cliente.email,
                cliente.status
            ])

    print("Export completed!")
```

---

## Performance Monitoring

### Enable Monitoring

```python
from wborm import configure_monitoring

# Enable with 0.5s slow query threshold
configure_monitoring(
    enabled=True,
    slow_query_threshold=0.5,
    log_slow_queries=True
)
```

### Get Performance Statistics

```python
from wborm import get_performance_stats

# Execute some queries
Cliente.all()
Pedido.filter(status="PENDENTE").all()
Produto.filter(preco__gt=100).all()

# Get stats
stats = get_performance_stats()

print(f"Total queries: {stats['total_queries']}")
print(f"Slow queries: {stats['slow_queries']}")
print(f"Average duration: {stats['average_duration']:.3f}s")
print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
```

### Print Performance Report

```python
from wborm import print_performance_report

# Execute application queries...
# (application code here)

# Print detailed report
print_performance_report()

# Output:
# ============================================================
# WBORM Performance Report
# ============================================================
# Total Queries:        245
# Slow Queries:         12 (4.9%)
# Average Duration:     0.145s
# Total Rows Fetched:   15,234
# Cache Hit Rate:       73.5%
#
# ------------------------------------------------------------
# Top 5 Slowest Queries:
# ------------------------------------------------------------
#
# 1. 1.234s (1,500 rows)
#    SELECT * FROM orders WHERE date > '2024-01-01'...
```

### Custom Monitoring

```python
from wborm import get_monitor

# Get global monitor
monitor = get_monitor()

# Get detailed statistics
stats = monitor.get_statistics()
slow_queries = monitor.get_slow_queries(limit=10)
query_stats = monitor.get_query_stats(limit=10)

# Reset statistics
monitor.reset_statistics()
```

### Log Slow Queries Automatically

```python
import logging
from wborm import configure_monitoring

# Configure logging
logging.basicConfig(level=logging.WARNING)

# Enable slow query logging
configure_monitoring(
    slow_query_threshold=0.3,  # 300ms
    log_slow_queries=True
)

# Slow queries will be logged automatically:
# WARNING:wborm.performance:⚠️  SLOW QUERY (1.234s): SELECT * FROM...
```

---

## Combined Examples

### Example 1: High-Performance Dashboard

```python
from wborm import (
    configure_cache, configure_monitoring,
    LRUCacheBackend, get_performance_stats
)

# Setup
configure_cache(
    ttl=300,  # 5 minutes
    backend=LRUCacheBackend(max_size=100)
)

configure_monitoring(
    enabled=True,
    slow_query_threshold=0.5
)

def dashboard():
    """Load dashboard data efficiently"""

    # Stats: fast queries with cache
    total_clientes = Cliente.all().count()  # Cached
    total_pedidos = Pedido.filter(status="ATIVO").count()  # Cached

    # Recent orders: load only needed fields
    pedidos_recentes = (
        Pedido
        .only("id", "data", "valor", "status")
        .order_by("data DESC")
        .limit(10)
        .all()
    )

    # Top products: paginated
    page = (
        Produto
        .only("id", "nome", "vendas")
        .order_by("vendas DESC")
        .paginate(page=1, page_size=20)
    )

    return {
        "stats": {
            "clientes": total_clientes,
            "pedidos": total_pedidos
        },
        "recent_orders": [p.to_dict() for p in pedidos_recentes],
        "top_products": [p.to_dict() for p in page.items],
        "performance": get_performance_stats()
    }
```

### Example 2: Batch Processing with Monitoring

```python
from wborm import (
    CursorPaginator,
    configure_monitoring,
    print_performance_report
)

# Enable detailed monitoring
configure_monitoring(
    log_all_queries=True,
    slow_query_threshold=0.3
)

def process_all_orders():
    """Process millions of orders efficiently"""

    # Use cursor pagination for memory efficiency
    paginator = CursorPaginator(
        Pedido.only("id", "status", "valor"),  # Lazy loading!
        cursor_field="id",
        page_size=1000
    )

    processed = 0
    total_valor = 0.0

    for pedido in paginator.iter_all():
        # Process order...
        if pedido.status == "PENDENTE":
            # Do something
            pass

        total_valor += pedido.valor
        processed += 1

        if processed % 10000 == 0:
            print(f"Processed {processed} orders...")

    print(f"\nTotal processed: {processed}")
    print(f"Total value: R${total_valor:,.2f}")

    # Print performance report
    print_performance_report()
```

### Example 3: API Endpoint with All Features

```python
from flask import Flask, request, jsonify
from wborm import (
    configure_cache,
    configure_monitoring,
    LRUCacheBackend
)

app = Flask(__name__)

# Configure on startup
configure_cache(
    ttl=180,  # 3 minutes for API
    backend=LRUCacheBackend(max_size=200)
)

configure_monitoring(
    enabled=True,
    slow_query_threshold=0.5,
    log_slow_queries=True
)

@app.route("/api/produtos")
def get_produtos():
    """Get products with pagination and caching"""

    # Get pagination parameters
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    # Build query with lazy loading
    query = Produto.only("id", "nome", "preco", "estoque")

    # Apply filters if provided
    if search := request.args.get("search"):
        query = query.filter(f"nome LIKE '%{search}%'")

    # Paginate
    page_obj = query.paginate(page=page, page_size=page_size)

    return jsonify({
        "items": [p.to_dict() for p in page_obj.items],
        "pagination": {
            "page": page_obj.page,
            "page_size": page_obj.page_size,
            "total": page_obj.total,
            "pages": page_obj.pages,
            "has_next": page_obj.has_next,
            "has_prev": page_obj.has_prev
        }
    })

@app.route("/api/stats")
def get_stats():
    """Get performance statistics"""
    from wborm import get_performance_stats

    return jsonify(get_performance_stats())
```

---

## Best Practices

### 1. Cache Configuration

```python
# Development: short TTL
if ENV == "development":
    configure_cache(ttl=10)

# Production: longer TTL with LRU
else:
    configure_cache(
        ttl=300,
        backend=LRUCacheBackend(max_size=500)
    )
```

### 2. Lazy Loading

```python
# List views: minimal data
produtos = Produto.only("id", "nome", "preco").all()

# Detail views: full data
produto = Produto.filter(id=produto_id).first()
```

### 3. Pagination

```python
# Small datasets: page-based
page = Cliente.paginate(page=1, page_size=50)

# Large datasets (millions): cursor-based
from wborm import CursorPaginator
paginator = CursorPaginator(Cliente.all(), page_size=1000)
```

### 4. Monitoring

```python
# Always monitor in production
configure_monitoring(
    enabled=True,
    slow_query_threshold=0.5,
    log_slow_queries=True
)

# Periodically review performance
import schedule
schedule.every().day.at("00:00").do(print_performance_report)
```

---

## Performance Tips

1. **Use `.only()` for list views** - Don't load BLOB/TEXT columns unnecessarily
2. **Use `.cache()` for repeated queries** - Dashboard stats, dropdown options
3. **Use `.live()` for critical data** - Account balances, inventory
4. **Use cursor pagination for exports** - Memory efficient for large datasets
5. **Monitor slow queries** - Identify optimization opportunities
6. **Batch load when needed** - Avoid N+1 queries

---

## Troubleshooting

### Cache not working?

```python
from wborm import get_cache_config

config = get_cache_config()
print(f"Enabled: {config.enabled}")
print(f"TTL: {config.ttl}")
print(f"Backend: {config.backend}")
```

### Slow queries?

```python
from wborm import get_monitor

monitor = get_monitor()
slow = monitor.get_slow_queries(limit=10)

for query in slow:
    print(f"{query.duration:.3f}s: {query.sql[:100]}")
```

### Memory issues with pagination?

Use cursor pagination instead of offset-based:

```python
# Bad for millions of records (high offsets slow)
page = Model.paginate(page=1000, page_size=50)  # offset=49,950!

# Good for millions of records (always fast)
from wborm import CursorPaginator
paginator = CursorPaginator(Model.all(), page_size=1000)
```

---

**Note**: All features work together seamlessly. Use what you need for your specific use case!
