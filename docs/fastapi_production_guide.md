# FastAPI Production Guide

This guide shows a practical way to use `wborm + wbjdbc` in Python backends built with FastAPI.

## Recommended Structure

```text
app/
  db.py
  models.py
  schemas.py
  repositories.py
  services.py
  api.py
  main.py
```

## Responsibilities

- `db.py`: creates the `wbjdbc` connection and exports the FastAPI session dependency
- `models.py`: declares ORM models and relationships
- `schemas.py`: creates Pydantic read/write/patch schemas
- `repositories.py`: isolates persistence logic and query composition
- `services.py`: enforces business rules and transaction boundaries
- `api.py`: receives HTTP input and returns HTTP responses
- `main.py`: builds the FastAPI app and registers middleware/handlers

## Connection and Session

Use one shared JDBC connection factory and one `Session` per request:

```python
from wbjdbc import connect_optimized
from wborm import create_session_dependency, register_global_connection

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
get_session = create_session_dependency(conn)
```

For writes, prefer explicit transactions:

```python
session.begin()
session.add(entity)
session.commit()
```

## Modeling

Prefer explicit model declarations for stable domain code:

```python
from decimal import Decimal
from datetime import datetime
from wborm.core import Model
from wborm.fields import Field


class Customer(Model):
    __tablename__ = "customer"
    customer_num = Field(int, primary_key=True)
    name = Field(str, nullable=False, max_length=120)
    credit_limit = Field(Decimal, precision=12, scale=2)
    updated_at = Field(datetime)
```

Relationships can be declared directly:

```python
Customer.has_many("orders", "orders", local_key="customer_num", remote_key="customer_num")
```

## Schemas

Use Pydantic schemas generated from ORM models:

```python
from wborm import create_read_schema, create_write_schema

CustomerRead = create_read_schema(Customer)
CustomerWrite = create_write_schema(Customer, exclude={"customer_num"})
CustomerPatch = create_write_schema(Customer, exclude={"customer_num"}, partial=True)
```

## Repositories

Keep query composition out of endpoints:

```python
class CustomerRepository:
    def __init__(self, session):
        self.session = session

    def list_active(self):
        return self.session.query(Customer).filter(active=True).order_by("customer_num").all()

    def get(self, customer_num: int):
        return self.session.query(Customer).filter(customer_num=customer_num).first()
```

## Services

Use services for write workflows, cascades and locking:

```python
class CustomerService:
    def __init__(self, session):
        self.session = session
        self.repo = CustomerRepository(session)

    def rename(self, customer_num: int, name: str):
        self.session.begin()
        customer = self.repo.get(customer_num)
        if not customer:
            self.session.rollback()
            return None
        customer.name = name
        self.session.commit()
        return customer
```

## API Layer

Register default handlers and observability middleware:

```python
from fastapi import FastAPI
from wborm import register_exception_handlers, register_observability_middleware

app = FastAPI()
register_exception_handlers(app)
register_observability_middleware(app)
```

For list endpoints, the built-in pagination envelope is a good default:

```python
return paginate_query(queryset, page=page, page_size=page_size, envelope=True, request=request)
```

## Migrations

For app evolution, prefer versioned migration objects:

```python
from wborm import Migrator, CreateTableMigration, diff_model_schema

migrator = Migrator(conn)
migrator.apply([CreateTableMigration.from_model("001", Customer)])
```

If you already know the live schema metadata, `diff_model_schema(...)` can generate simple add/drop/rename/modify steps.

## Current Practical Scope

WBORM is now suitable for:

- CRUD-heavy internal systems
- business APIs on top of Informix, DB2 or Oracle through `wbjdbc`
- services that need session tracking, locking, relationships and migrations without a giant ORM stack

WBORM still intentionally keeps some areas simpler than SQLAlchemy/Django ORM:

- migration autogeneration is heuristic, not a full schema planner
- relationship cascades are practical, not exhaustive
- composite primary keys are supported in the core paths, but not every legacy helper is equally sophisticated
