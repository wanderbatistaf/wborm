"""
Informix Dialect

Informix-specific SQL generation and type mapping.

Supports Informix Dynamic Server (IDS) and Informix SE.
"""

from typing import Type, Union, Optional, List
from .base import BaseDialect


class InformixDialect(BaseDialect):
    """
    Dialect for IBM Informix databases.

    Implements Informix-specific SQL syntax and type mapping.
    """

    def __init__(self):
        """Initialize Informix dialect"""
        super().__init__()
        self.name = "informix"
        self.supports_limit_offset = True  # SKIP/FIRST
        self.supports_window_functions = True  # IDS 12.10+
        self.supports_cte = True  # Common Table Expressions
        self.limit_offset_position = "start"  # Informix uses SKIP/FIRST after SELECT

    def map_type_to_python(self, db_type: Union[int, str]) -> Type:
        """
        Map Informix type to Python type.

        Args:
            db_type: Informix type code or name

        Returns:
            Python type

        Examples:
            >>> dialect = InformixDialect()
            >>> dialect.map_type_to_python(0)
            <class 'int'>
        """
        # If integer type code
        if isinstance(db_type, int):
            type_code = db_type & 0xFF

            type_map = {
                0: str,      # CHAR
                1: int,      # SMALLINT
                2: int,      # INTEGER
                3: float,    # FLOAT
                4: float,    # SMALLFLOAT
                5: float,    # DECIMAL
                6: int,      # SERIAL
                7: str,      # DATE
                8: float,    # MONEY
                9: str,      # NULL
                10: str,     # DATETIME
                11: bytes,   # BYTE
                12: str,     # TEXT
                13: str,     # VARCHAR
                14: str,     # INTERVAL
                15: str,     # NCHAR
                16: str,     # NVARCHAR
                17: int,     # INT8
                18: int,     # SERIAL8
                19: str,     # SET
                20: str,     # MULTISET
                21: str,     # LIST
                22: str,     # ROW (unnamed)
                23: str,     # COLLECTION
                40: str,     # LVARCHAR
                41: bytes,   # BLOB
                43: bytes,   # CLOB
                52: int,     # BIGINT
                53: int,     # BIGSERIAL
            }

            return type_map.get(type_code, str)

        # If string type name
        if isinstance(db_type, str):
            type_str = str(db_type).upper()

            if type_str in ("SMALLINT", "INTEGER", "INT", "INT8", "BIGINT", "SERIAL", "SERIAL8", "BIGSERIAL"):
                return int
            elif type_str in ("FLOAT", "SMALLFLOAT", "DOUBLE", "REAL", "DECIMAL", "NUMERIC", "MONEY"):
                return float
            elif type_str in ("CHAR", "VARCHAR", "NCHAR", "NVARCHAR", "LVARCHAR", "TEXT", "CLOB"):
                return str
            elif type_str in ("DATE", "DATETIME", "INTERVAL"):
                return str
            elif type_str in ("BYTE", "BLOB"):
                return bytes
            elif type_str == "BOOLEAN":
                return bool

        return str

    def limit_offset_clause(self, limit: Optional[int], offset: Optional[int]) -> str:
        """
        Generate Informix SKIP/FIRST clause.

        Args:
            limit: Row limit
            offset: Row offset

        Returns:
            SQL clause

        Examples:
            >>> dialect = InformixDialect()
            >>> dialect.limit_offset_clause(10, 20)
            "SKIP 20 FIRST 10"
        """
        if limit is None:
            return ""

        parts = []
        if offset:
            parts.append(f"SKIP {offset}")
        parts.append(f"FIRST {limit}")

        return " ".join(parts)

    def get_optimizer_hints(self, query_type: str) -> str:
        """
        Get Informix optimizer hints.

        Args:
            query_type: Query type

        Returns:
            Optimizer hint

        Examples:
            >>> dialect = InformixDialect()
            >>> dialect.get_optimizer_hints("select")
            ""
        """
        # Informix supports optimizer directives like {+ INDEX(table index_name)}
        # But these are typically query-specific
        return ""

    def optimize_join(self, join_type: str, tables: List[str]) -> str:
        """
        Get Informix JOIN optimization hint.

        Args:
            join_type: JOIN type
            tables: Tables being joined

        Returns:
            Optimization hint

        Examples:
            >>> dialect = InformixDialect()
            >>> dialect.optimize_join("INNER", ["t1", "t2"])
            ""
        """
        # Informix can use {+ ORDERED} to force join order
        # But this is optional and query-specific
        return ""

    def get_table_list_query(self) -> str:
        """
        Get query to list Informix tables.

        Returns:
            SQL query
        """
        return """
            SELECT tabname AS table_name
            FROM systables
            WHERE tabtype = 'T'
            AND tabid >= 100
            ORDER BY tabname
        """

    def get_table_info_query(self, table_name: str) -> str:
        """
        Get query to retrieve Informix table column information.

        Args:
            table_name: Table name

        Returns:
            SQL query
        """
        return f"""
            SELECT c.colname AS column_name,
                   c.coltype AS data_type,
                   CASE WHEN MOD(c.coltype, 256) >= 256 THEN 'YES' ELSE 'NO' END AS is_nullable
            FROM syscolumns c
            JOIN systables t ON c.tabid = t.tabid
            WHERE t.tabname = '{table_name}'
            ORDER BY c.colno
        """

    def concat_function(self, *args: str) -> str:
        """
        Generate Informix CONCAT (uses || operator).

        Args:
            *args: Values to concatenate

        Returns:
            SQL expression

        Examples:
            >>> dialect = InformixDialect()
            >>> dialect.concat_function("col1", "'_'", "col2")
            "col1 || '_' || col2"
        """
        return " || ".join(args)

    def substring_function(self, string: str, start: int, length: Optional[int] = None) -> str:
        """
        Generate Informix SUBSTRING.

        Args:
            string: String expression
            start: Start position (1-indexed)
            length: Length (optional)

        Returns:
            SQL function call

        Examples:
            >>> dialect = InformixDialect()
            >>> dialect.substring_function("col", 1, 10)
            "SUBSTRING(col FROM 1 FOR 10)"
        """
        if length:
            return f"SUBSTRING({string} FROM {start} FOR {length})"
        return f"SUBSTRING({string} FROM {start})"

    def current_timestamp(self) -> str:
        """
        Get Informix current timestamp.

        Returns:
            SQL expression
        """
        return "CURRENT"

    def date_add(self, date_expr: str, interval: int, unit: str = "DAY") -> str:
        """
        Generate Informix date addition.

        Args:
            date_expr: Date expression
            interval: Interval value
            unit: Time unit

        Returns:
            SQL expression

        Examples:
            >>> dialect = InformixDialect()
            >>> dialect.date_add("order_date", 7, "DAY")
            "order_date + 7 UNITS DAY"
        """
        return f"{date_expr} + {interval} UNITS {unit}"
