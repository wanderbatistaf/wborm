"""
Type Mapping Utilities

This module provides utilities for mapping database column types to Python types.
It supports both integer type codes (Informix bitmask) and string type names.

Extracted from utils.py to reduce coupling and improve testability.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Type, Union, Any


def map_coltype_to_python(coltype: Union[int, str]) -> Type[Union[int, float, str, bool, bytes, date, datetime, Decimal]]:
    """
    Mapeia o tipo da coluna (int ou string) para um tipo Python.

    - Se receber um int (tipo Informix original), usa o bitmask.
    - Se receber uma string (como 'VARCHAR'), faz o mapeamento direto.

    Args:
        coltype: int ou str - Tipo da coluna do banco de dados

    Returns:
        type: Tipo Python correspondente

    Examples:
        >>> map_coltype_to_python(2)  # INTEGER
        <class 'int'>
        >>> map_coltype_to_python("VARCHAR")
        <class 'str'>
        >>> map_coltype_to_python("SERIAL")
        <class 'int'>
    """
    if isinstance(coltype, int):
        # Informix type codes (bitmask)
        type_code = coltype & 0xFF
        if type_code in (1, 2, 6, 17, 18):  # SMALLINT, INTEGER, SERIAL, INT8, SERIAL8
            return int
        if type_code in (3, 4):  # FLOAT, SMALLFLOAT
            return float
        if type_code in (5, 8):  # DECIMAL, MONEY
            return Decimal
        if type_code == 7:  # DATE
            return date
        if type_code == 10:  # DATETIME
            return datetime
        if type_code in (11, 43):  # BYTE, BLOB
            return bytes
        if type_code == 44:  # BOOLEAN
            return bool
        return str
    else:
        # String type names
        type_str = str(coltype).strip().upper()
        if type_str in ("SMALLINT", "INTEGER", "INT8", "SERIAL", "SERIAL8"):
            return int
        if type_str in ("FLOAT", "SMALLFLOAT", "REAL"):
            return float
        if type_str in ("DECIMAL", "MONEY", "NUMERIC"):
            return Decimal
        if type_str == "DATE":
            return date
        if type_str in ("DATETIME", "TIMESTAMP"):
            return datetime
        if type_str in ("BOOLEAN",):
            return bool
        if type_str in ("BYTE", "BLOB", "RAW", "BINARY", "VARBINARY"):
            return bytes
        return str


# Type mapping reference for documentation
INFORMIX_TYPE_MAP = {
    # Integer types
    "SMALLINT": int,
    "INTEGER": int,
    "INT8": int,
    "SERIAL": int,
    "SERIAL8": int,

    # Float types
    "FLOAT": float,
    "SMALLFLOAT": float,
    "REAL": float,
    "DECIMAL": Decimal,
    "MONEY": Decimal,

    # String types
    "CHAR": str,
    "VARCHAR": str,
    "LVARCHAR": str,
    "NCHAR": str,
    "NVARCHAR": str,
    "TEXT": str,
    "CLOB": str,

    # Date/Time types
    "DATE": date,
    "DATETIME": datetime,
    "INTERVAL": str,

    # Boolean
    "BOOLEAN": bool,

    # Binary types
    "BYTE": bytes,
    "BLOB": bytes,
}


def get_python_type_name(py_type: Type[Any]) -> str:
    """
    Retorna o nome do tipo Python como string para geração de stubs.

    Args:
        py_type: Tipo Python (int, str, float, etc.)

    Returns:
        Nome do tipo como string (ex: 'int', 'str', 'Any')

    Examples:
        >>> get_python_type_name(int)
        'int'
        >>> get_python_type_name(str)
        'str'
        >>> get_python_type_name(type(None))
        'Any'
    """
    if hasattr(py_type, "__name__"):
        return py_type.__name__
    return "Any"
