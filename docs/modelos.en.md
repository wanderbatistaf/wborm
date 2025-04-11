# Models

## Creating a Model

```python
from wborm.core import Model
from wborm.fields import Field

class Cliente(Model):
    __tablename__ = "clientes"
    id = Field(int, primary_key=True)
    nome = Field(str, nullable=False)
    idade = Field(int)
```

## Field Validation

```python
cliente = Cliente(nome="João")
cliente.validate()  # Validates required fields
```

## Table Creation

```python
Cliente().create_table()
```

## Table Description

```python
Cliente.describe()
```

Example output:

```
+--------+------+-----+----------+
| Field  | Type | PK  | Nullable |
+--------+------+-----+----------+
| id     | int  | ✓   | Yes      |
| nome   | str  |     | No       |
| idade  | int  |     | Yes      |
+--------+------+-----+----------+
```