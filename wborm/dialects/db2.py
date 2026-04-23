"""
DB2 Dialect

IBM DB2-specific SQL generation and type mapping.

Supports DB2 for LUW (Linux, Unix, Windows), z/OS, and i (AS/400).
"""

from typing import Type, Union, Optional, List
from .base import BaseDialect


class DB2Dialect(BaseDialect):
    """
    Dialect for IBM DB2 databases.

    Implements DB2-specific SQL syntax and type mapping.
    """

    def __init__(self):
        """Initialize DB2 dialect"""
        super().__init__()
        self.name = "db2"
        self.supports_limit_offset = True  # FETCH FIRST
        self.supports_window_functions = True  # DB2 9.7+
        self.supports_cte = True

    def map_type_to_python(self, db_type: Union[int, str]) -> Type:
        """
        Map DB2 type to Python type.

        Args:
            db_type: DB2 type name

        Returns:
            Python type
        """
        if isinstance(db_type, str):
            type_str = str(db_type).upper()

            if type_str in ("SMALLINT", "INTEGER", "INT", "BIGINT"):
                return int
            elif type_str in ("DECIMAL", "NUMERIC", "REAL", "DOUBLE", "FLOAT", "DECFLOAT"):
                return float
            elif type_str in ("CHAR", "VARCHAR", "CLOB", "GRAPHIC", "VARGRAPHIC", "DBCLOB"):
                return str
            elif type_str in ("DATE", "TIME", "TIMESTAMP"):
                return str
            elif type_str in ("BLOB", "BINARY", "VARBINARY"):
                return bytes
            elif type_str == "BOOLEAN":
                return bool
            elif type_str == "XML":
                return str

        return str

    def limit_offset_clause(self, limit: Optional[int], offset: Optional[int]) -> str:
        """
        Generate DB2 FETCH FIRST clause.

        Args:
            limit: Row limit
            offset: Row offset

        Returns:
            SQL clause

        Examples:
            >>> dialect = DB2Dialect()
            >>> dialect.limit_offset_clause(10, 20)
            "OFFSET 20 ROWS FETCH FIRST 10 ROWS ONLY"
        """
        if limit is None:
            return ""

        clause = ""
        if offset:
            clause += f"OFFSET {offset} ROWS "

        clause += f"FETCH FIRST {limit} ROWS ONLY"

        return clause

    def get_optimizer_hints(self, query_type: str) -> str:
        """
        Get DB2 optimizer hints.

        Args:
            query_type: Query type

        Returns:
            Optimizer hint
        """
        # DB2 supports OPTIMIZE FOR n ROWS
        return ""

    def optimize_join(self, join_type: str, tables: List[str]) -> str:
        """
        Get DB2 JOIN optimization hint.

        Args:
            join_type: JOIN type
            tables: Tables being joined

        Returns:
            Optimization hint
        """
        # DB2 can use query optimization hints like REOPT
        return ""

    def get_table_list_query(self) -> str:
        """
        Get query to list DB2 tables.

        Returns:
            SQL query
        """
        return """
            SELECT tabname AS table_name
            FROM syscat.tables
            WHERE tabschema = CURRENT SCHEMA
            AND type = 'T'
            ORDER BY tabname
        """

    def get_table_info_query(self, table_name: str) -> str:
        """
        Get query to retrieve DB2 table column information.

        Args:
            table_name: Table name

        Returns:
            SQL query
        """
        return f"""
            SELECT colname AS column_name,
                   typename AS data_type,
                   CASE WHEN nulls = 'Y' THEN 'YES' ELSE 'NO' END AS is_nullable
            FROM syscat.columns
            WHERE tabname = '{table_name}'
            AND tabschema = CURRENT SCHEMA
            ORDER BY colno
        """

    def concat_function(self, *args: str) -> str:
        """
        Generate DB2 CONCAT (uses || or CONCAT function).

        Args:
            *args: Values to concatenate

        Returns:
            SQL expression
        """
        # DB2 supports both || and CONCAT function
        return " || ".join(args)

    def substring_function(self, string: str, start: int, length: Optional[int] = None) -> str:
        """
        Generate DB2 SUBSTRING.

        Args:
            string: String expression
            start: Start position (1-indexed)
            length: Length (optional)

        Returns:
            SQL function call
        """
        if length:
            return f"SUBSTRING({string}, {start}, {length})"
        return f"SUBSTRING({string}, {start})"

    def current_timestamp(self) -> str:
        """
        Get DB2 current timestamp.

        Returns:
            SQL expression
        """
        return "CURRENT TIMESTAMP"

    def date_add(self, date_expr: str, interval: int, unit: str = "DAY") -> str:
        """
        Generate DB2 date addition.

        Args:
            date_expr: Date expression
            interval: Interval value
            unit: Time unit

        Returns:
            SQL expression
        """
        # DB2 uses + INTERVAL notation
        unit_map = {
            "DAY": "DAYS",
            "MONTH": "MONTHS",
            "YEAR": "YEARS",
            "HOUR": "HOURS",
            "MINUTE": "MINUTES",
            "SECOND": "SECONDS",
        }
        db2_unit = unit_map.get(unit.upper(), "DAYS")
        return f"{date_expr} + {interval} {db2_unit}"
