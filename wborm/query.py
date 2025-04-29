import time
from tabulate import tabulate
from wborm.registry import _query_result_cache
from colorama import Fore, Style
import os
import tempfile
import pickle
from wborm.registry import _model_registry
from hashlib import md5

class _Alias:
    def __init__(self, alias): self.alias = alias
    def __call__(self, **kwargs): return [(f"{self.alias}.{k}", v) for k, v in kwargs.items()]


def _auto_inject_aliases():
    import builtins
    for i in range(1, 21):
        builtins.__dict__[f"t{i}"] = _Alias(f"t{i}")

_auto_inject_aliases()  # Executa automaticamente no load do módulo

class QuerySet:
    def __init__(self, model, conn):
        self.model = model
        self.conn = conn
        self._filters = []
        self._in_filters = []
        self._not_in_filters = []
        self._limit = None
        self._offset = None
        self._order_by = []
        self._joins = []
        self._select_fields = []
        self._group_by = []
        self._having = None
        self._distinct = False
        self._raw_sql = None
        self._preloads = []
        self._cache_enabled = True
        self._cache_ttl = 60

        from wborm.bootstrap import auto_load_cached_models
        auto_load_cached_models(conn)

    def filter(self, *args, **kwargs):
        """
            Adiciona condições de filtro (WHERE) à consulta.

            Aceita filtros em três formas:

            - Strings diretas de condição (ex: "t1.nome = 'João'")
            - Listas de pares (ex: [("nome", "João"), ("idade", 30)])
            - Argumentos nomeados (ex: filter(nome="João", idade=30))

            Todos os valores são automaticamente escapados para evitar erros de SQL.

            Exemplos de uso:
            ---------
            queryset.filter("t1.status = 'ativo'")

            queryset.filter([("nome", "João"), ("cidade", "Lisboa")])

            queryset.filter(nome="João", cidade="Lisboa")
            """
        for cond in args:
            if isinstance(cond, str):
                self._filters.append(cond)
            elif isinstance(cond, list):
                for k, v in cond:
                    escaped = str(v).replace("'", "''")
                    self._filters.append(f"{k} = '{escaped}'")
        for k, v in kwargs.items():
            escaped = str(v).replace("'", "''")
            self._filters.append(f"{k} = '{escaped}'")
        return self

    def filter_in(self, *args):
        """
            Adiciona uma cláusula IN ao filtro da consulta.

            Suporta duas formas de uso:

            1. Modo direto:
               filter_in("coluna", [valor1, valor2, ...])

            2. Modo lista de pares (mais flexível):
               filter_in(t1(coluna=[valor1, valor2]), t2(outro=["x", "y"]))
               → representado como: filter_in([("coluna", [...]), ("outra_coluna", [...])])

            Exemplos:
            ---------
            queryset.filter_in("status", ["ATIVO", "PENDENTE"])

            queryset.filter_in([("t1.cliente_id", [1, 2, 3]), ("t2.cidade", ["Lisboa", "Porto"])])

            Gera cláusulas como:
                WHERE status IN ('ATIVO', 'PENDENTE')
            """
        if len(args) == 1 and isinstance(args[0], list):
            # Suporta formato: filter_in(t1(coluna=[valores]))
            for k, v in args[0]:
                self._in_filters.append((k, v))
        elif len(args) == 2:
            column, values = args
            self._in_filters.append((column, values))
        else:
            raise ValueError(
                "Uso incorreto de filter_in. Use filter_in('coluna', [valores]) ou filter_in(t1(coluna=[...])).")
        return self

    def not_in(self, column, values):
        """
            Aplica uma cláusula NOT IN para exclusão de valores específicos.

            Forma de uso:
            -------------
            queryset.not_in("status", ["CANCELADO", "REJEITADO"])

            Gera cláusulas como:
            -------------------
            WHERE status NOT IN ('CANCELADO', 'REJEITADO')
            """
        self._not_in_filters.append((column, values))
        return self

    def join(self, other, on, *args, type=None):
        """
            Adiciona uma cláusula JOIN à consulta.

            Formas de uso:
            --------------
            join(outros_dados, "id")
            → INNER JOIN padrão

            join(outros_dados, "id", "left")
            → LEFT JOIN

            join(outros_dados, "id", type="right")
            → RIGHT JOIN

            join(outros_dados, "id", "left_anti")
            → LEFT JOIN + WHERE t2.id IS NULL (simula LEFT ANTI JOIN)

            join(outros_dados, ["id", "grupo"], "inner")
            → JOIN com múltiplas colunas de ligação

            Regras:
            -------
            - Se `args` for usado para o tipo, não pode passar `type=` junto.
            - Tipos especiais como `left_anti` e `right_anti` são convertidos para JOIN + filtro `IS NULL`.
            """
        if not hasattr(self, "_table_alias"):
            self._table_alias = "t1"

        if args and type:
            raise ValueError("Não pode passar tipo de join posicional e nomeado ao mesmo tempo. Use apenas um.")

        join_type = "INNER"
        anti_join = None

        if args:
            join_type = args[0].upper().replace("_", " ")
        elif type:
            join_type = type.upper().replace("_", " ")

        if join_type in ("LEFT ANTI", "RIGHT ANTI"):
            anti_join = join_type
            join_type = "LEFT" if join_type == "LEFT ANTI" else "RIGHT"

        join_index = len(self._joins) + 2
        other_alias = f"t{join_index}"

        if isinstance(other, QuerySet):
            if not hasattr(other, "_as_temp_table_alias"):
                other = other.as_temp_table(other_alias)
            subquery_sql = other._build_query()
            tablename = f"({subquery_sql}) AS {other._as_temp_table_alias}"
            alias = other._as_temp_table_alias
            model_to_register = other.model

        elif isinstance(other, str):
            tablename = f"{other} AS {other_alias}"
            alias = other_alias
            model_to_register = None

        else:
            tablename = f"{other.__tablename__} AS {other_alias}"
            alias = other_alias
            model_to_register = other

        if alias not in _model_registry and model_to_register:
            _model_registry[alias] = model_to_register

        if isinstance(on, (list, tuple)):
            conditions = [f"{self._table_alias}.{col} = {alias}.{col}" for col in on]
            on_clause = " AND ".join(conditions)
        elif "." not in on and "=" not in on:
            on_clause = f"{self._table_alias}.{on} = {alias}.{on}"
        else:
            on_clause = on

        self._joins.append((join_type, tablename, on_clause))

        if anti_join:
            self._anti_join_condition = (anti_join, on, self._table_alias, alias)

        return self

    def limit(self, value):
        """
            Limita a quantidade máxima de registros retornados pela consulta.

            Forma de uso:
            -------------
            queryset.limit(10)

            Gera cláusulas como:
            -------------------
            Adiciona FIRST 10 à cláusula SELECT.
            """
        self._limit = value
        return self

    def offset(self, value):
        """
           Define a quantidade de registros a serem ignorados no início da consulta.

           Forma de uso:
           -------------
           queryset.offset(20)

           Gera cláusulas como:
           -------------------
           Adiciona SKIP 20 à cláusula SELECT.
           """
        self._offset = value
        return self

    def order_by(self, *fields):
        """
            Define a ordenação dos resultados da consulta.

            Forma de uso:
            -------------
            queryset.order_by("nome")
            queryset.order_by("t1.data_criacao", "t1.nome DESC")

            Gera cláusulas como:
            --------------------
            ORDER BY nome
            ORDER BY t1.data_criacao, t1.nome DESC
            """
        self._order_by.extend(fields)
        return self

    def select(self, *fields):
        """
           Define explicitamente os campos que devem ser retornados na consulta.

           Forma de uso:
           -------------
           queryset.select("t1.nome", "t1.email")

           Gera cláusulas como:
           --------------------
           SELECT t1.nome, t1.email
           """
        self._select_fields = list(fields)
        return self

    def group_by(self, *fields):
        """
            Agrupa os resultados com base nos campos especificados.

            Forma de uso:
            -------------
            queryset.group_by("t1.status")

            Gera cláusulas como:
            --------------------
            GROUP BY t1.status
            """
        self._group_by.extend(fields)
        return self

    def having(self, condition):
        """
            Adiciona uma cláusula HAVING à consulta após um GROUP BY.

            Forma de uso:
            -------------
            queryset.group_by("status").having("COUNT(*) > 1")

            Gera cláusulas como:
            --------------------
            HAVING COUNT(*) > 1
            """
        self._having = condition
        return self

    def distinct(self):
        """
            Remove registros duplicados do resultado da consulta.

            Forma de uso:
            -------------
            queryset.distinct()

            Gera cláusulas como:
            --------------------
            SELECT DISTINCT ...
            """
        self._distinct = True
        return self

    def raw_sql(self, sql):
        """
            Substitui completamente a query gerada por uma SQL customizada.

            Forma de uso:
            -------------
            queryset.raw_sql("SELECT * FROM clientes WHERE ativo = 1")

            Gera cláusulas como:
            --------------------
            Usa exatamente o SQL fornecido, ignorando todos os filtros e joins definidos anteriormente.
            """
        self._raw_sql = sql
        return self

    def exists(self):
        """
            Verifica se a consulta retorna ao menos um registro.

            Forma de uso:
            -------------
            if queryset.filter(status="ATIVO").exists():
                print("Há registros ativos.")

            Gera cláusulas como:
            --------------------
            SELECT FIRST 1 1 FROM (<sua_query>) t
            """
        sql = self._build_query()
        result = self.conn.execute_query(f"SELECT FIRST 1 1 FROM ({sql}) t")
        return len(result) > 0

    def live(self):
        """
            Desativa o cache de resultados e força a execução da consulta em tempo real.

            Forma de uso:
            -------------
            queryset.filter(status="ATIVO").live().show()

            Gera cláusulas como:
            --------------------
            Consulta é sempre executada diretamente no banco, sem usar cache local.
            """
        self._cache_enabled = False
        return self

    def _cache_key(self, sql):
        import hashlib
        return hashlib.sha256(sql.encode()).hexdigest()

    def _build_query(self):
        if self._raw_sql:
            return self._raw_sql

        if not hasattr(self, "_table_alias"):
            self._table_alias = "t1"

        skip_first = ""
        if self._limit is not None:
            skip_first = f"SKIP {self._offset or 0} FIRST {self._limit} "

        prefix = "DISTINCT " if self._distinct else ""

        if self._select_fields:
            selected = ", ".join(self._select_fields)
        else:
            selected_parts = []

            # Principal: t1 (sem prefixo se não houver joins)
            for col in self.model._fields:
                if self._joins:
                    selected_parts.append(f"{self._table_alias}.{col} AS {self._table_alias}_{col}")
                else:
                    selected_parts.append(f"{self._table_alias}.{col}")

            # Joins: t2, t3, etc — evita duplicação
            used_aliases = set()
            for join_type, join_table, _ in self._joins:
                alias = join_table.split(" AS ")[-1]
                if alias in used_aliases:
                    continue
                used_aliases.add(alias)

                joined_model = _model_registry.get(alias)
                if joined_model and hasattr(joined_model, "_fields"):
                    for col in joined_model._fields:
                        selected_parts.append(f"{alias}.{col} AS {alias}_{col}")

            selected = ", ".join(selected_parts)

        sql = f"SELECT {skip_first}{prefix}{selected} FROM {self.model.__tablename__} AS {self._table_alias}"

        for join_type, join_table, condition in self._joins:
            sql += f" {join_type} JOIN {join_table} ON {condition}"

        conditions = []

        # 📌 Aqui adicionamos o filtro automático para LEFT ANTI ou RIGHT ANTI
        if hasattr(self, "_anti_join_condition"):
            anti_type, on, left_alias, right_alias = self._anti_join_condition
            if anti_type == "LEFT ANTI":
                conditions.append(f"{right_alias}.{on} IS NULL")
            elif anti_type == "RIGHT ANTI":
                conditions.append(f"{left_alias}.{on} IS NULL")

        if self._filters:
            conditions += [f for f in self._filters]
        if self._in_filters:
            for col, vals in self._in_filters:
                lista = ", ".join(f"'{v}'" for v in vals)
                conditions.append(f"{col} IN ({lista})")
        if self._not_in_filters:
            for col, vals in self._not_in_filters:
                lista = ", ".join(f"'{v}'" for v in vals)
                conditions.append(f"{col} NOT IN ({lista})")

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        if self._group_by:
            sql += " GROUP BY " + ", ".join(self._group_by)

        if self._having:
            sql += f" HAVING {self._having}"

        if self._order_by:
            sql += " ORDER BY " + ", ".join(self._order_by)

        return sql

    def preload(self, *relations):
        self._preloads.extend(relations)
        return self

    def all(self):
        sql = self._build_query()
        key = self._cache_key(sql)

        if self._cache_enabled:
            cached = _query_result_cache.get(key)
            if cached:
                results, timestamp = cached
                if time.time() - timestamp < self._cache_ttl:
                    resultset = ResultSet([
                        self._create_instance_from_row(row) for row in results
                    ])
                    if self._select_fields:
                        resultset._selected_fields = self._select_fields
                    return resultset

        results = self.conn.execute_query(sql)
        if self._cache_enabled:
            _query_result_cache[key] = (results, time.time())

        resultset = ResultSet([
            self._create_instance_from_row(row) for row in results
        ], selected_fields=self._select_fields if self._select_fields else None)
        return resultset

    def _create_instance_from_row(self, row):
        obj = self.model()
        for k, v in row.items():
            k = str(k)
            if self._joins:  # só ignora sem tX_ se houver joins
                if not k.startswith("t"):
                    continue
            obj.__dict__[k] = v
        return obj

    def first(self):
        """
            Retorna apenas o primeiro registro da consulta.

            Forma de uso:
            -------------
            cliente = queryset.filter(status="ATIVO").first()

            Gera cláusulas como:
            --------------------
            SELECT FIRST 1 ...
            """
        self.limit(1)
        results = self.all()
        return results[0] if results else None

    def count(self):
        """
            Retorna a quantidade de registros que atendem aos filtros definidos.

            Forma de uso:
            -------------
            total = queryset.filter(status="ATIVO").count()

            Gera cláusulas como:
            --------------------
            SELECT COUNT(*) FROM nome_tabela WHERE status = 'ATIVO'
            """
        sql = f"SELECT COUNT(*) as count FROM {self.model.__tablename__}"
        if self._filters:
            conditions = ["{} = '{}'".format(k, str(v).replace("'", "''")) for k, v in self._filters]
            sql += " WHERE " + " AND ".join(conditions)
        result = self.conn.execute_query(sql)
        return result[0]["count"] if result else 0

    def show(self, tablefmt="grid"):
        """
            Executa a consulta e exibe os resultados formatados como tabela.

            Forma de uso:
            -------------
            queryset.filter(status="ATIVO").show()

            queryset.select("nome", "email").order_by("nome").show(tablefmt="fancy_grid")

            Gera cláusulas como:
            --------------------
            SELECT ... FROM ... [com filtros, ordenações, etc.]

            Observações:
            ------------
            - Requer que a consulta retorne um DataFrame com método `.show()`.
            - O parâmetro `tablefmt` define o estilo da tabela (padrão: "grid").
            """
        return self.all().show(tablefmt=tablefmt)

    def pivot(self, index=None, columns=None, values=None, limit=500):
        """
            Gera uma tabela dinâmica (pivot) a partir do resultado da consulta.

            Forma de uso:
            -------------
            queryset.select("categoria", "ano", "vendas").pivot()

            queryset.pivot(index="categoria", columns="ano", values=["vendas", "lucro"])

            Gera visualizações como:
            ------------------------
            +--------------+----------+----------------+
            | categoria    | 2023.vendas | 2024.vendas |
            +--------------+----------+----------------+
            | Alimentos    | 12000    | 13400          |
            | Bebidas      |  8900    |  9100          |

            Observações:
            ------------
            - O parâmetro `index` define a linha (ex: "categoria")
            - O parâmetro `columns` define as colunas dinâmicas (ex: "ano")
            - O parâmetro `values` define os campos a serem agregados
            - Usa um limite padrão de 500 registros (configurável)
            - Exibe a tabela formatada no terminal com cores (verde = direto do banco, azul = cache)
            """
        from tabulate import tabulate
        from collections import defaultdict
        import time

        GREEN = "\033[92m"
        BLUE = "\033[94m"
        RESET = "\033[0m"

        t0 = time.time()
        results = self.limit(limit).all()
        if not results:
            print("⚠ Nenhum dado retornado para pivot.")
            return

        sample = results[0]
        fields = list(sample.to_dict().keys())

        index = index or fields[0]
        columns = columns or fields[1]
        values = values or fields[2:]

        data = defaultdict(dict)
        for row in results:
            i_val = getattr(row, index)
            c_val = getattr(row, columns)
            for v in values:
                col_name = f"{c_val}.{v}"
                data[i_val][col_name] = getattr(row, v)

        all_cols = sorted({col for d in data.values() for col in d})
        headers = [index] + all_cols

        rows = []
        for i_val, cols in data.items():
            row = [i_val]
            for col in all_cols:
                row.append(cols.get(col, ""))
            rows.append(row)

        table = tabulate(rows, headers=headers, tablefmt="grid")

        color = BLUE if getattr(self.model, "_from_cache", False) else GREEN
        colored_lines = []
        for line in table.splitlines():
            if line.strip().startswith("+") or line.strip().startswith("|") and set(line.strip()) <= {"|", "-"}:
                colored_lines.append(f"{color}{line}{RESET}")
            else:
                colored_lines.append(line)

        print("\n".join(colored_lines))

    def create_temp_table(self, temp_name, with_log=False):
        """
            Cria uma tabela temporária com base na consulta atual.

            Forma de uso:
            -------------
            queryset.filter(status="ATIVO").create_temp_table("temp_ativos")

            queryset.create_temp_table("temp_resultados", with_log=True)

            Gera cláusulas como:
            --------------------
            CREATE TEMP TABLE temp_ativos AS (SELECT ...) WITH NO LOG

            Observações:
            ------------
            - O nome da tabela é definido por `temp_name`
            - O parâmetro `with_log` define se será criada com ou sem log
            - A tabela temporária pode ser usada diretamente como um novo modelo
            """
        sql = self._build_query()
        log_clause = "WITH LOG" if with_log else "WITH NO LOG"
        create_sql = f"CREATE TEMP TABLE {temp_name} AS ({sql}) {log_clause}"

        print(f" Criando tabela temporária:\n{create_sql}")
        self.conn.execute(create_sql)

        from wborm.utils import generate_model
        model = generate_model(temp_name, self.conn, inject_globals=True)
        return model

