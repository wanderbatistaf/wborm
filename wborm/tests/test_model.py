# tests/test_model.py
import pytest
from wborm.core import Model
from wborm.fields import Field

# Simulador de conexão para testes
class DummyConnection:
    def __init__(self):
        self.last_query = None
        self.fail = False

    def execute(self, sql):
        self.last_query = sql
        if self.fail:
            raise Exception("Erro simulado")

    def execute_query(self, sql):
        self.last_query = sql
        return [{"id": 1, "nome": "Teste"}]

    def rollback(self):
        self.last_query = "ROLLBACK WORK"


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
    assert "INSERT INTO clientes" in conn.last_query


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
    assert "INSERT INTO clientes" in conn.last_query
