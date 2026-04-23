import json
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

from wborm.compat import cprint, tabulate_data, terminal_colors
from wborm.connection_utils import begin_transaction, can_use_execute_batch, commit_transaction, execute_sql, rollback_transaction, run_query
from wborm.cache_config import clear_cache
from wborm.exceptions import ORMValidationError
from wborm.fields import Field
from wborm.query import QuerySet
from wborm.session import Session

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


class RelationCollection(list):
    def __init__(self, owner, config, items=None):
        super().__init__(items or [])
        self.owner = owner
        self.config = config

    def add(self, *targets):
        for target in targets:
            self.owner._attach_many_to_many_relation(self.config, target)
            if target not in self:
                super().append(target)
        return self

    def remove(self, *targets):
        for target in targets:
            self.owner._detach_many_to_many_relation(self.config, target)
            while target in self:
                super().remove(target)
        return self

    def clear(self):
        self.owner._clear_many_to_many_relation(self.config)
        super().clear()
        return self

    def set(self, targets):
        self.clear()
        self.add(*list(targets))
        return self

class ModelMeta(type):
    def __new__(cls, name, bases, attrs):
        base_fields = {}
        base_relations = {}
        base_relation_configs = {}
        for base in bases:
            base_fields.update(getattr(base, "_fields", {}))
            base_relations.update(getattr(base, "_relations", {}))
            base_relation_configs.update(getattr(base, "_relation_configs", {}))
        fields = {str(k): v for k, v in attrs.items() if isinstance(v, Field)}
        attrs["_fields"] = {**base_fields, **fields}
        attrs["_relations"] = dict(base_relations)
        attrs["_relation_configs"] = dict(base_relation_configs)
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
    _relation_configs = {}

    def __init__(self, **kwargs):
        object.__setattr__(self, "_session", kwargs.pop("_session", None))
        object.__setattr__(self, "_state", "new")
        object.__setattr__(self, "_original_values", {})
        object.__setattr__(self, "_expired_fields", set())
        for field_name, field in self._fields.items():
            if field_name in kwargs:
                value = kwargs[field_name]
            else:
                default = field.default() if callable(field.default) else field.default
                value = default
            object.__setattr__(self, field_name, value)
        self._take_snapshot()

    def __getattribute__(self, name):
        value = object.__getattribute__(self, name)
        if name.startswith("_"):
            return value
        try:
            expired = object.__getattribute__(self, "_expired_fields")
        except AttributeError:
            return value
        if name in expired:
            session = object.__getattribute__(self, "_session")
            if session:
                session.refresh(self, fields=[name])
                return object.__getattribute__(self, name)
        return value

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        if name.startswith("_") or name not in getattr(self, "_fields", {}):
            return
        session = getattr(self, "_session", None)
        if session and getattr(self, "_state", None) in {"clean", "dirty"}:
            session.mark_dirty(self)
            object.__setattr__(self, "_state", "dirty")

    @classmethod
    def _pk_field_names(cls):
        names = [name for name, field in cls._fields.items() if field.primary_key]
        if names:
            return names
        return ["id"] if "id" in cls._fields else ([next(iter(cls._fields))] if cls._fields else [])

    @classmethod
    def _pk_field_name(cls):
        names = cls._pk_field_names()
        return names[0] if names else None

    def _pk_value(self):
        pk_names = self._pk_field_names()
        if not pk_names:
            return None
        if len(pk_names) == 1:
            return getattr(self, pk_names[0], None)
        values = tuple(getattr(self, name, None) for name in pk_names)
        return None if any(value is None for value in values) else values

    def _pk_filter_dict(self):
        pk_names = self._pk_field_names()
        if not pk_names:
            return {}
        return {name: getattr(self, name, None) for name in pk_names}

    def identity_key(self):
        pk_name = tuple(self._pk_field_names())
        pk_value = self._pk_value()
        if pk_name is None or pk_value is None:
            return None
        return self.__class__, pk_name, pk_value

    def _take_snapshot(self):
        object.__setattr__(
            self,
            "_original_values",
            {field_name: getattr(self, field_name, None) for field_name in self._fields},
        )
        object.__getattribute__(self, "_expired_fields").clear()

    @classmethod
    def _get_connection(cls):
        if cls._connection is None:
            raise RuntimeError(f"Modelo '{cls.__name__}' sem conexão associada.")
        return cls._connection

    @staticmethod
    def _serialize_value(value):
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return f"'{value.isoformat(sep=' ', timespec='seconds')}'"
        if isinstance(value, date):
            return f"'{value.isoformat()}'"
        if isinstance(value, (int, float)):
            return str(value)
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    @classmethod
    def _build_where_clause(cls, filters):
        return " AND ".join(f"{key} = ?" for key in filters), list(filters.values())

    def _collect_field_values(self):
        return {field_name: getattr(self, field_name, None) for field_name in self._fields}

    def _dirty_field_values(self):
        current = self._collect_field_values()
        original = getattr(self, "_original_values", {})
        return {key: value for key, value in current.items() if original.get(key) != value}

    @classmethod
    def _resolve_related_model(cls, model_ref):
        if isinstance(model_ref, str):
            from wborm.utils import generate_model
            return generate_model(model_ref, cls._get_connection(), inject_globals=False)
        return model_ref

    @classmethod
    def _normalize_value(cls, field_name, value):
        if value is None or isinstance(value, (str, int, float, bool, bytes)):
            if value is None:
                return value
        elif isinstance(value, memoryview):
            value = value.tobytes()
        elif isinstance(value, bytearray):
            value = bytes(value)

        field = cls._fields.get(field_name)
        target_type = field.field_type if field else None

        if target_type is Decimal:
            try:
                return Decimal(str(value).strip())
            except Exception:
                return value
        if target_type is datetime:
            if isinstance(value, datetime):
                return value
            try:
                return datetime.fromisoformat(str(value).strip().replace(" ", "T", 1))
            except Exception:
                return value
        if target_type is date:
            if isinstance(value, date) and not isinstance(value, datetime):
                return value
            try:
                return date.fromisoformat(str(value).strip().split(" ")[0])
            except Exception:
                return value
        if target_type is bytes:
            if isinstance(value, bytes):
                return value
            if isinstance(value, str):
                return value.encode()
            return bytes(value) if isinstance(value, bytearray) else value
        if target_type is int:
            try:
                return int(value)
            except Exception:
                return value
        if target_type is float:
            try:
                return float(value)
            except Exception:
                return value
        if target_type is bool:
            try:
                return bool(value)
            except Exception:
                return value
        if target_type is str:
            try:
                return str(value)
            except Exception:
                return value

        try:
            return str(value)
        except Exception:
            return value

    @staticmethod
    def _export_value(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except Exception:
                return value.hex()
        return value

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
        payload = {}
        for k in self.__dict__:
            if k.startswith("_") or callable(getattr(self, k)):
                continue
            payload[k] = self._export_value(self._normalize_value(k, getattr(self, k)))
        return payload

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
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data, session=None):
        instance = cls(**data, _session=session)
        object.__setattr__(instance, "_state", "clean")
        instance._take_snapshot()
        if session:
            session.register_loaded(instance)
        return instance

    @classmethod
    def from_row(cls, row, session=None):
        payload = {}
        for field_name, field in cls._fields.items():
            if field_name in row:
                payload[field_name] = cls._normalize_value(field_name, row[field_name])
                continue
            column_name = field.column_name or field_name
            if column_name in row:
                payload[field_name] = cls._normalize_value(field_name, row[column_name])
        instance = cls.from_dict(payload, session=session)
        for key, value in row.items():
            if key not in payload:
                object.__setattr__(instance, str(key), cls._normalize_value(str(key), value))
        return instance

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

    def serialize(self, deep=False):
        return self.as_dict(deep=deep)

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
        try:
            Fore, Style = terminal_colors()
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
            tabela = tabulate_data(rows, headers=headers, tablefmt="grid")

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
        table = tabulate_data(data, headers=["Campo", "Tipo", "PK", "Nullable"], tablefmt="grid")
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

    def before_insert(self):
        self.before_add()

    def after_insert(self):
        pass

    def before_update(self):
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

    def before_delete(self):
        pass

    def after_delete(self):
        pass

    def before_save(self):
        pass

    def after_save(self):
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
        for name, field in self._fields.items():
            val = getattr(self, name)
            if val is None:
                if not field.nullable:
                    raise ORMValidationError(f"Campo obrigatório: {name}")
                continue
            if field.choices and val not in field.choices:
                raise ORMValidationError(f"Valor inválido para {name}: {val!r}")
            if field.max_length is not None and len(str(val)) > field.max_length:
                raise ORMValidationError(f"Campo excede tamanho máximo: {name}")
            if field.field_type and not isinstance(val, field.field_type):
                raise ORMValidationError(
                    f"Tipo inválido para {name}: esperado {field.field_type.__name__}, recebido {type(val).__name__}"
                )
            if field.validator:
                result = field.validator(val)
                if result is False:
                    raise ORMValidationError(f"Validação customizada falhou para {name}")
        return True

    @contextmanager
    def _transaction_context(self, connection=None):
        conn = connection or self._get_connection()
        begin_transaction(conn)
        try:
            yield conn
            commit_transaction(conn)
        except Exception:
            rollback_transaction(conn)
            raise

    def _run_insert(self, connection=None):
        conn = connection or self._get_connection()
        for _, target in self._cascade_targets("save-update"):
            if hasattr(target, "_pk_value") and target._pk_value() is None:
                target._run_insert(connection=conn)
        self.before_save()
        self.before_insert()
        self.validate()
        keys = list(self._fields.keys())
        values = [getattr(self, key) for key in keys]
        placeholders = ", ".join("?" for _ in keys)
        sql = f"INSERT INTO {self.__tablename__} ({', '.join(keys)}) VALUES ({placeholders})"
        execute_sql(conn, sql, params=values)
        self._increment_version()
        self.after_insert()
        self.after_save()
        clear_cache()
        object.__setattr__(self, "_state", "clean")
        self._take_snapshot()
        return sql

    def _run_update(self, filters, connection=None):
        if not filters:
            raise ValueError("Update requer cláusula explícita: ex. update(confirm=True, id=1)")
        conn = connection or self._get_connection()
        self.before_save()
        self.before_update()
        self.validate()
        updates = self._dirty_field_values() or self._collect_field_values()
        if not updates:
            return None
        where_filters = dict(filters)
        self._apply_optimistic_lock(where_filters, updates)
        where_clause, where_params = self._build_where_clause(where_filters)
        update_clause = ", ".join(f"{key} = ?" for key in updates)
        sql = (
            f"UPDATE {self.__tablename__} SET "
            f"{update_clause} "
            f"WHERE {where_clause}"
        )
        execute_sql(conn, sql, params=list(updates.values()) + where_params)
        self._handle_delete_orphans(connection=conn)
        self.after_update()
        self.after_save()
        clear_cache()
        object.__setattr__(self, "_state", "clean")
        self._take_snapshot()
        return sql

    def _run_delete(self, filters, connection=None):
        if not filters:
            raise ValueError("Delete requer cláusula explícita: ex. delete(confirm=True, id=1)")
        conn = connection or self._get_connection()
        self.before_delete()
        for config, target in self._cascade_targets("delete"):
            if config["kind"] == "many_to_many":
                self._detach_many_to_many_relation(config, target)
            elif hasattr(target, "_pk_value") and target._pk_value() is not None:
                target._run_delete(target._pk_filter_dict(), connection=conn)
        for config in getattr(self.__class__, "_relation_configs", {}).values():
            cascade = tuple(config.get("cascade", ()))
            if config.get("kind") == "many_to_many" and ("all" in cascade or "delete" in cascade):
                self._clear_many_to_many_relation(config)
        where_clause, where_params = self._build_where_clause(filters)
        sql = f"DELETE FROM {self.__tablename__} WHERE {where_clause}"
        execute_sql(conn, sql, params=where_params)
        self.after_delete()
        clear_cache()
        object.__setattr__(self, "_state", "deleted")
        return sql

    def _insert_via_session(self, session):
        return self._run_insert(connection=session.connection)

    def _update_via_session(self, session):
        return self._run_update(self._pk_filter_dict(), connection=session.connection)

    def _delete_via_session(self, session):
        return self._run_delete(self._pk_filter_dict(), connection=session.connection)

    def _increment_version(self):
        for field_name, field in self._fields.items():
            if field.version:
                current = getattr(self, field_name, 0) or 0
                setattr(self, field_name, current + 1)

    def _apply_optimistic_lock(self, where_filters, updates):
        for field_name, field in self._fields.items():
            if not field.version:
                continue
            current = getattr(self, field_name, 0) or 0
            original = self._original_values.get(field_name, current)
            where_filters.setdefault(field_name, original)
            updates[field_name] = current + 1
            setattr(self, field_name, current + 1)
            return

    def _cascade_targets(self, action):
        for relation, config in getattr(self.__class__, "_relation_configs", {}).items():
            cascade = tuple(config.get("cascade", ()))
            if "all" not in cascade and action not in cascade:
                continue
            if relation not in self.__dict__:
                continue
            value = self.__dict__.get(relation)
            if value is None:
                continue
            if isinstance(value, list):
                for item in value:
                    if item is not None:
                        yield config, item
            else:
                yield config, value

    def _handle_delete_orphans(self, connection=None):
        conn = connection or self._get_connection()
        owner_pk = self._pk_value()
        if owner_pk is None:
            return
        for relation, config in getattr(self.__class__, "_relation_configs", {}).items():
            cascade = tuple(config.get("cascade", ()))
            if "delete-orphan" not in cascade or relation not in self.__dict__:
                continue
            if config["kind"] != "has_many":
                continue
            target_model = self._resolve_related_model(config["model"])
            local_key = config["local_key"]
            remote_key = config["remote_key"]
            current_children = self.__dict__.get(relation) or []
            current_ids = {
                child._pk_value() for child in current_children
                if hasattr(child, "_pk_value") and child._pk_value() is not None
            }
            existing = target_model.filter(**{remote_key: getattr(self, local_key)}).all()
            for child in existing:
                child_id = child._pk_value()
                if child_id is not None and child_id not in current_ids:
                    child._run_delete(child._pk_filter_dict(), connection=conn)

    def _attach_many_to_many_relation(self, config, target):
        owner_id = self._pk_value()
        target_key = config.get("target_key", "id")
        target_id = getattr(target, target_key, None)
        if owner_id is None or target_id is None:
            raise ORMValidationError("Relacionamento many-to-many requer IDs persistidos em ambos os lados")
        execute_sql(
            self._get_connection(),
            (
                f"INSERT INTO {config['through']} ({config['local_key']}, {config['remote_key']}) "
                "VALUES (?, ?)"
            ),
            params=[owner_id, target_id],
        )
        clear_cache()

    def _detach_many_to_many_relation(self, config, target):
        owner_id = self._pk_value()
        target_key = config.get("target_key", "id")
        target_id = getattr(target, target_key, None)
        execute_sql(
            self._get_connection(),
            (
                f"DELETE FROM {config['through']} "
                f"WHERE {config['local_key']} = ? AND {config['remote_key']} = ?"
            ),
            params=[owner_id, target_id],
        )
        clear_cache()

    def _clear_many_to_many_relation(self, config):
        execute_sql(
            self._get_connection(),
            f"DELETE FROM {config['through']} WHERE {config['local_key']} = ?",
            params=[self._pk_value()],
        )
        clear_cache()

    def refresh(self, fields=None):
        session = getattr(self, "_session", None)
        if session:
            session.refresh(self, fields=fields)
            return self
        refreshed = self.__class__.filter(**self._pk_filter_dict()).first()
        if not refreshed:
            return self
        selected = set(fields or self._fields.keys())
        for field_name in selected:
            if field_name in self._fields:
                object.__setattr__(self, field_name, getattr(refreshed, field_name, None))
        self._take_snapshot()
        object.__setattr__(self, "_state", "clean")
        return self

    def expire(self, *fields):
        selected = set(fields or self._fields.keys())
        self._expired_fields.update(selected)
        return self

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
        execute_sql(self._connection, sql)
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
        execute_sql(self._connection, sql)
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
        try:
            with self._transaction_context():
                self._run_insert()
            cprint(f"✔ Registro adicionado em {self.__tablename__}", "green")
        except Exception as e:
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
        keys = list(cls._fields.keys())
        try:
            begin_transaction(cls._connection)
            if can_use_execute_batch(cls._connection):
                batch_values = []
                for obj in objs:
                    obj.before_save()
                    obj.before_insert()
                    obj.validate()
                    batch_values.append(tuple(getattr(obj, key) for key in keys))
                placeholders = ", ".join("?" for _ in keys)
                cls._connection.execute_batch(
                    f"INSERT INTO {cls.__tablename__} ({', '.join(keys)}) VALUES ({placeholders})",
                    batch_values,
                )
                for obj in objs:
                    obj._increment_version()
                    obj.after_insert()
                    obj.after_save()
                    object.__setattr__(obj, "_state", "clean")
                    obj._take_snapshot()
            else:
                for obj in objs:
                    obj._run_insert(connection=cls._connection)
            commit_transaction(cls._connection)
            cprint(f"✔ {len(objs)} registros adicionados em {cls.__tablename__}", "green")
        except Exception as e:
            rollback_transaction(cls._connection)
            cprint(f"✖ Falha no bulk_add de {cls.__tablename__}: {str(e)}", "red")
            raise

    @classmethod
    def bulk_update(cls, objs, confirm=False, where_field=None):
        if not confirm:
            raise ValueError("Confirmação necessária: bulk_update(confirm=True)")
        if not objs:
            return
        if len(cls._pk_field_names()) > 1 and where_field is None:
            try:
                begin_transaction(cls._connection)
                for obj in objs:
                    obj._run_update(obj._pk_filter_dict(), connection=cls._connection)
                commit_transaction(cls._connection)
            except Exception:
                rollback_transaction(cls._connection)
                raise
            return
        where_field = where_field or cls._pk_field_name()
        updates = [field for field in cls._fields.keys() if field != where_field]
        try:
            begin_transaction(cls._connection)
            if can_use_execute_batch(cls._connection):
                sql = (
                    f"UPDATE {cls.__tablename__} SET "
                    f"{', '.join(f'{field} = ?' for field in updates)} "
                    f"WHERE {where_field} = ?"
                )
                params = []
                for obj in objs:
                    obj.before_save()
                    obj.before_update()
                    obj.validate()
                    params.append(tuple(getattr(obj, field) for field in updates) + (getattr(obj, where_field),))
                cls._connection.execute_batch(sql, params)
                for obj in objs:
                    obj.after_update()
                    obj.after_save()
                    object.__setattr__(obj, "_state", "clean")
                    obj._take_snapshot()
            else:
                for obj in objs:
                    obj._run_update({where_field: getattr(obj, where_field)}, connection=cls._connection)
            commit_transaction(cls._connection)
        except Exception:
            rollback_transaction(cls._connection)
            raise

    @classmethod
    def bulk_delete(cls, objs_or_ids, confirm=False, where_field=None):
        if not confirm:
            raise ValueError("Confirmação necessária: bulk_delete(confirm=True)")
        if not objs_or_ids:
            return
        if len(cls._pk_field_names()) > 1 and where_field is None:
            try:
                begin_transaction(cls._connection)
                for item in objs_or_ids:
                    if isinstance(item, cls):
                        filters = item._pk_filter_dict()
                    elif isinstance(item, dict):
                        filters = dict(item)
                    elif isinstance(item, tuple):
                        filters = dict(zip(cls._pk_field_names(), item))
                    else:
                        raise ValueError("bulk_delete com PK composta requer tupla, dict ou instancia do modelo")
                    where_clause, params = cls._build_where_clause(filters)
                    execute_sql(cls._connection, f"DELETE FROM {cls.__tablename__} WHERE {where_clause}", params=params)
                commit_transaction(cls._connection)
            except Exception:
                rollback_transaction(cls._connection)
                raise
            return
        where_field = where_field or cls._pk_field_name()
        normalized = []
        for item in objs_or_ids:
            if isinstance(item, cls):
                normalized.append(getattr(item, where_field))
            else:
                normalized.append(item)
        try:
            begin_transaction(cls._connection)
            if can_use_execute_batch(cls._connection):
                sql = f"DELETE FROM {cls.__tablename__} WHERE {where_field} = ?"
                cls._connection.execute_batch(sql, [(value,) for value in normalized])
            else:
                for value in normalized:
                    execute_sql(
                        cls._connection,
                        f"DELETE FROM {cls.__tablename__} WHERE {where_field} = ?",
                        params=[value],
                    )
            commit_transaction(cls._connection)
        except Exception:
            rollback_transaction(cls._connection)
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
            with self._transaction_context():
                self._run_update(kwargs)
            where_clause, _ = self._build_where_clause(kwargs)
            cprint(f"✔ Registro atualizado em {self.__tablename__} (WHERE {where_clause})", "yellow")
        except Exception as e:
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
            with self._transaction_context():
                self._run_delete(kwargs)
            where_clause, _ = self._build_where_clause(kwargs)
            cprint(f"✔ Registro deletado de {self.__tablename__} (WHERE {where_clause})", "red")
        except Exception as e:
            cprint(f"✖ Falha ao deletar de {self.__tablename__}: {str(e)}", "red")
            raise

    def save(self, confirm=False, **kwargs):
        if self._pk_value() is None or self._state == "new":
            return self.add(confirm=confirm)
        if not kwargs:
            kwargs = self._pk_filter_dict()
        return self.update(confirm=confirm, **kwargs)

    @classmethod
    def _get_queryset(cls, session=None):
        connection = session.connection if session else cls._connection
        return QuerySet(cls, connection, session=session)

    @classmethod
    def session(cls):
        return Session(cls._get_connection())

    @classmethod
    @contextmanager
    def transaction(cls):
        session = cls.session()
        with session.transaction():
            yield session

    @classmethod
    def begin(cls):
        begin_transaction(cls._get_connection())

    @classmethod
    def commit(cls):
        commit_transaction(cls._get_connection())

    @classmethod
    def rollback(cls):
        rollback_transaction(cls._get_connection())

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
    def raw_sql(cls, sql, params=None):
        """
        Substitui a consulta atual por um SQL customizado.

        Forma de uso:
        -------------
        Cliente.raw_sql("SELECT * FROM clientes WHERE status = 'ATIVO'")

        Gera cláusulas como:
        --------------------
        Executa exatamente o SQL fornecido, ignorando filtros e joins definidos no queryset.
        """
        return cls._get_queryset().raw_sql(sql, params=params)

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
    def belongs_to(cls, relation_name, target_model, local_key=None, remote_key="id", cascade=()):
        local_key = local_key or f"{relation_name}_id"
        model_ref = target_model if not isinstance(target_model, str) else target_model

        def relation_getter(self):
            if relation_name in self.__dict__:
                return self.__dict__[relation_name]
            resolved = cls._resolve_related_model(model_ref)
            value = resolved.filter(**{remote_key: getattr(self, local_key)}).first()
            self.__dict__[relation_name] = value
            return value

        def relation_setter(self, value):
            self.__dict__[relation_name] = value

        setattr(cls, relation_name, property(relation_getter, relation_setter))
        cls._relations[relation_name] = getattr(target_model, "__tablename__", target_model)
        cls._relation_configs[relation_name] = {
            "kind": "belongs_to",
            "model": model_ref,
            "local_key": local_key,
            "remote_key": remote_key,
            "cascade": tuple(cascade),
        }
        return cls

    @classmethod
    def has_many(cls, relation_name, target_model, local_key="id", remote_key=None, cascade=()):
        remote_key = remote_key or f"{cls.__tablename__.rstrip('s')}_id"
        model_ref = target_model if not isinstance(target_model, str) else target_model

        def relation_getter(self):
            if relation_name in self.__dict__:
                return self.__dict__[relation_name]
            resolved = cls._resolve_related_model(model_ref)
            value = resolved.filter(**{remote_key: getattr(self, local_key)}).all()
            self.__dict__[relation_name] = value
            return value

        def relation_setter(self, value):
            self.__dict__[relation_name] = value

        setattr(cls, relation_name, property(relation_getter, relation_setter))
        cls._relations[relation_name] = getattr(target_model, "__tablename__", target_model)
        cls._relation_configs[relation_name] = {
            "kind": "has_many",
            "model": model_ref,
            "local_key": local_key,
            "remote_key": remote_key,
            "cascade": tuple(cascade),
        }
        return cls

    @classmethod
    def many_to_many(cls, relation_name, target_model, through, local_key=None, remote_key=None, target_key="id", cascade=()):
        target_table = getattr(target_model, "__tablename__", target_model)
        model_ref = target_model if not isinstance(target_model, str) else target_model
        local_key = local_key or f"{cls.__tablename__.rstrip('s')}_id"
        remote_key = remote_key or f"{str(target_table).rstrip('s')}_id"

        def relation_getter(self):
            if relation_name in self.__dict__:
                return self.__dict__[relation_name]
            related_model = cls._resolve_related_model(model_ref)
            sql = (
                f"SELECT t.* FROM {related_model.__tablename__} t "
                f"JOIN {through} r ON t.{target_key} = r.{remote_key} "
                f"WHERE r.{local_key} = ?"
            )
            related = related_model.raw_sql(sql, params=[self._pk_value()]).all()
            if not related:
                collection = RelationCollection(self, cls._relation_configs[relation_name], [])
                self.__dict__[relation_name] = collection
                return collection
            collection = RelationCollection(self, cls._relation_configs[relation_name], list(related))
            self.__dict__[relation_name] = collection
            return collection

        def relation_setter(self, value):
            self.__dict__[relation_name] = value

        setattr(cls, relation_name, property(relation_getter, relation_setter))
        cls._relations[relation_name] = target_table
        cls._relation_configs[relation_name] = {
            "kind": "many_to_many",
            "model": model_ref,
            "through": through,
            "local_key": local_key,
            "remote_key": remote_key,
            "target_key": target_key,
            "cascade": tuple(cascade),
        }
        return cls

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
        execute_sql(cls._connection, sql)
        cprint(f"🧪 Tabela temporária criada: {cls.__tablename__}", "cyan")


