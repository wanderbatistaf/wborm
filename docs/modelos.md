# Modelos

## Criando um Modelo

```python
from wborm.core import Model
from wborm.fields import Field

class Cliente(Model):
    __tablename__ = "clientes"
    id = Field(int, primary_key=True)
    nome = Field(str, nullable=False)
    idade = Field(int)
```

## Validação de Campos

```python
cliente = Cliente(nome="João")
cliente.validate()  # Valida campos obrigatórios
```

## Criação de Tabela

```python
Cliente().create_table()
```

## Descrição da Tabela

```python
Cliente.describe()
```

Exemplo de saída:

```
+--------+------+-----+----------+
| Campo | Tipo | PK  | Nullable |
+--------+------+-----+----------+
| id     | int  | ✓   | Sim      |
| nome   | str  |     | Não      |
| idade  | int  |     | Sim      |
+--------+------+-----+----------+
```