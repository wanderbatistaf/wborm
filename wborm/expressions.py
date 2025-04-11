from datetime import datetime

class Expression:
    def __init__(self, sql):
        self.sql = sql

    def __str__(self):
        return self.sql

    def __eq__(self, other):
        return f"{self.sql} = {format_informix_datetime(other)}"

    def __ne__(self, other):
        return f"{self.sql} <> {format_informix_datetime(other)}"

    def __gt__(self, other):
        return f"{self.sql} > {format_informix_datetime(other)}"

    def __lt__(self, other):
        return f"{self.sql} < {format_informix_datetime(other)}"

    def __ge__(self, other):
        return f"{self.sql} >= {format_informix_datetime(other)}"

    def __le__(self, other):
        return f"{self.sql} <= {format_informix_datetime(other)}"


def col(name):
    return Expression(name)

def date(field):
    return Expression(f"DATE({field})")

def raw(expr):
    return Expression(expr)

def now():
    return Expression("CURRENT")

from datetime import datetime

def format_informix_datetime(value):
    from datetime import datetime

    if isinstance(value, datetime):
        sql_val = f"DATETIME({value.strftime('%Y-%m-%d %H:%M:%S')}) YEAR TO SECOND"
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            sql_val = f"DATETIME({dt.strftime('%Y-%m-%d %H:%M:%S')}) YEAR TO SECOND"
        except ValueError:
            sql_val = f"'{value}'"  # fallback se for uma string literal
    else:
        sql_val = str(value)

    # print(f"📦 format_informix_datetime → {sql_val}")
    return sql_val




__all__ = ["Expression", "col", "date", "raw", "now", "format_informix_datetime"]

