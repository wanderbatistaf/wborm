# Why Use `wborm`?

## Native Integration with JDBC
`wborm` is tailor-made to integrate seamlessly with the `wbjdbc` library, offering a Python → JDBC → database pipeline that works **without heavy dependencies**, and with no need for intermediaries like SQLAlchemy or SQLAlchemy-based ORMs.

---

## Compatible with “Forgotten” Databases like Informix
Popular ORM frameworks such as Django ORM, SQLAlchemy, or Tortoise ORM:
- **Do not support Informix natively**
- Depend on ODBC connectors or specialized drivers
- Focus mainly on mainstream databases like Postgres or MySQL

`wborm` works **effortlessly** with:
- Informix  
- DB2  
- Oracle  
- Firebird  
- Any database compatible with JDBC

---

## Zero Magic, Full Control
Unlike heavy ORMs that hide SQL details:
- You get full access to the generated query (`.raw_sql()`)
- You can inspect, customize, and audit the SQL before execution
- `confirm=True` ensures destructive or write actions are explicit

---

## Low Learning Curve
`wborm`’s API is close to the `pandas` mindset:

```python
Cliente.select("nome").filter(idade=30).all()
```

And if needed, you can still do:

```python
pd.DataFrame([c.to_dict() for c in Cliente.all()])
```

---

## Security First
- Requires `confirm=True` for `add()`, `update()`, and `delete()`
- Blocks updates or deletions without a WHERE clause
- Wraps operations in transactions (`BEGIN WORK / COMMIT / ROLLBACK`) automatically

---

## Real Introspection Support
You can do:

```python
generate_model("clientes", conn)
```

And dynamically get a model with:
- Fields
- Types
- PKs and nullable flags

---

## Combined with `wbjdbc`, Becomes a Full JDBC Framework for Python
- `wbjdbc` manages the JDBC connection
- `wborm` maps tables and simplifies querying
- Together, they form a lightweight, Pythonic alternative to Spring Data — with no Java needed

---

## Perfect for ETL, Inspection, Automation, and Dashboards
Need to expose your Informix ERP data in Power BI or Grafana?  
`wborm` + `wbjdbc` give you:
- Simple transformation/read models
- Instant integration with Pandas or Spark
- All in pure Python

---

## When to Use `wborm`

- You are working with legacy databases via JDBC  
- You need to query Informix, Oracle, Firebird, etc.  
- You want a lightweight and explicit ORM  
- You want to transform data into DataFrames safely and clearly  
- You need automated schema introspection  

---

WBORM: productivity, control, and compatibility where other ORMs won’t go.