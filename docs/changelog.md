## 📝 **Changelog – Atualizações de Abril 2025**

---

### 🔥 **QuerySet.py — Novas Melhorias e Métodos**

#### 🧠 Melhorias nas Funções Existentes
- `join(...)` agora suporta tipos especiais como `LEFT ANTI` e `RIGHT ANTI`.
- Aceita tipo de JOIN tanto posicional quanto nomeado.
- `filter(...)` aceita expressões livres, listas e dicionários.
- `filter_in(...)` e `not_in(...)` melhorados para múltiplos formatos.
- `order_by()`, `group_by()`, `select()` refinados para melhor flexibilidade sem impor prefixos.

#### 🆕 Novos métodos no QuerySet
- `limit()`, `offset()`, `distinct()`, `having()`, `live()`, `count()`, `first()`
- `show()` — Exibe resultados com paginação automática.
- `pivot()` — Geração de tabelas dinâmicas diretamente.
- `create_temp_table()` — Criação de tabelas temporárias diretamente de uma query.

---

### 📦 **ResultSet.py — Melhorias Visuais**

- Tabelas com cores no terminal:
  - 🔵 Azul: resultados de cache.
  - 🟢 Verde: resultados live.
- Paginador automático no `show(page_size=50)`.

---

### 🛠️ **Model.py — Novas Operações e Melhorias**

#### 📋 Manipulação de Dados
- `to_dict()`, `to_json()`, `as_dict(deep=True)`.

#### 🔧 Validação e Hooks
- `validate()`, `before_add()`, `after_update()`.

#### 🗑️ Operações CRUD
- `add(confirm=True)`, `update(confirm=True)`, `delete(confirm=True)`, `bulk_add(confirm=True)`.

---

### 📚 **ModelMeta.py — Interceptação de Métodos**

- Métodos de `QuerySet` agora podem ser chamados diretamente da classe `Model`.
- Exemplo: `User.filter(active=True).limit(10).show()`.

---

### 📈 **Expressions.py — Melhorias**

- `col()`, `date()`, `now()`, `raw()` refinados.
- Documentação ampliada e exemplos práticos.

---

### 📄 **Documentação Estendida**

- Todos os métodos possuem docstrings e exemplos claros.
- Novos tipos de JOINs explicados.

---

### 🎯 **Resumo das Novidades**

| Novidade | Descrição |
|:---------|:----------|
| JOINs ANTI suportados | `left_anti`, `right_anti` |
| Filtros inteligentes | `filter`, `filter_in`, `not_in` refinados |
| Pivot direto de queryset | `.pivot()` |
| Criação de tabelas temporárias | `.create_temp_table()` |
| Segurança obrigatória | `confirm=True` em add/update/delete |
| Visualização colorida e paginada | `show()` com UX melhorado |
| Autocomplete completo | `.pyi` atualizado com todos os modelos |

---

## ✅ **Retrocompatibilidade Garantida**

Todas as melhorias são 100% compatíveis com versões anteriores.

---


## 📝 **Changelog – Novos Módulos e Funcionalidades**

---
### 📚 `Registry.py` – **Registro Global de Modelos e Cache**

#### 🗂️ Estrutura Global
- `_model_registry`: armazena todas as classes `Model` já geradas e disponíveis para autocomplete e reuso.
- `_model_cache`: mapeia modelos por `(table_name, conn_id)` para evitar recriação redundante.
- `_query_result_cache`: cache em memória de resultados de queries, com TTL, usado em `QuerySet`.

> Este módulo fornece a base para funcionalidades como:
> - Cache de queries (com `live()` para bypass).
> - Reload automático de modelos.
> - Geração de stubs baseados em modelos carregados dinamicamente.

---

### 📦 `Model_cache.py` – **Persistência de Modelos em Disco**

#### 🔐 Criptografia e Armazenamento
- Implementado mecanismo de **cache criptografado de modelos** em `.wbmodels/` com chave Fernet salva em `.wbormkey`.
- Os modelos são serializados com `pickle`, criptografados e salvos com a extensão `.wbm`.

#### 📤 Funções Principais

- `save_model_to_disk(table_name, model_cls)`
  - Salva um modelo ORM como dicionário de atributos serializáveis (campos e relações).
- `try_load_model_from_disk(table_name, conn)`
  - Tenta carregar um modelo previamente salvo, reconstruindo a classe com `ModelMeta`, registrando no cache e módulo principal.
- `generate_model_stub(output_path)`
  - Gera automaticamente o arquivo `.pyi` para autocomplete com base nos modelos registrados.
  - Produz anotações de tipo para editores com base em campos e nullability.

#### 🔑 Segurança
- Utiliza `cryptography.fernet.Fernet` para garantir que o cache seja seguro, mesmo se exposto.

