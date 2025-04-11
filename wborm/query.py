import time
from tabulate import tabulate
from wborm.registry import _query_result_cache
from colorama import Fore, Style

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

    def filter(self, *args, **kwargs):
        for cond in args:
            if isinstance(cond, str):
                self._filters.append(cond)
            elif isinstance(cond, ColumnExpr):
                self._filters.append(str(cond))
        for k, v in kwargs.items():
            escaped = str(v).replace("'", "''")
            self._filters.append(f"{k} = '{escaped}'")
        return self

    def filter_in(self, column, values):
        self._in_filters.append((column, values))
        return self

    def not_in(self, column, values):
        self._not_in_filters.append((column, values))
        return self

    def join(self, other, on):
        if isinstance(other, QuerySet):
            if not hasattr(other, "_as_temp_table_alias"):
                raise ValueError(
                    "O QuerySet precisa ser nomeado com `.as_temp_table(alias)` antes de ser usado como join.")
            subquery_sql = other._build_query()
            tablename = f"({subquery_sql}) AS {other._as_temp_table_alias}"
            alias = other._as_temp_table_alias
        elif isinstance(other, str):
            tablename = other
            alias = other
        else:
            tablename = other.__tablename__
            alias = other.__tablename__

        # Monta cláusula ON conforme formato
        if isinstance(on, (list, tuple)):
            conditions = [
                f"{self.model.__tablename__}.{col} = {alias}.{col}" for col in on
            ]
            on_clause = " AND ".join(conditions)
        elif "." not in on and "=" not in on:
            on_clause = f"{self.model.__tablename__}.{on} = {alias}.{on}"
        else:
            on_clause = on  # já completa

        self._joins.append((tablename, on_clause))
        return self

    def limit(self, value):
        self._limit = value
        return self

    def offset(self, value):
        self._offset = value
        return self

    def order_by(self, *fields):
        self._order_by.extend(fields)
        return self

    def select(self, *fields):
        self._select_fields = list(fields)
        return self

    def group_by(self, *fields):
        self._group_by.extend(fields)
        return self

    def having(self, condition):
        self._having = condition
        return self

    def distinct(self):
        self._distinct = True
        return self

    def raw_sql(self, sql):
        self._raw_sql = sql
        return self

    def exists(self):
        sql = self._build_query()
        result = self.conn.execute_query(f"SELECT FIRST 1 1 FROM ({sql}) t")
        return len(result) > 0

    def live(self):
        self._cache_enabled = False
        return self

    def _cache_key(self, sql):
        import hashlib
        return hashlib.sha256(sql.encode()).hexdigest()

    def _build_query(self):
        if self._raw_sql:
            return self._raw_sql

        skip_first = ""
        if self._limit is not None:
            skip_first = f"SKIP {self._offset or 0} FIRST {self._limit} "

        prefix = "DISTINCT " if self._distinct else ""
        selected = ", ".join(self._select_fields) if self._select_fields else "*"
        sql = f"SELECT {skip_first}{prefix}{selected} FROM {self.model.__tablename__}"

        for join_table, condition in self._joins:
            sql += f" JOIN {join_table} ON {condition}"

        conditions = []
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

        # print(sql)

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

        return resultset

    def _create_instance_from_row(self, row):
        obj = self.model()
        for k, v in row.items():
            k = str(k)
            if hasattr(self.model, "_fields") and k in self.model._fields:
                setattr(obj, k, v)
            else:
                obj.__dict__[k] = v
        return obj

    def first(self):
        self.limit(1)
        results = self.all()
        return results[0] if results else None

    def count(self):
        sql = f"SELECT COUNT(*) as count FROM {self.model.__tablename__}"
        if self._filters:
            # conditions += [f"{k} = '{str(v).replace("'", "''")}'" for k, v in self._filters]
            conditions = ["{} = '{}'".format(k, str(v).replace("'", "''")) for k, v in self._filters]
            sql += " WHERE " + " AND ".join(conditions)
        result = self.conn.execute_query(sql)
        return result[0]["count"] if result else 0


    def show(self, tablefmt="grid"):
        return self.all().show(tablefmt=tablefmt)

    def pivot(self, index=None, columns=None, values=None, limit=500):
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
        Cria uma tabela temporária com base no SQL atual.

        Parâmetros:
        - temp_name (str): nome da tabela temporária.
        - with_log (bool): define se a tabela será criada com log (padrão: False).
        """
        sql = self._build_query()
        log_clause = "WITH LOG" if with_log else "WITH NO LOG"
        create_sql = f"CREATE TEMP TABLE {temp_name} AS ({sql}) {log_clause}"

        print(f" Criando tabela temporária:\n{create_sql}")
        self.conn.execute(create_sql)

        # Gera e retorna o modelo temporário com injeção global
        from wborm.utils import generate_model
        model = generate_model(temp_name, self.conn, inject_globals=True)
        return model


class ResultSet(list):
    def __init__(self, data=None, selected_fields=None):
        super().__init__(data or [])
        self._selected_fields = selected_fields

    def show(self, tablefmt="grid"):
        if not self:
            print("Nenhum resultado encontrado.")
            return

        from tabulate import tabulate
        from colorama import Fore, Style
        from collections import OrderedDict

        # Debug explícito
        # print(f"🧪 DEBUG: Campos selecionados = {self._selected_fields}")

        # Usa os campos explicitamente selecionados, se houver
        if self._selected_fields:
            headers = self._selected_fields
        else:
            seen = OrderedDict()
            for obj in self:
                for k in obj.to_dict().keys():
                    if k not in seen:
                        seen[k] = True
            headers = list(seen.keys())

        # Prepara as linhas considerando os headers detectados
        rows = [[getattr(obj, h, "") for h in headers] for obj in self]

        # Remove colunas completamente vazias
        col_indexes_to_keep = [
            idx for idx, h in enumerate(headers)
            if any(str(row[idx]).strip() != "" for row in rows)
        ]
        headers = [headers[i] for i in col_indexes_to_keep]
        rows = [[row[i] for i in col_indexes_to_keep] for row in rows]

        # Renderiza tabela com cor no contorno
        tabela = tabulate(rows, headers=headers, tablefmt=tablefmt)
        model_cls = self[0].__class__
        cor = Fore.GREEN if not getattr(model_cls, "_from_cache", False) else Fore.BLUE

        linhas_coloridas = []
        for linha in tabela.splitlines():
            if linha and (linha[0] in "+╒╞╘╤╧═" or all(c in "+-=│╒╞╘╤╧═│ " for c in linha)):
                linhas_coloridas.append(f"{cor}{linha}{Style.RESET_ALL}")
            else:
                linhas_coloridas.append(linha)

        print("\n".join(linhas_coloridas))



