from datetime import datetime
import re

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
    """
        Representa uma coluna como expressão utilizável em filtros.

        Forma de uso:
        -------------
        queryset.filter(col("status") == "ATIVO")

        Gera cláusulas como:
        --------------------
        WHERE status = 'ATIVO'
        """
    return Expression(name)

def date(field):
    """
        Converte um campo para o tipo DATE na cláusula SQL.

        Forma de uso:
        -------------
        queryset.filter(date("data_criacao") >= "2024-01-01")

        Gera cláusulas como:
        --------------------
        WHERE DATE(data_criacao) >= '2024-01-01'
        """
    return Expression(f"DATE({field})")

def raw(expr):
    """
        Insere uma expressão SQL bruta no filtro ou seleção.

        Forma de uso:
        -------------
        queryset.select(raw("COUNT(*) AS total"))

        Gera cláusulas como:
        --------------------
        SELECT COUNT(*) AS total
        """
    return Expression(expr)

def now():
    """
        Representa a data/hora atual do banco de dados.

        Forma de uso:
        -------------
        queryset.filter(date("data_atualizacao") >= now())

        Gera cláusulas como:
        --------------------
        WHERE DATE(data_atualizacao) >= CURRENT
        """
    return Expression("CURRENT")

from datetime import datetime

def format_informix_datetime(value):
    from datetime import datetime

    if isinstance(value, datetime):
        return f"DATETIME({value.strftime('%Y-%m-%d %H:%M:%S')}) YEAR TO SECOND"
    if isinstance(value, str):
        if re.match(r"^t\d+\.\w+$", value):  # trata como coluna válida
            return value
        try:
            dt = datetime.fromisoformat(value)
            if dt.time() == datetime.min.time():
                return f"'{dt.date().isoformat()}'"
            return f"DATETIME({dt.strftime('%Y-%m-%d %H:%M:%S')}) YEAR TO SECOND"
        except ValueError:
            return f"'{value}'"
    return str(value)





__all__ = ["Expression", "col", "date", "raw", "now", "format_informix_datetime"]

