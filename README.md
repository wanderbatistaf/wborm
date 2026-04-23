[![PyPI](https://img.shields.io/pypi/v/wborm)](https://pypi.org/project/wborm/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/wborm)](https://pypi.org/project/wborm/)
[![CI](https://github.com/wanderbatistaf/wborm/actions/workflows/ci.yml/badge.svg)](https://github.com/wanderbatistaf/wborm/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/pypi/pyversions/wborm)](https://pypi.org/project/wborm/)
![License: MIT](https://img.shields.io/github/license/wanderbatistaf/wborm)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# WBORM 🚀

**Enterprise-Ready ORM para Python com Performance de Alto Nível**

WBORM é uma biblioteca ORM profissional para Python, projetada para trabalhar com bancos de dados legados via JDBC (Informix, DB2, Oracle, entre outros). Com foco em **performance, escalabilidade e produtividade**, oferece recursos avançados de caching, lazy loading, paginação eficiente e monitoramento automático.

---

## ✨ Destaques v0.4.0

### 🎯 Performance & Escalabilidade

- **Cache Configurável**: 3 backends (Memory, LRU, Disk) com TTL customizável
- **Lazy Loading**: `.only()` e `.defer()` para otimizar queries
- **Paginação Eficiente**: Page-based e cursor-based para milhões de registros
- **Monitoramento Automático**: Track de todas as queries com métricas detalhadas
- **Otimização de Queries**: Análise automática de JOIN/GROUP BY/PIVOT

### 💎 Core Features

- Conexão direta via JDBC usando `wbjdbc`
- Geração automática de modelos com introspecção
- API fluente: `.select()`, `.filter()`, `.join()`, `.group_by()`, `.order_by()`
- JOINs avançados: `LEFT ANTI`, `RIGHT ANTI`
- Pivot dinâmico: `.pivot()`
- Tabelas temporárias: `.create_temp_table()`
- Visualização terminal com cores e paginação
- Operações CRUD com segurança
- Integração Pandas e Spark
- Autocomplete com stubs `.pyi`
- Expressões SQL: `col()`, `now()`, `date()`, `raw()`

---

## 📁 Instalação

```bash
pip install wborm wbjdbc
```

Para uso real com `wbjdbc 2.0`, prefira Python `3.12` ou `3.13`. Neste momento, ambientes apenas com Python `3.14` podem falhar na instalação do `JPype1`, que é dependência do `wbjdbc`.

---

## 🚀 Quick Start

### Conexão e Modelos

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
    server="informix"
)

register_global_connection(conn)

# Gerar modelo
Cliente = generate_model("customer")
```

### Consultas Básicas

```python
# Query simples
clientes = Cliente.filter(status="ATIVO").all()

# Com ordenação e limite
clientes = (
    Cliente
    .filter(idade__gt=18)
    .order_by("nome")
    .limit(10)
    .all()
)

# Exibir resultados
Cliente.filter(cidade="São Paulo").show()
```

### Sessão, transação e Unit of Work

```python
session = Cliente.session()

with session.transaction():
    cliente = session.query(Cliente).filter(id=101).first()
    cliente.nome = "Novo nome"
```

### Eager loading, locking e bulk operations

```python
# Eager loading básico
clientes = Cliente.preload("orders").limit(20).all()

# Pessimistic locking
cliente = Cliente.filter(id=101).lock_for_update().first()

# Bulk operations com execute_batch() do wbjdbc quando disponível
Cliente.bulk_add([Cliente(id=1, nome="A"), Cliente(id=2, nome="B")], confirm=True)
Cliente.bulk_delete([1, 2], confirm=True)
```

### Migrações

```python
from wborm import CreateTableMigration, Migrator
from wborm.core import Model
from wborm.fields import Field

class CustomerNote(Model):
    __tablename__ = "customer_notes"
    id = Field(int, primary_key=True)
    customer_id = Field(int, nullable=False)
    note = Field(str, max_length=255)

migrator = Migrator(conn)
migrations = [
    CreateTableMigration.from_model("001", CustomerNote)
]

migrator.apply(migrations)
```

### FastAPI

Instalação opcional:

```bash
pip install "wborm[api]"
```

Integração por request:

```python
from fastapi import Depends, FastAPI
from wborm import create_session_dependency

app = FastAPI()
get_session = create_session_dependency(conn)

@app.get("/customers/{customer_id}")
def get_customer(customer_id: int, session=Depends(get_session)):
    customer = session.query(Customer).filter(customer_num=customer_id).first()
    return customer.to_dict() if customer else {"detail": "not found"}
```

Também há helpers prontos para API:

- `create_read_schema(...)` e `create_write_schema(...)` para Pydantic
- `register_exception_handlers(app)` para mapear erros do ORM em HTTP
- `apply_api_filters(...)` para whitelisting de filtros
- `paginate_query(...)` para resposta paginada padrão

---

## 🎯 Performance Features (Epic 2)

### 1. Cache Configurável

```python
from wborm import configure_cache, LRUCacheBackend

# Configurar cache global
configure_cache(
    ttl=300,  # 5 minutos
    backend=LRUCacheBackend(max_size=100)
)

# Cache por query
clientes = Cliente.filter(tipo="VIP").cache(ttl=600).all()

# Bypass cache (força query ao vivo)
saldo = Conta.filter(id=123).live().first()

# Estatísticas
from wborm import cache_stats
stats = cache_stats()
print(f"Hit rate: {stats['hit_rate']:.1%}")
```

**Backends disponíveis**:
- `MemoryCacheBackend`: Dict simples, rápido
- `LRUCacheBackend`: Evicção LRU inteligente  
- `DiskCacheBackend`: Persistente em disco

### 2. Lazy Loading

```python
# Carregar apenas colunas necessárias
produtos = Produto.only("id", "nome", "preco").all()
# Reduz 50-70% de dados com BLOBs!

# Adiar colunas pesadas
produtos = Produto.defer("imagem_blob", "descricao_completa").all()

# Batch loading (evita N+1)
from wborm import batch_load_fields
batch_load_fields(produtos, ["descricao", "categoria"])
```

Também há eager loading via `.preload(...)` para relações registradas.

### 3. Paginação Eficiente

```python
# Paginação simples
page = Cliente.filter(ativo=True).paginate(page=2, page_size=50)

print(f"Página {page.page} de {page.pages}")
for cliente in page.items:
    print(cliente.nome)

# Cursor pagination (para milhões de registros)
from wborm import cursor_paginate

page1 = cursor_paginate(Cliente.all(), page_size=1000)
page2 = cursor_paginate(Cliente.all(), cursor=page1['next_cursor'])
# Performance O(1) constante!
```

### 4. Monitoramento Automático

```python
from wborm import configure_monitoring, print_performance_report

# Configurar threshold de 0.5s
configure_monitoring(slow_query_threshold=0.5)

# Executar queries...
Cliente.all()
Pedido.filter(status="PENDENTE").all()

# Ver relatório
print_performance_report()
```

**Output**:
```
============================================================
WBORM Performance Report
============================================================
Total Queries:        245
Slow Queries:         12 (4.9%)
Average Duration:     0.145s
Cache Hit Rate:       73.5%

Top 5 Slowest Queries:
------------------------------------------------------------
1. 1.234s (1,500 rows)
   SELECT * FROM orders WHERE...
```

### 5. Otimização de Queries

```python
from wborm import analyze_query, register_table_stats

# Registrar tamanhos de tabelas
register_table_stats("clientes", 50000)
register_table_stats("pedidos", 1000000)

# Analisar query
sql = "SELECT * FROM clientes JOIN pedidos JOIN items"
analysis = analyze_query(sql)

print(analysis['complexity_score'])  # 8
print(analysis['suggestions'])
# ["Multiple JOINs detected - ensure JOIN columns are indexed"]

# Agregações otimizadas
from wborm import Count, Sum, Avg, aggregate_with_cache

results = aggregate_with_cache(
    Pedido.filter(status="COMPLETO"),
    total=Count(),
    valor_total=Sum("valor"),
    valor_medio=Avg("valor")
)
# Cached automaticamente por 5 minutos!
```

---

## 📊 JOINs e Agregações

### JOINs

```python
# INNER JOIN
resultado = (
    Cliente
    .join(Pedido, "cliente_id")
    .filter(t1(status="ATIVO"))
    .show()
)

# LEFT JOIN
resultado = Cliente.join(Pedido, "cliente_id", "left").all()

# ANTI JOIN (clientes sem pedidos)
sem_pedidos = Cliente.join(Pedido, "cliente_id", "left_anti").all()
```

### Relacionamentos

```python
# Relações 1:1 / 1:N podem ser inferidas das FKs pela introspecção
pedidos = Cliente.preload("orders").first().orders

# N:N explícito via tabela associativa
Usuario.many_to_many("roles", Role, through="usuario_role", local_key="usuario_id", remote_key="role_id")
roles = Usuario.filter(id=10).first().roles
```

### Agregações

```python
# COUNT
total = Cliente.count()

# Agregações múltiplas
from wborm import Count, Sum, Avg

stats = aggregate_with_cache(
    Pedido.all(),
    total_pedidos=Count(),
    valor_total=Sum("valor"),
    ticket_medio=Avg("valor")
)
```

### PIVOT

```python
# Pivot dinâmico
vendas.pivot(
    index="categoria",
    columns="mes",
    values=["quantidade", "valor"]
)
```

---

## 🔧 Desenvolvimento

### Configuração

```bash
# Instalar dependências
pip install -e ".[dev]"

# Formatar código
make format

# Rodar testes
make test

# Verificar tipos
make type-check

# Tudo de uma vez
make check
```

### Tooling

- **black**: Formatação de código
- **isort**: Organização de imports
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: Testes

---

## 📚 Documentação Completa

- [Cache Configuration Guide](docs/cache_configuration.md)
- [Epic 2 Examples](docs/performance_features_examples.md)
- [Refactoring Report](REFACTORING.md)
- [Contributing Guide](CONTRIBUTING.md)

---

## 🎯 Roadmap

### ✅ Core Refactoring (100%)
- Módulos utilitários extraídos
- Código morto removido
- Type hints completos
- Suite de testes
- CI/CD completo

### ✅ Performance & Escalabilidade (100%)
- Cache configurável com múltiplos backends
- Lazy loading de colunas
- Paginação eficiente (offset + cursor)
- Monitoramento automático de queries
- Otimização de JOIN/GROUP BY/PIVOT

### 🔜 Multi-Database Support
- Suporte DB2
- Suporte Oracle
- Type mapping específico por banco
- Documentação de diferenças

### 🔜 Fluent API Enhancements
- Query builders avançados
- Subquery support melhorado
- Sessões e locking mais avançados

---

## 📌 Estado atual do ORM

Hoje o `wborm` já cobre:

- mapeamento objeto <-> tabela e coluna ↔ atributo
- suporte a tipos, validação, hooks e serialização
- CRUD, SQL nativo, query builder, joins, paginação e cache
- relacionamentos 1:1, 1:N e N:N explícito
- lazy loading parcial, eager loading básico, sessão/transação
- identity map, unit of work básico, optimistic/pessimistic locking
- bulk insert/update/delete e migrações simples versionadas

O que continua propositalmente simples:

- migrações ainda são SQL-first, não um DSL completo
- eager loading e N:N cobrem o caso prático, não uma engine relacional genérica ao nível de SQLAlchemy/Django ORM

---

## 📈 Performance Benchmarks

| Feature | Antes | Depois | Ganho |
|---------|-------|--------|-------|
| Cache hit rate | - | 85%+ | - |
| Data transfer (com BLOBs) | 100% | 30-50% | 50-70% |
| Pagination (1M+ records) | O(n) | O(1) | Constante |
| Slow query detection | Manual | Automático | 100% |

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Veja [CONTRIBUTING.md](CONTRIBUTING.md) para guidelines.

```bash
# Fork o projeto
# Crie uma branch
git checkout -b feature/nova-feature

# Commit suas mudanças
git commit -m "feat: adiciona nova feature"

# Push para a branch
git push origin feature/nova-feature

# Abra um Pull Request
```

---

## 📄 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

---

## 🙏 Agradecimentos

- Comunidade Python
- Colaboradores do projeto
- Usuários e early adopters

---

## 📞 Suporte

- **Issues**: [GitHub Issues](https://github.com/wanderbatistaf/wborm/issues)
- **Documentação**: [Docs](docs/)
- **Email**: [wanderbatistaf@gmail.com]

---

**WBORM** - Production-ready ORM com performance enterprise-level! 🚀
