# Integração entre `wborm` e `wbjdbc`

## Por que usar `wborm` junto com `wbjdbc`?

### 1. Integração nativa e direta

A `wborm` foi **projetada para usar diretamente a conexão criada com o `wbjdbc`**, sem precisar adaptar cursores, drivers ou fazer mapeamentos adicionais.

```python
from wbjdbc import connect_to_db
from meu_modelo import Cliente

conn = connect_to_db(...)
Cliente._connection = conn
clientes = Cliente.filter(idade=25).all()
```

---

### 2. Foco total no ecossistema JDBC e Informix

- `wbjdbc` resolve um problema base: **conectar Python com bancos legados via JDBC**, como **Informix**, que normalmente exige Java.
- `wborm` resolve o passo seguinte: **consultar e manipular esses dados via ORM**, sem escrever SQL na mão o tempo todo.

Juntas, formam um fluxo natural:
```
JDBC → wbjdbc → conexão → wborm → modelo/tabela
```

---

###  3. Segurança e abstração sem perder controle

- `wbjdbc` lida com JVM, classpath, arquivos `.jar`, autenticação, etc.
- `wborm` abstrai a escrita e leitura SQL com segurança: exige `confirm=True`, valida campos, exige `where` para deletes etc.
- Nenhuma das duas tenta esconder demais o que está acontecendo.

Você ganha produtividade **sem perder a clareza do SQL**.

---

### 4. Perfeito para uso em ETL, BI e transformação de dados

Com `wbjdbc`, você já consegue executar queries JDBC a partir do Python. Mas com `wborm` você:

- Mapeia tabelas como classes
- Usa `.filter()` e `.select()` sem se preocupar com string SQL
- Integra com Pandas ou Spark diretamente

Exemplo para DataFrame:

```python
from wborm.core import Model
import pandas as pd

df = pd.DataFrame([c.to_dict() for c in Cliente.all()])
```

---

### 5. Compatibilidade com recursos avançados do Informix

`wborm` respeita nuances como:

- `SKIP` e `FIRST` logo após `SELECT`
- Locks por transação (`BEGIN WORK / COMMIT WORK`)
- Evita deletar ou atualizar sem cláusulas de segurança

Coisas que ORMs genéricos não tratam bem para bancos como Informix.

---

## Tabela comparativa

| Recurso                         | wbjdbc                         | wborm                            |
|--------------------------------|--------------------------------|----------------------------------|
| Inicializa JVM                 | ✅                              | ❌                               |
| Carrega `.jar` e drivers       | ✅                              | ❌                               |
| Cria conexão JDBC              | ✅                              | ❌                               |
| Executa SQL                    | ✅ (`cursor.execute`)           | ✅ (`.raw_sql()` ou `.filter()`) |
| ORM com validação e modelo     | ❌                              | ✅                               |
| Geração automática de modelos  | ❌                              | ✅ (`generate_model`)            |

---

## Conclusão

Se você trabalha com Informix, DB2, Oracle ou outro banco via JDBC — o combo `wbjdbc` + `wborm` entrega:

- Conexão confiável e automática via Java
- ORM leve e poderoso com validação e segurança
- Facilidade de uso com Pandas, Spark e qualquer ferramenta Python

Use o poder do JDBC com a simplicidade do Python!
