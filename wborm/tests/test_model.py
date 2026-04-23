# tests/test_model.py
import pytest
from datetime import date, datetime
from decimal import Decimal
from wborm.core import Model
from wborm.fields import Field

# Simulador de conexão para testes
class DummyConnection:
    def __init__(self):
        self.last_query = None
        self.fail = False
        self.executed = []
        self.batch_calls = []
        self.last_params = None
        self.param_calls = []

    def execute(self, sql, params=None):
        self.last_query = sql
        self.last_params = params
        self.executed.append(sql)
        self.param_calls.append((sql, params))
        if self.fail:
            raise Exception("Erro simulado")

    def execute_query(self, sql, params=None):
        self.last_query = sql
        self.last_params = params
        self.executed.append(sql)
        self.param_calls.append((sql, params))
        return [{"id": 1, "nome": "Teste"}]

    def rollback(self):
        self.last_query = "ROLLBACK WORK"

    def execute_batch(self, sql, params):
        self.last_query = sql
        self.batch_calls.append((sql, params))


class Cliente(Model):
    __tablename__ = "clientes"
    id = Field(int, primary_key=True)
    nome = Field(str, nullable=False)
    idade = Field(int)


@pytest.fixture
def conn():
    return DummyConnection()


def test_add_sucesso(conn):
    Cliente._connection = conn
    c = Cliente(nome="Ana")
    c.add(confirm=True)
    assert any("INSERT INTO clientes" in sql for sql in conn.executed)


def test_add_falha_sem_confirmacao(conn):
    Cliente._connection = conn
    c = Cliente(nome="Ana")
    with pytest.raises(ValueError):
        c.add()


def test_update_sem_where_falha(conn):
    Cliente._connection = conn
    c = Cliente(nome="Ana")
    with pytest.raises(ValueError):
        c.update(confirm=True)


def test_delete_falha_sem_where(conn):
    Cliente._connection = conn
    c = Cliente()
    with pytest.raises(ValueError):
        c.delete(confirm=True)


def test_validate_falha_campo_obrigatorio(conn):
    Cliente._connection = conn
    c = Cliente()
    with pytest.raises(ValueError):
        c.validate()


def test_bulk_add_varios(conn):
    Cliente._connection = conn
    c1 = Cliente(nome="A")
    c2 = Cliente(nome="B")
    Cliente.bulk_add([c1, c2], confirm=True)
    assert "INSERT INTO clientes" in conn.batch_calls[0][0]
    assert conn.batch_calls


def test_filter_lookup_gt_builds_expected_sql(conn):
    Cliente._connection = conn
    Cliente.filter(idade__gt=18).all()
    assert "idade > ?" in conn.last_query
    assert conn.last_params == [18]


def test_insert_uses_parameterized_sql(conn):
    Cliente._connection = conn
    Cliente(nome="Ana").add(confirm=True)
    insert_sql = next(sql for sql in conn.executed if sql.startswith("INSERT INTO clientes"))
    assert "VALUES (?, ?, ?)" in insert_sql


def test_cache_key_differs_for_same_sql_with_different_params(conn):
    Cliente._connection = conn
    qs = Cliente.filter(id=1)
    sql, params = qs._build_query_data()
    key1 = qs._cache_key(sql, params)
    qs2 = Cliente.filter(id=2)
    sql2, params2 = qs2._build_query_data()
    key2 = qs2._cache_key(sql2, params2)
    assert key1 != key2


def test_hooks_are_called_on_save(conn):
    class AuditCliente(Cliente):
        before_insert_called = False
        after_insert_called = False
        before_save_called = False
        after_save_called = False

        def before_insert(self):
            type(self).before_insert_called = True

        def after_insert(self):
            type(self).after_insert_called = True

        def before_save(self):
            type(self).before_save_called = True

        def after_save(self):
            type(self).after_save_called = True

    AuditCliente._connection = conn
    AuditCliente(nome="Ana").save(confirm=True)
    assert AuditCliente.before_insert_called is True
    assert AuditCliente.after_insert_called is True
    assert AuditCliente.before_save_called is True
    assert AuditCliente.after_save_called is True


