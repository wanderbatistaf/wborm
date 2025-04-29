from wborm.fields import Field
from wborm.query import QuerySet
from termcolor import cprint
from tabulate import tabulate

class lazy_property:
    def __init__(self, func):
        self.func = func
        self.attr_name = f"_lazy_{func.__name__}"

    def __get__(self, obj, cls):
        if obj is None:
            return self
        if not hasattr(obj, self.attr_name):
            setattr(obj, self.attr_name, self.func(obj))
        return getattr(obj, self.attr_name)

class ModelMeta(type):
    def __new__(cls, name, bases, attrs):
        fields = {str(k): v for k, v in attrs.items() if isinstance(v, Field)}
        attrs["_fields"] = fields
        return super().__new__(cls, name, bases, attrs)

    def __getattr__(cls, name):
        queryset = cls._get_queryset()
        if hasattr(queryset, name):
            return getattr(queryset, name)
        raise AttributeError(f"'{cls.__name__}' object has no attribute '{name}'")


class Model(metaclass=ModelMeta):
    __tablename__ = None
    _connection = None
    _relations = {}

    def __init__(self, **kwargs):
        for field in self._fields:
            setattr(self, field, kwargs.get(field))

    def to_dict(self):
        """
            Converte o objeto em um dicionário simples com seus campos públicos.

            Forma de uso:
            -------------
            resultado = queryset.first().to_dict()

            Gera estruturas como:
            ---------------------
            {
                "id": 1,
                "nome": "João",
                "ativo": True
            }

            Observações:
            ------------
            - Ignora atributos iniciados com "_" e métodos.
            - Útil para serialização ou exportação de dados.
            """
        return {
            k: getattr(self, k)
            for k in self.__dict__
            if not k.startswith("_") and not callable(getattr(self, k))
        }

    def to_json(self):
        """
            Converte o objeto para uma string JSON com seus campos públicos.

            Forma de uso:
            -------------
            json_str = queryset.first().to_json()

            Gera estruturas como:
            ---------------------
            '{"id": 1, "nome": "João", "ativo": true}'

            Observações:
            ------------
            - Utiliza os dados de `to_dict()`.
            - Ideal para exportar objetos como JSON em APIs ou logs.
            """
        import json
        return json.dumps(self.to_dict())

    def as_dict(self, deep=False):
        """
            Converte o objeto em dicionário, com opção de incluir relações aninhadas.

            Forma de uso:
            -------------
            obj.as_dict()               # Retorna apenas os campos do objeto atual
            obj.as_dict(deep=True)      # Inclui também objetos relacionados (recursivamente)

            Gera estruturas como:
            ---------------------
            {
                "id": 1,
                "nome": "João",
                "enderecos": [
                    {"rua": "Rua A", "cidade": "Lisboa"},
                    {"rua": "Rua B", "cidade": "Porto"}
                ]
            }

            Observações:
            ------------
            - Quando `deep=True`, percorre recursivamente os campos definidos em `_relations`.
            - Suporta relações 1:N (listas) e 1:1 (objeto).
            """
        base = self.to_dict()
        if deep:
            for rel in self._relations:
                value = getattr(self, rel, None)
                if isinstance(value, list):
                    base[rel] = [v.as_dict(deep=True) for v in value]
                elif value:
                    base[rel] = value.as_dict(deep=True)
        return base

    @classmethod
    def show(cls, limit=50, **filters):
        """
            Exibe os registros do modelo atual formatados como tabela no terminal.

            Forma de uso:
            -------------
            Cliente.show()
            Cliente.show(limit=10)
            Cliente.show(status="ATIVO", cidade="Lisboa")

            Gera visualizações como:
            ------------------------
            +----+----------+-----------+
            | id | nome     | cidade    |
            +----+----------+-----------+
            |  1 | João     | Lisboa    |
            |  2 | Maria    | Porto     |

            Observações:
            ------------
            - Por padrão mostra até 50 registros.
            - Se filtros forem passados, aplica automaticamente.
            - Usa cor azul se o modelo estiver em cache (`_from_cache = True`), verde se for consulta direta.
            - Utiliza `tabulate` para renderização da tabela.
            """
        from tabulate import tabulate
        from colorama import Fore, Style

        try:
            qs = cls._get_queryset()
            if filters:
                qs = qs.filter(**filters)
            else:
                qs = qs.limit(limit)

            results = qs.all()

            if not results:
                print("Nenhum resultado encontrado.")
                return

            headers = list(results[0].to_dict().keys())
            rows = [list(obj.to_dict().values()) for obj in results]
            tabela = tabulate(rows, headers=headers, tablefmt="grid")

            cor = Fore.BLUE if getattr(cls, "_from_cache", False) else Fore.GREEN
            linhas_coloridas = []
            for linha in tabela.splitlines():
                if linha.startswith("+") or set(linha) <= {"-", "=", "+"}:
                    linhas_coloridas.append(f"{cor}{linha}{Style.RESET_ALL}")
                else:
                    linhas_coloridas.append(linha)

            print("\n".join(linhas_coloridas))

        except Exception as e:
            print(f"❌ Erro ao mostrar dados: {e}")

    @classmethod
    def describe(cls, inline=False):
        """
            Exibe uma descrição da estrutura do modelo (campos, tipos e propriedades).

            Forma de uso:
            -------------
            Cliente.describe()
            tabela = Cliente.describe(inline=True)  # retorna string ao invés de imprimir

            Gera visualizações como:
            ------------------------
            +-----------+--------+------+-----------+
            | Campo     | Tipo   | PK   | Nullable  |
            +-----------+--------+------+-----------+
            | id        | int    | True | False     |
            | nome      | str    | False| False     |
            | email     | str    | False| True      |

            Observações:
            ------------
            - Mostra o nome, tipo, se é chave primária (PK) e se permite nulo.
            - Use `inline=True` para capturar o resultado como texto (sem print).
            """
        data = [(k, v.field_type.__name__, v.primary_key, v.nullable) for k, v in cls._fields.items()]
        table = tabulate(data, headers=["Campo", "Tipo", "PK", "Nullable"], tablefmt="grid")
        if inline:
            return table
        print(table)

    def invalidate_lazy(self, attr):
        """
            Remove o cache de um atributo calculado de forma preguiçosa (lazy).

            Forma de uso:
            -------------
            obj.invalidate_lazy("enderecos")

            Gera ações como:
            ----------------
            ⚠ Cache invalidado para 'enderecos'

            Observações:
            ------------
            - O atributo precisa ter sido cacheado com o nome `_lazy_<attr>`.
            - Útil quando é necessário forçar o recálculo de dados relacionados.
            """
        cache_name = f"_lazy_{attr}"
        if hasattr(self, cache_name):
            delattr(self, cache_name)
            cprint(f"⚠ Cache invalidado para '{attr}'", "cyan")

    def before_add(self):
        """
            Método chamado automaticamente antes de adicionar um novo registro.

            Forma de uso:
            -------------
            def before_add(self):
                self.data_criacao = now()

            Observações:
            ------------
            - Pode ser sobrescrito nos modelos para preencher campos automaticamente ou validar dados.
            - Se não sobrescrito, é ignorado sem efeito.
            """
        pass

    def after_update(self):
        """
            Método chamado automaticamente após uma atualização bem-sucedida.

            Forma de uso:
            -------------
            def after_update(self):
                print(f"Registro atualizado: {self.id}")

            Observações:
            ------------
            - Pode ser sobrescrito nos modelos para ações pós-update (ex: auditoria, logs, etc).
            - Se não sobrescrito, é ignorado sem efeito.
            """
        pass

    def validate(self):
        """
            Valida os campos obrigatórios do modelo antes de salvar.

            Forma de uso:
            -------------
            obj.validate()

            Gera validações como:
            ---------------------
            - Verifica se campos não nulos foram preenchidos.
            - Se algum campo obrigatório estiver vazio, levanta ValueError.

            Exemplo de erro:
            ----------------
            ValueError: Campo obrigatório: nome
            """
        for k in self._fields:
            val = getattr(self, k)
            if val is None and not self._fields[k].nullable:
                raise ValueError(f"Campo obrigatório: {k}")

    def create_table(self):
        """
            Cria a tabela no banco de dados com base na definição dos campos do modelo.

            Forma de uso:
            -------------
            obj.create_table()

            Gera comandos como:
            -------------------
            CREATE TABLE nome_tabela (
                id INT NOT NULL PRIMARY KEY,
                nome VARCHAR(255) NOT NULL,
                preco FLOAT
            )

            Observações:
            ------------
            - Infere os tipos SQL a partir dos tipos Python (`int`, `float`, `str`).
            - Aplica `NOT NULL` e `PRIMARY KEY` conforme definido nos campos.
            - Executa o SQL diretamente via conexão associada ao modelo.
            """
        parts = []
        for name, field in self._fields.items():
            sql_type = "INT" if field.field_type == int else "FLOAT" if field.field_type == float else "VARCHAR(255)"
            nullable = "" if field.nullable else "NOT NULL"
            primary = "PRIMARY KEY" if field.primary_key else ""
            parts.append(f"{name} {sql_type} {nullable} {primary}")
        sql = f"CREATE TABLE {self.__tablename__} ({', '.join(parts)})"
        self._connection.execute(sql)
        cprint(f"✔ Tabela criada: {self.__tablename__}", "cyan")

    def create_temp_table(self):
        """
            Cria uma tabela temporária no banco com base nos campos definidos no modelo.

            Forma de uso:
            -------------
            obj.create_temp_table()

            Gera comandos como:
            -------------------
            CREATE TEMP TABLE nome_tabela (
                id INT NOT NULL PRIMARY KEY,
                nome VARCHAR(255) NOT NULL,
                valor FLOAT
            )

            Observações:
            ------------
            - Os tipos SQL são inferidos automaticamente (`INT`, `FLOAT`, `VARCHAR(255)`).
            - Inclui `NOT NULL` e `PRIMARY KEY` conforme a definição dos campos.
            - A tabela criada é temporária e válida apenas durante a sessão atual.
            - Exibe mensagem de confirmação no terminal ao final.
            """
        parts = []
        for name, field in self._fields.items():
            sql_type = "INT" if field.field_type == int else \
                "FLOAT" if field.field_type == float else \
                    "VARCHAR(255)"
            nullable = "" if field.nullable else "NOT NULL"
            primary = "PRIMARY KEY" if field.primary_key else ""
            parts.append(f"{name} {sql_type} {nullable} {primary}".strip())

        sql = f"CREATE TEMP TABLE {self.__tablename__} ({', '.join(parts)})"
        self._connection.execute(sql)
        from termcolor import cprint
        cprint(f"🧪 Tabela temporária criada: {self.__tablename__}", "cyan")

    def add(self, confirm=False):
        """
            Insere um novo registro na tabela correspondente ao modelo.

            Forma de uso:
            -------------
            obj = Cliente(id=1, nome="João", email="joao@email.com")
            obj.add(confirm=True)

            Gera comandos como:
            -------------------
            INSERT INTO clientes (id, nome, email) VALUES ('1', 'João', 'joao@email.com')

            Observações:
            ------------
            - Requer confirmação explícita com `confirm=True` para evitar inserções acidentais.
            - Executa `validate()` automaticamente antes de salvar.
            - Realiza `BEGIN WORK` e `COMMIT WORK` para controle transacional.
            - Em caso de falha, executa `ROLLBACK WORK` e exibe erro no terminal.
            - Chama `before_add()` antes da validação, se definido.
            """
        if not confirm:
            raise ValueError("Confirmação necessária: add(confirm=True)")
        self.before_add()
        self.validate()
        try:
            self._connection.execute("BEGIN WORK")
            keys = list(self._fields.keys())
            values = [getattr(self, k) for k in keys]
            placeholders = ", ".join(f"'{v}'" if v is not None else "NULL" for v in values)
            sql = f"INSERT INTO {self.__tablename__} ({', '.join(keys)}) VALUES ({placeholders})"
            self._connection.execute(sql)
            self._connection.execute("COMMIT WORK")
            cprint(f"✔ Registro adicionado em {self.__tablename__}", "green")
        except Exception as e:
            self._connection.execute("ROLLBACK WORK")
            cprint(f"✖ Falha ao adicionar em {self.__tablename__}: {str(e)}", "red")
            raise

    @classmethod
    def bulk_add(cls, objs, confirm=False):
        """
            Insere múltiplos registros na tabela de forma transacional.

            Forma de uso:
            -------------
            Cliente.bulk_add([Cliente(id=1, nome="João"), Cliente(id=2, nome="Maria")], confirm=True)

            Gera comandos como:
            -------------------
            INSERT INTO clientes (id, nome) VALUES ('1', 'João')
            INSERT INTO clientes (id, nome) VALUES ('2', 'Maria')

            Observações:
            ------------
            - Requer `confirm=True` para prevenir inserções acidentais.
            - Cada objeto é validado individualmente com `validate()`.
            - A operação é transacional: se qualquer inserção falhar, um rollback é executado.
            - Exibe no terminal o total de registros adicionados ou o erro ocorrido.
            """
        if not confirm:
            raise ValueError("Confirmação necessária: bulk_add(confirm=True)")
        if not objs:
            return
        try:
            cls._connection.execute("BEGIN WORK")
            keys = list(cls._fields.keys())
            for obj in objs:
                obj.validate()
                values = [getattr(obj, k) for k in keys]
                placeholders = ", ".join(f"'{v}'" if v is not None else "NULL" for v in values)
                sql = f"INSERT INTO {cls.__tablename__} ({', '.join(keys)}) VALUES ({placeholders})"
                cls._connection.execute(sql)
            cls._connection.execute("COMMIT WORK")
            cprint(f"✔ {len(objs)} registros adicionados em {cls.__tablename__}", "green")
        except Exception as e:
            cls._connection.execute("ROLLBACK WORK")
            cprint(f"✖ Falha no bulk_add de {cls.__tablename__}: {str(e)}", "red")
            raise

    def update(self, confirm=False, **kwargs):
        """
            Atualiza o registro atual no banco de dados com base em cláusulas WHERE explícitas.

            Forma de uso:
            -------------
            obj.nome = "João da Silva"
            obj.status = "ATIVO"
            obj.update(confirm=True, id=1)

            Gera comandos como:
            -------------------
            UPDATE clientes SET nome = 'João da Silva', status = 'ATIVO' WHERE id = '1'

            Observações:
            ------------
            - `confirm=True` é obrigatório para evitar alterações não intencionais.
            - É necessário informar uma cláusula WHERE via `kwargs`.
            - Todos os campos com valor não-nulo são incluídos na atualização.
            - Executa `BEGIN WORK` e `COMMIT WORK` para garantir atomicidade.
            - Em caso de erro, executa `ROLLBACK WORK` e exibe mensagem de falha.
            - Chama `after_update()` após o sucesso.
            """
        if not confirm:
            raise ValueError("Confirmação necessária: update(confirm=True)")
        if not kwargs:
            raise ValueError("Update requer cláusula explícita: ex. update(confirm=True, id=1)")
        try:
            self._connection.execute("BEGIN WORK")
            updates = [f"{k} = '{getattr(self, k)}'" for k in self._fields if getattr(self, k) is not None]
            where_clause = " AND ".join(f"{k} = '{v}'" for k, v in kwargs.items())
            sql = f"UPDATE {self.__tablename__} SET {', '.join(updates)} WHERE {where_clause}"
            self._connection.execute(sql)
            self._connection.execute("COMMIT WORK")
            self.after_update()
            cprint(f"✔ Registro atualizado em {self.__tablename__} (WHERE {where_clause})", "yellow")
        except Exception as e:
            self._connection.execute("ROLLBACK WORK")
            cprint(f"✖ Falha ao atualizar {self.__tablename__}: {str(e)}", "red")
            raise

    def delete(self, confirm=False, **kwargs):
        """
            Deleta um ou mais registros da tabela com base em cláusulas WHERE explícitas.

            Forma de uso:
            -------------
            obj.delete(confirm=True, id=1)

            Gera comandos como:
            -------------------
            DELETE FROM clientes WHERE id = '1'

            Observações:
            ------------
            - `confirm=True` é obrigatório para evitar exclusões acidentais.
            - A cláusula WHERE deve ser informada via argumentos nomeados.
            - Executa `BEGIN WORK` e `COMMIT WORK` para garantir atomicidade.
            - Em caso de falha, executa `ROLLBACK WORK` e mostra erro no terminal.
            """
        if not confirm:
            raise ValueError("Confirmação necessária: delete(confirm=True)")
        if not kwargs:
            raise ValueError("Delete requer cláusula explícita: ex. delete(confirm=True, id=1)")
        try:
            self._connection.execute("BEGIN WORK")
            where_clause = " AND ".join(f"{k} = '{v}'" for k, v in kwargs.items())
            sql = f"DELETE FROM {self.__tablename__} WHERE {where_clause}"
            self._connection.execute(sql)
            self._connection.execute("COMMIT WORK")
            cprint(f"✔ Registro deletado de {self.__tablename__} (WHERE {where_clause})", "red")
        except Exception as e:
            self._connection.execute("ROLLBACK WORK")
            cprint(f"✖ Falha ao deletar de {self.__tablename__}: {str(e)}", "red")
            raise

    @classmethod
    def _get_queryset(cls):
        return QuerySet(cls, cls._connection)

    @classmethod
    def all(cls):
        """
            Retorna todos os registros da tabela representada pelo modelo.

            Forma de uso:
            -------------
            registros = Cliente.all()

            Gera cláusulas como:
            --------------------
            SELECT * FROM clientes
            """
        return cls._get_queryset().all()

    @classmethod
    def filter(cls, *args, **kwargs):
        """
            Aplica filtros e retorna um queryset com os registros correspondentes.

            Forma de uso:
            -------------
            Cliente.filter(status="ATIVO")
            Cliente.filter("nome LIKE 'J%'")

            Gera cláusulas como:
            --------------------
            SELECT * FROM clientes WHERE status = 'ATIVO'
            SELECT * FROM clientes WHERE nome LIKE 'J%'
            """
        return cls._get_queryset().filter(*args, **kwargs)

    @classmethod
    def filter_in(cls, column, values):
        """
            Filtra os registros onde o valor da coluna esteja dentro de uma lista.

            Forma de uso:
            -------------
            Cliente.filter_in("status", ["ATIVO", "INATIVO"])

            Gera cláusulas como:
            --------------------
            SELECT * FROM clientes WHERE status IN ('ATIVO', 'INATIVO')
            """
        return cls._get_queryset().filter_in(column, values)

    @classmethod
    def not_in(cls, column, values):
        """
        Filtra os registros onde o valor da coluna não esteja em uma lista.

        Forma de uso:
        -------------
        Cliente.not_in("status", ["CANCELADO", "BLOQUEADO"])

        Gera cláusulas como:
        --------------------
        SELECT * FROM clientes WHERE status NOT IN ('CANCELADO', 'BLOQUEADO')
        """
        return cls._get_queryset().not_in(column, values)

    @classmethod
    def order_by(cls, *fields):
        """
        Define a ordenação dos resultados retornados pela consulta.

        Forma de uso:
        -------------
        Cliente.order_by("nome")
        Cliente.order_by("status DESC", "data_cadastro")

        Gera cláusulas como:
        --------------------
        ORDER BY nome
        ORDER BY status DESC, data_cadastro
        """
        return cls._get_queryset().order_by(*fields)

    @classmethod
    def select(cls, *fields):
        """
        Define explicitamente os campos que devem ser retornados.

        Forma de uso:
        -------------
        Cliente.select("id", "nome", "email")

        Gera cláusulas como:
        --------------------
        SELECT id, nome, email FROM clientes
        """
        return cls._get_queryset().select(*fields)

    @classmethod
    def join(cls, other, on, *args, type=None):
        """
            Realiza um join com outra tabela, subquery ou modelo, suportando diferentes tipos de JOIN.

            Forma de uso:
            -------------
            # Join padrão (INNER)
            Cliente.join("enderecos", "cliente_id")

            # Join com tipo posicional
            Cliente.join("enderecos", "cliente_id", "LEFT")

            # Join com tipo nomeado
            Cliente.join("enderecos", "cliente_id", type="RIGHT")

            # Joins especiais (filtragem negativa)
            Cliente.join("enderecos", "cliente_id", "LEFT_ANTI")
            Cliente.join("enderecos", "cliente_id", type="RIGHT_ANTI")

            Tipos de JOIN suportados:
            -------------------------
            - INNER
            - LEFT
            - RIGHT
            - FULL (se suportado pela engine)
            - LEFT_ANTI
            - RIGHT_ANTI

            Gera cláusulas como:
            --------------------
            LEFT JOIN enderecos ON t1.cliente_id = t2.cliente_id
            """
        return cls._get_queryset().join(other, on, *args, type=type)

    @classmethod
    def group_by(cls, *fields):
        """
        Agrupa os resultados com base nos campos especificados.

        Forma de uso:
        -------------
        Cliente.group_by("status")

        Gera cláusulas como:
        --------------------
        GROUP BY status
        """
        return cls._get_queryset().group_by(*fields)

    @classmethod
    def having(cls, condition):
        """
        Aplica uma cláusula HAVING após um agrupamento (GROUP BY).

        Forma de uso:
        -------------
        Cliente.group_by("status").having("COUNT(*) > 1")

        Gera cláusulas como:
        --------------------
        HAVING COUNT(*) > 1
        """
        return cls._get_queryset().having(condition)

    @classmethod
    def count(cls):
        """
        Retorna o número total de registros que atendem aos filtros aplicados.

        Forma de uso:
        -------------
        total = Cliente.filter(status="ATIVO").count()

        Gera cláusulas como:
        --------------------
        SELECT COUNT(*) FROM clientes WHERE status = 'ATIVO'
        """
        return cls._get_queryset().count()

    @classmethod
    def distinct(cls):
        """
            Remove registros duplicados dos resultados da consulta.

            Forma de uso:
            -------------
            Cliente.select("cidade").distinct()

            Gera cláusulas como:
            --------------------
            SELECT DISTINCT cidade FROM clientes
            """
        return cls._get_queryset().distinct()

    @classmethod
    def raw_sql(cls, sql):
        """
        Substitui a consulta atual por um SQL customizado.

        Forma de uso:
        -------------
        Cliente.raw_sql("SELECT * FROM clientes WHERE status = 'ATIVO'")

        Gera cláusulas como:
        --------------------
        Executa exatamente o SQL fornecido, ignorando filtros e joins definidos no queryset.
        """
        return cls._get_queryset().raw_sql(sql)

    @classmethod
    def exists(cls):
        """
            Verifica se existe pelo menos um registro que satisfaça os filtros definidos.

            Forma de uso:
            -------------
            if Cliente.filter(status="ATIVO").exists():
                print("Há clientes ativos.")

            Gera cláusulas como:
            --------------------
            SELECT FIRST 1 1 FROM (...)
            """
        return cls._get_queryset().exists()

    @classmethod
    def preload(cls, *relations):
        """
            Pré-carrega relações definidas no modelo para evitar N+1 queries.

            Forma de uso:
            -------------
            Cliente.preload("enderecos")
            Pedido.preload("itens", "cliente")

            Gera comportamento como:
            ------------------------
            - Executa consultas adicionais para as relações informadas e as popula automaticamente no objeto.
            - Ideal para usar junto com `.all()` ou `.filter()` quando há uso de listas ou laços.

            Observações:
            ------------
            - As relações devem estar declaradas no atributo `_relations` do modelo.
            """
        return cls._get_queryset().preload(*relations)

    @classmethod
    def pivot(cls, index, columns, values=None, aggfunc="count", filters=None, tablefmt="grid"):
        """
            Gera uma tabela dinâmica (pivot) a partir dos dados da consulta.

            Forma de uso:
            -------------
            Cliente.pivot("cidade", "status")
            Pedido.pivot(index="cliente_id", columns="ano", values="total", aggfunc="sum")

            Parâmetros:
            -----------
            index : str
                Coluna base das linhas.
            columns : str
                Coluna que definirá as colunas dinâmicas.
            values : str ou list, opcional
                Campos numéricos a serem agregados (padrão: count).
            aggfunc : str
                Função de agregação: "count", "sum", "avg" etc.
            filters : dict, opcional
                Filtros adicionais para a consulta.
            tablefmt : str
                Formato da tabela para exibição (padrão: "grid").

            Exemplo visual:
            ----------------
            +-------------+--------+--------+
            | cidade      | ATIVO  | INATIVO|
            +-------------+--------+--------+
            | Lisboa      |   12   |   3    |
            | Porto       |   5    |   1    |
            """
        qs = cls._get_queryset()
        if filters:
            qs = qs.filter(**filters)
        records = qs.all()
        return pivot(records, index, columns, values, aggfunc=aggfunc, tablefmt=tablefmt)

    @classmethod
    def __getattr__(cls, name):
        queryset = cls._get_queryset()
        if hasattr(queryset, name):
            return getattr(queryset, name)
        raise AttributeError(f"'{cls.__name__}' object has no attribute '{name}'")

    @classmethod
    def describe_relations(cls):
        """
            Exibe no terminal as relações declaradas no modelo (atributo `_relations`).

            Forma de uso:
            -------------
            Cliente.describe_relations()

            Saída esperada:
            ----------------
             Relações para Cliente:
              - enderecos ➝ endereco
              - pedidos ➝ pedido

            Observações:
            ------------
            - Apenas exibe as relações se `_relations` estiver definido.
            - Útil para depuração e entendimento da estrutura do modelo.
            """
        if not hasattr(cls, "_relations") or not cls._relations:
            print(f"    '{cls.__name__}' não possui relações mapeadas.")
            return
        print(f"\n Relações para {cls.__name__}:")
        for rel_name, target_table in cls._relations.items():
            print(f"  - {rel_name} ➝ {target_table}")

    @classmethod
    def create_temp_table(cls):
        """
           Cria uma tabela temporária com base na estrutura do modelo atual.

           Forma de uso:
           -------------
           Cliente.create_temp_table()

           Gera comandos como:
           -------------------
           CREATE TEMP TABLE clientes (
               id INT NOT NULL PRIMARY KEY,
               nome VARCHAR(255),
               saldo FLOAT
           )

           Observações:
           ------------
           - Utiliza os tipos `INT`, `FLOAT` ou `VARCHAR(255)` com base nos tipos Python.
           - Inclui `NOT NULL` e `PRIMARY KEY` conforme definido nos campos.
           - A tabela é válida apenas durante a sessão.
           - Exibe mensagem de sucesso no terminal.
           """
        parts = []
        for name, field in cls._fields.items():
            sql_type = (
                "INT" if field.field_type == int else
                "FLOAT" if field.field_type == float else
                "VARCHAR(255)"
            )
            nullable = "" if field.nullable else "NOT NULL"
            primary = "PRIMARY KEY" if field.primary_key else ""
            parts.append(f"{name} {sql_type} {nullable} {primary}".strip())

        sql = f"CREATE TEMP TABLE {cls.__tablename__} ({', '.join(parts)})"
        cls._connection.execute(sql)

        from termcolor import cprint
        cprint(f"🧪 Tabela temporária criada: {cls.__tablename__}", "cyan")


