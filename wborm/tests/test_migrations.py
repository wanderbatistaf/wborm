from wborm.core import Model
from wborm.fields import Field
from datetime import date, datetime
from decimal import Decimal
from wborm.migrations import (
    Migration,
    Migrator,
    CreateTableMigration,
    AddColumnMigration,
    DropColumnMigration,
    RenameColumnMigration,
    AddForeignKeyMigration,
    CreateIndexMigration,
    create_model_table_sql,
    add_column_sql,
    modify_column_sql,
    drop_column_sql,
    rename_column_sql,
    create_index_sql,
    add_foreign_key_sql,
    diff_model_schema,
)


class DummyConnection:
    def __init__(self):
        self.executed = []
        self.rows = []

    def execute(self, sql):
        self.executed.append(sql)

    def execute_query(self, sql):
        self.executed.append(sql)
        if "SELECT version FROM wborm_migrations" in sql:
            return list(self.rows)
        return []


class Cliente(Model):
    __tablename__ = "clientes"
    id = Field(int, primary_key=True)
    nome = Field(str, nullable=False)


def test_create_model_table_sql():
    sql = create_model_table_sql(Cliente)
    assert sql.startswith("CREATE TABLE clientes")
    assert "id INT" in sql


def test_add_column_sql():
    sql = add_column_sql("clientes", "email", "VARCHAR(255)", nullable=False)
    assert sql == "ALTER TABLE clientes ADD email VARCHAR(255) NOT NULL"


def test_migrator_apply_records_version():
    conn = DummyConnection()
    migrator = Migrator(conn)
    migration = Migration(version="001", description="init", up_sql=["CREATE TABLE teste (id INT)"])
    applied = migrator.apply([migration])
    assert applied[0].version == "001"
    assert any("INSERT INTO wborm_migrations" in sql for sql in conn.executed)


def test_create_table_migration_from_model():
    migration = CreateTableMigration.from_model("001", Cliente)
    assert migration.up_sql[0].startswith("CREATE TABLE clientes")
    assert migration.down_sql[0] == "DROP TABLE clientes"


def test_add_column_migration_from_field():
    migration = AddColumnMigration.from_field("002", "clientes", "email", Field(str, max_length=120, nullable=False))
    assert migration.up_sql[0] == "ALTER TABLE clientes ADD email VARCHAR(120) NOT NULL"


def test_create_index_sql():
    sql = create_index_sql("clientes", "idx_clientes_nome", ["nome"], unique=True)
    assert sql == "CREATE UNIQUE INDEX idx_clientes_nome ON clientes (nome)"


def test_create_index_migration():
    migration = CreateIndexMigration.for_columns("003", "clientes", "idx_clientes_nome", ["nome"])
    assert migration.up_sql[0] == "CREATE INDEX idx_clientes_nome ON clientes (nome)"


def test_drop_column_sql():
    assert drop_column_sql("clientes", "email") == "ALTER TABLE clientes DROP email"


def test_rename_column_sql():
    assert rename_column_sql("clientes", "nome", "nome_completo") == "RENAME COLUMN clientes.nome TO nome_completo"


def test_add_foreign_key_sql():
    assert (
        add_foreign_key_sql("pedidos", "fk_pedidos_cliente", "cliente_id", "clientes", "id")
        == "ALTER TABLE pedidos ADD CONSTRAINT FOREIGN KEY (cliente_id) REFERENCES clientes (id) CONSTRAINT fk_pedidos_cliente"
    )


def test_drop_column_migration():
    migration = DropColumnMigration.for_column("004", "clientes", "email")
    assert migration.up_sql[0] == "ALTER TABLE clientes DROP email"


def test_rename_column_migration():
    migration = RenameColumnMigration.rename("005", "clientes", "nome", "nome_completo")
    assert migration.up_sql[0] == "RENAME COLUMN clientes.nome TO nome_completo"
    assert migration.down_sql[0] == "RENAME COLUMN clientes.nome_completo TO nome"


def test_add_foreign_key_migration():
    migration = AddForeignKeyMigration.between("006", "pedidos", "fk_pedidos_cliente", "cliente_id", "clientes")
    assert "FOREIGN KEY (cliente_id)" in migration.up_sql[0]


def test_python_type_to_sql_supports_decimal_and_datetime():
    decimal_field = Field(Decimal, precision=12, scale=4)
    date_field = Field(date)
    datetime_field = Field(datetime)
    sql = create_model_table_sql(type("Tmp", (Model,), {
        "__tablename__": "tmp",
        "id": Field(int, primary_key=True),
        "valor": decimal_field,
        "emissao": date_field,
        "atualizado_em": datetime_field,
    }))
    assert "DECIMAL(12,4)" in sql
    assert "emissao DATE" in sql
    assert "atualizado_em DATETIME YEAR TO SECOND" in sql


def test_create_model_table_sql_supports_composite_primary_key():
    Composite = type("Composite", (Model,), {
        "__tablename__": "composite_table",
        "pedido_id": Field(int, primary_key=True),
        "produto_id": Field(int, primary_key=True),
    })
    sql = create_model_table_sql(Composite)
    assert "PRIMARY KEY (pedido_id, produto_id)" in sql


def test_diff_model_schema_generates_add_and_drop_migrations():
    current = [{"name": "id"}, {"name": "legacy"}, {"name": "obsolete"}]
    changes = diff_model_schema(Cliente, current)
    assert any(m.version == "auto_add_clientes_nome" for m in changes)
    assert any(m.version == "auto_drop_clientes_legacy" for m in changes)


def test_modify_column_sql():
    assert modify_column_sql("clientes", "nome", "VARCHAR(200)", nullable=False) == "ALTER TABLE clientes MODIFY (nome VARCHAR(200) NOT NULL)"


def test_diff_model_schema_detects_rename():
    current = [{"name": "id"}, {"name": "apelido"}]
    Renamed = type("Renamed", (Model,), {
        "__tablename__": "clientes",
        "id": Field(int, primary_key=True),
        "nome": Field(str, nullable=False),
    })
    changes = diff_model_schema(Renamed, current)
    assert any(m.version == "auto_rename_clientes_apelido_to_nome" for m in changes)


def test_diff_model_schema_detects_type_change():
    current = [{"name": "id", "type": "INTEGER"}, {"name": "nome", "type": "VARCHAR(50)"}]
    Changed = type("Changed", (Model,), {
        "__tablename__": "clientes",
        "id": Field(int, primary_key=True),
        "nome": Field(str, max_length=120, nullable=False),
    })
    changes = diff_model_schema(Changed, current)
    assert any(m.version == "auto_modify_clientes_nome" for m in changes)
