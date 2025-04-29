# wborm/bootstrap.py
import os
import pickle
import inspect
from cryptography.fernet import Fernet
from wborm.registry import _model_registry, _model_cache
from wborm.core import Model
from wborm.fields import Field
from wborm.model_cache import get_or_create_key


def auto_load_cached_models(conn, inject_globals=True, verbose=False, target_globals=None):
    """
    Carrega automaticamente todos os modelos salvos localmente (.wbmodels/*.wbm)
    e os injeta no registry e no escopo global, se desejado.

    Uso:
        from wborm.bootstrap import auto_load_cached_models
        auto_load_cached_models(conn)
    """
    key = get_or_create_key()
    folder = ".wbmodels"
    if not os.path.isdir(folder):
        return

    caller_globals = target_globals or inspect.stack()[1].frame.f_globals

    for file in os.listdir(folder):
        if not file.endswith(".wbm"):
            continue

        try:
            table = file.replace(".wbm", "")
            path = os.path.join(folder, file)
            with open(path, "rb") as f:
                encrypted = f.read()
            data = Fernet(key).decrypt(encrypted)
            cached = pickle.loads(data)

            field_map = {}
            for name, f in cached["fields"].items():
                field_map[name] = Field(
                    f.field_type,
                    primary_key=f.primary_key,
                    nullable=f.nullable
                )

            class_attrs = {
                "__tablename__": table,
                "_relations": cached["relations"],
                **field_map
            }

            model_cls = type(table.capitalize(), (Model,), class_attrs)
            model_cls.__annotations__ = {
                name: field.field_type for name, field in field_map.items()
            }
            model_cls._connection = conn
            model_cls._from_cache = True

            _model_registry[table] = model_cls
            _model_cache[(table, id(conn))] = model_cls

            if inject_globals:
                caller_globals[table] = model_cls

            if verbose:
                print(f" Modelo carregado: {table}")

        except Exception as e:
            print(f"  ❌ Erro ao carregar modelo '{file}': {e}")

    if inject_globals:
        for i in range(1, 11):
            alias_name = f"t{i}"
            if alias_name not in caller_globals:
                from wborm.query import _Alias
                caller_globals[alias_name] = _Alias(alias_name)

    if verbose:
        print("\n Modelos carregados automaticamente com sucesso.\n")
