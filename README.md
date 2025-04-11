[![PyPI](https://img.shields.io/pypi/v/wborm)](https://pypi.org/project/wborm/) [![PyPI - Downloads](https://img.shields.io/pypi/dm/wborm)](https://pypi.org/project/wborm/) [![Build Status](https://github.com/wanderbatistaf/wborm/actions/workflows/publish-package.yml/badge.svg)](https://github.com/wanderbatistaf/wborm/actions) ![License: MIT](https://img.shields.io/github/license/wanderbatistaf/wborm) [![Último Commit](https://img.shields.io/github/last-commit/wanderbatistaf/wborm)](https://github.com/wanderbatistaf/wborm) [![GitHub issues](https://img.shields.io/github/issues/wanderbatistaf/wborm)](https://github.com/wanderbatistaf/wborm/issues) [![GitHub forks](https://img.shields.io/github/forks/wanderbatistaf/wborm?style=social)](https://github.com/wanderbatistaf/wborm) [![GitHub stars](https://img.shields.io/github/stars/wanderbatistaf/wborm?style=social)](https://github.com/wanderbatistaf/wborm) 
# WBORM

**WBORM** é uma biblioteca ORM leve para Python, projetada para funcionar diretamente com bancos de dados legados via JDBC, como Informix, DB2, Oracle e outros. Com foco em transparência, segurança e introspecção automática, ela é a parceira ideal da `wbjdbc`, entregando produtividade sem esconder o SQL.

---

## ✨ Destaques

- Suporte completo a conexões JDBC via `wbjdbc`
- Geração automática de modelos com introspecção
- API fluente com `.select()`, `.filter()`, `.join()` e mais
- Pivot e visualização tabular com bordas coloridas
- Criação de tabelas temporárias com `.create_temp_table()`
- Confirmação obrigatória em operações destrutivas
- Bloqueio de UPDATE/DELETE sem WHERE
- Transações automáticas com rollback
- Cache de resultados com TTL e bypass com `.live()`
- Integração com Pandas e Spark
- Hooks como `before_add()` e `after_update()`
- Criptografia e cache de modelos com `model_cache`
- Stub `.pyi` automático para autocomplete

---

## 📁 Instalação

```bash
pip install wborm wbjdbc
```

---

## 🚀 Começando Rápido

### 1. Conectando via `wbjdbc`

```python
from wbjdbc import connect_to_db

conn = connect_to_db(
    db_type="informix-sqli",
    host="localhost",
    port=1526,
    database="meubanco",
    user="usuario",
    password="senha",
    server="ol_informix"
)
```

### 2. Gerando modelos

```python
from wborm.utils import generate_model, generate_all_models

# Modelo único:
generate_model("clientes", conn)

# Todos os modelos:
generate_all_models(conn)
```

> Os modelos são injetados automaticamente no escopo global com o nome da tabela, ex: `clientes`.

### 3. Consultando dados

```python
clientes.select("nome").filter("idade > 30").order_by("nome").limit(5).show()
```

---

## 🛠️ Definindo modelos manualmente (opcional)

```python
from wborm.core import Model
from wborm.fields import Field

class Cliente(Model):
    __tablename__ = "clientes"
    id = Field(int, primary_key=True)
    nome = Field(str)
    idade = Field(int)

Cliente._connection = conn
```

> Ideal para customizações, uso com `.create_table()` ou definir campos antes da criação no banco.

---

## 🔒 Segurança embutida

- `.add()`, `.update()` e `.delete()` exigem `confirm=True`
- Bloqueio automático de UPDATE ou DELETE sem cláusula WHERE
- Transações protegidas com `BEGIN WORK / COMMIT / ROLLBACK`

---

## 📊 Integração com Pandas e Spark

```python
import pandas as pd

clientes = clientes.all()
df = pd.DataFrame([c.to_dict() for c in clientes])
```

```python
spark.createDataFrame([c.to_dict() for c in clientes.all()])
```

---

## 📦 Cache e performance

- Consultas são cacheadas automaticamente (`TTL = 60s` por padrão)
- Use `.live()` para forçar leitura ao vivo:

```python
clientes.live().filter(ativo=True).all()
```

---

## 📌 Cores no terminal

### Logs (via `termcolor`)
- ✅ Verde: inserções (`add`, `bulk_add`)
- 🟡 Amarelo: atualizações (`update`)
- ❌ Vermelho: erros ou exclusões (`delete`)
- 🔵 Azul / 🔷 Ciano: mensagens informativas e tabelas de cache

### Tabelas renderizadas com `show()` ou `pivot()`
- Modelos criados dinamicamente: bordas **verdes**
- Modelos carregados via cache: bordas **azuis**

---

## 📖 Documentação completa

Acesse:
[https://wanderbatistaf.github.io/wborm](https://wanderbatistaf.github.io/wborm)

Inclui:
- Guia de Início Rápido
- QuerySet com todos os métodos
- Pivot e tabelas temporárias
- Introspecção de chaves estrangeiras
- Cache de modelos e autocomplete

---

## 📜 Licença

Este projeto é licenciado sob a Licença MIT. Consulte o arquivo LICENSE para mais informações.

---

## 🤝 Contribuindo

Pull requests são bem-vindos! Envie sugestões ou melhorias diretamente no [repositório do GitHub](https://github.com/wanderbatistaf/wborm).

