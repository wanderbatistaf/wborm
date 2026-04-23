import time
import os
import tempfile
import pickle
import re
from wborm.registry import _model_registry
from wborm.cache_config import get_cache_config
from wborm.compat import tabulate_data, terminal_colors
from wborm.connection_utils import run_query
from wborm.performance import get_monitor
from hashlib import md5, sha256

class _Alias:
    def __init__(self, alias): self.alias = alias
    def __call__(self, **kwargs): return [(f"{self.alias}.{k}", v) for k, v in kwargs.items()]


def _auto_inject_aliases():
    import builtins
    for i in range(1, 21):
        builtins.__dict__[f"t{i}"] = _Alias(f"t{i}")

_auto_inject_aliases()  # Executa automaticamente no load do módulo

class QuerySet:
    def __init__(self, model, conn, session=None):
        self.model = model
        self.conn = conn
        self.session = session
        self._filters = []
        self._filter_params = []
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
        self._raw_params = []
        self._preloads = []
        self._lock_clause = None

        # Cache configuration - use global by default
        self._cache_config = get_cache_config()
        self._cache_enabled = None  # None = use global config
        self._cache_ttl = None  # None = use global config

        # Lazy loading configuration
        self._only_fields = []  # Load only these fields
        self._deferred_fields = []  # Don't load these fields

        # Set operations
        self._union_queries = []  # For UNION operations
        self._union_all = False

        from wborm.bootstrap import auto_load_cached_models
        auto_load_cached_models(conn)

    def _qualify_column(self, column):
        if "." in column or not hasattr(self, "_table_alias"):
            return column
        return f"{self._table_alias}.{column}"

    def _build_lookup_condition(self, key, value):
        parts = key.rsplit("__", 1)
        if len(parts) == 2 and parts[1] in {"gt", "gte", "lt", "lte", "ne", "like", "ilike", "contains", "startswith", "endswith"}:
            column, lookup = parts
        else:
            column, lookup = key, "exact"

        column = self._qualify_column(column)
        lookup_map = {
            "exact": (f"{column} = ?", [value]),
            "gt": (f"{column} > ?", [value]),
            "gte": (f"{column} >= ?", [value]),
            "lt": (f"{column} < ?", [value]),
            "lte": (f"{column} <= ?", [value]),
            "ne": (f"{column} <> ?", [value]),
            "like": (f"{column} LIKE ?", [value]),
            "ilike": (f"UPPER({column}) LIKE UPPER(?)", [value]),
            "contains": (f"{column} LIKE ?", [f"%{value}%"]),
            "startswith": (f"{column} LIKE ?", [f"{value}%"]),
            "endswith": (f"{column} LIKE ?", [f"%{value}"]),
        }
        return lookup_map[lookup]

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
                    clause, params = self._build_lookup_condition(k, v)
                    self._filters.append(clause)
                    self._filter_params.extend(params)
        for k, v in kwargs.items():
            clause, params = self._build_lookup_condition(k, v)
            self._filters.append(clause)
            self._filter_params.extend(params)
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
        if isinstance(values, str) and values.strip().upper().startswith("SELECT"):
            self._not_in_filters.append((column, values, True))  # flag subquery
        else:
            self._not_in_filters.append((column, values, False))
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

    def raw_sql(self, sql, params=None):
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
        self._raw_params = list(params or [])
        return self

    def lock_for_update(self, nowait: bool = False):
        self._lock_clause = "FOR UPDATE NOWAIT" if nowait else "FOR UPDATE"
        return self

    def lock_in_share_mode(self):
        self._lock_clause = "FOR SHARE"
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
        sql, params = self._build_query_data()
        result = run_query(self.conn, f"SELECT FIRST 1 1 FROM ({sql}) t", params=params)
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

    def cache(self, enabled: bool = True, ttl: int = None):
        """
            Configura o cache para esta consulta específica.

            Forma de uso:
            -------------
            # Habilita cache com TTL personalizado de 5 minutos
            queryset.filter(status="ATIVO").cache(ttl=300).all()

            # Desabilita cache (equivalente a .live())
            queryset.cache(enabled=False).all()

            Parâmetros:
            -----------
            enabled : bool
                Habilita ou desabilita cache para esta consulta
            ttl : int, optional
                Time-to-live em segundos (sobrescreve configuração global)

            Observações:
            ------------
            Esta configuração afeta apenas a consulta atual e sobrescreve
            a configuração global de cache.
            """
        self._cache_enabled = enabled
        if ttl is not None:
            self._cache_ttl = ttl
        return self

    def only(self, *fields):
        """
            Carrega apenas os campos especificados (lazy loading).

            Todos os outros campos serão marcados como "deferred" e só serão
            carregados quando acessados pela primeira vez.

            Forma de uso:
            -------------
            # Carregar apenas id e nome
            clientes = Cliente.only("id", "nome").all()

            # Acessar campo carregado (sem query adicional)
            print(clientes[0].nome)  # OK

            # Acessar campo deferred (faz query adicional automaticamente)
            print(clientes[0].email)  # Carrega do banco

            Parâmetros:
            -----------
            *fields : str
                Nomes dos campos a serem carregados

            Observações:
            ------------
            - Melhora performance ao evitar carregar colunas grandes não utilizadas
            - Útil para colunas BLOB, TEXT, ou com muitos dados
            - Campos deferred são carregados automaticamente quando acessados
            """
        self._only_fields = list(fields)
        return self

    def defer(self, *fields):
        """
            Adia o carregamento dos campos especificados (lazy loading).

            Os campos especificados não serão carregados na consulta inicial,
            mas serão carregados automaticamente quando acessados.

            Forma de uso:
            -------------
            # Não carregar campos grandes/desnecessários
            produtos = Produto.defer("descricao_completa", "imagem").all()

            # Campos normais são carregados normalmente
            print(produtos[0].nome)  # OK

            # Campos deferred são carregados sob demanda
            print(produtos[0].descricao_completa)  # Carrega do banco

            Parâmetros:
            -----------
            *fields : str
                Nomes dos campos a serem adiados

            Observações:
            ------------
            - Complementar ao .only() - especifica o que NÃO carregar
            - Útil para otimizar queries com muitas colunas
            - Campos deferred são carregados em queries separadas quando necessário
            """
        self._deferred_fields = list(fields)
        return self

    def _cache_key(self, sql, params=None):
        if not params:
            payload = sql
        else:
            payload = f"{sql}|{repr(list(params))}"
        return sha256(payload.encode()).hexdigest()

    def _build_query_data(self):
        if self._raw_sql:
            return self._raw_sql, list(self._raw_params)

        if not hasattr(self, "_table_alias"):
            self._table_alias = "t1"

        # Determine limit/offset clause and position
        skip_first_start = ""
        skip_first_end = ""
        if self._limit is not None:
            # Use dialect-specific limit/offset clause
            dialect = getattr(self.model, '_dialect', None)
            if dialect:
                limit_clause = dialect.limit_offset_clause(self._limit, self._offset)
                if limit_clause:
                    # Check if dialect places limit/offset at start or end
                    if getattr(dialect, 'limit_offset_position', 'end') == 'start':
                        skip_first_start = f"{limit_clause} "
                    else:
                        skip_first_end = f" {limit_clause}"
            else:
                # Fallback to Informix syntax (at start)
                skip_first_start = f"SKIP {self._offset or 0} FIRST {self._limit} "

        prefix = "DISTINCT " if self._distinct else ""

        if self._select_fields:
            selected = ", ".join(self._select_fields)
        else:
            selected_parts = []

            # Determine which fields to load based on .only() and .defer()
            fields_to_load = self.model._fields

            if self._only_fields:
                # Load only specified fields
                fields_to_load = [f for f in fields_to_load if f in self._only_fields]
            elif self._deferred_fields:
                # Load all except deferred fields
                fields_to_load = [f for f in fields_to_load if f not in self._deferred_fields]

            # Principal: t1 (sem prefixo se não houver joins)
            for col in fields_to_load:
                if self._joins:
                    selected_parts.append(f"{self._table_alias}.{col} AS {self._table_alias}_{col}")
                else:
                    selected_parts.append(f"{col}")

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

        base_table = f"{self.model.__tablename__} {self._table_alias}" if self._joins else self.model.__tablename__
        sql = f"SELECT {skip_first_start}{prefix}{selected} FROM {base_table}"

        for join_type, join_table, condition in self._joins:
            sql += f" {join_type} JOIN {join_table} ON {condition}"

        conditions = []
        params = list(self._filter_params)

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
                placeholders = ", ".join("?" for _ in vals)
                conditions.append(f"{col} IN ({placeholders})")
                params.extend(list(vals))
        if self._not_in_filters:
            for col, vals, is_subquery in self._not_in_filters:
                if is_subquery:
                    conditions.append(f"{col} NOT IN ({vals})")
                else:
                    placeholders = ", ".join("?" for _ in vals)
                    conditions.append(f"{col} NOT IN ({placeholders})")
                    params.extend(list(vals))

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        if self._group_by:
            sql += " GROUP BY " + ", ".join(self._group_by)

        if self._having:
            sql += f" HAVING {self._having}"

        if self._order_by:
            sql += " ORDER BY " + ", ".join(self._order_by)

        # Add limit/offset at end if dialect requires it
        sql += skip_first_end
        if self._lock_clause:
            sql += f" {self._lock_clause}"

        return sql, params

    def _build_query(self):
        sql, _ = self._build_query_data()
        return sql

    def preload(self, *relations):
        self._preloads.extend(relations)
        return self

    def all(self):
        sql, params = self._build_query_data()
        key = self._cache_key(sql, params)

        # Determine if cache is enabled for this query
        cache_enabled = (
            self._cache_enabled
            if self._cache_enabled is not None
            else self._cache_config.enabled
        )

        # Get performance monitor
        monitor = get_monitor()

        # Check cache if enabled
        if cache_enabled:
            # If custom TTL is set, temporarily override global config
            if self._cache_ttl is not None:
                original_ttl = self._cache_config.ttl
                self._cache_config.ttl = self._cache_ttl
                cached = self._cache_config.get(key)
                self._cache_config.ttl = original_ttl
            else:
                cached = self._cache_config.get(key)

            if cached is not None:
                # Cache hit - record metrics
                with monitor.measure(sql) as ctx:
                    ctx.set_cache_hit(True)
                    ctx.set_rows(len(cached))

                resultset = ResultSet([
                    self._create_instance_from_row(row) for row in cached
                ])
                if self._select_fields:
                    resultset._selected_fields = self._select_fields
                self._apply_preloads(resultset)
                return resultset

        # Execute query with performance monitoring
        with monitor.measure(sql) as ctx:
            results = run_query(self.conn, sql, params=params)
            ctx.set_rows(len(results))
            ctx.set_cache_hit(False)

        # Store in cache if enabled
        if cache_enabled:
            self._cache_config.set(key, results)

        resultset = ResultSet([
            self._create_instance_from_row(row) for row in results
        ], selected_fields=self._select_fields if self._select_fields else None)
        self._apply_preloads(resultset)
        return resultset

    def _apply_preloads(self, resultset):
        if not self._preloads or not resultset:
            return resultset
        relation_configs = getattr(self.model, "_relation_configs", {})
        from wborm.core import RelationCollection

        for relation in self._preloads:
            config = relation_configs.get(relation)
            if not config:
                continue

            related_model = self.model._resolve_related_model(config["model"])
            local_key = config["local_key"]
            remote_key = config["remote_key"]
            values = [getattr(item, local_key, None) for item in resultset if getattr(item, local_key, None) is not None]
            if not values:
                continue

            related_items = related_model.filter_in(remote_key, list(dict.fromkeys(values))).all()
            if config["kind"] == "belongs_to":
                mapping = {getattr(item, remote_key, None): item for item in related_items}
                for row in resultset:
                    row.__dict__[relation] = mapping.get(getattr(row, local_key, None))
            elif config["kind"] == "many_to_many":
                through = config["through"]
                target_key = config["target_key"]
                target_model = related_model
                owner_ids = list(dict.fromkeys(values))
                owner_list = ", ".join("?" for _ in owner_ids)
                join_rows = run_query(
                    self.conn,
                    f"SELECT {local_key}, {remote_key} FROM {through} WHERE {local_key} IN ({owner_list})",
                    params=owner_ids,
                )
                target_ids = list(dict.fromkeys(row[remote_key] for row in join_rows if remote_key in row))
                if not target_ids:
                    for row in resultset:
                        setattr(row, relation, [])
                    continue
                related_items = target_model.filter_in(target_key, target_ids).all()
                target_map = {getattr(item, target_key, None): item for item in related_items}
                grouped = {}
                for link in join_rows:
                    grouped.setdefault(link[local_key], []).append(target_map.get(link[remote_key]))
                for row in resultset:
                    row.__dict__[relation] = RelationCollection(
                        row,
                        config,
                        [item for item in grouped.get(getattr(row, local_key, None), []) if item is not None],
                    )
            else:
                grouped = {}
                for item in related_items:
                    grouped.setdefault(getattr(item, remote_key, None), []).append(item)
                for row in resultset:
                    row.__dict__[relation] = grouped.get(getattr(row, local_key, None), [])
        return resultset

    def _create_instance_from_row(self, row):
        identity_source = {}
        for key, value in row.items():
            key = str(key)
            if self._joins:
                if key.startswith("t1_"):
                    identity_source[key[3:]] = value
                elif key in self.model._fields:
                    identity_source[key] = value
            else:
                identity_source[key] = value

        obj = self.model.from_row(identity_source, session=self.session) if hasattr(self.model, "from_row") else self.model(**identity_source)
        if self.session:
            obj = self.session.register_loaded(obj)

        for k, v in row.items():
            k = str(k)
            if self._joins:  # só ignora sem tX_ se houver joins
                if not k.startswith("t"):
                    continue
            normalized = self.model._normalize_value(k[3:] if k.startswith("t1_") else k, v) if hasattr(self.model, "_normalize_value") else v
            object.__setattr__(obj, k, normalized)
        obj._connection = self.conn
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
            sql += " WHERE " + " AND ".join(self._filters)
        result = run_query(self.conn, sql, params=self._filter_params)
        return result[0]["count"] if result else 0

    def max(self, column):
        """
        Retorna o valor máximo de uma coluna.

        Exemplo:
        --------
        ultimo = Model.filter(status="ATIVO").max("data_criacao")
        """
        sql = f"SELECT MAX({column}) as max_value FROM {self.model.__tablename__}"

        if self._filters:
            sql += " WHERE " + " AND ".join(self._filters)

        result = run_query(self.conn, sql, params=self._filter_params)
        return result[0]["max_value"] if result else None

    def min(self, column):
        """
        Retorna o valor mínimo de uma coluna.

        Exemplo:
        --------
        primeiro = Model.filter(status="ATIVO").min("data_criacao")
        """
        sql = f"SELECT MIN({column}) as min_value FROM {self.model.__tablename__}"

        if self._filters:
            sql += " WHERE " + " AND ".join(self._filters)

        result = run_query(self.conn, sql, params=self._filter_params)
        return result[0]["min_value"] if result else None

    def sum(self, column):
        """
        Retorna a soma dos valores de uma coluna.

        Exemplo:
        --------
        total = Model.filter(status="ATIVO").sum("valor")
        """
        sql = f"SELECT SUM({column}) as sum_value FROM {self.model.__tablename__}"

        if self._filters:
            sql += " WHERE " + " AND ".join(self._filters)

        result = run_query(self.conn, sql, params=self._filter_params)
        return result[0]["sum_value"] if result else None

    def paginate(self, page: int = 1, page_size: int = 50):
        """
            Pagina os resultados da consulta com metadados completos.

            Forma de uso:
            -------------
            # Página 1 com 20 itens por página
            page = Cliente.filter(status="ATIVO").paginate(page=1, page_size=20)

            # Acessar itens
            for cliente in page.items:
                print(cliente.nome)

            # Metadados de paginação
            print(f"Página {page.page} de {page.pages}")
            print(f"Total: {page.total} clientes")

            # Navegação
            if page.has_next:
                next_page = Cliente.filter(status="ATIVO").paginate(page.next_page)

            Parâmetros:
            -----------
            page : int
                Número da página (1-indexed, padrão: 1)
            page_size : int
                Itens por página (padrão: 50)

            Retorna:
            --------
            Page object com:
                - items: Lista de resultados da página
                - page: Número da página atual
                - page_size: Itens por página
                - total: Total de itens
                - pages: Total de páginas
                - has_next: Se existe próxima página
                - has_prev: Se existe página anterior
                - next_page: Número da próxima página
                - prev_page: Número da página anterior

            Observações:
            ------------
            - Usa SKIP/FIRST para paginação eficiente
            - Calcula automaticamente o total de páginas
            - Fornece metadados completos para UI de paginação
            """
        from wborm.pagination import Paginator
        paginator = Paginator(self, page_size=page_size)
        return paginator.page(page)

    def union(self, other_queryset, all=False):
        """
            Combina resultados de duas queries usando UNION.

            Por padrão, UNION remove duplicatas. Use all=True para UNION ALL.

            Forma de uso:
            -------------
            # UNION (remove duplicatas)
            resultado = Cliente.filter(cidade="SP").union(
                Cliente.filter(cidade="RJ")
            )

            # UNION ALL (mantém duplicatas)
            resultado = Cliente.filter(tipo="VIP").union(
                Cliente.filter(tipo="Premium"),
                all=True
            )

            Parâmetros:
            -----------
            other_queryset : QuerySet
                Outro queryset para combinar
            all : bool
                Se True, usa UNION ALL (mantém duplicatas)

            Retorna:
            --------
            QuerySet com operação UNION configurada

            Observações:
            ------------
            - Ambas as queries devem ter o mesmo número de colunas
            - Tipos de dados devem ser compatíveis
            - ORDER BY só pode ser aplicado no resultado final
            """
        self._union_queries.append(other_queryset)
        self._union_all = all
        return self

    def intersect(self, other_queryset):
        """
            Retorna apenas registros presentes em ambas as queries (INTERSECT).

            Forma de uso:
            -------------
            # Clientes que são VIP E estão em São Paulo
            resultado = Cliente.filter(tipo="VIP").intersect(
                Cliente.filter(cidade="São Paulo")
            )

            Parâmetros:
            -----------
            other_queryset : QuerySet
                Outro queryset para intersecção

            Retorna:
            --------
            ResultSet com registros comuns

            Observações:
            ------------
            - Remove automaticamente duplicatas
            - Ambas queries devem ter mesma estrutura
            - Equivalente a um AND lógico entre conjuntos
            """
        # INTERSECT: Executa ambas queries e retorna apenas IDs em comum
        results1 = self.all()
        results2 = other_queryset.all()

        # Assume que modelos têm um campo 'id' ou primeiro campo como PK
        pk_fields = self.model._pk_field_names() if hasattr(self.model, "_pk_field_names") else [getattr(self.model, '_pk_field', None) or self.model._fields[0]]
        key_for = lambda record: tuple(getattr(record, field) for field in pk_fields) if len(pk_fields) > 1 else getattr(record, pk_fields[0])

        ids1 = {key_for(r) for r in results1}
        ids2 = {key_for(r) for r in results2}

        common_ids = ids1 & ids2

        # Retorna apenas registros com IDs em comum
        return ResultSet([r for r in results1 if key_for(r) in common_ids])

    def except_(self, other_queryset):
        """
            Retorna registros da primeira query que NÃO estão na segunda (EXCEPT).

            Forma de uso:
            -------------
            # Clientes VIP que NÃO estão em São Paulo
            resultado = Cliente.filter(tipo="VIP").except_(
                Cliente.filter(cidade="São Paulo")
            )

            Parâmetros:
            -----------
            other_queryset : QuerySet
                Queryset com registros a serem excluídos

            Retorna:
            --------
            ResultSet com registros únicos da primeira query

            Observações:
            ------------
            - Remove automaticamente duplicatas
            - Equivalente a diferença de conjuntos (A - B)
            - Método chamado except_ (com underscore) pois 'except' é palavra reservada
            """
        results1 = self.all()
        results2 = other_queryset.all()

        pk_fields = self.model._pk_field_names() if hasattr(self.model, "_pk_field_names") else [getattr(self.model, '_pk_field', None) or self.model._fields[0]]
        key_for = lambda record: tuple(getattr(record, field) for field in pk_fields) if len(pk_fields) > 1 else getattr(record, pk_fields[0])

        ids1 = {key_for(r) for r in results1}
        ids2 = {key_for(r) for r in results2}

        diff_ids = ids1 - ids2

        return ResultSet([r for r in results1 if key_for(r) in diff_ids])

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

        table = tabulate_data(rows, headers=headers, tablefmt="grid")

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
        create_sql = f"{sql} INTO TEMP {temp_name} {log_clause}"

        print(f"Criando tabela temporária:\n{create_sql}")
        self.conn.execute_query(create_sql)

        # Sempre retorna o Model, mesmo se estiver vazia
        from wborm.utils import generate_model
        return generate_model(temp_name, self.conn, inject_globals=True)

    def create_empty_temp_table(self, temp_name, columns, with_log=False):
        """
        Cria uma tabela temporária vazia com schema explícito.

        Exemplo:
            qs.create_empty_temp_table(
                "tmp_01",
                [
                    ("mach_cd", "VARCHAR(20)"),
                    ("back_load", "VARCHAR(20)"),
                    ("wgt_cons", "DECIMAL(18,2)")
                ],
                with_log=False
            )
        """
        log_clause = "WITH LOG" if with_log else "WITH NO LOG"
        cols = ",\n    ".join([f"{name} {dtype}" for name, dtype in columns])

        create_sql = f"""
                    CREATE TEMP TABLE {temp_name} (
                        {cols}
                    ) {log_clause}
                """
        print(f"Criando tabela temporária vazia:\n{create_sql}")
        self.conn.execute_query(create_sql)

        from wborm.utils import generate_model
        model = generate_model(temp_name, self.conn, inject_globals=True)

        # Fallback: garante que _fields exista mesmo sem linhas
        if not getattr(model, "_fields", None):
            model._fields = [name for name, _ in columns]

        return model


    def insert_into(self, table_name, columns=None):
        """
        Insere o resultado da query atual na tabela informada.

        Exemplo:
            qs.select("... AS c1", "... AS c2").insert_into("tmp_tab", columns=["c1","c2"])
        """
        sql = self._build_query()
        if not sql:
            # nada pra inserir → apenas retorna, não quebra
            return self
        if columns:
            cols = ", ".join(columns)
            insert_sql = f"INSERT INTO {table_name} ({cols}) {sql}"
        else:
            insert_sql = f"INSERT INTO {table_name} {sql}"
        self.conn.execute_query(insert_sql)
        return self

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
        from collections import OrderedDict
        from hashlib import md5
        Fore, Style = terminal_colors()

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
            tabela = tabulate_data(rows_subset, headers=headers, tablefmt=tablefmt)
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
