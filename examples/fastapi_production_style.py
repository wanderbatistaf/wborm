"""Production-style FastAPI example using wborm + wbjdbc."""

from decimal import Decimal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request

from wborm import (
    apply_api_filters,
    create_read_schema,
    create_session_dependency,
    create_write_schema,
    paginate_query,
    register_exception_handlers,
    register_observability_middleware,
)
from wborm.core import Model
from wborm.fields import Field


class Customer(Model):
    __tablename__ = "customer"
    customer_num = Field(int, primary_key=True)
    name = Field(str, nullable=False, max_length=120)
    city = Field(str, max_length=80)
    credit_limit = Field(Decimal, precision=12, scale=2)


CustomerRead = create_read_schema(Customer)
CustomerWrite = create_write_schema(Customer, exclude={"customer_num"})
CustomerPatch = create_write_schema(Customer, exclude={"customer_num"}, partial=True)


class CustomerRepository:
    def __init__(self, session):
        self.session = session

    def base_query(self):
        return self.session.query(Customer).order_by("customer_num")

    def get(self, customer_num: int):
        return self.session.query(Customer).filter(customer_num=customer_num).first()


class CustomerService:
    def __init__(self, session):
        self.session = session
        self.repo = CustomerRepository(session)

    def create(self, customer_num: int, payload: CustomerWrite):
        entity = Customer(customer_num=customer_num, **payload.model_dump())
        self.session.begin()
        self.session.add(entity)
        self.session.commit()
        return entity

    def patch(self, customer_num: int, payload: CustomerPatch):
        self.session.begin()
        entity = self.repo.get(customer_num)
        if not entity:
            self.session.rollback()
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(entity, key, value)
        self.session.commit()
        return entity

    def delete(self, customer_num: int):
        self.session.begin()
        entity = self.repo.get(customer_num)
        if not entity:
            self.session.rollback()
            return False
        self.session.delete(entity)
        self.session.commit()
        return True


def create_app(connection):
    Customer._connection = connection
    get_session = create_session_dependency(connection)

    app = FastAPI()
    register_exception_handlers(app)
    register_observability_middleware(app)

    router = APIRouter(prefix="/customers", tags=["customers"])

    @router.get("/{customer_num}", response_model=CustomerRead)
    def get_customer(customer_num: int, session=Depends(get_session)):
        entity = CustomerRepository(session).get(customer_num)
        if not entity:
            raise HTTPException(status_code=404, detail="customer not found")
        return entity.to_dict()

    @router.get("")
    def list_customers(
        request: Request,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
        city: str | None = None,
        session=Depends(get_session),
    ):
        qs = CustomerRepository(session).base_query()
        qs = apply_api_filters(qs, {"city": city}, allowed_fields={"city"})
        return paginate_query(qs, page=page, page_size=page_size, envelope=True, request=request)

    @router.post("/{customer_num}", response_model=CustomerRead, status_code=201)
    def create_customer(customer_num: int, payload: CustomerWrite, session=Depends(get_session)):
        return CustomerService(session).create(customer_num, payload).to_dict()

    @router.patch("/{customer_num}", response_model=CustomerRead)
    def patch_customer(customer_num: int, payload: CustomerPatch, session=Depends(get_session)):
        entity = CustomerService(session).patch(customer_num, payload)
        if not entity:
            raise HTTPException(status_code=404, detail="customer not found")
        return entity.to_dict()

    @router.delete("/{customer_num}", status_code=204)
    def delete_customer(customer_num: int, session=Depends(get_session)):
        deleted = CustomerService(session).delete(customer_num)
        if not deleted:
            raise HTTPException(status_code=404, detail="customer not found")
        return None

    app.include_router(router)
    return app
