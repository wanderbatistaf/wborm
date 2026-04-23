"""
Database Dialects

Provides database-specific SQL generation and type mapping for different
database systems (Informix, DB2, Oracle).

Features:
- Automatic dialect detection
- Database-specific type mapping
- SQL syntax variations
- Query optimization hints per database
"""

from typing import Optional, Type
from .base import BaseDialect
from .informix import InformixDialect
from .db2 import DB2Dialect
from .oracle import OracleDialect


# Registry of available dialects
_DIALECTS = {
    "informix": InformixDialect,
    "informix-sqli": InformixDialect,
    "db2": DB2Dialect,
    "oracle": OracleDialect,
}


def get_dialect(db_type: str) -> BaseDialect:
    """
    Get dialect instance for database type.

    Args:
        db_type: Database type string (e.g., "informix", "db2", "oracle")

    Returns:
        Dialect instance

    Raises:
        ValueError: If database type not supported

    Examples:
        >>> dialect = get_dialect("informix")
        >>> dialect.quote_identifier("table_name")
        '"table_name"'
    """
    db_type_lower = db_type.lower()

    if db_type_lower not in _DIALECTS:
        raise ValueError(
            f"Unsupported database type: {db_type}. "
            f"Supported types: {', '.join(_DIALECTS.keys())}"
        )

    return _DIALECTS[db_type_lower]()


def detect_dialect(connection) -> BaseDialect:
    """
    Detect database dialect from connection.

    Args:
        connection: Database connection object

    Returns:
        Appropriate dialect instance

    Examples:
        >>> conn = connect_to_db(db_type="db2", ...)
        >>> dialect = detect_dialect(conn)
        >>> isinstance(dialect, DB2Dialect)
        True
    """
    # Try to get database type from connection
    if hasattr(connection, 'db_type'):
        db_type = getattr(connection, "db_type", None)
        if isinstance(db_type, str) and db_type:
            return get_dialect(db_type)

    # Try to detect from connection string or metadata
    if hasattr(connection, '_conn_str'):
        conn_str = getattr(connection, "_conn_str", None)
        if isinstance(conn_str, str):
            conn_str = conn_str.lower()
            if 'informix' in conn_str:
                return InformixDialect()
            elif 'db2' in conn_str:
                return DB2Dialect()
            elif 'oracle' in conn_str:
                return OracleDialect()

    # Default to Informix (original WBORM behavior)
    return InformixDialect()


def register_dialect(name: str, dialect_class: Type[BaseDialect]) -> None:
    """
    Register a custom dialect.

    Args:
        name: Dialect name
        dialect_class: Dialect class

    Examples:
        >>> class MyDialect(BaseDialect):
        >>>     pass
        >>> register_dialect("mydb", MyDialect)
    """
    _DIALECTS[name.lower()] = dialect_class


__all__ = [
    "BaseDialect",
    "InformixDialect",
    "DB2Dialect",
    "OracleDialect",
    "get_dialect",
    "detect_dialect",
    "register_dialect",
]
