"""End-to-end integration check for the local Informix Docker container.

Recommended runtime:
    Python 3.12 or 3.13 with `wbjdbc` installed.
"""

import importlib.util
import os
import sys


def require_wbjdbc():
    if importlib.util.find_spec("wbjdbc") is None:
        raise RuntimeError(
            "wbjdbc não está instalado neste Python. "
            "Use Python 3.12/3.13 e instale `wbjdbc` antes de rodar este script."
        )


def main():
    require_wbjdbc()

    from wbjdbc import connect_optimized
    from wborm import CreateTableMigration, Migrator, register_global_connection, generate_model
    from wborm.core import Model
    from wborm.fields import Field

    host = os.getenv("WBORM_IFX_HOST", "localhost")
    port = int(os.getenv("WBORM_IFX_PORT", "9088"))
    database = os.getenv("WBORM_IFX_DB", "stores_demo")
    user = os.getenv("WBORM_IFX_USER", "informix")
    password = os.getenv("WBORM_IFX_PASS", "in4mix")
    server = os.getenv("WBORM_IFX_SERVER", "informix")

    conn = connect_optimized(
        db_type="informix-sqli",
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        server=server,
    )
    register_global_connection(conn)

    class DemoSchema(Model):
        __tablename__ = "wborm_integration_demo"
        id = Field(int, primary_key=True)
        nome = Field(str, max_length=100)
        versao = Field(int)

    class UserSchema(Model):
        __tablename__ = "wborm_integration_user"
        id = Field(int, primary_key=True)
        nome = Field(str, max_length=100)

    class RoleSchema(Model):
        __tablename__ = "wborm_integration_role"
        id = Field(int, primary_key=True)
        nome = Field(str, max_length=100)

    class UserRoleSchema(Model):
        __tablename__ = "wborm_integration_user_role"
        user_id = Field(int, nullable=False)
        role_id = Field(int, nullable=False)

    migrations = [
        CreateTableMigration.from_model("ifx_001", DemoSchema),
        CreateTableMigration.from_model("ifx_002", UserSchema),
        CreateTableMigration.from_model("ifx_003", RoleSchema),
        CreateTableMigration.from_model("ifx_004", UserRoleSchema),
    ]
    Migrator(conn).apply(migrations)

    Demo = generate_model("wborm_integration_demo", refresh=True, inject_globals=False)
    User = generate_model("wborm_integration_user", refresh=True, inject_globals=False)
    Role = generate_model("wborm_integration_role", refresh=True, inject_globals=False)
    UserRole = generate_model("wborm_integration_user_role", refresh=True, inject_globals=False)
    User.many_to_many("roles", Role, through="wborm_integration_user_role", local_key="user_id", remote_key="role_id")

    Demo.bulk_delete([1, 2, 3], confirm=True)
    UserRole.bulk_delete([1], confirm=True, where_field="user_id")
    User.bulk_delete([1], confirm=True)
    Role.bulk_delete([1, 2], confirm=True)
    Demo.bulk_add(
        [
            Demo(id=1, nome="alpha", versao=1),
            Demo(id=2, nome="beta", versao=1),
            Demo(id=3, nome="gamma", versao=2),
        ],
        confirm=True,
    )

    filtered = Demo.filter(versao__gte=1).order_by("id").all()
    print(f"Filtered rows: {len(filtered)}")

    row = Demo.filter(id=2).first()
    row.nome = "beta-updated"
    row.update(confirm=True, id=2)

    updated = Demo.filter(id=2).first()
    print(f"Updated row: {updated.to_dict()}")

    page = Demo.order_by("id").paginate(page=1, page_size=2)
    print(f"Paginated items: {len(page.items)} / total {page.total}")

    Demo.begin()
    rows = Demo.filter(id=1).lock_for_update().all()
    Demo.rollback()
    print(f"Locked rows loaded: {len(rows)}")
    for row in rows:
        print(row.to_dict())

    Demo(id=3).delete(confirm=True, id=3)
    remaining = Demo.count()
    print(f"Remaining rows after delete: {remaining}")

    User.bulk_add([User(id=1, nome="Alice")], confirm=True)
    Role.bulk_add([Role(id=1, nome="admin"), Role(id=2, nome="ops")], confirm=True)

    user = User.filter(id=1).first()
    role_admin = Role.filter(id=1).first()
    role_ops = Role.filter(id=2).first()
    user.roles.add(role_admin, role_ops)
    print(f"Many-to-many roles after add: {[role.nome for role in user.roles]}")

    preloaded_user = User.preload("roles").filter(id=1).first()
    print(f"Preloaded roles: {[role.nome for role in preloaded_user.roles]}")

    user.roles.remove(role_ops)
    refreshed_user = User.filter(id=1).first()
    print(f"Roles after remove: {[role.nome for role in refreshed_user.roles]}")

    session = Demo.session()
    tracked = session.query(Demo).filter(id=2).first()
    updated.nome = "beta-session-refresh"
    updated.update(confirm=True, id=2)
    session.expire(tracked, fields=["nome"])
    print(f"Expired/refresh nome: {tracked.nome}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