---

### 🧠 `Expressions.py` – **Expressões SQL Customizadas**

#### 📐 Expressões Declarativas
- **Classe `Expression`** permite construir expressões SQL de forma fluida e segura:
  - Operadores implementados: `==`, `!=`, `>`, `<`, `>=`, `<=`.
  - Integração com valores do tipo `datetime` com conversão automática.

#### 🔧 Funções utilitárias para consultas

- `col(name)` – cria expressão com base em nome de coluna.
- `date(field)` – envolve campo com `DATE(...)` do Informix.
- `now()` – insere a expressão `CURRENT`.
- `raw(expr)` – insere SQL arbitrário diretamente.
- `format_informix_datetime(value)` – converte `datetime` ou `str` para formato `DATETIME(...) YEAR TO SECOND`, suportando ISO8601 ou fallback para strings brutas.

> Essas funções já estão expostas no pacote principal via `__init__.py`, permitindo:
```python
from wborm import col, now, raw
```

---

## 📝 **`Utils.py`**

### 🚀 **Novas Funcionalidades**

- **Persistência de modelos em disco (cache local)**
  - Adição da verificação de modelos armazenados via `try_load_model_from_disk()` antes de gerar novamente.
  - Os modelos gerados são salvos com `save_model_to_disk()` para reutilização futura sem nova introspecção.

- **Injeção automática no escopo global**
  - Nova funcionalidade com `inject_globals=True` para permitir que os modelos sejam automaticamente atribuídos a variáveis globais com o nome da tabela.

- **Stub de autocomplete**
  - Introdução de `generate_model_stub()` após geração de modelos, preparando arquivos `.pyi` para suporte a autocomplete em editores de código.

- **Listagem de modelos**
  - Nova função `list_models()` que permite:
    - Listar todos os modelos carregados do banco de dados se houver uma conexão.
    - Listar modelos armazenados no cache `.wbmodels/` se não houver conexão ativa, com descriptografia via `cryptography.fernet`.

- **Geração em lote de modelos**
  - Nova função `generate_all_models(conn)` para introspecção automática de todas as tabelas (e opcionalmente views), com controle de verbosity e injeção em escopo.

- **Acesso seguro a modelos por nome**
  - Função `get_model_by_name(name)` permite acesso direto ao modelo carregado a partir do `_model_registry`.

- **Criação de tabelas temporárias a partir de queryset**
  - Adição da função `create_temp_table_from_queryset(...)` que permite gerar tabelas temporárias (`TEMP TABLE`) a partir de uma consulta ORM.

---

### 🔧 **Aprimoramentos**

- **Tratamento de exceções em FKs**
  - Implementado `try/except` com mensagem de aviso amigável ao ignorar falhas na leitura de FKs.

- **Módulo do modelo explicitamente definido**
  - Atributo `__module__` dos modelos agora é definido como `"wborm.core"`, garantindo rastreabilidade correta e suporte ao autocomplete.

- **Registro global de modelos**
  - Modelos agora também são armazenados em `_model_registry`, além do `_model_cache`, permitindo recuperação nominal direta.

- **Melhoria no mapeamento de nomes**
  - Os nomes de variáveis e atributos agora são tratados explicitamente como `str(col["name"])` para evitar inconsistências.

- **Distribuição de importações**
  - Organização mais clara dos `imports`, separando o uso de bibliotecas externas (`cryptography`, `pickle`) e módulos internos (`wborm.registry`, `wborm.model_cache` etc.).

---

### 🗑️ **Remoções**

- Nenhuma funcionalidade foi removida. A nova versão mantém **retrocompatibilidade total**, ampliando as capacidades existentes.

---

### ⚠️ **Observações Técnicas**

- Para o correto funcionamento do cache local, é necessário garantir que:
  - A chave de criptografia está acessível (`get_or_create_key()`).
  - O diretório `.wbmodels/` esteja presente e com permissões adequadas.
- A introspecção de FKs pode ser ignorada silenciosamente em caso de falhas, garantindo robustez mas ocultando erros mais sutis se não logado em detalhes.


---

## 📝 **`Introspect.py`**

### 🚀 **Melhoria Robusta na Função `get_foreign_keys()`**

#### 🔍 **Análise de Chaves Estrangeiras (FK) com Base em Índices**
- A consulta agora utiliza **`sysindexes`** para identificar corretamente as colunas envolvidas nos relacionamentos, tanto no lado da chave estrangeira quanto da chave primária.
- Suporte a até **16 colunas de índice** (usando `part1` a `part16`), permitindo detectar relacionamentos compostos com múltiplas colunas.

