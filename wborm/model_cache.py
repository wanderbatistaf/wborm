import os, sys
import pickle
from cryptography.fernet import Fernet
from wborm.registry import _model_registry, _model_cache
from wborm.core import Model, ModelMeta
from wborm.fields import Field

CACHE_DIR = ".wbmodels"
KEY_PATH = ".wbormkey"
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STUB_FILE = os.path.join(ROOT_DIR, "models.pyi")

os.makedirs(CACHE_DIR, exist_ok=True)

def get_or_create_key():
    if os.path.exists(KEY_PATH):
        return open(KEY_PATH, "rb").read()
    key = Fernet.generate_key()
    with open(KEY_PATH, "wb") as f:
        f.write(key)
    return key

def model_cache_path(table_name):
    return os.path.join(CACHE_DIR, f"{table_name}.wbm")

def save_model_to_disk(table_name, model_cls):
    key = get_or_create_key()
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

    encrypted = Fernet(key).encrypt(pickle.dumps(data))
    with open(model_cache_path(table_name), "wb") as f:
        f.write(encrypted)

def try_load_model_from_disk(table_name, conn):
    path = model_cache_path(table_name)
    if not os.path.exists(path):
        return None

    try:
        key = get_or_create_key()
        with open(path, "rb") as f:
            encrypted = f.read()
        data = Fernet(key).decrypt(encrypted)
        cached = pickle.loads(data)

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

# Para gerar/atualizar o stub incrementalmente (por tabela)
def update_model_stub_file(path: str, model_name: str, fields: dict):
    from typing import Optional

    header = [
        "from wborm.core import Model",
        "from typing import Optional",
        "",
    ]

    target_class = f"class {model_name}(Model):"
    lines = [target_class]

    if not fields:
        lines.append("    pass")
    else:
        for fname, field in fields.items():
            py_type = field.field_type.__name__ if hasattr(field.field_type, "__name__") else "Any"
            nullable = f"Optional[{py_type}]" if getattr(field, "nullable", True) else py_type
            lines.append(f"    {fname}: {nullable}")
    lines.append("")

    new_block = "\n".join(lines)

    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(header + [new_block]))
        print(f"✅ Stub criado com {model_name}: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    class_pattern = rf"(class {model_name}\(Model\):\n(?:    .*\n)*?)\n"
    if re.search(class_pattern, content):
        updated = re.sub(class_pattern, f"{new_block}\n", content, flags=re.MULTILINE)
    else:
        updated = content.rstrip() + "\n\n" + new_block + "\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"✅ Stub atualizado: {model_name} → {path}")

# Para gerar todos os modelos do zero (usado no generate_all_models)
def generate_model_stub(output_path=STUB_FILE):
    from wborm.core import Model

    if not _model_registry:
        print("⚠ Nenhum modelo carregado.")
        return

    lines = [
        "from wborm.core import Model",
        "from typing import Optional",
        "",
    ]

    for name, model_cls in sorted(_model_registry.items()):
        if not issubclass(model_cls, Model):
            continue
        lines.append(f"class {model_cls.__name__}(Model):")

        fields = getattr(model_cls, "_fields", {})
        if not fields:
            lines.append("    pass\n")
            continue

        for fname, field in fields.items():
            py_type = field.field_type.__name__ if hasattr(field.field_type, "__name__") else "Any"
            nullable = f"Optional[{py_type}]" if getattr(field, "nullable", True) else py_type
            lines.append(f"    {fname}: {nullable}")
        lines.append("")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    # print(f"✅ Stub completo gerado: {output_path}")

def generate_type_aliases_stub(path="globals.pyi"):
    from wborm.registry import _model_registry
    lines = [
        "from models import *",
        "",
    ]
    for name, model_cls in sorted(_model_registry.items()):
        class_name = model_cls.__name__
        lines.append(f"{name}: {class_name}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    # print(f"✅ Aliases gerados para type-checking: {path}")
