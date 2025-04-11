# Integration Between `wborm` and `wbjdbc`

## Why Use `wborm` Together with `wbjdbc`?

### 1. Native and Direct Integration

`wborm` was **designed to work directly with the connection created by `wbjdbc`**, without needing to adapt cursors, drivers, or perform additional mappings.

```python
from wbjdbc import connect_to_db
from my_model import Cliente

conn = connect_to_db(...)
Cliente._connection = conn
clientes = Cliente.filter(idade=25).all()
```

---

### 2. Full Focus on JDBC and Informix Ecosystem

- `wbjdbc` solves a core problem: **connecting Python to legacy databases via JDBC**, like **Informix**, which usually requires Java.
- `wborm` handles the next step: **querying and manipulating those data through an ORM**, without writing raw SQL all the time.

Together, they create a natural flow:
```
JDBC → wbjdbc → connection → wborm → model/table
```

---

### 3. Safety and Abstraction Without Losing Control

- `wbjdbc` manages JVM, classpath, `.jar` files, authentication, etc.
- `wborm` abstracts SQL reading and writing safely: requires `confirm=True`, validates fields, enforces `WHERE` on deletes, etc.
- Neither tries to hide too much of what’s going on.

You gain productivity **without losing SQL clarity**.

---

### 4. Perfect for ETL, BI, and Data Transformation Workflows

With `wbjdbc`, you can already run JDBC queries from Python. But with `wborm`, you can:

- Map tables as classes  
- Use `.filter()` and `.select()` without worrying about raw SQL strings  
- Integrate directly with Pandas or Spark  

Example using DataFrame:

```python
from wborm.core import Model
import pandas as pd

df = pd.DataFrame([c.to_dict() for c in Cliente.all()])
```

---

### 5. Compatibility with Informix Advanced Features

`wborm` respects Informix-specific behavior such as:

- `SKIP` and `FIRST` immediately after `SELECT`  
- Transaction-level locks (`BEGIN WORK / COMMIT WORK`)  
- Prevents updates or deletes without proper `WHERE` clauses  

Things that generic ORMs often handle poorly for Informix-like databases.

---

## Comparison Table

| Feature                        | wbjdbc                         | wborm                            |
|-------------------------------|--------------------------------|----------------------------------|
| JVM Initialization            | ✅                              | ❌                               |
| Loads `.jar` and drivers      | ✅                              | ❌                               |
| Creates JDBC connection       | ✅                              | ❌                               |
| Executes SQL                  | ✅ (`cursor.execute`)           | ✅ (`.raw_sql()` or `.filter()`) |
| ORM with validation and models| ❌                              | ✅                               |
| Automatic model generation    | ❌                              | ✅ (`generate_model`)            |

---

## Conclusion

If you work with Informix, DB2, Oracle, or any other JDBC-compatible database — the `wbjdbc` + `wborm` combo offers:

- Reliable and automated Java-based connection  
- Lightweight and powerful ORM with validation and safety  
- Seamless usage with Pandas, Spark, and any Python tool

Harness the power of JDBC with the simplicity of Python!