class ResultSet(list):
    def __init__(self, data=None, selected_fields=None):
        super().__init__(data or [])
        self._selected_fields = selected_fields
        self._render_cache = None
        self._disk_cache_path = None
        self._disk_cache_time = None 

    def clear_render_cache(self):
        self._render_cache = None
        if self._disk_cache_path and os.path.exists(self._disk_cache_path):
            os.remove(self._disk_cache_path)
            self._disk_cache_path = None
            self._disk_cache_time = None

    def _write_to_disk_cache(self, headers, rows):
        h = md5("|".join(headers).encode()).hexdigest()
        path = os.path.join(tempfile.gettempdir(), f"resultset_{h}.wbormcache")

        def _convert_to_python(value):
            try:
                return str(value)
            except Exception:
                return value

        # Conversão de todos os valores da tabela
        safe_rows = [[_convert_to_python(cell) for cell in row] for row in rows]

        with open(path, "wb") as f:
            pickle.dump((headers, safe_rows), f)

        self._disk_cache_path = path
        self._disk_cache_time = time.time()

    def _read_from_disk_cache(self):
        if not self._disk_cache_path:
            return None, None
        try:
            with open(self._disk_cache_path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None, None

    def show(self, tablefmt="grid", hide_empty_columns=False, page_size=50, reset=False):
        """
            Exibe os resultados da consulta formatados como tabela interativa no terminal.

            Forma de uso:
            -------------
            queryset.show()
            queryset.select("nome", "email").show(tablefmt="fancy_grid")
            queryset.show(hide_empty_columns=True, page_size=20)

            Gera visualizações como:
            ------------------------
            +------------+----------------------+
            | nome       | email                |
            +------------+----------------------+
            | João       | joao@email.com       |
            | Maria      | maria@email.com      |

            Parâmetros:
            -----------
            tablefmt : str
                Formato da tabela. Padrão: "grid" (veja opções em tabulate).
            hide_empty_columns : bool
                Oculta colunas completamente vazias. Útil para joins parciais.
            page_size : int or None
                Define a quantidade de linhas por página (paginação no terminal). Se None, mostra tudo de uma vez.
            reset : bool
                Ignora cache local e força novo processamento da tabela.
            """
        if not self:
            print("Nenhum resultado encontrado.")
            return

        import time
        from tabulate import tabulate
        from colorama import Fore, Style
        from collections import OrderedDict
        import re
        from hashlib import md5

        now = time.time()

        headers, rows = None, None

        if not reset and self._disk_cache_path and self._disk_cache_time and (now - self._disk_cache_time < 120):
            headers, rows = self._read_from_disk_cache()

        if headers is None or rows is None:
            seen = OrderedDict()
            for obj in self:
                for k in obj.to_dict().keys():
                    if k not in seen:
                        seen[k] = True

            all_keys = list(seen.keys())
            has_alias = any(re.match(r"t\d+_", k) for k in all_keys)
            headers = []

            if has_alias:
                from wborm.registry import _model_registry
                aliases = sorted(set(re.match(r"(t\d+)_", k).group(1) for k in all_keys if re.match(r"(t\d+)_", k)))
                for alias in aliases:
                    model = _model_registry.get(alias)
                    if model and hasattr(model, "_fields"):
                        for field in model._fields:
                            alias_field = f"{alias}_{field}"
                            if alias_field in all_keys:
                                headers.append(alias_field)
                    else:
                        headers += [k for k in all_keys if k.startswith(f"{alias}_") and k not in headers]
            else:
                headers = list(seen.keys())

            rows = [[getattr(obj, h, "") for h in headers] for obj in self]

            if hide_empty_columns:
                col_indexes_to_keep = [
                    idx for idx, h in enumerate(headers)
                    if any(str(row[idx]).strip() != "" for row in rows)
                ]
                headers = [headers[i] for i in col_indexes_to_keep]
                headers = [h.replace("_", ".", 1) if re.match(r"t\d+_", h) else h for h in headers]
                rows = [[row[i] for i in col_indexes_to_keep] for row in rows]
            else:
                headers = [h.replace("_", ".", 1) if re.match(r"t\d+_", h) else h for h in headers]

            self._write_to_disk_cache(headers, rows)

        model_cls = self[0].__class__
        cor = Fore.GREEN if not getattr(model_cls, "_from_cache", False) else Fore.BLUE

        def print_page(rows_subset):
            tabela = tabulate(rows_subset, headers=headers, tablefmt=tablefmt)
            linhas_coloridas = []
            for linha in tabela.splitlines():
                if linha and (linha[0] in "+╒╞╘╤╧═" or all(c in "+-=│╒╞╘╤╧═│ " for c in linha)):
                    linhas_coloridas.append(f"{cor}{linha}{Style.RESET_ALL}")
                else:
                    linhas_coloridas.append(linha)
            print("\n".join(linhas_coloridas))

        if page_size is None:
            print_page(rows)
        else:
            total = len(rows)
            for start in range(0, total, page_size):
                end = min(start + page_size, total)
                print_page(rows[start:end])
                if end < total:
                    res = input(
                        f"\n🔽 Mostrando {start + 1}–{end} de {total}. Pressione Enter para continuar ou 'q' para sair...\n")
                    if res.strip().lower() == 'q':
                        print("⏹ Interrompido pelo usuário.\n")
                        break
