"""Simple schema migration support for WBORM."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Optional, Sequence
from wborm.connection_utils import execute_sql, begin_transaction, commit_transaction, rollback_transaction


@dataclass
class Migration:
    version: str
    description: str = ""
    up_sql: Sequence[str] = field(default_factory=list)
    down_sql: Sequence[str] = field(default_factory=list)
    up_callable: Optional[Callable] = None
    down_callable: Optional[Callable] = None

    def apply(self, connection):
        for sql in self.up_sql:
            execute_sql(connection, sql)
        if self.up_callable:
            self.up_callable(connection)

    def rollback(self, connection):
        for sql in self.down_sql:
            execute_sql(connection, sql)
        if self.down_callable:
            self.down_callable(connection)


def python_type_to_sql(field):
    if field.field_type == int:
        return "INT"
    if field.field_type == float:
        return "FLOAT"
    if field.field_type == Decimal:
        precision = field.precision or 18
        scale = field.scale if field.scale is not None else 2
        return f"DECIMAL({precision},{scale})"
    if field.field_type == bool:
        return "BOOLEAN"
    if field.field_type == date:
        return "DATE"
    if field.field_type == datetime:
        return "DATETIME YEAR TO SECOND"
    if field.field_type == bytes:
        return "BLOB"
    if field.max_length:
        return f"VARCHAR({field.max_length})"
    return "VARCHAR(255)"


class Migrator:
    TABLE_NAME = "wborm_migrations"

    def __init__(self, connection):
        self.connection = connection
        self._ensure_schema_table()

    def _ensure_schema_table(self):
        try:
            rows = self.connection.execute_query(f"SELECT version FROM {self.TABLE_NAME}")
            if isinstance(rows, list):
                return
        except Exception:
            pass
        try:
            execute_sql(
                self.connection,
                f"CREATE TABLE {self.TABLE_NAME} (version VARCHAR(255) PRIMARY KEY, description VARCHAR(255), applied_at DATETIME YEAR TO SECOND)"
            )
        except Exception:
            pass

    def applied_versions(self):
        try:
            rows = self.connection.execute_query(f"SELECT version FROM {self.TABLE_NAME}")
        except Exception:
            return set()
        return {str(row["version"]).strip() for row in rows}

    def apply(self, migrations: Sequence[Migration]):
        applied = self.applied_versions()
        pending = [migration for migration in migrations if migration.version not in applied]
        if not pending:
            return []

        begin_transaction(self.connection)
        try:
            for migration in pending:
                migration.apply(self.connection)
                execute_sql(
                    self.connection,
                    "INSERT INTO wborm_migrations (version, description, applied_at) VALUES (?, ?, CURRENT)",
                    params=[migration.version, migration.description],
                )
            commit_transaction(self.connection)
            return pending
        except Exception:
            rollback_transaction(self.connection)
            raise

    def rollback_last(self, migrations: Sequence[Migration]):
        applied = self.applied_versions()
        ordered = [migration for migration in migrations if migration.version in applied]
        if not ordered:
            return None
        migration = ordered[-1]
        begin_transaction(self.connection)
        try:
            migration.rollback(self.connection)
            execute_sql(
                self.connection,
                f"DELETE FROM {self.TABLE_NAME} WHERE version = ?",
                params=[migration.version],
            )
            commit_transaction(self.connection)
            return migration
        except Exception:
            rollback_transaction(self.connection)
            raise


def create_model_table_sql(model):
    parts = []
    pk_columns = []
    for name, field in model._fields.items():
        sql_type = python_type_to_sql(field)
        nullable = "" if field.nullable else "NOT NULL"
        if field.primary_key:
            pk_columns.append(name)
        parts.append(f"{name} {sql_type} {nullable}".strip())
    if len(pk_columns) == 1:
        parts = [
            f"{part} PRIMARY KEY" if part.startswith(f"{pk_columns[0]} ") else part
            for part in parts
        ]
    elif len(pk_columns) > 1:
        parts.append(f"PRIMARY KEY ({', '.join(pk_columns)})")
    return f"CREATE TABLE {model.__tablename__} ({', '.join(parts)})"


def add_column_sql(table_name, column_name, sql_type, nullable=True):
    nullable_clause = "" if nullable else " NOT NULL"
    return f"ALTER TABLE {table_name} ADD {column_name} {sql_type}{nullable_clause}"


def modify_column_sql(table_name, column_name, sql_type, nullable=True):
    nullable_clause = "" if nullable else " NOT NULL"
    return f"ALTER TABLE {table_name} MODIFY ({column_name} {sql_type}{nullable_clause})"


def drop_table_sql(table_name):
    return f"DROP TABLE {table_name}"


def drop_column_sql(table_name, column_name):
    return f"ALTER TABLE {table_name} DROP {column_name}"


def rename_column_sql(table_name, old_name, new_name):
    return f"RENAME COLUMN {table_name}.{old_name} TO {new_name}"


def create_index_sql(table_name, index_name, columns, unique=False):
    unique_clause = "UNIQUE " if unique else ""
    column_list = ", ".join(columns)
    return f"CREATE {unique_clause}INDEX {index_name} ON {table_name} ({column_list})"


def drop_index_sql(index_name):
    return f"DROP INDEX {index_name}"


def add_foreign_key_sql(table_name, constraint_name, column_name, ref_table, ref_column="id"):
    return (
        f"ALTER TABLE {table_name} ADD CONSTRAINT FOREIGN KEY ({column_name}) "
        f"REFERENCES {ref_table} ({ref_column}) CONSTRAINT {constraint_name}"
    )


def diff_model_schema(model, current_columns):
    migrations = []
    current_map = {str(column["name"]).strip(): column for column in current_columns}
    desired_map = model._fields
    added = []
    removed = []

    for name, field in desired_map.items():
        if name not in current_map:
            added.append((name, field))
        else:
            current_type = str(current_map[name].get("type", "")).strip().upper()
            desired_type = python_type_to_sql(field).strip().upper()
            if current_type and current_type != desired_type:
                migrations.append(
                    Migration(
                        version=f"auto_modify_{model.__tablename__}_{name}",
                        description=f"modify column {name} on {model.__tablename__}",
                        up_sql=[modify_column_sql(model.__tablename__, name, python_type_to_sql(field), nullable=field.nullable)],
                    )
                )

    for name in current_map:
        if name not in desired_map:
            removed.append(name)

    if len(added) == 1 and len(removed) == 1:
        added_name, _ = added[0]
        removed_name = removed[0]
        migrations.append(
            RenameColumnMigration.rename(
                f"auto_rename_{model.__tablename__}_{removed_name}_to_{added_name}",
                model.__tablename__,
                removed_name,
                added_name,
            )
        )
        return migrations

    for name, field in added:
        migrations.append(
            AddColumnMigration.from_field(f"auto_add_{model.__tablename__}_{name}", model.__tablename__, name, field)
        )

    for name in removed:
        migrations.append(
            DropColumnMigration.for_column(f"auto_drop_{model.__tablename__}_{name}", model.__tablename__, name)
        )
    return migrations


class CreateTableMigration(Migration):
    @classmethod
    def from_model(cls, version, model, description=None):
        return cls(
            version=version,
            description=description or f"create table {model.__tablename__}",
            up_sql=[create_model_table_sql(model)],
            down_sql=[drop_table_sql(model.__tablename__)],
        )


class DropTableMigration(Migration):
    @classmethod
    def from_model(cls, version, model, description=None):
        return cls(
            version=version,
            description=description or f"drop table {model.__tablename__}",
            up_sql=[drop_table_sql(model.__tablename__)],
        )


class AddColumnMigration(Migration):
    @classmethod
    def from_field(cls, version, table_name, column_name, field, description=None):
        return cls(
            version=version,
            description=description or f"add column {column_name} to {table_name}",
            up_sql=[add_column_sql(table_name, column_name, python_type_to_sql(field), nullable=field.nullable)],
            down_sql=[drop_column_sql(table_name, column_name)],
        )


class CreateIndexMigration(Migration):
    @classmethod
    def for_columns(cls, version, table_name, index_name, columns, unique=False, description=None):
        return cls(
            version=version,
            description=description or f"create index {index_name} on {table_name}",
            up_sql=[create_index_sql(table_name, index_name, columns, unique=unique)],
            down_sql=[drop_index_sql(index_name)],
        )


class DropColumnMigration(Migration):
    @classmethod
    def for_column(cls, version, table_name, column_name, description=None):
        return cls(
            version=version,
            description=description or f"drop column {column_name} from {table_name}",
            up_sql=[drop_column_sql(table_name, column_name)],
        )


class RenameColumnMigration(Migration):
    @classmethod
    def rename(cls, version, table_name, old_name, new_name, description=None):
        return cls(
            version=version,
            description=description or f"rename column {old_name} to {new_name} on {table_name}",
            up_sql=[rename_column_sql(table_name, old_name, new_name)],
            down_sql=[rename_column_sql(table_name, new_name, old_name)],
        )


class AddForeignKeyMigration(Migration):
    @classmethod
    def between(cls, version, table_name, constraint_name, column_name, ref_table, ref_column="id", description=None):
        return cls(
            version=version,
            description=description or f"add foreign key {constraint_name} on {table_name}",
            up_sql=[add_foreign_key_sql(table_name, constraint_name, column_name, ref_table, ref_column)],
        )
