# Global Connection Guide

How to use WBORM with global connection for cleaner code.

---

## Overview

WBORM now supports **optional global connection**, making your code cleaner and more convenient. Instead of passing `conn` to every `generate_model()` call, you can register it once and use it everywhere.

---

## The Problem (Before)

**Traditional approach** - passing `conn` everywhere:

```python
from wbjdbc import connect_to_db
from wborm import generate_model

# Connect to database
conn = connect_to_db(
    db_type="informix",
    host="localhost",
    database="mydb",
    user="myuser",
    password="mypass"
)

# Generate models - need to pass conn every time
Customer = generate_model("customers", conn)
Order = generate_model("orders", conn)
Product = generate_model("products", conn)
Invoice = generate_model("invoices", conn)

# Query - conn is embedded in models
customers = Customer.filter(status="ACTIVE").all()
```

**Issues:**
- 😟 Repetitive - passing `conn` to every model
- 😟 Verbose - extra parameter everywhere
- 😟 Error-prone - easy to forget `conn`

---

## The Solution (After)

**New approach** - register once, use everywhere:

```python
from wbjdbc import connect_to_db
from wborm import register_global_connection, generate_model

# Connect to database
conn = connect_to_db(
    db_type="informix",
    host="localhost",
    database="mydb",
    user="myuser",
    password="mypass"
)

# Register connection ONCE
register_global_connection(conn)

# Generate models - no conn needed! 🎉
Customer = generate_model("customers")
Order = generate_model("orders")
Product = generate_model("products")
Invoice = generate_model("invoices")

# Query normally
customers = Customer.filter(status="ACTIVE").all()
```

**Benefits:**
- ✅ Cleaner code - no repetitive `conn` parameter
- ✅ Less typing - faster development
- ✅ Easier to read - focus on intent, not boilerplate
- ✅ Still flexible - can override with explicit `conn` if needed

---

## API Reference

### `register_global_connection(conn)`

Register a database connection globally so it can be used by all models.

**Parameters:**
- `conn` (Connection): Database connection object

**Returns:** None

**Example:**
```python
from wborm import register_global_connection

register_global_connection(conn)
```

**Note:** This also auto-loads cached models into the global namespace.

---

### `get_global_connection()`

Get the currently registered global connection.

**Parameters:** None

**Returns:** Connection object

**Raises:** `RuntimeError` if no connection is registered

**Example:**
```python
from wborm import get_global_connection

# Get the global connection
conn = get_global_connection()

# Use it directly
results = conn.execute_query("SELECT * FROM customers")
```

---

### `generate_model(table_name, conn=None, ...)`

Generate a model from a database table. If `conn` is not provided, uses the global connection.

**Parameters:**
- `table_name` (str): Name of the database table
- `conn` (Connection, optional): Database connection. If not provided, uses global connection.
- `refresh` (bool, optional): Force re-introspection (default: False)
- `inject_globals` (bool, optional): Inject model into global namespace (default: True)
- `target_globals` (dict, optional): Alternative namespace for injection

**Returns:** Model class

**Raises:** `RuntimeError` if `conn` not provided and no global connection registered

**Examples:**

```python
# With global connection
register_global_connection(conn)
Customer = generate_model("customers")

# With explicit connection (overrides global)
Other = generate_model("other_table", other_conn)

# Force refresh
Customer = generate_model("customers", refresh=True)
```

---

### `get_model(table_name, conn=None)`

Get or generate a model for a table. Shortcut for `generate_model()`.

**Parameters:**
- `table_name` (str): Name of the database table
- `conn` (Connection, optional): Database connection. If not provided, uses global connection.

**Returns:** Model class

**Example:**
```python
# Same as generate_model
Customer = get_model("customers")
```

---

### `generate_all_models(conn=None, ...)`

Generate models for all tables in the database.

**Parameters:**
- `conn` (Connection, optional): Database connection. If not provided, uses global connection.
- `include_views` (bool, optional): Include views (default: False)
- `inject_globals` (bool, optional): Inject models into global namespace (default: True)
- `target_globals` (dict, optional): Alternative namespace
- `verbose` (bool, optional): Show progress bar (default: True)

**Returns:** dict of {table_name: ModelClass}

**Example:**
```python
register_global_connection(conn)

# Generate all models at once
models = generate_all_models()

# Now all tables are available
customers = customers.all()  # 'customers' model was auto-injected
orders = orders.all()        # 'orders' model was auto-injected
```

---

## Usage Patterns

### Pattern 1: Application Setup (Recommended)

**Create a database module** (`db.py`):

```python
# db.py
from wbjdbc import connect_to_db
from wborm import register_global_connection, generate_all_models

def setup_database():
    """Initialize database connection and models"""
    conn = connect_to_db(
        db_type="informix",
        host="localhost",
        database="mydb",
        user="myuser",
        password="mypass"
    )

    # Register globally
    register_global_connection(conn)

    # Load all models
    generate_all_models(verbose=True)

    print("✅ Database initialized")

# Call once at application start
setup_database()
```

**Use in your code:**

```python
# app.py
import db  # Initializes connection and loads models

from wborm import generate_model

# Models work immediately - no conn needed!
Customer = generate_model("customers")
Order = generate_model("orders")

# Query
active_customers = Customer.filter(status="ACTIVE").all()
```

---

### Pattern 2: Context Manager (Advanced)

For applications that need multiple connections or want explicit control:

