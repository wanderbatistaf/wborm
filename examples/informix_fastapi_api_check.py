"""FastAPI integration check against the local Informix container."""

import importlib.util
import os
import sys


def require_dependencies():
    missing = [name for name in ("wbjdbc", "fastapi", "pydantic") if importlib.util.find_spec(name) is None]
    if missing:
        raise RuntimeError(f"Dependências ausentes para o check de API: {', '.join(missing)}")


def main():
    require_dependencies()

    from fastapi import Depends, FastAPI, Query, Request
    from fastapi.testclient import TestClient
    from wbjdbc import connect_optimized
    from wborm import (
        CreateTableMigration,
        Migrator,
        apply_api_filters,
        create_read_schema,
        create_session_dependency,
        create_write_schema,
        generate_model,
        paginate_query,
        register_exception_handlers,
        register_observability_middleware,
        register_global_connection,
    )
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

    class ApiDemoSchema(Model):
        __tablename__ = "wborm_fastapi_demo"
        id = Field(int, primary_key=True)
        nome = Field(str, max_length=100)
        cidade = Field(str, max_length=80)

    Migrator(conn).apply([CreateTableMigration.from_model("ifx_api_001", ApiDemoSchema)])
    ApiDemo = generate_model("wborm_fastapi_demo", refresh=True, inject_globals=False)
    ApiDemo.bulk_delete(list(range(1, 21)), confirm=True)
    ApiDemo.bulk_add(
        [
            ApiDemo(id=1, nome="Ana", cidade="SP"),
            ApiDemo(id=2, nome="Bia", cidade="RJ"),
            ApiDemo(id=3, nome="Caio", cidade="SP"),
        ],
        confirm=True,
    )

    app = FastAPI()
    register_exception_handlers(app)
    register_observability_middleware(app)
    get_session = create_session_dependency(conn)
    ApiDemoRead = create_read_schema(ApiDemo)
    ApiDemoWrite = create_write_schema(ApiDemo, exclude={"id"})
    ApiDemoPatch = create_write_schema(ApiDemo, exclude={"id"}, partial=True)

    @app.get("/demo/{item_id}", response_model=ApiDemoRead | dict)
    def get_item(item_id: int, session=Depends(get_session)):
        item = session.query(ApiDemo).filter(id=item_id).first()
        return item.to_dict() if item else {"detail": "not found"}

    @app.get("/demo")
    def list_items(
        request: Request,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=2, ge=1, le=10),
        cidade: str | None = None,
        session=Depends(get_session),
    ):
        qs = session.query(ApiDemo).order_by("id")
        qs = apply_api_filters(qs, {"cidade": cidade}, allowed_fields={"cidade"})
        return paginate_query(qs, page=page, page_size=page_size, envelope=True, request=request)

    @app.post("/demo/{item_id}", response_model=ApiDemoRead, status_code=201)
    def create_item(item_id: int, payload: ApiDemoWrite, session=Depends(get_session)):
        session.begin()
        entity = ApiDemo(id=item_id, **payload.model_dump())
        session.add(entity)
        session.commit()
        return entity.to_dict()

    @app.put("/demo/{item_id}", response_model=ApiDemoRead | dict)
    def update_item(item_id: int, payload: ApiDemoWrite, session=Depends(get_session)):
        session.begin()
        entity = session.query(ApiDemo).filter(id=item_id).first()
        if not entity:
            session.rollback()
            return {"detail": "not found"}
        for key, value in payload.model_dump().items():
            setattr(entity, key, value)
        session.commit()
        return entity.to_dict()

    @app.delete("/demo/{item_id}")
    def delete_item(item_id: int, session=Depends(get_session)):
        session.begin()
        entity = session.query(ApiDemo).filter(id=item_id).first()
        if not entity:
            session.rollback()
            return {"detail": "not found"}
        session.delete(entity)
        session.commit()
        return {"deleted": item_id}

    @app.patch("/demo/{item_id}", response_model=ApiDemoRead | dict)
    def patch_item(item_id: int, payload: ApiDemoPatch, session=Depends(get_session)):
        session.begin()
        entity = session.query(ApiDemo).filter(id=item_id).first()
        if not entity:
            session.rollback()
            return {"detail": "not found"}
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(entity, key, value)
        session.commit()
        return entity.to_dict()

    client = TestClient(app)
    one = client.get("/demo/1")
    listing = client.get("/demo", params={"cidade": "SP", "page": 1, "page_size": 2})
    created = client.post("/demo/10", json={"nome": "Dora", "cidade": "BA"})
    conflict = client.post("/demo/10", json={"nome": "Dora-dup", "cidade": "BA"})
    updated = client.put("/demo/2", json={"nome": "Bia-2", "cidade": "MG"})
    patched = client.patch("/demo/1", json={"cidade": "PR"})
    deleted = client.delete("/demo/3")
    listing_after = client.get("/demo", params={"page": 1, "page_size": 10})
    invalid = client.post("/demo/11", json={"nome": "X" * 101, "cidade": "BA"})
    invalid_patch = client.patch("/demo/2", json={"nome": "Y" * 101})

    print("GET /demo/1 ->", one.status_code, one.json())
    print("GET /demo/1 headers ->", {"X-Request-ID": one.headers.get("X-Request-ID"), "X-Process-Time": one.headers.get("X-Process-Time")})
    print("GET /demo?cidade=SP ->", listing.status_code, listing.json())
    print("POST /demo/10 ->", created.status_code, created.json())
    print("POST /demo/10 duplicate ->", conflict.status_code, conflict.json())
    print("PUT /demo/2 ->", updated.status_code, updated.json())
    print("PATCH /demo/1 ->", patched.status_code, patched.json())
    print("DELETE /demo/3 ->", deleted.status_code, deleted.json())
    print("POST /demo/11 invalid ->", invalid.status_code, invalid.json())
    print("PATCH /demo/2 invalid ->", invalid_patch.status_code, invalid_patch.json())
    print("GET /demo ->", listing_after.status_code, listing_after.json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
