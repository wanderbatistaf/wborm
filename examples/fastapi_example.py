"""Minimal FastAPI integration example for WBORM."""

from fastapi import Depends, FastAPI, Query, Request

from wborm import (
    apply_api_filters,
    create_read_schema,
    create_write_schema,
    create_session_dependency,
    generate_model,
    paginate_query,
    register_exception_handlers,
    register_observability_middleware,
    register_global_connection,
)


def create_app(connection):
    register_global_connection(connection)
    get_session = create_session_dependency(connection)
    Customer = generate_model("customer", inject_globals=False)
    CustomerRead = create_read_schema(Customer, exclude={"password"})
    CustomerPatch = create_write_schema(Customer, exclude={"customer_num", "password"}, partial=True)

    app = FastAPI()
    register_exception_handlers(app)
    register_observability_middleware(app)

    @app.get("/customers/{customer_id}", response_model=CustomerRead | dict)
    def get_customer(customer_id: int, session=Depends(get_session)):
        customer = session.query(Customer).filter(customer_num=customer_id).first()
        return customer.to_dict() if customer else {"detail": "not found"}

    @app.get("/customers")
    def list_customers(
        request: Request,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
        city: str | None = None,
        session=Depends(get_session),
    ):
        qs = session.query(Customer)
        qs = apply_api_filters(qs, {"city": city}, allowed_fields={"city"})
        return paginate_query(qs.order_by("customer_num"), page=page, page_size=page_size, envelope=True, request=request)

    @app.patch("/customers/{customer_id}", response_model=CustomerRead | dict)
    def patch_customer(customer_id: int, payload: CustomerPatch, session=Depends(get_session)):
        session.begin()
        customer = session.query(Customer).filter(customer_num=customer_id).first()
        if not customer:
            session.rollback()
            return {"detail": "not found"}
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(customer, key, value)
        session.commit()
        return customer.to_dict()

    return app
