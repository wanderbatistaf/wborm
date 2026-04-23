"""
Oracle Dialect

Oracle Database-specific SQL generation and type mapping.

Supports Oracle 11g, 12c, 18c, 19c, and 21c.
"""

from typing import Type, Union, Optional, List
from .base import BaseDialect


class OracleDialect(BaseDialect):
    """
    Dialect for Oracle databases.

    Implements Oracle-specific SQL syntax and type mapping.
    """

    def __init__(self):
        """Initialize Oracle dialect"""
        super().__init__()
        self.name = "oracle"
        self.supports_limit_offset = True  # ROW_NUMBER or OFFSET/FETCH
        self.supports_window_functions = True  # Oracle 8i+
        self.supports_cte = True  # Oracle 9i+

    def map_type_to_python(self, db_type: Union[int, str]) -> Type:
        """
        Map Oracle type to Python type.

        Args:
            db_type: Oracle type name or code

        Returns:
            Python type

        Examples:
            >>> dialect = OracleDialect()
            >>> dialect.map_type_to_python("NUMBER")
            <class 'float'>
            >>> dialect.map_type_to_python("VARCHAR2")
            <class 'str'>
        """
        if isinstance(db_type, str):
            type_str = str(db_type).upper()

            # Numeric types
            if type_str in ("NUMBER", "NUMERIC", "DECIMAL", "DEC"):
                return float
            elif type_str in ("INTEGER", "INT", "SMALLINT"):
                return int
            elif type_str in ("FLOAT", "DOUBLE PRECISION", "REAL", "BINARY_FLOAT", "BINARY_DOUBLE"):
                return float

            # String types
            elif type_str in ("CHAR", "VARCHAR", "VARCHAR2", "NCHAR", "NVARCHAR2"):
                return str
            elif type_str in ("CLOB", "NCLOB", "LONG"):
                return str

            # Date/Time types
            elif type_str in ("DATE", "TIMESTAMP", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP WITH LOCAL TIME ZONE"):
                return str

            # Binary types
            elif type_str in ("BLOB", "RAW", "LONG RAW", "BFILE"):
                return bytes

            # Oracle-specific types
            elif type_str == "ROWID" or type_str == "UROWID":
                return str
            elif type_str == "XMLTYPE":
                return str
            elif type_str == "JSON":
                return str

        return str

    def limit_offset_clause(self, limit: Optional[int], offset: Optional[int]) -> str:
        """
        Generate Oracle OFFSET/FETCH clause (12c+) or ROW_NUMBER (11g).

        For Oracle 12c+, uses OFFSET/FETCH FIRST syntax.
        For older versions, should use ROW_NUMBER() in a subquery.

        Args:
            limit: Row limit
            offset: Row offset

        Returns:
            SQL clause

        Examples:
            >>> dialect = OracleDialect()
            >>> dialect.limit_offset_clause(10, 20)
            "OFFSET 20 ROWS FETCH FIRST 10 ROWS ONLY"
            >>> dialect.limit_offset_clause(10, None)
            "FETCH FIRST 10 ROWS ONLY"
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
        Get Oracle optimizer hints.

        Args:
            query_type: Query type (SELECT, INSERT, etc.)

        Returns:
            Optimizer hint

        Examples:
            >>> dialect = OracleDialect()
            >>> dialect.get_optimizer_hints("SELECT")
            "/*+ FIRST_ROWS */"
        """
        hints = {
            "SELECT": "/*+ FIRST_ROWS */",
            "INSERT": "/*+ APPEND */",
            "UPDATE": "/*+ ROWID */",
            "DELETE": "/*+ ROWID */",
        }
        return hints.get(query_type.upper(), "")

    def optimize_join(self, join_type: str, tables: List[str]) -> str:
        """
        Get Oracle JOIN optimization hint.

        Args:
            join_type: JOIN type
            tables: Tables being joined

        Returns:
            Optimization hint

        Examples:
            >>> dialect = OracleDialect()
            >>> dialect.optimize_join("INNER", ["orders", "customers"])
            "/*+ USE_HASH(orders customers) */"
        """
        if len(tables) >= 2:
            table_list = " ".join(tables)
            return f"/*+ USE_HASH({table_list}) */"
        return ""

    def get_table_list_query(self) -> str:
        """
        Get query to list Oracle tables.

        Returns:
            SQL query

        Examples:
            >>> dialect = OracleDialect()
            >>> query = dialect.get_table_list_query()
            >>> "USER_TABLES" in query
            True
        """
        return """
            SELECT table_name
            FROM user_tables
            ORDER BY table_name
        """

    def get_table_info_query(self, table_name: str) -> str:
        """
        Get query to retrieve Oracle table column information.

        Args:
            table_name: Table name

        Returns:
            SQL query

        Examples:
            >>> dialect = OracleDialect()
            >>> query = dialect.get_table_info_query("EMPLOYEES")
            >>> "USER_TAB_COLUMNS" in query
            True
        """
        return f"""
            SELECT column_name,
                   data_type,
                   nullable
            FROM user_tab_columns
            WHERE table_name = '{table_name.upper()}'
            ORDER BY column_id
        """

    def concat_function(self, *args: str) -> str:
        """
        Generate Oracle CONCAT (uses || operator).

        Args:
            *args: Values to concatenate

        Returns:
            SQL expression

        Examples:
            >>> dialect = OracleDialect()
            >>> dialect.concat_function("first_name", "' '", "last_name")
            "first_name || ' ' || last_name"
        """
        return " || ".join(args)

    def substring_function(self, string: str, start: int, length: Optional[int] = None) -> str:
        """
        Generate Oracle SUBSTR.

        Args:
            string: String expression
            start: Start position (1-indexed)
            length: Length (optional)

        Returns:
            SQL function call

        Examples:
            >>> dialect = OracleDialect()
            >>> dialect.substring_function("name", 1, 5)
            "SUBSTR(name, 1, 5)"
        """
        if length:
            return f"SUBSTR({string}, {start}, {length})"
        return f"SUBSTR({string}, {start})"

    def current_timestamp(self) -> str:
        """
        Get Oracle current timestamp.

        Returns:
            SQL expression

        Examples:
            >>> dialect = OracleDialect()
            >>> dialect.current_timestamp()
            "SYSTIMESTAMP"
        """
        return "SYSTIMESTAMP"

    def date_add(self, date_expr: str, interval: int, unit: str = "DAY") -> str:
        """
        Generate Oracle date addition.

        Args:
            date_expr: Date expression
            interval: Interval value
            unit: Time unit (DAY, MONTH, YEAR, HOUR, MINUTE, SECOND)

        Returns:
            SQL expression

        Examples:
            >>> dialect = OracleDialect()
            >>> dialect.date_add("hire_date", 30, "DAY")
            "hire_date + INTERVAL '30' DAY"
            >>> dialect.date_add("hire_date", 1, "MONTH")
            "hire_date + INTERVAL '1' MONTH"
        """
        return f"{date_expr} + INTERVAL '{interval}' {unit.upper()}"

    def date_diff(self, date1: str, date2: str, unit: str = "DAY") -> str:
        """
        Generate Oracle date difference.

        Args:
            date1: First date expression
            date2: Second date expression
            unit: Time unit

        Returns:
            SQL expression

        Examples:
            >>> dialect = OracleDialect()
            >>> dialect.date_diff("end_date", "start_date", "DAY")
            "TRUNC(end_date - start_date)"
        """
        if unit.upper() == "DAY":
            return f"TRUNC({date1} - {date2})"
        elif unit.upper() == "MONTH":
            return f"MONTHS_BETWEEN({date1}, {date2})"
        elif unit.upper() == "YEAR":
            return f"FLOOR(MONTHS_BETWEEN({date1}, {date2}) / 12)"
        return f"TRUNC({date1} - {date2})"

    def quote_identifier(self, identifier: str) -> str:
        """
        Quote identifier for Oracle (case-sensitive names).

        Args:
            identifier: Table or column name

        Returns:
            Quoted identifier

        Examples:
            >>> dialect = OracleDialect()
            >>> dialect.quote_identifier("MyTable")
            '"MyTable"'
        """
        # Oracle converts unquoted identifiers to uppercase
        # Use quotes to preserve case
        return f'"{identifier}"'

    def sequence_next_value(self, sequence_name: str) -> str:
        """
        Get next value from Oracle sequence.

        Args:
            sequence_name: Sequence name

        Returns:
            SQL expression

        Examples:
            >>> dialect = OracleDialect()
            >>> dialect.sequence_next_value("employee_seq")
            "employee_seq.NEXTVAL"
        """
        return f"{sequence_name}.NEXTVAL"

    def supports_returning(self) -> bool:
        """
        Check if Oracle supports RETURNING clause.

        Returns:
            True (Oracle supports RETURNING for INSERT/UPDATE/DELETE)

        Examples:
            >>> dialect = OracleDialect()
            >>> dialect.supports_returning()
            True
        """
        return True
