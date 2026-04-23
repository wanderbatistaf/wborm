"""Modern WBORM + WBJDBC integration examples."""


def connect():
    from wbjdbc import connect_optimized
    from wborm import register_global_connection

    conn = connect_optimized(
        db_type="informix-sqli",
        host="localhost",
        port=9088,
        database="stores_demo",
        user="informix",
        password="in4mix",
        server="informix",
    )
    register_global_connection(conn)
    return conn


def basic_usage():
    from wborm import generate_model

    Customer = generate_model("customer")
    rows = Customer.filter(customer_num__gt=100).order_by("customer_num").limit(5).all()
    for row in rows:
        print(row.to_dict())


def session_and_locking():
    from wborm import generate_model

    Customer = generate_model("customer")
    session = Customer.session()

    with session.transaction():
        customer = session.query(Customer).filter(customer_num=101).lock_for_update().first()
        if customer:
            customer.fname = f"{customer.fname}"


def migrations_example(conn):
    from wborm import Migration, Migrator

    migrations = [
        Migration(
            version="001",
            description="create wborm_demo_note",
            up_sql=[
                "CREATE TABLE wborm_demo_note (id INT PRIMARY KEY, customer_num INT, note VARCHAR(255))"
            ],
            down_sql=[
                "DROP TABLE wborm_demo_note"
            ],
        )
    ]

    migrator = Migrator(conn)
    migrator.apply(migrations)


def bulk_operations():
    from wborm import Model, Field

    class DemoNote(Model):
        __tablename__ = "wborm_demo_note"
        id = Field(int, primary_key=True)
        customer_num = Field(int, nullable=False)
        note = Field(str)

    DemoNote._connection = connect()

    DemoNote.bulk_add(
        [
            DemoNote(id=1, customer_num=101, note="primeira nota"),
            DemoNote(id=2, customer_num=102, note="segunda nota"),
        ],
        confirm=True,
    )


if __name__ == "__main__":
    connection = connect()
    basic_usage()
    session_and_locking()
    migrations_example(connection)
