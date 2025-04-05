from wborm.fields import Field
from wborm.core import Model
from wborm.introspect import introspect_table, get_foreign_keys

_model_cache = {}

def map_coltype_to_python(coltype):
    type_code = coltype & 0xFF
    if type_code in (0, 5): return int
    if type_code in (1, 13): return str
    if type_code in (2, 3): return float
    return str

def generate_model(table_name, conn):
    if (table_name, id(conn)) in _model_cache:
        return _model_cache[(table_name, id(conn))]

    metadata = introspect_table(table_name, conn)
    class_attrs = {"__tablename__": table_name}

    for col in metadata:
        py_type = map_coltype_to_python(col["type"])
        class_attrs[col["name"]] = Field(py_type)

    model_class = type(table_name.capitalize(), (Model,), class_attrs)
    model_class._connection = conn

    # relações automáticas via FK
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

    _model_cache[(table_name, id(conn))] = model_class
    return model_class

def get_model(table_name, conn):
    return generate_model(table_name, conn)