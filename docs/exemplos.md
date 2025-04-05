# Exemplos de Uso

## Inserção de Registros

```python
cliente = Cliente(nome="João")
cliente.add(confirm=True)
```

## Inserção em lote

```python
Cliente.bulk_add([
    Cliente(nome="Maria"),
    Cliente(nome="José")
], confirm=True)
```

## Atualização e Exclusão

```python
cliente.nome = "Carlos"
cliente.update(confirm=True, id=1)

cliente.delete(confirm=True, id=1)
```

## Query Encadeada (QuerySet)

```python
clientes = Cliente.select("id", "nome")\
                  .filter(idade=30)\
                  .order_by("nome")\
                  .all()
```

- `filter_in()`
- `not_in()`
- `group_by()`
- `having()`
- `distinct()`
- `count()`
- `exists()`

## Lazy Property e Cache

```python
from wborm.core import lazy_property

class Cliente(Model):
    @lazy_property
    def pedidos(self):
        return Pedido.filter(cliente_id=self.id).all()
```

```python
cliente.invalidate_lazy("pedidos")
```

## Integração com Pandas

```python
import pandas as pd

df = pd.DataFrame([c.to_dict() for c in Cliente.all()])
```

## Integração com Spark

```python
spark.createDataFrame([c.to_dict() for c in Cliente.all()])
```

## Confirmação obrigatória

```python
cliente.delete(confirm=True, id=5)
```

## Log com cores

- Verde: inserção
- Amarelo: atualização
- Vermelho: erro ou exclusão
- Azul/ciano: informações gerais