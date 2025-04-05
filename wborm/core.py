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
        fields = {k: v for k, v in attrs.items() if isinstance(v, Field)}
        attrs["_fields"] = fields
        return super().__new__(cls, name, bases, attrs)

class Model(metaclass=ModelMeta):
    __tablename__ = None
    _connection = None
    _relations = {}

    def __init__(self, **kwargs):
        for field in self._fields:
            setattr(self, field, kwargs.get(field))

    def to_dict(self):
        return {k: getattr(self, k) for k in self._fields}

    def to_json(self):
        import json
        return json.dumps(self.to_dict())

    def as_dict(self, deep=False):
        base = self.to_dict()
        if deep:
            for rel in self._relations:
                value = getattr(self, rel, None)
                if isinstance(value, list):
                    base[rel] = [v.as_dict(deep=True) for v in value]
                elif value:
                    base[rel] = value.as_dict(deep=True)
        return base

    def show(self):
        print(tabulate([self.to_dict().values()], headers=self.to_dict().keys(), tablefmt="grid"))

    @classmethod
    def describe(cls, inline=False):
        data = [(k, v.field_type.__name__, v.primary_key, v.nullable) for k, v in cls._fields.items()]
        table = tabulate(data, headers=["Campo", "Tipo", "PK", "Nullable"], tablefmt="grid")
        if inline:
            return table
        print(table)

    def invalidate_lazy(self, attr):
        cache_name = f"_lazy_{attr}"
        if hasattr(self, cache_name):
            delattr(self, cache_name)
            cprint(f"⚠ Cache invalidado para '{attr}'", "cyan")

    def before_add(self):
        pass

    def after_update(self):
        pass

    def validate(self):
        for k in self._fields:
            val = getattr(self, k)
            if val is None and not self._fields[k].nullable:
                raise ValueError(f"Campo obrigatório: {k}")

    def create_table(self):
        parts = []
        for name, field in self._fields.items():
            sql_type = "INT" if field.field_type == int else "FLOAT" if field.field_type == float else "VARCHAR(255)"
            nullable = "" if field.nullable else "NOT NULL"
            primary = "PRIMARY KEY" if field.primary_key else ""
            parts.append(f"{name} {sql_type} {nullable} {primary}")
        sql = f"CREATE TABLE {self.__tablename__} ({', '.join(parts)})"
        self._connection.execute(sql)
        cprint(f"✔ Tabela criada: {self.__tablename__}", "cyan")

    def add(self, confirm=False):
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
        return cls._get_queryset().all()

    @classmethod
    def filter(cls, **kwargs):
        return cls._get_queryset().filter(**kwargs)

    @classmethod
    def filter_in(cls, column, values):
        return cls._get_queryset().filter_in(column, values)

    @classmethod
    def not_in(cls, column, values):
        return cls._get_queryset().not_in(column, values)

    @classmethod
    def order_by(cls, *fields):
        return cls._get_queryset().order_by(*fields)

    @classmethod
    def select(cls, *fields):
        return cls._get_queryset().select(*fields)

    @classmethod
    def join(cls, other, on):
        return cls._get_queryset().join(other, on)

    @classmethod
    def group_by(cls, *fields):
        return cls._get_queryset().group_by(*fields)

    @classmethod
    def having(cls, condition):
        return cls._get_queryset().having(condition)

    @classmethod
    def count(cls):
        return cls._get_queryset().count()

    @classmethod
    def distinct(cls):
        return cls._get_queryset().distinct()

    @classmethod
    def raw_sql(cls, sql):
        return cls._get_queryset().raw_sql(sql)

    @classmethod
    def exists(cls):
        return cls._get_queryset().exists()

    @classmethod
    def preload(cls, *relations):
        return cls._get_queryset().preload(*relations)
