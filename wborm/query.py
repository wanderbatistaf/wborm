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

    def filter(self, **kwargs):
        for key, value in kwargs.items():
            self._filters.append((key, value))
        return self

    def filter_in(self, column, values):
        self._in_filters.append((column, values))
        return self

    def not_in(self, column, values):
        self._not_in_filters.append((column, values))
        return self

    def join(self, other, on):
        if isinstance(other, str):
            tablename = other
        else:
            tablename = other.__tablename__
        self._joins.append((tablename, on))
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
            conditions += [f"{k} = '{v}'" for k, v in self._filters]
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
        results = self.conn.execute_query(sql)
        objects = [self.model(**row) for row in results]

        if self._preloads and objects:
            for rel in self._preloads:
                if rel in self.model._relations:
                    Related = generate_model(self.model._relations[rel], self.conn)
                    local_field = None
                    remote_field = None
                    # heurística direta
                    if hasattr(objects[0], "id"):
                        local_field = "id"
                        remote_field = self.model.__tablename__[:-1] + "_id"
                    # heurística reversa
                    elif hasattr(objects[0], rel + "_id"):
                        remote_field = "id"
                        local_field = rel + "_id"
                    if local_field and remote_field:
                        ids = [getattr(obj, local_field) for obj in objects]
                        related = Related.filter_in(remote_field, ids).all()
                        grouped = defaultdict(list)
                        for item in related:
                            key = getattr(item, remote_field)
                            grouped[key].append(item)
                        for obj in objects:
                            val = grouped.get(getattr(obj, local_field), [])
                            setattr(obj, rel, val if isinstance(val, list) else [val])
        return objects

    def first(self):
        self.limit(1)
        results = self.all()
        return results[0] if results else None

    def count(self):
        sql = f"SELECT COUNT(*) as count FROM {self.model.__tablename__}"
        if self._filters:
            conditions = [f"{k} = '{v}'" for k, v in self._filters]
            sql += " WHERE " + " AND " + " AND ".join(conditions)
        result = self.conn.execute_query(sql)
        return result[0]["count"] if result else 0