def test_session_identity_map_reuses_instances(conn):
    Cliente._connection = conn
    session = Cliente.session()
    first = session.query(Cliente).filter(id=1).first()
    second = session.query(Cliente).filter(id=1).first()
    assert first is second


def test_session_tracks_dirty_objects(conn):
    Cliente._connection = conn
    session = Cliente.session()
    cliente = session.query(Cliente).filter(id=1).first()
    cliente.nome = "Atualizado"
    assert cliente in session.dirty


def test_loaded_instance_is_not_dirty_immediately(conn):
    Cliente._connection = conn
    session = Cliente.session()
    cliente = session.query(Cliente).filter(id=1).first()
    assert cliente not in session.dirty


def test_preload_populates_relation_without_n_plus_one(conn):
    class Pedido(Model):
        __tablename__ = "pedidos"
        id = Field(int, primary_key=True)
        cliente_id = Field(int)

    Cliente._connection = conn
    Pedido._connection = conn
    Cliente._relation_configs = {
        "pedidos": {
            "kind": "has_many",
            "model": "pedidos",
            "local_key": "id",
            "remote_key": "cliente_id",
        }
    }

    from wborm.registry import _model_registry
    _model_registry["pedidos"] = Pedido
    import wborm.utils
    original_generate_model = wborm.utils.generate_model
    wborm.utils.generate_model = lambda table_name, conn=None, inject_globals=False, target_globals=None: Pedido if table_name == "pedidos" else Cliente

    try:
        def fake_execute_query(sql):
            conn.last_query = sql
            conn.executed.append(sql)
            if "FROM clientes" in sql:
                return [{"id": 1, "nome": "Ana"}]
            if "FROM pedidos" in sql:
                return [{"id": 10, "cliente_id": 1}]
            return []

        conn.execute_query = fake_execute_query
        cliente = Cliente.preload("pedidos").first()
        assert len(cliente.pedidos) == 1
        assert cliente.pedidos[0].cliente_id == 1
    finally:
        wborm.utils.generate_model = original_generate_model


def test_bulk_update_uses_execute_batch(conn):
    Cliente._connection = conn
    c1 = Cliente(id=1, nome="A")
    c2 = Cliente(id=2, nome="B")
    Cliente.bulk_update([c1, c2], confirm=True)
    assert conn.batch_calls[0][0].startswith("UPDATE clientes SET")


def test_bulk_delete_uses_execute_batch(conn):
    Cliente._connection = conn
    Cliente.bulk_delete([1, 2], confirm=True)
    assert conn.batch_calls[0][0].startswith("DELETE FROM clientes")


def test_lock_for_update_appends_clause(conn):
    Cliente._connection = conn
    Cliente.filter(id=1).lock_for_update().all()
    assert conn.last_query.endswith("FOR UPDATE")


def test_many_to_many_relation_fetches_through_join_table(conn):
    class Role(Model):
        __tablename__ = "roles"
        id = Field(int, primary_key=True)
        nome = Field(str)

    class Usuario(Model):
        __tablename__ = "usuarios"
        id = Field(int, primary_key=True)
        nome = Field(str)

    Role._connection = conn
    Usuario._connection = conn
    Usuario.many_to_many("roles", Role, through="usuario_role", local_key="usuario_id", remote_key="role_id")

    def fake_execute_query(sql):
        conn.last_query = sql
        conn.executed.append(sql)
        if "FROM roles" in sql:
            return [{"id": 1, "nome": "admin"}]
        return []

    conn.execute_query = fake_execute_query
    usuario = Usuario(id=10, nome="Ana")
    roles = usuario.roles
    assert len(roles) == 1
    assert roles[0].nome == "admin"


