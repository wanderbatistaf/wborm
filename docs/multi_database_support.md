# Multi-Database Support

Complete documentation for WBORM's multi-database support system.

---

## Table of Contents

1. [Overview](#overview)
2. [Supported Databases](#supported-databases)
3. [Database Dialects](#database-dialects)
4. [Automatic Detection](#automatic-detection)
5. [Usage Examples](#usage-examples)
6. [Advanced Features](#advanced-features)
7. [Custom Dialects](#custom-dialects)

---

## Overview

WBORM now supports multiple database systems through a comprehensive dialect system. Each database has its own dialect that handles:

- **SQL Syntax Variations**: Different LIMIT/OFFSET syntax, string functions, date functions
- **Type Mapping**: Database-specific type conversion to Python types
- **Query Optimization**: Database-specific optimizer hints
- **Feature Detection**: Automatic detection of supported features (window functions, CTEs, etc.)

**Key Benefits:**
- Write once, run on Informix, DB2, or Oracle
- Automatic dialect detection
- Zero code changes for basic queries
- Database-specific optimizations when needed

---

## Supported Databases

### IBM Informix

**Versions:** IDS 11.x, 12.x, 14.x
**Dialect:** `InformixDialect`

**Features:**
- ✅ SKIP/FIRST syntax for pagination
- ✅ Window functions (12.10+)
- ✅ Common Table Expressions (CTEs)
- ✅ Comprehensive type mapping

**Example SQL:**
```sql
SELECT SKIP 20 FIRST 10 * FROM customers
```

### IBM DB2

**Versions:** DB2 9.7+, 10.x, 11.x
**Dialect:** `DB2Dialect`

**Features:**
- ✅ OFFSET/FETCH syntax for pagination
- ✅ Window functions (9.7+)
- ✅ Common Table Expressions (CTEs)
- ✅ DB2 optimizer hints

**Example SQL:**
```sql
SELECT * FROM customers
OFFSET 20 ROWS FETCH FIRST 10 ROWS ONLY
```

### Oracle Database

**Versions:** 11g, 12c, 18c, 19c, 21c
**Dialect:** `OracleDialect`

**Features:**
- ✅ OFFSET/FETCH syntax (12c+)
- ✅ ROW_NUMBER for older versions
- ✅ Window functions (8i+)
- ✅ Common Table Expressions (9i+)
- ✅ Sequences support
- ✅ RETURNING clause support

**Example SQL:**
```sql
SELECT * FROM customers
OFFSET 20 ROWS FETCH FIRST 10 ROWS ONLY
```

---

## Database Dialects

### What is a Dialect?

A dialect is a class that encapsulates all database-specific behavior. Every model automatically gets the appropriate dialect based on its connection.

### Dialect Interface

All dialects implement these methods:

```python
class BaseDialect:
    # Type mapping
    def map_type_to_python(self, db_type) -> Type
    def map_python_to_db(self, python_type) -> str

    # SQL generation
    def limit_offset_clause(self, limit, offset) -> str
    def concat_function(*args) -> str
    def substring_function(string, start, length) -> str
    def current_timestamp() -> str
    def date_add(date_expr, interval, unit) -> str

    # Query optimization
    def get_optimizer_hints(query_type) -> str
    def optimize_join(join_type, tables) -> str

    # Information schema
    def get_table_list_query() -> str
    def get_table_info_query(table_name) -> str
```

### Dialect Properties

```python
dialect.name                    # "informix", "db2", "oracle"
dialect.supports_limit_offset   # True/False
dialect.supports_window_functions  # True/False
dialect.supports_cte            # True/False
dialect.limit_offset_position   # "start" or "end"
```

---

## Automatic Detection

WBORM automatically detects the database type from your connection:

```python
from wbjdbc import connect_to_db
from wborm import generate_model

# Connect to any supported database
conn = connect_to_db(
    db_type="db2",  # or "informix", "oracle"
    host="localhost",
    database="mydb",
    user="myuser",
    password="mypass"
)

# Model automatically uses correct dialect
Customer = generate_model("customers", conn)

# Queries use DB2 syntax automatically
customers = Customer.limit(10).all()
# Generates: SELECT * FROM customers FETCH FIRST 10 ROWS ONLY
```

### Manual Dialect Access

```python
# Access the dialect
dialect = Customer._dialect
print(dialect.name)  # "db2"
print(dialect.supports_window_functions)  # True

# Use dialect methods directly
limit_clause = dialect.limit_offset_clause(10, 20)
print(limit_clause)  # "OFFSET 20 ROWS FETCH FIRST 10 ROWS ONLY"
```

---

## Usage Examples

### Example 1: Same Code, Multiple Databases

```python
# This code works identically on Informix, DB2, and Oracle
def get_active_customers(conn):
    Customer = generate_model("customers", conn)

    return (
        Customer
        .filter(status="ACTIVE")
        .order_by("name")
        .limit(100)
        .all()
    )

# Informix generates: SELECT SKIP 0 FIRST 100 * FROM customers WHERE ...
# DB2 generates: SELECT * FROM customers WHERE ... FETCH FIRST 100 ROWS ONLY
# Oracle generates: SELECT * FROM customers WHERE ... FETCH FIRST 100 ROWS ONLY
```

### Example 2: Pagination Across Databases

```python
def paginated_orders(conn, page=1, page_size=20):
    Order = generate_model("orders", conn)

    # Works on all databases
    page_obj = Order.filter(status="PENDING").paginate(
        page=page,
        page_size=page_size
    )

    return {
        "items": [order.to_dict() for order in page_obj.items],
        "total": page_obj.total,
        "pages": page_obj.pages
    }
```

### Example 3: Database-Specific Features

```python
from wborm import get_dialect, InformixDialect, OracleDialect

def get_current_timestamp(conn):
    """Get current timestamp using database-specific syntax"""
    dialect = get_dialect(conn.db_type)

    if isinstance(dialect, InformixDialect):
        return "CURRENT"  # Informix syntax
    elif isinstance(dialect, OracleDialect):
        return "SYSTIMESTAMP"  # Oracle syntax
    else:
        return dialect.current_timestamp()  # Generic
```

### Example 4: Type Mapping

```python
from wborm import generate_model

def introspect_table_types(table_name, conn):
    """Show how database types map to Python"""
    Model = generate_model(table_name, conn)
    dialect = Model._dialect

    # Get table columns from database
    for col in metadata:
        db_type = col["type"]
        python_type = dialect.map_type_to_python(db_type)
        print(f"{col['name']}: {db_type} -> {python_type.__name__}")

# Informix: SERIAL -> int, VARCHAR -> str, DATETIME -> str
# DB2: INTEGER -> int, VARCHAR -> str, TIMESTAMP -> str
# Oracle: NUMBER -> float, VARCHAR2 -> str, DATE -> str
```

### Example 5: Custom SQL with Dialect Functions

```python
from wborm import generate_model

def search_customers(conn, search_term):
    """Search using database-specific string functions"""
    Customer = generate_model("customers", conn)
    dialect = Customer._dialect

    # Build database-specific CONCAT
    full_name = dialect.concat_function("first_name", "' '", "last_name")

    # Use in raw SQL
    results = Customer.raw_sql(f"""
        SELECT *,
               {full_name} AS full_name,
               {dialect.substring_function("email", 1, 50)} AS short_email
        FROM customers
        WHERE {full_name} LIKE '%{search_term}%'
    """).all()

    return results
```

---

## Advanced Features

### Optimizer Hints

Each dialect provides database-specific optimizer hints:

```python
from wborm import get_optimizer

# Register table sizes for JOIN optimization
optimizer = get_optimizer()
optimizer.join_optimizer.register_table_size("customers", 10000)
optimizer.join_optimizer.register_table_size("orders", 1000000)

# Get JOIN optimization suggestions
tables = ["customers", "orders", "items"]
suggested_order = optimizer.join_optimizer.suggest_join_order(tables)
print(suggested_order)  # ['customers', 'orders', 'items'] (smallest first)

# Get database-specific hints
dialect = Customer._dialect
hint = dialect.get_optimizer_hints("SELECT")
# Informix: ""
# Oracle: "/*+ FIRST_ROWS */"
# DB2: ""
```

### Information Schema Queries

```python
def list_all_tables(conn):
    """List tables using database-specific system catalogs"""
    dialect = detect_dialect(conn)

    query = dialect.get_table_list_query()
    # Informix: SELECT tabname FROM systables WHERE ...
    # DB2: SELECT tabname FROM syscat.tables WHERE ...
    # Oracle: SELECT table_name FROM user_tables ...

    results = conn.execute_query(query)
    return [row["table_name"] for row in results]

def get_table_structure(table_name, conn):
    """Get table columns using database-specific catalogs"""
    dialect = detect_dialect(conn)

    query = dialect.get_table_info_query(table_name)
    # Returns column_name, data_type, is_nullable for all databases

    return conn.execute_query(query)
```

### Window Functions with Dialects

```python
from wborm import Window, ROW_NUMBER

def get_top_customers_per_region(conn):
    """Use window functions (works on all databases)"""

    Customer = generate_model("customers", conn)

    # Check if database supports window functions
    if not Customer._dialect.supports_window_functions:
        print("Warning: Window functions not supported")
        return None

    # Build window function query
    row_num = ROW_NUMBER().over(
        partition_by="region",
        order_by="total_sales DESC"
    )

    sql = f"""
        SELECT * FROM (
            SELECT *, {row_num} AS rn
            FROM customers
        ) WHERE rn <= 5
    """

    return Customer.raw_sql(sql).all()
```

---

## Custom Dialects

You can create custom dialects for other databases:

### Step 1: Create Dialect Class

```python
from wborm.dialects import BaseDialect
from typing import Type, Union, Optional

class PostgreSQLDialect(BaseDialect):
    """PostgreSQL dialect"""

    def __init__(self):
        super().__init__()
        self.name = "postgresql"
        self.supports_limit_offset = True
        self.supports_window_functions = True
        self.supports_cte = True
        self.limit_offset_position = "end"  # LIMIT goes at end

    def map_type_to_python(self, db_type: Union[int, str]) -> Type:
        """Map PostgreSQL types to Python"""
        if isinstance(db_type, str):
            type_str = db_type.upper()

            if type_str in ("SMALLINT", "INTEGER", "BIGINT"):
                return int
            elif type_str in ("NUMERIC", "DECIMAL", "REAL", "DOUBLE PRECISION"):
                return float
            elif type_str in ("VARCHAR", "TEXT", "CHAR"):
                return str
            elif type_str == "BOOLEAN":
                return bool
            elif type_str == "BYTEA":
                return bytes

        return str

    def limit_offset_clause(self, limit: Optional[int], offset: Optional[int]) -> str:
        """Generate PostgreSQL LIMIT/OFFSET"""
        if limit is None:
            return ""

        clause = f"LIMIT {limit}"
        if offset:
            clause += f" OFFSET {offset}"

        return clause

    def current_timestamp(self) -> str:
        """PostgreSQL current timestamp"""
        return "CURRENT_TIMESTAMP"

    def concat_function(self, *args: str) -> str:
        """PostgreSQL concatenation (uses ||)"""
        return " || ".join(args)
```

### Step 2: Register Custom Dialect

```python
from wborm import register_dialect

# Register your custom dialect
register_dialect("postgresql", PostgreSQLDialect)

# Now you can use it
dialect = get_dialect("postgresql")
print(dialect.limit_offset_clause(10, 20))  # "LIMIT 10 OFFSET 20"
```

### Step 3: Use with Connection

```python
# If your connection has db_type attribute
conn.db_type = "postgresql"

# Models will automatically use PostgreSQL dialect
Customer = generate_model("customers", conn)
assert isinstance(Customer._dialect, PostgreSQLDialect)
```

---

## Best Practices

### 1. Let WBORM Handle Dialect Selection

```python
# ✅ Good: Automatic detection
Customer = generate_model("customers", conn)
customers = Customer.limit(100).all()

# ❌ Avoid: Hardcoding database-specific SQL
Customer.raw_sql("SELECT SKIP 0 FIRST 100 * FROM customers")
```

### 2. Check Feature Support

```python
# ✅ Good: Check before using advanced features
if Customer._dialect.supports_window_functions:
    # Use window functions
    pass
else:
    # Fallback to alternative approach
    pass

# ❌ Avoid: Assuming features are available
result = Customer.raw_sql("SELECT ROW_NUMBER() OVER ...")  # May fail
```

### 3. Use Dialect Methods for Custom SQL

```python
dialect = Customer._dialect

# ✅ Good: Use dialect methods
concat = dialect.concat_function("first_name", "last_name")
timestamp = dialect.current_timestamp()

# ❌ Avoid: Hardcoding SQL functions
concat = "first_name || last_name"  # May not work on all databases
```

### 4. Register Table Statistics

```python
from wborm import register_table_stats

# ✅ Good: Help optimizer make better decisions
register_table_stats("customers", 10000)
register_table_stats("orders", 1000000)

# Now queries will use this information for JOINs
```

---

## Migration Guide

### Moving from Informix-Only to Multi-Database

If you have existing WBORM code for Informix:

**No changes needed!** Your code will continue to work:

```python
# This code works on Informix AND now also on DB2/Oracle
Customer.filter(status="ACTIVE").limit(100).all()
```

**Optional improvements:**

1. **Remove Informix-specific SQL:**
   ```python
   # Before (Informix-specific)
   Customer.raw_sql("SELECT SKIP 20 FIRST 10 * FROM customers")

   # After (database-agnostic)
   Customer.offset(20).limit(10).all()
   ```

2. **Check dialect when using raw SQL:**
   ```python
   dialect = Customer._dialect
   if dialect.name == "informix":
       # Informix-specific query
   elif dialect.name == "oracle":
       # Oracle-specific query
   ```

---

## Troubleshooting

### Dialect Not Detected

```python
# Check connection db_type
print(conn.db_type)  # Should be "informix", "db2", or "oracle"

# Manually detect
from wborm.dialects import detect_dialect
dialect = detect_dialect(conn)
print(dialect.name)
```

### Wrong SQL Generated

```python
# Verify dialect
Customer = generate_model("customers", conn)
print(f"Using dialect: {Customer._dialect.name}")
print(f"Position: {Customer._dialect.limit_offset_position}")

# Test limit clause
clause = Customer._dialect.limit_offset_clause(10, 20)
print(f"Limit clause: {clause}")
```

### Feature Not Supported

```python
# Check feature support
dialect = Customer._dialect
print(f"Window functions: {dialect.supports_window_functions}")
print(f"CTEs: {dialect.supports_cte}")
print(f"Limit/Offset: {dialect.supports_limit_offset}")

# Fallback if needed
if not dialect.supports_window_functions:
    # Use alternative approach without window functions
    pass
```

---

## Technical Details

### Limit/Offset Positioning

Different databases place LIMIT/OFFSET clauses in different positions:

**Start (after SELECT):**
- Informix: `SELECT SKIP 20 FIRST 10 * FROM ...`

**End (after ORDER BY):**
- DB2: `SELECT * FROM ... ORDER BY ... OFFSET 20 ROWS FETCH FIRST 10 ROWS ONLY`
- Oracle: `SELECT * FROM ... ORDER BY ... OFFSET 20 ROWS FETCH FIRST 10 ROWS ONLY`

WBORM handles this automatically using `limit_offset_position` property.

### Type Mapping

Each dialect maps database types to Python types:

| Python Type | Informix | DB2 | Oracle |
|------------|----------|-----|--------|
| `int` | SERIAL, INTEGER, SMALLINT | INTEGER, SMALLINT, BIGINT | NUMBER, INTEGER |
| `float` | FLOAT, DECIMAL | DECIMAL, FLOAT, DOUBLE | NUMBER, FLOAT, BINARY_DOUBLE |
| `str` | VARCHAR, CHAR, TEXT | VARCHAR, CHAR, CLOB | VARCHAR2, CHAR, CLOB |
| `bytes` | BYTE, BLOB | BLOB, BINARY | BLOB, RAW |
| `bool` | BOOLEAN, CHAR(1) | BOOLEAN | NUMBER(1) |

### Query Building Process

1. Model is created with `generate_model()`
2. Connection dialect is detected with `detect_dialect()`
3. Dialect is attached to model as `Model._dialect`
4. QuerySet uses `Model._dialect.limit_offset_clause()` for pagination
5. SQL is built with dialect-specific syntax

---

## Summary

**Multi-Database Support Achievements:**

✅ **Multi-Database Support**: Informix, DB2, Oracle
✅ **Automatic Dialect Detection**: Zero configuration
✅ **Backward Compatible**: Existing code works unchanged
✅ **Type Mapping**: Database-specific type conversion
✅ **Query Optimization**: Database-specific hints
✅ **Extensible**: Custom dialects supported

**Next Steps:**

- Test with real DB2 and Oracle connections
- Add more database-specific optimizations
- Consider adding MySQL, PostgreSQL, SQL Server support

---

**For more examples and use cases, see:**
- Performance Examples: `docs/performance_examples.md`
- Query Optimization: `wborm/query_optimizer.py`
- Dialect Source Code: `wborm/dialects/`
