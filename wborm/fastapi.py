"""FastAPI integration helpers for WBORM."""

from contextlib import contextmanager
from time import perf_counter
from uuid import uuid4

from wborm.exceptions import ORMConcurrencyError, ORMDatabaseError, ORMValidationError
from wborm.session import Session


def create_session_dependency(connection, auto_commit: bool = False):
    """Return a FastAPI dependency that yields a WBORM Session per request."""

    def get_session():
        session = Session(connection)
        try:
            yield session
            if auto_commit:
                session.commit()
        except Exception:
            session.rollback()
            raise

    return get_session


@contextmanager
def session_scope(connection):
    """Framework-agnostic session scope helper."""
    session = Session(connection)
    session.begin()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise


def register_exception_handlers(app):
    """Register default WBORM exception handlers on a FastAPI app."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(ORMValidationError)
    async def handle_validation_error(request: Request, exc: ORMValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": str(exc),
                "type": "validation_error",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(ORMConcurrencyError)
    async def handle_concurrency_error(request: Request, exc: ORMConcurrencyError):
        return JSONResponse(
            status_code=409,
            content={
                "detail": str(exc),
                "type": "concurrency_error",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(ORMDatabaseError)
    async def handle_database_error(request: Request, exc: ORMDatabaseError):
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "type": "database_error",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    return app


def register_observability_middleware(
    app,
    request_id_header: str = "X-Request-ID",
    process_time_header: str = "X-Process-Time",
):
    """Attach request id and timing headers to every FastAPI response."""
    from fastapi import Request

    @app.middleware("http")
    async def wborm_request_context(request: Request, call_next):
        request_id = request.headers.get(request_id_header) or uuid4().hex
        request.state.request_id = request_id
        started_at = perf_counter()
        response = await call_next(request)
        response.headers[request_id_header] = request_id
        response.headers[process_time_header] = f"{perf_counter() - started_at:.6f}"
        return response

    return app


def api_response(data=None, meta=None, message: str | None = None, request=None, request_id: str | None = None):
    """Return a consistent API envelope payload."""
    resolved_request_id = request_id or getattr(getattr(request, "state", None), "request_id", None)
    payload = {
        "success": True,
        "data": data,
        "meta": meta or {},
    }
    if message is not None:
        payload["message"] = message
    if resolved_request_id is not None:
        payload["request_id"] = resolved_request_id
    return payload


def apply_api_filters(queryset, filters, allowed_fields):
    """Apply only whitelisted filters from API input."""
    if not filters:
        return queryset

    normalized = {}
    for key, value in filters.items():
        base_field = key.split("__", 1)[0]
        if base_field in allowed_fields and value is not None:
            normalized[key] = value
    if not normalized:
        return queryset
    return queryset.filter(**normalized)


def paginate_query(
    queryset,
    page: int = 1,
    page_size: int = 50,
    max_page_size: int = 100,
    envelope: bool = False,
    request=None,
):
    """Return API-friendly pagination payload."""
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), max_page_size)
    result = queryset.paginate(page=safe_page, page_size=safe_page_size)
    payload = {
        "items": [item.to_dict() for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "total": result.total,
        "pages": result.pages,
        "has_next": result.has_next,
        "has_prev": result.has_prev,
    }
    if not envelope:
        return payload
    return api_response(
        data=payload["items"],
        meta={key: value for key, value in payload.items() if key != "items"},
        request=request,
    )
