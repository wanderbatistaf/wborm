### Complete Guide to ORM Functions and Utilities

---

### ☝️ Getting Started

Before using `QuerySet` functions, generate the models with:

```python
from wborm.utils import generate_model, generate_all_models

# For a single table:
generate_model("clientes", conn)

# For all tables:
generate_all_models(conn)
```

This will create global variables with the table names, allowing direct calls like `clientes.filter(...)`.

---

## 🔍 `QuerySet` Methods

### `filter(*args, **kwargs)`
Adds `WHERE` clauses to the query.

**Example:**
```python
clientes.filter(nome='João', idade=30)
clientes.filter("idade > 25")
```
**Output:**
```
+--------+-------+
| nome   | idade |
+========+=======+
| João   | 30    |
+--------+-------+
```

---

### `filter_in(column, values)`
Filters values using the `IN` clause.

**Example:**
```python
clientes.filter_in("cidade", ["SP", "RJ"])
```
**Output:**
```
SELECT * FROM clientes WHERE cidade IN ('SP', 'RJ')
```

---

### `not_in(column, values)`
Filters values using the `NOT IN` clause.

**Example:**
```python
clientes.not_in("status", ["inactive"])
```
**Output:**
```
SELECT * FROM clientes WHERE status NOT IN ('inactive')
```

---

### `join(other, on)`
Adds a `JOIN` to the query.

**Example:**
```python
clientes.join("vendas", on="id_cliente")
```
**Output:**
```
SELECT * FROM clientes JOIN vendas ON clientes.id_cliente = vendas.id_cliente
```

---

### `limit(n)` and `offset(n)`
Defines the maximum number of returned records and pagination offset.

```python
clientes.limit(10).offset(20)
```
**Output:**
```
SELECT SKIP 20 FIRST 10 * FROM clientes
```

---

### `order_by(*fields)`
Sorts the results.

```python
clientes.order_by("nome", "-data_criacao")
```
**Output:**
```
SELECT * FROM clientes ORDER BY nome, data_criacao DESC
```

---

### `select(*fields)`
Selects specific fields.

```python
clientes.select("id", "nome").limit(5).show()
```
**Output:**
```
+----+--------+
| id | nome   |
+====+========+
| 1  | João   |
| 2  | Maria  |
+----+--------+
```

---

### `group_by(*fields)` + `having(condition)`
Groups results and applies filters on aggregates.

```python
clientes.select("cidade", "COUNT(*) as total")\
        .group_by("cidade")\
        .having("total > 10")
```
**Output:**
```
+---------+--------+
| cidade  | total  |
+=========+========+
| SP      | 150    |
| RJ      | 120    |
+---------+--------+
```

---

### `distinct()`
Removes duplicates.

```python
clientes.select("nome").distinct().show()
```
**Output:**
```
+--------+
| nome   |
+========+
| João   |
| Maria  |
+--------+
```

---

### `raw_sql(sql)`
Executes raw SQL.

```python
clientes.raw_sql("SELECT * FROM clientes WHERE idade > 30").all()
```

---

### `exists()`
Returns `True` if there are results.

```python
if clientes.filter(ativo=True).exists():
    print("OK")
```

---

### `live()`
Disables query caching.

```python
clientes.live().filter(ativo=True).all()
```

---

### `all()` and `first()`
Executes the query and returns all or the first result.

```python
clientes.all()
clientes.first()
```

---

### `count()`
Returns the number of found records.

```python
clientes.filter(ativo=True).count()
```
**Output:**
```
42
```

---

### `show(tablefmt="grid")`
Displays the results in a table.

```python
clientes.select("nome").limit(5).show()
```
**Output:**
```
+--------+
| nome   |
+========+
| João   |
| Maria  |
+--------+
```

---

### `pivot(index, columns, values)`
Transforms query into a pivot table.

```python
clientes.select("cidade", "status", "COUNT(*) as total")\
        .group_by("cidade", "status")\
        .pivot(index="cidade", columns="status", values="total")
```
**Output:**
```
+-----------+--------+----------+
| cidade    | ativo  | inativo  |
+===========+========+==========+
| SP        | 100    | 20       |
| RJ        | 70     | 10       |
+-----------+--------+----------+
```

---

### `create_temp_table(temp_name)`
Creates a temporary table from the current query.

```python
temp = clientes.filter(ativo=True).create_temp_table("clientes_ativos")
```
**Expected SQL:**
```
CREATE TEMP TABLE clientes_ativos AS (SELECT * FROM clientes WHERE ativo = 'True') WITH NO LOG
```

---

## ⚙️ Model Functions

### `add(confirm=True)`
Adds a new record to the database.

```python
cliente = clientes(id=1, nome="João")
cliente.add(confirm=True)
```
✅ Log color: Green

---

### `bulk_add([...], confirm=True)`
Adds multiple records.

```python
clientes.bulk_add([
    clientes(id=2, nome="Maria"),
    clientes(id=3, nome="Carlos")
], confirm=True)
```
✅ Log color: Green

---

### `update(confirm=True, **where)`
Updates the current record with filter clause.

```python
cliente.nome = "João Silva"
cliente.update(confirm=True, id=1)
```
🟡 Log color: Yellow

---

### `delete(confirm=True, **where)`
Deletes the record.

```python
cliente.delete(confirm=True, id=1)
```
❌ Log color: Red

---

### `create_table()`
Creates the table based on the model definition.

```python
clientes.create_table()
```
**Expected SQL:**
```
CREATE TABLE clientes (id INT NOT NULL PRIMARY KEY, nome VARCHAR(255))
```
🔷 Log color: Cyan

---

## 🎨 Terminal Colors

### Log colors:
- ✅ Green: insertions (`add`, `bulk_add`)
- 🟡 Yellow: updates (`update`)
- ❌ Red: errors or deletions (`delete`)
- 🔵 Blue / 🔷 Cyan: info and cache tables

### Table display:
- Models created live: **green borders**
- Cached models: **blue borders**

---

### ✅ Full Example
```python
# Generate the model
generate_model("clientes", conn)

# Query with chaining
clientes.select("nome", "cidade")\
        .filter("idade > 25")\
        .order_by("nome")\
        .limit(5)\
        .show()
```
**Expected Output:**
```
+----------+-------------------+
| nome     | cidade            |
+==========+===================+
| João     | São Paulo         |
| Maria    | Rio de Janeiro    |
+----------+-------------------+
```

```python
# Pivot table display
clientes.select("cidade", "status", "COUNT(*) as total")\
        .group_by("cidade", "status")\
        .pivot(index="cidade", columns="status", values="total")
```
**Expected Output:**
```
+-----------+--------+----------+
| cidade    | ativo  | inativo  |
+===========+========+==========+
| SP        | 100    | 20       |
| RJ        | 70     | 10       |
+-----------+--------+----------+
```
