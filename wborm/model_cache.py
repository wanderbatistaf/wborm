import os, sys
import pickle
from cryptography.fernet import Fernet
from wborm.registry import _model_registry, _model_cache
from wborm.core import Model, ModelMeta
from wborm.fields import Field

CACHE_DIR = ".wbmodels"
KEY_PATH = ".wbormkey"

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

# Salva apenas os atributos da classe (não uma instância dela)
def save_model_to_disk(table_name, model_cls):
    key = get_or_create_key()
    from wborm.fields import Field

    # 🔁 Salva apenas os dados serializáveis de cada Field
    simplified_fields = {}
    for name, field in model_cls._fields.items():
        simplified_fields[name] = Field(
            field.field_type,
            primary_key=field.primary_key,
            nullable=field.nullable
        )

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

        field_map = {}
        for name, f in cached["fields"].items():
            field_map[name] = Field(
                f.field_type,
                primary_key=f.primary_key,
                nullable=f.nullable
            )

        class_attrs = {
            "__tablename__": table_name,
            "_relations": cached["relations"],
        }
        class_attrs.update(field_map)  # adiciona os Field() visíveis para a metaclass

        model_cls = ModelMeta(table_name.capitalize(), (Model,), class_attrs)
        model_cls._connection = conn
        model_cls.__module__ = "wborm.core"

        sys.modules["wborm.core"].__dict__[table_name.capitalize()] = model_cls
        _model_registry[table_name] = model_cls
        _model_cache[(table_name, id(conn))] = model_cls

        # print(f"📦 Modelo '{table_name}' carregado do cache com sucesso.")
        model_cls._from_cache = True  # <- define flag visível no show()

        return model_cls

    except Exception as e:
        print(f"     ⚠️ Falha ao carregar modelo '{table_name}' do cache: {e}")
        return None


def generate_model_stub(output_path=".wbmodels/models.pyi"):
    if not _model_registry:
        print("⚠ Nenhum modelo carregado. Use generate_model ou generate_all_models(conn) primeiro.")
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
            nullable = "Optional[" + py_type + "]" if field.nullable else py_type
            lines.append(f"    {fname}: {nullable}")
        lines.append("")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f" Stub gerado: {output_path}")




