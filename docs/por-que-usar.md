# Por que usar a `wborm`?

## Integração nativa com JDBC
A `wborm` foi feita sob medida para se integrar à biblioteca `wbjdbc`, oferecendo um pipeline Python → JDBC → banco de dados que funciona **sem dependências pesadas**, nem intermediários como SQLAlchemy ou ORMs baseados em SQLAlchemy.

---

## Compatível com bancos "esquecidos" como Informix
Frameworks ORM populares como Django ORM, SQLAlchemy ou Tortoise ORM:
- **Não suportam Informix nativamente**
- Dependem de conectores ODBC ou drivers específicos
- Têm foco em bancos mainstream como Postgres ou MySQL

A `wborm` funciona **sem esforço** com:
- Informix
- DB2
- Oracle
- Firebird
- Qualquer banco compatível com JDBC

---

## Zero mágica, total controle
Ao contrário de ORMs pesados que escondem o SQL:
- Você tem acesso total à query gerada (`.raw_sql()`)
- Pode inspecionar, ajustar e auditar o SQL antes de executar
- `confirm=True` obriga ações destrutivas ou de escrita a serem explícitas

---

## Curva de aprendizado baixa
A API da `wborm` é próxima da mentalidade `pandas`:

```python
Cliente.select("nome").filter(idade=30).all()
```

E se precisar, você ainda pode:

```python
pd.DataFrame([c.to_dict() for c in Cliente.all()])
```

---

## Segurança em primeiro lugar
- Requer `confirm=True` para `add()`, `update()` e `delete()`
- Proíbe atualizações ou exclusões sem cláusula WHERE
- Envolve transações (`BEGIN WORK / COMMIT / ROLLBACK`) automaticamente

---

## Suporte real a introspecção
Você pode fazer:

```python
generate_model("clientes", conn)
```

E obter dinamicamente um modelo com:
- Campos
- Tipos
- PKs e nullable

---

## Combinada com `wbjdbc`, vira um framework JDBC completo para Python
- `wbjdbc` gerencia a conexão com JDBC
- `wborm` mapeia as tabelas e simplifica a consulta
- Juntas, formam uma alternativa leve e Pythonic ao Spring Data, sem Java

---

## Ideal para ETL, inspeção, automações e dashboards
Quer expor os dados do seu ERP Informix num Power BI ou Grafana? A `wborm` com `wbjdbc` te dá:
- Modelos de leitura/transformação simples
- Integração instantânea com Pandas ou Spark
- E tudo em Python puro

---

## Quando usar a `wborm`?

- Você está lidando com bancos legados via JDBC
- Precisa consultar Informix, Oracle, Firebird, etc.
- Quer um ORM leve e explícito
- Deseja transformar dados para DataFrames de forma segura e legível
- Precisa de introspecção automatizada de esquemas

---

WBORM: produtividade, controle e compatibilidade onde os outros ORMs não chegam.