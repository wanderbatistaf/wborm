# Integração entre `wborm` e `wbjdbc`

## Fluxo recomendado

`wbjdbc` cuida da conexão JDBC otimizada. `wborm` cuida do modelo, query builder, sessão e persistência.

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

clientes = Customer.filter(customer_num__gt=100).limit(10).all()
```

## O que cada biblioteca faz

| Recurso | `wbjdbc` | `wborm` |
|---|---|---|
| Inicializa JVM / driver JDBC | ✅ | ❌ |
| Conexão otimizada | ✅ | ❌ |
| Pooling / metadata cache | ✅ | ❌ |
| `execute_batch()` | ✅ | usa quando disponível |
| ORM / modelos | ❌ | ✅ |
| Query builder | ❌ | ✅ |
| Sessão / Unit of Work | ❌ | ✅ |
| Migrações simples | ❌ | ✅ |

## Ganhos com `wbjdbc 2.0`

- `bulk_add()`, `bulk_update()` e `bulk_delete()` passam a aproveitar `execute_batch()`
- o ORM continua igual, mas herda pooling, cache de metadados e conexão otimizada
- o caminho recomendado agora é `connect_optimized(...)`, não `connect_to_db(...)`

## Recursos do `wborm` que fazem diferença com Informix

- `SKIP/FIRST` respeitando o dialeto
- transações explícitas
- locking pessimista com `.lock_for_update()`
- eager loading com `.preload(...)`
- lazy loading parcial com `.only()` / `.defer()`
- hooks, validação, serialização e SQL nativo

## Compatibilidade de ambiente

Para integração real com `wbjdbc`, prefira Python `3.12` ou `3.13`. Em ambientes apenas com `3.14`, a instalação do `JPype1` pode falhar e exigir build tools nativos.