def test_many_to_many_relation_collection_add_and_remove_are_parameterized(conn):
    class Role(Model):
        __tablename__ = "roles"
        id = Field(int, primary_key=True)
        nome = Field(str)

    class Usuario(Model):
        __tablename__ = "usuarios"
        id = Field(int, primary_key=True)
        nome = Field(str)

    Role._connection = conn
    Usuario._connection = conn
    Usuario.many_to_many("roles", Role, through="usuario_role", local_key="usuario_id", remote_key="role_id")

    def fake_execute_query(sql, params=None):
        conn.last_query = sql
        conn.last_params = params
        conn.executed.append(sql)
        if "SELECT role_id FROM usuario_role" in sql:
            return []
        return []

    conn.execute_query = fake_execute_query
    usuario = Usuario(id=10, nome="Ana")
    role = Role(id=1, nome="admin")
    usuario.roles.add(role)
    usuario.roles.remove(role)
    assert "INSERT INTO usuario_role (usuario_id, role_id) VALUES (?, ?)" in conn.executed
    assert "DELETE FROM usuario_role WHERE usuario_id = ? AND role_id = ?" in conn.executed


def test_session_refresh_and_expire_reload_fields(conn):
    Cliente._connection = conn
    session = Cliente.session()
    state = {"nome": "Teste"}

    def fake_execute_query(sql, params=None):
        conn.last_query = sql
        conn.last_params = params
        conn.executed.append(sql)
        return [{"id": 1, "nome": state["nome"]}]

    conn.execute_query = fake_execute_query
    cliente = session.query(Cliente).filter(id=1).first()
    state["nome"] = "Atualizado"
    session.expire(cliente, fields=["nome"])
    assert cliente.nome == "Atualizado"


def test_session_merge_updates_managed_instance(conn):
    Cliente._connection = conn
    session = Cliente.session()
    managed = Cliente(id=1, nome="Ana")
    session.attach(managed)
    merged = session.merge(Cliente(id=1, nome="Bia"))
    assert merged is managed
    assert managed.nome == "Bia"
    assert managed in session.dirty


def test_session_rollback_restores_dirty_values(conn):
    Cliente._connection = conn
    session = Cliente.session()
    cliente = Cliente(id=1, nome="Ana")
    session.attach(cliente)
    cliente.nome = "Bia"
    session.rollback()
    assert cliente.nome == "Ana"


def test_has_many_delete_cascade_deletes_children(conn):
    class Pedido(Model):
        __tablename__ = "pedidos"
        id = Field(int, primary_key=True)
        cliente_id = Field(int)

    class ClienteCascade(Model):
        __tablename__ = "clientes"
        id = Field(int, primary_key=True)
        nome = Field(str)

    Pedido._connection = conn
    ClienteCascade._connection = conn
    ClienteCascade.has_many("pedidos", Pedido, local_key="id", remote_key="cliente_id", cascade=("delete",))

    cliente = ClienteCascade(id=1, nome="Ana")
    pedido = Pedido(id=10, cliente_id=1)
    setattr(cliente, "pedidos", [pedido])
    cliente.delete(confirm=True, id=1)
    assert any(sql.startswith("DELETE FROM pedidos WHERE id = ?") for sql in conn.executed)


def test_bulk_delete_fallback_is_parameterized(conn):
    Cliente._connection = conn
    conn.__class__.__name__ = "OptimizedJDBCConnection"
    Cliente.bulk_delete([1], confirm=True)
    assert ("DELETE FROM clientes WHERE id = ?", [1]) in conn.param_calls


def test_from_row_normalizes_decimal_and_datetime_types(conn):
    class Fatura(Model):
        __tablename__ = "faturas"
        id = Field(int, primary_key=True)
        total = Field(Decimal, precision=12, scale=2)
        emissao = Field(date)
        atualizado_em = Field(datetime)

    row = {
        "id": "1",
        "total": "10.50",
        "emissao": "2026-04-09",
        "atualizado_em": "2026-04-09 13:00:00",
    }
    fatura = Fatura.from_row(row)
    assert fatura.total == Decimal("10.50")
    assert fatura.emissao == date(2026, 4, 9)
    assert fatura.atualizado_em == datetime(2026, 4, 9, 13, 0, 0)