#### 🧠 **Correções Semânticas e de Precisão**
- Substituição do join direto por `r.tabid = fk.tabid` para o uso de `c.tabid = fk.tabid`, garantindo precisão na tabela filha (`fk`).
- Inclusão do filtro `idx_fk.part1 IS NOT NULL AND idx_pk.part1 IS NOT NULL` para garantir que apenas relacionamentos com colunas de índice reais sejam retornados, evitando registros corrompidos ou incompletos.

#### 🧹 **Tratamento com `COALESCE`**
- Uso de `COALESCE(..., '')` garante robustez ao comparar nomes de tabelas com possíveis valores nulos, evitando falhas silenciosas ou quebras por `NULL`.

---

### 🛠️ **Outros Ajustes Técnicos**

- **Indentação SQL melhorada** para clareza e leitura.
- Os aliases `fk`, `pk`, `fc` e `pc` permanecem os mesmos, mas agora baseados em um cruzamento mais preciso com os índices referenciados nas constraints.
- Estrutura da query refatorada para melhor manutenção futura e consistência com bancos que seguem o padrão Informix para metadados.

---

### ✅ **Nenhuma alteração em `introspect_table()`**
A função `introspect_table(...)` permanece **inalterada** entre as versões antiga e nova. Portanto:

- Sem impacto em chamadas existentes.
- Mesma estrutura de introspecção de colunas.


---

## 📝 **`Query.py`**

### 🚀 **Novas Funcionalidades**

#### 🧠 **Cache de Resultados de Consultas**
- Introduzido cache local de resultados (`_query_result_cache`) com TTL configurável (`_cache_ttl = 60` segundos por padrão).
- Nova função `live()` para desativar temporariamente o cache em uma consulta específica.
- Verificação e reutilização de resultados cacheados em `all()` para otimizar desempenho.

#### 🧾 **Classe ResultSet com Métodos Avançados**
- Nova classe `ResultSet` herda de `list` e adiciona:
  - `show(tablefmt="grid")`: renderização de resultados com `tabulate`, com destaque de cor (verde para consulta ao vivo, azul para cache).
  - Suporte a colunas dinâmicas com detecção automática ou baseadas em `select(...)`.
  - Remoção automática de colunas 100% vazias.

#### 📊 **Função `pivot(...)`**
- Novo método `pivot(...)` permite transformar a saída em uma visualização estilo **tabela dinâmica**, com indexação, colunas cruzadas e valores preenchidos.
- Uso de `tabulate`, cores de terminal ANSI e performance otimizada.

#### 🧪 **Função `show(...)` no QuerySet**
- Método `show()` que simplesmente chama `all().show(...)` com suporte a formato tabular customizável.

#### 🧩 **Suporte a Subqueries via Join**
- Método `join()` agora aceita um `QuerySet` com alias definido por `.as_temp_table(alias)`, permitindo joins com subqueries SQL completas.

#### 🧪 **Criação de Tabelas Temporárias Encadeada**
- Método `create_temp_table(...)` disponível diretamente em um `QuerySet` para gerar uma tabela temporária com base na query atual e retornar automaticamente o modelo associado.

---

### 🔧 **Melhorias em Funcionalidades Existentes**

- **`filter(...)` mais poderoso**
  - Agora aceita expressões livres como strings (`filter("age > 30")`) e objetos `ColumnExpr`, além do tradicional `filter(campo=valor)` com escaping seguro de aspas simples.

- **`join(...)` com cláusula ON flexível**
  - Agora aceita:
    - Lista/tupla de colunas para `ON a.col = b.col`.
    - Expressão simples (`"user_id"`) assumindo igualdade padrão.
    - Expressão SQL customizada.

- **Criação explícita de instâncias**
  - Método `_create_instance_from_row(...)` cria objetos com fallback direto ao `__dict__` se o campo não estiver em `_fields`.

- **`select(...)` propaga campos para o `ResultSet`**
  - Permite renderização mais precisa e ordenada de colunas.

- **Escape seguro em `count()`**
  - Protege os valores de filtro contra SQL Injection com `str(v).replace("'", "''")`.

---

### 🗑️ **Remoções / Alterações Descontinuadas**

- A função `preload(...)` foi **removida** no novo código. A pré-carga de relações precisa ser reimplementada caso seja necessária.
- A lógica heurística de FKs inversas em `preload(...)` (baseada em `id` ou `<rel>_id`) foi descontinuada.
- O método `all()` agora retorna um `ResultSet`, em vez de uma lista simples.

---

### 🎨 **Melhorias Visuais e de UX**

- Integração com `colorama` para **colorir bordas** de tabelas no terminal conforme origem dos dados (cache ou vivo).
- Utilização de `tabulate` com diversos formatos para facilitar leitura em CLI.

---

### ⚙️ **Internals e Técnicas**

