### Guia Completo das Funções e Utilitários ORM

---

### ☝️ Como começar

Antes de usar as funções do `QuerySet`, gere os modelos com:

```python
from wborm.utils import generate_model, generate_all_models

# Para uma única tabela:
generate_model("clientes", conn)

# Para todas as tabelas:
generate_all_models(conn)
```

Isso criará variáveis globais com o nome das tabelas, permitindo chamadas diretas como `clientes.filter(...)`.

---

## 🔍 Funções do `QuerySet`

### `filter(*args, **kwargs)`
Adiciona cláusulas `WHERE` à consulta. 

**Exemplo:**
```python
clientes.filter(nome='João', idade=30)
clientes.filter("idade > 25")
```
**Saída:**
```
+--------+-------+
| nome   | idade |
+========+=======+
| João   | 30    |
+--------+-------+
```

---

### `filter_in(column, values)`
Filtra valores com cláusula `IN`.

**Exemplo:**
```python
clientes.filter_in("cidade", ["SP", "RJ"])
```
**Saída:**
```
SELECT * FROM clientes WHERE cidade IN ('SP', 'RJ')
```

---

### `not_in(column, values)`
Filtra valores com cláusula `NOT IN`.

**Exemplo:**
```python
clientes.not_in("status", ["inativo"])
```
**Saída:**
```
SELECT * FROM clientes WHERE status NOT IN ('inativo')
```

---

### `join(other, on)`
Adiciona um `JOIN` à consulta.

**Exemplo:**
```python
clientes.join("vendas", on="id_cliente")
```
**Saída:**
```
SELECT * FROM clientes JOIN vendas ON clientes.id_cliente = vendas.id_cliente
```

---

### `limit(n)` e `offset(n)`
Define o número máximo de registros retornados e o offset para paginação.

```python
clientes.limit(10).offset(20)
```
**Saída:**
```
SELECT SKIP 20 FIRST 10 * FROM clientes
```

---

### `order_by(*fields)`
Ordena os resultados.

```python
clientes.order_by("nome", "-data_criacao")
```
**Saída:**
```
SELECT * FROM clientes ORDER BY nome, data_criacao DESC
```

---

### `select(*fields)`
Seleciona campos específicos.

```python
clientes.select("id", "nome").limit(5).show()
```
**Saída:**
```
+----+--------+
| id | nome   |
+====+========+
| 1  | João   |
| 2  | Maria  |
+----+--------+
```

---

### `group_by(*fields)` + `having(condition)`
Agrupa resultados e aplica filtros sobre agregações.

```python
clientes.select("cidade", "COUNT(*) as total")\
        .group_by("cidade")\
        .having("total > 10")
```
**Saída:**
```
+---------+--------+
| cidade  | total  |
+=========+========+
| SP      | 150    |
| RJ      | 120    |
+---------+--------+
```

---

### `distinct()`
Remove duplicatas.

```python
clientes.select("nome").distinct().show()
```
**Saída:**
```
+--------+
| nome   |
+========+
| João   |
| Maria  |
+--------+
```

---

### `raw_sql(sql)`
Executa SQL puro.

```python
clientes.raw_sql("SELECT * FROM clientes WHERE idade > 30").all()
```

---

### `exists()`
Retorna `True` se houver resultados.

```python
if clientes.filter(ativo=True).exists():
    print("OK")
```

---

### `live()`
Desativa o cache da consulta.

```python
clientes.live().filter(ativo=True).all()
```

---

### `all()` e `first()`
Executa a consulta e retorna todos os resultados ou apenas o primeiro.

```python
clientes.all()
clientes.first()
```

---

### `count()`
Retorna o número de registros encontrados.

```python
clientes.filter(ativo=True).count()
```
**Saída:**
```
42
```

---

### `show(tablefmt="grid")`
Renderiza os resultados em tabela.

```python
clientes.select("nome").limit(5).show()
```
**Saída:**
```
+--------+
| nome   |
+========+
| João   |
| Maria  |
+--------+
```

---

### `pivot(index, columns, values)`
Transforma a consulta em tabela dinâmica.

```python
clientes.select("cidade", "status", "COUNT(*) as total")\
        .group_by("cidade", "status")\
        .pivot(index="cidade", columns="status", values="total")
```
**Saída:**
```
+-----------+--------+----------+
| cidade    | ativo  | inativo  |
+===========+========+==========+
| SP        | 100    | 20       |
| RJ        | 70     | 10       |
+-----------+--------+----------+
```

---

### `create_temp_table(temp_name)`
Cria uma tabela temporária a partir da consulta atual.

```python
temp = clientes.filter(ativo=True).create_temp_table("clientes_ativos")
```
**Saída esperada:**
```
CREATE TEMP TABLE clientes_ativos AS (SELECT * FROM clientes WHERE ativo = 'True') WITH NO LOG
```

---

## ⚙️ Funções do Modelo

### `add(confirm=True)`
Adiciona um novo registro ao banco.

```python
cliente = clientes(id=1, nome="João")
cliente.add(confirm=True)
```
**Cor de log:** Verde ✅

---

### `bulk_add([...], confirm=True)`
Adiciona vários registros de uma vez.

```python
clientes.bulk_add([
    clientes(id=2, nome="Maria"),
    clientes(id=3, nome="Carlos")
], confirm=True)
```
**Cor de log:** Verde ✅

---

### `update(confirm=True, **where)`
Atualiza o registro atual no banco com base na cláusula.

```python
cliente.nome = "João Silva"
cliente.update(confirm=True, id=1)
```
**Cor de log:** Amarelo 🟡

---

### `delete(confirm=True, **where)`
Exclui o registro do banco.

```python
cliente.delete(confirm=True, id=1)
```
**Cor de log:** Vermelho ❌

---

### `create_table()`
Cria a tabela no banco de dados com base nos campos definidos no modelo.

```python
clientes.create_table()
```
**Saída esperada:**
```
CREATE TABLE clientes (id INT NOT NULL PRIMARY KEY, nome VARCHAR(255))
```
**Cor de log:** Ciano 🔷

---

## 🎨 Cores e Feedback Visual

### Logs com Cores (via `termcolor`):

- ✅ Verde: inserções (`add`, `bulk_add`)
- 🟡 Amarelo: atualizações (`update`)
- ❌ Vermelho: erros ou exclusões (`delete`)
- 🔵 Azul / 🔷 Ciano: mensagens informativas e tabelas de cache

### Tabelas Renderizadas com Cor
- Quando `show()` ou `pivot()` são chamados:
  - Modelos carregados do cache: **bordas azuis** 🔵
  - Modelos criados dinamicamente: **bordas verdes** ✅

---

### ✅ Exemplo Completo
```python
# Gera o modelo
generate_model("clientes", conn)

# Consulta com encadeamento
clientes.select("nome", "cidade")\
        .filter("idade > 25")\
        .order_by("nome")\
        .limit(5)\
        .show()
```

Saída esperada:
```
+----------+-------------------+
| nome     | cidade            |
+==========+===================+
| João     | São Paulo         |
| Maria    | Rio de Janeiro    |
+----------+-------------------+
```

```python
# Criar e exibir uma tabela dinâmica
clientes.select("cidade", "status", "COUNT(*) as total")\
        .group_by("cidade", "status")\
        .pivot(index="cidade", columns="status", values="total")
```

Saída:
```
+-----------+--------+----------+
| cidade    | ativo  | inativo  |
+===========+========+==========+
| SP        | 100    | 20       |
| RJ        | 70     | 10       |
+-----------+--------+----------+
```

---