```python
from contextlib import contextmanager
from wborm import register_global_connection, get_global_connection

class DatabaseContext:
    def __init__(self, conn):
        self.conn = conn
        self.previous_conn = None

    def __enter__(self):
        try:
            self.previous_conn = get_global_connection()
        except RuntimeError:
            self.previous_conn = None

        register_global_connection(self.conn)
        return self.conn

    def __exit__(self, *args):
        if self.previous_conn:
            register_global_connection(self.previous_conn)

# Usage
with DatabaseContext(conn1):
    # conn1 is global here
    Customer = generate_model("customers")

with DatabaseContext(conn2):
    # conn2 is global here
    OtherCustomer = generate_model("customers")
```

---

### Pattern 3: Flask Application

```python
# app.py
from flask import Flask, g
from wbjdbc import connect_to_db
from wborm import register_global_connection, generate_model

app = Flask(__name__)

@app.before_first_request
def setup_database():
    """Setup database on first request"""
    conn = connect_to_db(
        db_type="informix",
        host="localhost",
        database="mydb",
        user="myuser",
        password="mypass"
    )
    register_global_connection(conn)

@app.route('/customers')
def list_customers():
    # Models work without passing conn
    Customer = generate_model("customers")
    customers = Customer.filter(status="ACTIVE").all()

    return {
        "customers": [c.to_dict() for c in customers]
    }
```

---

### Pattern 4: Multiple Databases

If you need to work with multiple databases, you can still pass `conn` explicitly:

```python
from wborm import register_global_connection, generate_model

# Primary database (global)
register_global_connection(primary_conn)

# Models from primary database
Customer = generate_model("customers")  # Uses primary_conn

# Models from secondary database (explicit)
Archive = generate_model("archive", secondary_conn)  # Uses secondary_conn

# Query both
active = Customer.all()           # From primary
old = Archive.all()               # From secondary
```

---

## Migration Guide

### Migrating Existing Code

**Step 1:** Find where you create the connection

```python
# Old code
conn = connect_to_db(...)
```

**Step 2:** Register it globally right after connection

```python
# New code
conn = connect_to_db(...)
register_global_connection(conn)  # ADD THIS LINE
```

**Step 3:** Remove `conn` from all `generate_model()` calls

```python
# Old
Customer = generate_model("customers", conn)
Order = generate_model("orders", conn)

# New
Customer = generate_model("customers")
Order = generate_model("orders")
```

**Step 4:** Test that everything still works

```python
# This should work immediately
customers = Customer.all()
orders = Order.all()
```

---

## Error Handling

### Error: Connection Not Registered

```python
from wborm import generate_model

# ❌ This will fail
Customer = generate_model("customers")

# RuntimeError: Nenhuma conexão fornecida e nenhuma conexão global registrada.
# Use: register_global_connection(conn) ou passe conn explicitamente.
```

**Solution:** Register connection first

```python
from wborm import register_global_connection

register_global_connection(conn)
Customer = generate_model("customers")  # ✅ Works
```

---

### Checking If Connection Is Registered

```python
from wborm import get_global_connection

try:
    conn = get_global_connection()
    print(f"✅ Connection registered: {conn}")
except RuntimeError:
    print("⚠️ No global connection registered")
```

---

## Best Practices

### ✅ DO

1. **Register early** - at application startup
   ```python
   # app_init.py
   register_global_connection(conn)
   ```

2. **Use for convenience** - in most of your code
   ```python
   Customer = generate_model("customers")
   ```

3. **Override when needed** - for specific cases
   ```python
   Archive = generate_model("archive", archive_conn)
   ```

4. **Document your setup** - help other developers
   ```python
   # This module requires global connection
   # Run: python setup_db.py before using
   ```

### ❌ DON'T

1. **Don't register in loops** - only once at startup
   ```python
   # ❌ Bad
   for table in tables:
       register_global_connection(conn)  # Wasteful
   ```

2. **Don't assume it's registered** - check in libraries
   ```python
   # ❌ Bad - library code
   def my_function():
       Customer = generate_model("customers")  # Might fail

   # ✅ Good - library code
   def my_function(conn=None):
       Customer = generate_model("customers", conn)
   ```

3. **Don't use for multiple concurrent connections** - use explicit `conn`
   ```python
   # ❌ Bad - confusing
   register_global_connection(conn1)
   M1 = generate_model("t1")
   register_global_connection(conn2)
   M2 = generate_model("t2")

   # ✅ Good - explicit
   M1 = generate_model("t1", conn1)
   M2 = generate_model("t2", conn2)
   ```

---

## Summary

**Before:**
```python
conn = connect_to_db(...)
Customer = generate_model("customers", conn)
Order = generate_model("orders", conn)
```

**After:**
```python
conn = connect_to_db(...)
register_global_connection(conn)

Customer = generate_model("customers")
Order = generate_model("orders")
```

**Key Benefits:**
- ✅ Cleaner, more readable code
- ✅ Less repetition
- ✅ Faster development
- ✅ Still flexible when needed

**Key Functions:**
- `register_global_connection(conn)` - Register once
- `get_global_connection()` - Get registered connection
- `generate_model(table_name)` - Generate without `conn`
- `generate_all_models()` - Generate all without `conn`

---

For more information, see:
- [Multi-Database Support Documentation](multi_database_support.md)
- [Cache Configuration](cache_configuration.md)
- [Performance Examples](performance_examples.md)
