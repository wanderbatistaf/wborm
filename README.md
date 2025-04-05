[![PyPI](https://img.shields.io/pypi/v/wborm)](https://pypi.org/project/wborm/) [![PyPI - Downloads](https://img.shields.io/pypi/dm/wborm)](https://pypi.org/project/wborm/) [![Build Status](https://github.com/wanderbatistaf/wborm/actions/workflows/publish-package.yml/badge.svg)](https://github.com/wanderbatistaf/wborm/actions) ![License: MIT](https://img.shields.io/github/license/wanderbatistaf/wborm) [![Último Commit](https://img.shields.io/github/last-commit/wanderbatistaf/wborm)](https://github.com/wanderbatistaf/wborm) [![GitHub issues](https://img.shields.io/github/issues/wanderbatistaf/wborm)](https://github.com/wanderbatistaf/wborm/issues) [![GitHub forks](https://img.shields.io/github/forks/wanderbatistaf/wborm?style=social)](https://github.com/wanderbatistaf/wborm) [![GitHub stars](https://img.shields.io/github/stars/wanderbatistaf/wborm?style=social)](https://github.com/wanderbatistaf/wborm) 
# WBORM

**WBORM** é uma biblioteca ORM leve para Python, projetada para funcionar diretamente com bancos de dados legados via JDBC, como Informix, DB2, Oracle e outros. Com foco em transparência, segurança e introspecção automática, ela é a parceira ideal da `wbjdbc`, entregando produtividade sem esconder o SQL.

---

## ✨ Destaques

- Suporte completo a conexões JDBC via `wbjdbc`
- Geração automática de modelos com introspecção
- API fluente com `.select()`, `.filter()`, `.join()` e mais
- Confirmação obrigatória em operações destrutivas
- Bloqueio de UPDATE/DELETE sem WHERE
- Transações automáticas com rollback
- Integração com Pandas e Spark
- Eager/lazy loading, cache, hooks e muito mais

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

### 2. Gerando modelo com introspecção

```python
from wborm.utils import generate_model

Cliente = generate_model("clientes", conn)
```

> Isso detecta automaticamente os campos, tipos, PKs e campos nulos da tabela!

### 3. Consultando dados

```python
clientes = Cliente.filter(idade=30).order_by("nome").all()
for c in clientes:
    print(c.nome)
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

> Ideal para quem quer customizar comportamento, usar `create_table()` ou definir campos antes de existir no banco.

---

## 🔒 Segurança embutida

- `.add()`, `.update()` e `.delete()` exigem `confirm=True`
- UPDATE/DELETE sem WHERE são bloqueados
- Transações com `BEGIN WORK / COMMIT / ROLLBACK`

---

## 📊 Integração com Pandas e Spark

```python
import pandas as pd

clientes = Cliente.all()
df = pd.DataFrame([c.to_dict() for c in clientes])
```

```python
spark.createDataFrame([c.to_dict() for c in Cliente.all()])
```

---

## 📖 Documentação completa

Acesse:
[https://wanderbatistaf.github.io/wborm](https://wanderbatistaf.github.io/wborm)

Inclui:
- Guia de Início Rápido
- Modelos com introspecção
- Operadores, joins, filtros, agrupamentos
- Lazy loading, hooks, cache, validações
- Integração wbjdbc-wborm

---

## 📜 Licença

Este projeto é licenciado sob a Licença MIT. Consulte o arquivo LICENSE para mais informações.

---

## 🤝 Contribuindo

Pull requests são bem-vindos! Envie sugestões ou melhorias diretamente no [repositório do GitHub](https://github.com/wanderbatistaf/wborm).