def test_to_dict_serializes_decimal_and_datetime_types(conn):
    class Fatura(Model):
        __tablename__ = "faturas"
        id = Field(int, primary_key=True)
        total = Field(Decimal, precision=12, scale=2)
        emissao = Field(date)
        payload = Field(bytes)

    fatura = Fatura(id=1, total=Decimal("10.50"), emissao=date(2026, 4, 9), payload=b"abc")
    data = fatura.to_dict()
    assert data["total"] == "10.50"
    assert data["emissao"] == "2026-04-09"
    assert data["payload"] == "abc"


def test_identity_key_supports_composite_primary_key(conn):
    class ItemPedido(Model):
        __tablename__ = "itens_pedido"
        pedido_id = Field(int, primary_key=True)
        produto_id = Field(int, primary_key=True)
        quantidade = Field(int)

    item = ItemPedido(pedido_id=10, produto_id=20, quantidade=2)
    assert item._pk_value() == (10, 20)
    assert item._pk_filter_dict() == {"pedido_id": 10, "produto_id": 20}
    assert item.identity_key() == (ItemPedido, ("pedido_id", "produto_id"), (10, 20))


def test_session_identity_map_supports_composite_primary_key(conn):
    class ItemPedido(Model):
        __tablename__ = "itens_pedido"
        pedido_id = Field(int, primary_key=True)
        produto_id = Field(int, primary_key=True)
        quantidade = Field(int)

    ItemPedido._connection = conn
    session = ItemPedido.session()
    item = ItemPedido(pedido_id=10, produto_id=20, quantidade=2)
    session.attach(item)
    assert session.get(ItemPedido, (10, 20)) is item


def test_delete_orphan_removes_missing_loaded_children(conn):
    class Filho(Model):
        __tablename__ = "filhos"
        id = Field(int, primary_key=True)
        pai_id = Field(int)

    class Pai(Model):
        __tablename__ = "pais"
        id = Field(int, primary_key=True)
        nome = Field(str)

    Pai._connection = conn
    Filho._connection = conn
    Pai.has_many("filhos", Filho, local_key="id", remote_key="pai_id", cascade=("delete-orphan",))

    state = {"children": [{"id": 1, "pai_id": 1}, {"id": 2, "pai_id": 1}]}

    def fake_execute_query(sql, params=None):
        conn.last_query = sql
        conn.last_params = params
        conn.executed.append(sql)
        conn.param_calls.append((sql, params))
        if "FROM filhos" in sql:
            return list(state["children"])
        return [{"id": 1, "nome": "Pai"}]

    conn.execute_query = fake_execute_query
    pai = Pai(id=1, nome="Pai")
    pai.filhos = [Filho(id=1, pai_id=1)]
    pai.update(confirm=True, id=1)
    assert ("DELETE FROM filhos WHERE id = ?", [2]) in conn.param_calls


def test_bulk_delete_supports_composite_primary_key(conn):
    class ItemPedido(Model):
        __tablename__ = "itens_pedido"
        pedido_id = Field(int, primary_key=True)
        produto_id = Field(int, primary_key=True)
        quantidade = Field(int)

    ItemPedido._connection = conn
    ItemPedido.bulk_delete([(10, 20)], confirm=True)
    assert ("DELETE FROM itens_pedido WHERE pedido_id = ? AND produto_id = ?", [10, 20]) in conn.param_calls


def test_bulk_update_supports_composite_primary_key(conn):
    class ItemPedido(Model):
        __tablename__ = "itens_pedido"
        pedido_id = Field(int, primary_key=True)
        produto_id = Field(int, primary_key=True)
        quantidade = Field(int)

    ItemPedido._connection = conn
    item = ItemPedido(pedido_id=10, produto_id=20, quantidade=3)
    item._state = "clean"
    item._take_snapshot()
    item.quantidade = 4
    ItemPedido.bulk_update([item], confirm=True)
    assert ("UPDATE itens_pedido SET quantidade = ? WHERE pedido_id = ? AND produto_id = ?", [4, 10, 20]) in conn.param_calls
