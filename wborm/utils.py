import sys, os
import time
from wborm.fields import Field
from wborm.core import Model
from wborm.introspect import introspect_table, get_foreign_keys
from wborm.model_cache import try_load_model_from_disk, save_model_to_disk, generate_model_stub, get_or_create_key
from wborm.registry import _model_registry, _model_cache
from cryptography.fernet import Fernet
import pickle

def map_coltype_to_python(coltype):
    type_code = coltype & 0xFF
    if type_code in (0, 5): return int
    if type_code in (1, 13): return str
    if type_code in (2, 3): return float
    return str

def generate_model(table_name, conn, refresh=False, inject_globals=True):
    import sys
    import inspect
    key = (table_name, id(conn))

    if not refresh and key in _model_cache:
        return _model_cache[key]

    if not refresh:
        model = try_load_model_from_disk(table_name, conn)
        if model:
            _model_cache[key] = model
            if inject_globals:
                caller_globals = inspect.stack()[1].frame.f_globals
                var_name = table_name
                caller_globals[var_name] = model
            return model

    metadata = introspect_table(table_name, conn)
    class_attrs = {"__tablename__": table_name}

    for col in metadata:
        py_type = map_coltype_to_python(col["type"])
        class_attrs[str(col["name"])] = Field(py_type)

    class_name = table_name.capitalize()
    class_attrs["__module__"] = "wborm.core"
    model_class = type(class_name, (Model,), class_attrs)
    model_class._connection = conn

    sys.modules["wborm.core"].__dict__[class_name] = model_class

    try:
        fks = get_foreign_keys(table_name, conn)
        for fk in fks:
            from_tbl = fk["from_table"]
            to_tbl = fk["to_table"]
            from_col = fk["from_column"]
            to_col = fk["to_column"]

            if from_tbl == table_name:
                rel_name = from_col.replace("_id", "")
                def relation_getter(self, t=to_tbl, fk_col=from_col, pk_col=to_col):
                    Target = generate_model(t, conn)
                    return Target.filter(**{pk_col: getattr(self, fk_col)}).first()
                setattr(model_class, rel_name, property(relation_getter))
                model_class._relations[rel_name] = to_tbl

            if to_tbl == table_name:
                reverse_name = from_tbl.lower() + "s"
                def reverse_getter(self, t=from_tbl, fk_col=from_col, pk_col=to_col):
                    Source = generate_model(t, conn)
                    return Source.filter(**{fk_col: getattr(self, pk_col)}).all()
                setattr(model_class, reverse_name, property(reverse_getter))
                model_class._relations[reverse_name] = from_tbl
    except Exception as e:
        print(f"     ⚠️ Ignorando FKs para '{table_name}': {e}")

    _model_cache[key] = model_class
    save_model_to_disk(table_name, model_class)

    model_class._from_cache = False

    if inject_globals:
        caller_globals = inspect.stack()[1].frame.f_globals
        var_name = table_name
        caller_globals[var_name] = model_class

    _model_registry[table_name] = model_class
    generate_model_stub()

    return model_class

def get_model(table_name, conn):
    return generate_model(table_name, conn)

def generate_all_models(conn, include_views=False, inject_globals=True, target_globals=None, verbose=True):
    from wborm.utils import generate_model
    import traceback

    tipo = "'T'" if not include_views else "'T','V'"
    query = f"SELECT TRIM(tabname) AS tabname FROM systables WHERE tabtype IN ({tipo}) AND tabid > 99"
    results = conn.execute_query(query)

    total = len(results)
    if verbose:
        print(f"\n🔄 Gerando modelos para {total} tabelas...")

    models = {}
    for i, row in enumerate(results, 1):
        table = str(row["tabname"])
        if verbose:
            print(f"  [{i}/{total}] ⏳ {table}")
        try:
            model = generate_model(table, conn)
            models[table] = model
        except Exception as e:
            print(f"  ⚠️ Erro ao gerar modelo para '{table}': {e}")

    _model_registry.update(models)

    if inject_globals:
        target = target_globals or globals()
        for name, model in models.items():
            target[name] = model

    if verbose:
        print(f"\n✅ Modelos gerados com sucesso: {len(models)} de {total} possíveis.\n")

    return models

def list_models(conn=None):
    if conn:
        models = generate_all_models(conn, inject_globals=True, verbose=True)
        if not models:
            print("⚠ Nenhum modelo encontrado no banco.")
            return

        print(f"\n📡 Modelos carregados do servidor ({len(models)}):\n")
        for name in sorted(models):
            print(f" - {name}")
    else:
        model_dir = ".wbmodels"
        if not os.path.isdir(model_dir):
            print("⚠ Diretório de modelos não encontrado.")
            return

        models = []
        key = get_or_create_key()
        for file in os.listdir(model_dir):
            if file.endswith(".wbm"):
                path = os.path.join(model_dir, file)
                try:
                    with open(path, "rb") as f:
                        encrypted = f.read()
                    data = Fernet(key).decrypt(encrypted)
                    cached = pickle.loads(data)
                    models.append(file.replace(".wbm", ""))
                except Exception as e:
                    print(f"⚠ Erro ao ler cache '{file}': {e}")

        if not models:
            print("⚠ Nenhum modelo válido no cache.")
        else:
            print(f"\n Modelos encontrados em cache ({len(models)}):\n")
            for name in sorted(models):
                print(f" - {name}")

def get_model_by_name(name):
    model = _model_registry.get(name)
    if not model:
        raise ValueError(f"Modelo '{name}' não encontrado. Use generate_all_models(conn) primeiro.")
    return model

def create_temp_table_from_queryset(queryset, temp_name, with_log=False):
    sql = queryset._build_query()
    log_clause = "WITH LOG" if with_log else "WITH NO LOG"
    create_sql = f"CREATE TEMP TABLE {temp_name} AS ({sql}) {log_clause}"

    # print(f"📦 Criando temp table: {create_sql}")
    queryset.conn.execute(create_sql)

    from wborm.utils import generate_model
    return generate_model(temp_name, queryset.conn, inject_globals=True)
