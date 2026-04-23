import os
import sys
from wborm.registry import _model_registry, _model_cache
from wborm.core import Model, ModelMeta
from wborm.fields import Field
from wborm.file_utils import model_cache_path
from wborm.cache_manager import encrypt_data, decrypt_data

def save_model_to_disk(table_name, model_cls):
    simplified_fields = {
        name: Field(
            field.field_type,
            primary_key=field.primary_key,
            nullable=field.nullable
        )
        for name, field in model_cls._fields.items()
    }

    data = {
        "fields": simplified_fields,
        "relations": model_cls._relations,
    }

    encrypted = encrypt_data(data)
    with open(model_cache_path(table_name), "wb") as f:
        f.write(encrypted)

def try_load_model_from_disk(table_name, conn):
    path = model_cache_path(table_name)
    if not os.path.exists(path):
        return None

    try:
        with open(path, "rb") as f:
            encrypted = f.read()
        cached = decrypt_data(encrypted)

        field_map = {
            name: Field(
                f.field_type,
                primary_key=f.primary_key,
                nullable=f.nullable
            ) for name, f in cached["fields"].items()
        }

        class_attrs = {
            "__tablename__": table_name,
            "_relations": cached["relations"],
        }
        class_attrs.update(field_map)

        model_cls = ModelMeta(table_name.capitalize(), (Model,), class_attrs)
        model_cls._connection = conn
        model_cls.__module__ = "wborm.core"
        model_cls._from_cache = True

        sys.modules["wborm.core"].__dict__[table_name.capitalize()] = model_cls
        _model_registry[table_name] = model_cls
        _model_cache[(table_name, id(conn))] = model_cls

        return model_cls

    except Exception as e:
        print(f"⚠️ Falha ao carregar modelo '{table_name}': {e}")
        return None

# Re-export stub generation functions from stub_generator module
from wborm.stub_generator import (
    update_model_stub_file,
    generate_model_stub,
    generate_type_aliases_stub
)
