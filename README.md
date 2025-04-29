[![PyPI](https://img.shields.io/pypi/v/wborm)](https://pypi.org/project/wborm/) [![PyPI - Downloads](https://img.shields.io/pypi/dm/wborm)](https://pypi.org/project/wborm/) [![Build Status](https://github.com/wanderbatistaf/wborm/actions/workflows/publish-package.yml/badge.svg)](https://github.com/wanderbatistaf/wborm/actions) ![License: MIT](https://img.shields.io/github/license/wanderbatistaf/wborm) [![Último Commit](https://img.shields.io/github/last-commit/wanderbatistaf/wborm)](https://github.com/wanderbatistaf/wborm) [![GitHub issues](https://img.shields.io/github/issues/wanderbatistaf/wborm)](https://github.com/wanderbatistaf/wborm/issues) [![GitHub forks](https://img.shields.io/github/forks/wanderbatistaf/wborm?style=social)](https://github.com/wanderbatistaf/wborm) [![GitHub stars](https://img.shields.io/github/stars/wanderbatistaf/wborm?style=social)](https://github.com/wanderbatistaf/wborm) 

# WBORM

**WBORM** é uma biblioteca ORM leve para Python, projetada para trabalhar com bancos de dados legados via JDBC (Informix, DB2, Oracle, entre outros).  
Com foco em transparência, segurança e geração automática de modelos, é a parceira ideal da `wbjdbc` para entregar produtividade sem esconder o SQL.

---

## ✨ Destaques

- Conexão direta via JDBC usando `wbjdbc`
- Geração automática de modelos com introspecção
- API fluente: `.select()`, `.filter()`, `.join()`, `.group_by()`, `.order_by()`
- Novos JOINs avançados: `LEFT ANTI`, `RIGHT ANTI`
- Pivot dinâmico diretamente do queryset com `.pivot()`
- Criação de tabelas temporárias com `.create_temp_table()`
- Visualização de resultados com paginação e cores no terminal
- Filtros flexíveis: strings, expressões, listas, dicionários
- Operações CRUD com segurança: `confirm=True` obrigatório
- Cache de consultas automático, com bypass por `.live()`
- Integração direta com Pandas e Spark
- Criptografia e persistência de modelos em cache local (`.wbmodels/`)
- Autocomplete melhorado via stub `.pyi` gerado automaticamente
- Suporte a expressões SQL dinâmicas: `col()`, `now()`, `date()`, `raw()`
- Totalmente retrocompatível com versões anteriores

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

# Gerar um modelo
generate_model("clientes", conn)

# Gerar todos os modelos
generate_all_models(conn)
```

> Modelos são automaticamente injetados no escopo global com o nome da tabela.

---

## 📊 Consultando dados de forma fluente

```python
clientes \
    .select("nome", "idade") \
    .filter("idade > 18") \
    .order_by("nome") \
    .limit(10) \
    .show()
```

---

## 📈 Criando pivôs e tabelas temporárias

```python
# Pivot
clientes.pivot(index="cidade", columns="sexo", values=["idade"])

# Tabela temporária
top10 = clientes.filter("idade > 30").limit(10).create_temp_table("tmp_top10")
top10.show()
```

---

## 🔒 Segurança embutida

- Operações `.add()`, `.update()`, `.delete()` exigem `confirm=True`.
- UPDATE ou DELETE sem WHERE são bloqueados automaticamente.
- Transações protegidas com `BEGIN WORK / COMMIT / ROLLBACK` automático.

---

## 📦 Cache inteligente

- Consultas armazenadas automaticamente por 60 segundos.
- Forçar leitura ao vivo com `.live()`:

```python
clientes.live().filter(ativo=True).all()
```

---

## 🎨 Visualização com cores no terminal

- Tabelas dinâmicas coloridas:
  - 🔵 Azul para resultados do cache.
  - 🟢 Verde para consultas ao vivo.
- Paginação automática para grandes volumes de dados.

---

## 📚 Documentação Completa

Acesse:
[https://wanderbatistaf.github.io/wborm](https://wanderbatistaf.github.io/wborm)

Inclui:
- Guia de Início Rápido
- API completa do QuerySet
- Uso de Pivot e Tabelas Temporárias
- Geração automática de modelos
- Cache local e stub de autocomplete

---

## 📜 Licença

Este projeto é licenciado sob a Licença MIT. Consulte o arquivo LICENSE para mais informações.

---

## 🤝 Contribuindo

Pull requests são bem-vindos!  
Sugestões e melhorias podem ser enviadas diretamente no [repositório do GitHub](https://github.com/wanderbatistaf/wborm).