- Inclusão de hashing (`sha256`) para cache de consultas baseado no texto SQL.
- Identificação de subqueries exige `._as_temp_table_alias` definido previamente para segurança.
- Compatível com `generate_model()` atualizado para modelos temporários injetáveis.


---

## 📝 **`Core.py`**

### 🚀 **Novas Funcionalidades**

#### 🧬 Suporte a métodos dinâmicos de `QuerySet`
- **Interceptação automática via `__getattr__` na metaclasse `ModelMeta`**:
  - Permite invocar qualquer método disponível no `QuerySet` diretamente pela classe modelo, como `User.limit(10).show()`.
  - Exemplo: `Model.join(...)`, `Model.show()`, `Model.pivot(...)`, etc., mesmo sem declarar manualmente.

#### 📦 Criação de Tabelas Temporárias
- **Novo método `create_temp_table()`** (em dois níveis: instância e classe):
  - Gera automaticamente a estrutura SQL com base nos campos do modelo.
  - Usa `CREATE TEMP TABLE ...` com log visual via `cprint`.
  - Útil para joins intermediários e persistência temporária de resultados filtrados.

#### 📊 Visualização Avançada: `Model.show(...)`
- Exibe resultados no terminal com `tabulate`, até 50 registros por padrão (ou filtrado).
- Renderiza com **cores no terminal** usando `colorama`:
  - Azul (🔵) se o modelo for proveniente de cache.
  - Verde (🟢) se for carregado dinamicamente.

#### 🔁 Pivot Dinâmico via `Model.pivot(...)`
- Geração de tabela dinâmica (`pivot`) diretamente pelo modelo, com suporte a filtros e agregações (`aggfunc="count"` por padrão).

#### 🔍 Relações Modeladas Visivelmente: `Model.describe_relations()`
- Lista todas as relações mapeadas automaticamente para o modelo, exibindo nome do relacionamento e tabela de destino.

---

### 🔧 Melhorias Significativas

- **Melhoria na introspecção de campos (`ModelMeta`)**:
  - Usa `str(k)` para garantir compatibilidade com chaves não-string (robustez com introspecção dinâmica ou subclasses especiais).

- **Refinamento em `to_dict()`**:
  - Agora ignora atributos que começam com `_` ou que são métodos, gerando um dicionário limpo apenas com dados úteis.

- **Melhoria na criação de tabelas (temporárias e fixas)**:
  - Compactação da lógica de tipo SQL + flags `NOT NULL` e `PRIMARY KEY` com `.strip()` no final.
  - Código mais legível e reutilizável.

---

### 🗑️ Remoções / Alterações Descontinuadas

- 📤 **Removido o método `show()` de instância**
  - Substituído por um `show()` de classe, mais útil e abrangente.

- 📦 **Método `preload()` do `QuerySet` ainda referenciado**, mas provavelmente obsoleto (dependência que sumiu em `QuerySet` novo).
  - Pode ser removido futuramente se confirmado o desuso.

---

### 🎨 Melhorias de Interface e UX

- **Saída mais bonita** com `colorama` para destaque de tabelas, relações e mensagens de criação.
- **Mensagens informativas** ao criar tabelas (`🧪 Tabela temporária criada: ...`), deletar ou atualizar.

---

### 🛠️ Técnicas e Estruturais

- `lazy_property` permanece como helper funcional, sem alterações.
- `validate()` continua garantindo consistência e obrigatório antes de qualquer operação de persistência (`add`, `bulk_add`, etc.).


---

## 📝 **`__init__.py`**

### 🚀 **Novos Recursos Exportados Publicamente**

Foram adicionados novos utilitários à API pública da biblioteca, permitindo um uso mais expressivo e direto de expressões SQL e funções auxiliares:

#### 📐 Expressões e Funções Utilitárias
- **`col`** – Criação de expressões baseadas em colunas (ex: `col("idade") > 18`).
- **`date`** – Conversão e manipulação de valores de data.
- **`now`** – Data/hora atual para uso em filtros ou inserções.
- **`raw`** – Inserção de SQL bruto diretamente em expressões.
- **`format_informix_datetime`** – Utilitário para formatar datas no padrão aceito pelo Informix.

> Esses recursos vêm do novo módulo `expressions.py`, agora incluído como parte do pacote principal.

---

### 🧭 **Exportação Explícita com `__all__`**

- Adição do bloco `__all__ = [...]`, tornando explícito o que é exportado ao usar `from wborm import *`, melhorando:
  - Legibilidade e manutenção.
  - Controle de namespace.
  - Completude para IDEs e documentação automática.

---

### ✅ **Retrocompatibilidade Mantida**

- Todos os elementos anteriormente exportados (`Model`, `Field`, `generate_model`, `get_model`, `QuerySet`) continuam disponíveis sem alterações.