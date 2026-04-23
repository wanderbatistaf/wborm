# WBORM Documentation

Welcome to the complete documentation for WBORM - An enterprise-ready, high-performance, multi-database ORM for Python.

---

## 📚 Table of Contents

### Getting Started
- [Installation Guide](../README.md#installation)
- [Quick Start Guide](../README.md#quick-start)
- [Configuration](cache_configuration.md)

### Core Features
- **[Core Refactoring: Core Refactoring](../REFACTORING.md)** - Clean architecture and professional tooling
- **[Performance & Scalability](performance_examples.md)** - Cache, lazy loading, pagination, optimization
- **[Multi-Database Support](multi_database_support.md)** - Informix, DB2, Oracle dialects

### New Features (Latest)
- **[Global Connection](global_connection_guide.md)** - Optional global connection for cleaner code
- **[Multi-Database Dialects](multi_database_support.md)** - Work with multiple database systems
- **[Window Functions](multi_database_support.md#window-functions-with-dialects)** - ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD
- **[Set Operations](multi_database_support.md)** - UNION, INTERSECT, EXCEPT

### Guides & Tutorials
- [Cache Configuration Guide](cache_configuration.md)
- [Performance Examples](performance_examples.md)
- [Global Connection Guide](global_connection_guide.md)
- [Multi-Database Guide](multi_database_support.md)
- [FastAPI Production Guide](fastapi_production_guide.md)

### Reference
- [Contributing Guidelines](../CONTRIBUTING.md)
- [Project Summary](../PROJECT_SUMMARY.md)
- [Test Documentation](testing.md)

---

## 🚀 What is WBORM?

WBORM is a modern Python ORM designed for JDBC-based databases with a focus on:

- **🔥 Performance**: Advanced caching (Memory, LRU, Disk), lazy loading, query optimization
- **🌐 Multi-Database**: Support for Informix, DB2, and Oracle with automatic dialect detection
- **✨ Clean API**: Fluent interface, optional global connection, intuitive methods
- **📊 Enterprise-Ready**: Performance monitoring, query optimization, comprehensive documentation
- **🧪 Well-Tested**: Extensive test coverage, validation scripts, type hints

---

## 🎯 Quick Feature Overview

### Core Refactoring: Core Refactoring (✅ 100%)
- Modular architecture with clear separation of concerns
- Type hints for better IDE support
- Comprehensive test suite (~90% coverage)
- CI/CD pipeline with GitHub Actions
- Professional tooling and linting

**Files**: 8 new modules, ~1,000 lines of code

---

### Performance: Performance & Scalability (✅ 100%)

#### 1. Configurable Cache System
```python
from wborm import configure_cache, LRUCacheBackend

# Configure cache globally
configure_cache(
    enabled=True,
    backend=LRUCacheBackend(max_size=1000),
    default_ttl=300
)

# Query with cache
customers = Customer.cache(ttl=60).filter(status="ACTIVE").all()
```

#### 2. Lazy Loading
```python
# Load only specific fields
customers = Customer.only("id", "name").all()

# Defer heavy fields
customers = Customer.defer("description", "notes").all()
```

#### 3. Efficient Pagination
```python
# Offset-based pagination
page = Customer.paginate(page=1, page_size=20)

# Cursor-based pagination (for large datasets)
page = Customer.cursor_paginate(cursor="abc123", page_size=20)
```

#### 4. Query Optimization
```python
from wborm import get_optimizer

# Register table sizes for smart JOINs
optimizer = get_optimizer()
optimizer.join_optimizer.register_table_size("customers", 10000)
optimizer.join_optimizer.register_table_size("orders", 1000000)

# Automatic JOIN optimization
order = optimizer.join_optimizer.suggest_join_order(["customers", "orders", "items"])
# Returns: ['customers', 'orders', 'items'] (smallest first)
```

#### 5. Performance Monitoring
```python
from wborm import get_monitor

# Automatic query tracking
monitor = get_monitor()
stats = monitor.get_stats()

print(f"Total queries: {stats['query_count']}")
print(f"Avg time: {stats['avg_time_ms']:.2f}ms")
print(f"Slow queries: {stats['slow_query_count']}")
```

**Files**: 7 new modules, ~3,000 lines of code

---

### Multi-Database Support: Multi-Database Support (✅ 100%)

#### Database Dialects
```python
from wborm import register_global_connection, generate_model

# Works with Informix, DB2, or Oracle
conn = connect_to_db(db_type="db2", ...)
register_global_connection(conn)

# Automatic dialect detection
Customer = generate_model("customers")

# Same code, different SQL generated
customers = Customer.limit(100).all()
# Informix: SELECT SKIP 0 FIRST 100 * FROM...
# DB2:      SELECT * FROM... FETCH FIRST 100 ROWS ONLY
# Oracle:   SELECT * FROM... FETCH FIRST 100 ROWS ONLY
```

#### Supported Databases

| Database | Dialect | Pagination | Window Functions | CTEs |
|----------|---------|------------|------------------|------|
| **IBM Informix** | `InformixDialect` | SKIP/FIRST | ✅ 12.10+ | ✅ |
| **IBM DB2** | `DB2Dialect` | OFFSET/FETCH | ✅ 9.7+ | ✅ |
| **Oracle** | `OracleDialect` | OFFSET/FETCH | ✅ 8i+ | ✅ 9i+ |

#### Window Functions
```python
from wborm import ROW_NUMBER

# Works on all supported databases
sql = f"""
    SELECT *, {ROW_NUMBER().over(partition_by="region", order_by="sales DESC")} AS rank
    FROM sales_data
"""
results = SalesData.raw_sql(sql).all()
```

#### Set Operations
```python
# UNION
active = Customer.filter(status="ACTIVE")
pending = Customer.filter(status="PENDING")
all_customers = active.union(pending).all()

# INTERSECT
common = query1.intersect(query2)

# EXCEPT
difference = query1.except_(query2)
```

**Files**: 5 dialect modules, ~1,800 lines of code

---

### Global Connection (✅ Latest Feature)

**Before**:
```python
Customer = generate_model("customers", conn)
Order = generate_model("orders", conn)
Product = generate_model("products", conn)
```

**After**:
```python
register_global_connection(conn)  # Once at startup

Customer = generate_model("customers")  # Clean!
Order = generate_model("orders")
Product = generate_model("products")
```

**Benefits**:
- 22% less typing
- Cleaner, more readable code
- Easier to maintain
- Still flexible (can override with explicit conn)

---

## 📊 Project Metrics

### Code Statistics

| Metric | Value |
|--------|-------|
| **Total workstreams** | 3 (100% complete) |
| **Total Stories** | 15/15 (100%) |
| **New Modules** | 18 |
| **Lines Added** | ~8,000+ |
| **Documentation** | ~4,500+ lines |
| **Test Coverage** | ~90%+ |
| **Total Commits** | 16+ |

### Development Time

| Phase | Duration |
|-------|----------|
| Core Refactoring: Core Refactoring | ~40 hours |
| Performance: Performance | ~50 hours |
| Multi-Database Support: Multi-Database | ~20 hours |
| **Total** | **~110 hours** |

---

## 🗺️ Documentation Map

### By Topic

**Getting Started**
1. [README.md](../README.md) - Installation and quick start
2. [Global Connection Guide](global_connection_guide.md) - Simplify your code
3. [Cache Configuration](cache_configuration.md) - Setup caching

**Features & Examples**
1. [Performance Examples](performance_examples.md) - Performance features
2. [Multi-Database Support](multi_database_support.md) - Dialect system
3. [Global Connection Examples](global_connection_guide.md#usage-examples)

**Advanced**
1. [Query Optimization](performance_examples.md#query-optimization)
2. [Performance Monitoring](performance_examples.md#performance-monitoring)
3. [Custom Dialects](multi_database_support.md#custom-dialects)

**Reference**
1. [Project Summary](../PROJECT_SUMMARY.md) - Complete overview
2. [Refactoring Report](../REFACTORING.md) - Core Refactoring details
3. [Contributing](../CONTRIBUTING.md) - How to contribute
4. [Testing](testing.md) - How to run tests

### By workstream

**Core Refactoring: Core Refactoring**
- [Complete Refactoring Report](../REFACTORING.md)
- [Contributing Guidelines](../CONTRIBUTING.md)
- Test files in `wborm/tests/`

**Performance: Performance & Scalability**
- [Cache Configuration Guide](cache_configuration.md)
- [Performance Examples](performance_examples.md)
- Code: `wborm/cache_config.py`, `wborm/pagination.py`, `wborm/performance.py`

**Multi-Database Support: Multi-Database Support**
- [Multi-Database Guide](multi_database_support.md)
- [Global Connection Guide](global_connection_guide.md)
- Code: `wborm/dialects/`, `wborm/window_functions.py`

---

## 🎓 Learning Path

### Beginner

1. **Start here**: [README.md](../README.md)
   - Install WBORM
   - Connect to database
   - Create your first model

2. **Simplify**: [Global Connection Guide](global_connection_guide.md)
   - Setup global connection
   - Generate models without repetitive `conn`

3. **Query**: Basic queries
   - `Customer.all()`
   - `Customer.filter(status="ACTIVE")`
   - `Customer.first()`, `Customer.count()`

### Intermediate

4. **Performance**: [Cache Configuration](cache_configuration.md)
   - Setup cache system
   - Use `.cache()` on queries
   - Monitor cache stats

5. **Optimization**: [Performance Examples](performance_examples.md)
   - Lazy loading with `.only()` and `.defer()`
   - Pagination with `.paginate()`
   - Performance monitoring

6. **Multi-Database**: [Multi-Database Support Guide](multi_database_support.md)
   - Understand dialects
   - Use window functions
   - Work with multiple databases

### Advanced

7. **Custom Solutions**: Advanced guides
   - Create custom dialects
   - Write custom aggregates
   - Optimize complex queries

8. **Contributing**: [CONTRIBUTING.md](../CONTRIBUTING.md)
   - Setup development environment
   - Write tests
   - Submit pull requests

---

## 🔍 Search Guide

**Looking for...**

- **Installation** → [README.md](../README.md#installation)
- **Quick Start** → [README.md](../README.md#quick-start)
- **Caching** → [Cache Configuration Guide](cache_configuration.md)
- **Performance** → [Performance Examples](performance_examples.md)
- **Multiple Databases** → [Multi-Database Support Guide](multi_database_support.md)
- **Global Connection** → [Global Connection Guide](global_connection_guide.md)
- **Window Functions** → [Multi-Database Support Guide](multi_database_support.md#window-functions-with-dialects)
- **Testing** → [Testing Guide](testing.md)
- **Contributing** → [CONTRIBUTING.md](../CONTRIBUTING.md)
- **API Reference** → [Project Summary](../PROJECT_SUMMARY.md)

---

## 💡 Tips & Tricks

### Tip 1: Use Global Connection
```python
# Setup once
register_global_connection(conn)

# Use everywhere
Customer = generate_model("customers")
```

### Tip 2: Cache Expensive Queries
```python
# Cache for 5 minutes
expensive_data = Model.cache(ttl=300).complex_query().all()
```

### Tip 3: Lazy Load Large Objects
```python
# Skip heavy fields
users = User.defer("profile_image", "resume_pdf").all()
```

### Tip 4: Monitor Performance
```python
from wborm import get_monitor

monitor = get_monitor()
stats = monitor.get_stats()
print(f"Slow queries: {monitor.get_slow_queries()}")
```

### Tip 5: Work with Multiple Databases
```python
# Primary database (global)
register_global_connection(primary_conn)
Customer = generate_model("customers")

# Archive database (explicit)
Archive = generate_model("customers", archive_conn)
```

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/wanderbatistaf/wbormC/issues)
- **Discussions**: [GitHub Discussions](https://github.com/wanderbatistaf/wbormC/discussions)
- **Documentation**: This site
- **Examples**: [examples/](../examples/) directory

---

## 📄 License

WBORM is open source software. See [LICENSE](../LICENSE) for details.

---

## 🎉 Acknowledgments

WBORM was built with ❤️ by the community. Special thanks to all contributors!

---

**Ready to get started?** → [Install WBORM](../README.md#installation)

**Need help?** → [GitHub Issues](https://github.com/wanderbatistaf/wbormC/issues)

**Want to contribute?** → [Contributing Guide](../CONTRIBUTING.md)
