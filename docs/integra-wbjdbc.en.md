# Integration Between `wborm` and `wbjdbc`

## Recommended flow

`wbjdbc` handles the optimized JDBC connection. `wborm` handles models, query building, sessions, and persistence.

```python
from wbjdbc import connect_optimized
from wborm import register_global_connection, generate_model

conn = connect_optimized(
    db_type="informix-sqli",
    host="localhost",
    port=9088,
    database="stores_demo",
    user="informix",
    password="in4mix",
    server="informix",
)

register_global_connection(conn)
Customer = generate_model("customer")

customers = Customer.filter(customer_num__gt=100).limit(10).all()
```

## Responsibility split

| Feature | `wbjdbc` | `wborm` |
|---|---|---|
| JVM / JDBC driver bootstrap | ✅ | ❌ |
| Optimized connection | ✅ | ❌ |
| Pooling / metadata cache | ✅ | ❌ |
| `execute_batch()` | ✅ | used when available |
| ORM / models | ❌ | ✅ |
| Query builder | ❌ | ✅ |
| Session / Unit of Work | ❌ | ✅ |
| Simple migrations | ❌ | ✅ |

## What `wbjdbc 2.0` improves for `wborm`

- `bulk_add()`, `bulk_update()`, and `bulk_delete()` can leverage `execute_batch()`
- the ORM keeps the same API while benefiting from pooling and metadata caching
- the recommended connection entry point is now `connect_optimized(...)`

## `wborm` features that matter for Informix

- dialect-aware `SKIP/FIRST`
- explicit transactions
- pessimistic locking with `.lock_for_update()`
- eager loading with `.preload(...)`
- partial lazy loading with `.only()` / `.defer()`
- hooks, validation, serialization, and native SQL

## Environment compatibility

For real `wbjdbc` integration, prefer Python `3.12` or `3.13`. On `3.14`-only environments, `JPype1` installation may fail and require native build tools.
