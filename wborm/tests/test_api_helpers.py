from fastapi import FastAPI
from fastapi.testclient import TestClient

from wborm.core import Model
from wborm.fields import Field
from wborm.fastapi import api_response, apply_api_filters, paginate_query, register_exception_handlers, register_observability_middleware
from wborm.connection_utils import _normalize_db_exception
from wborm.exceptions import ORMConcurrencyError
from wborm.pydantic import create_read_schema, create_write_schema, dump_entity


class DummyConnection:
    def __init__(self):
        self.last_query = None
        self.last_params = None

    def execute_query(self, sql, params=None):
        self.last_query = sql
        self.last_params = params
        if "COUNT(*)" in sql:
            return [{"count": 2}]
        return [{"id": 1, "nome": "Ana"}, {"id": 2, "nome": "Bia"}]


class Cliente(Model):
    __tablename__ = "clientes"
    id = Field(int, primary_key=True)
    nome = Field(str, nullable=False, max_length=120)
    cidade = Field(str)


def test_pydantic_schemas_from_model():
    read_schema = create_read_schema(Cliente)
    write_schema = create_write_schema(Cliente)
    patch_schema = create_write_schema(Cliente, partial=True)
    assert "id" in read_schema.model_fields
    assert "nome" in write_schema.model_fields
    assert write_schema.model_fields["nome"].metadata
    assert patch_schema.model_fields["nome"].default is None


def test_partial_write_schema_accepts_sparse_payload_and_keeps_constraints():
    patch_schema = create_write_schema(Cliente, partial=True)
    payload = patch_schema(nome="Ana")
    assert payload.model_dump(exclude_unset=True) == {"nome": "Ana"}

    try:
        patch_schema(nome="X" * 121)
    except Exception as exc:
        assert "at most 120 characters" in str(exc)
    else:
        raise AssertionError("Expected max_length validation for partial schema")


def test_dump_entity_with_schema():
    schema = create_read_schema(Cliente)
    entity = Cliente(id=1, nome="Ana", cidade="SP")
    dumped = dump_entity(entity, schema)
    assert dumped["nome"] == "Ana"


def test_dump_entity_normalizes_non_python_string_values():
    class JavaStringLike:
        def __str__(self):
            return "Ana"

    schema = create_read_schema(Cliente)
    entity = Cliente(id=1, nome="Ana", cidade="SP")
    entity.nome = JavaStringLike()
    dumped = dump_entity(entity, schema)
    assert dumped["nome"] == "Ana"


def test_apply_api_filters_whitelists_fields():
    conn = DummyConnection()
    Cliente._connection = conn
    qs = apply_api_filters(Cliente.filter(), {"cidade": "SP", "hack": "x"}, allowed_fields={"cidade"})
    qs.all()
    assert "cidade = ?" in conn.last_query
    assert conn.last_params == ["SP"]


def test_paginate_query_payload():
    conn = DummyConnection()
    Cliente._connection = conn
    payload = paginate_query(Cliente.filter(), page=1, page_size=1)
    assert payload["page"] == 1
    assert "items" in payload


def test_paginate_query_envelope_payload():
    conn = DummyConnection()
    Cliente._connection = conn
    payload = paginate_query(Cliente.filter(), page=1, page_size=1, envelope=True)
    assert payload["success"] is True
    assert isinstance(payload["data"], list)
    assert payload["meta"]["page"] == 1


def test_api_response_includes_request_id():
    class DummyState:
        request_id = "req-123"

    class DummyRequest:
        state = DummyState()

    payload = api_response(data={"ok": True}, request=DummyRequest())
    assert payload["request_id"] == "req-123"
    assert payload["data"]["ok"] is True


def test_register_exception_handlers():
    app = FastAPI()
    register_exception_handlers(app)
    assert len(app.exception_handlers) >= 3


def test_observability_middleware_adds_headers():
    app = FastAPI()
    register_observability_middleware(app)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/ping", headers={"X-Request-ID": "abc-1"})
    assert response.headers["X-Request-ID"] == "abc-1"
    assert "X-Process-Time" in response.headers


def test_unique_constraint_maps_to_concurrency_error():
    exc = Exception("java.sql.SQLIntegrityConstraintViolationException: Unique constraint violated")
    normalized = _normalize_db_exception(exc)
    assert isinstance(normalized, ORMConcurrencyError)
