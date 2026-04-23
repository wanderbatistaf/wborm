"""
Base Dialect

Defines the interface that all database dialects must implement.

Provides default implementations that can be overridden by specific dialects.
"""

from typing import Any, Dict, List, Optional, Type, Union


class BaseDialect:
    """
    Base class for database dialects.

    Subclasses override methods to provide database-specific behavior.
    """

    def __init__(self):
        """Initialize dialect"""
        self.name = "base"
        self.supports_limit_offset = True
        self.supports_window_functions = False
        self.supports_cte = False
        self.limit_offset_position = "end"  # "start" (after SELECT) or "end" (after ORDER BY)

    # Type Mapping
    # ============

    def map_type_to_python(self, db_type: Union[int, str]) -> Type:
        """
        Map database type to Python type.

        Args:
            db_type: Database type code or name

        Returns:
            Python type

        Examples:
            >>> dialect.map_type_to_python("VARCHAR")
            <class 'str'>
        """
        raise NotImplementedError("Subclass must implement map_type_to_python")

    def map_python_to_db(self, python_type: Type) -> str:
        """
        Map Python type to database type name.

        Args:
            python_type: Python type

        Returns:
            Database type name

        Examples:
            >>> dialect.map_python_to_db(str)
            "VARCHAR"
        """
        type_map = {
            str: "VARCHAR",
            int: "INTEGER",
            float: "FLOAT",
            bool: "BOOLEAN",
            bytes: "BLOB",
        }
        return type_map.get(python_type, "VARCHAR")

    # SQL Generation
    # ==============

    def quote_identifier(self, identifier: str) -> str:
        """
        Quote identifier (table/column name).

        Args:
            identifier: Identifier to quote

        Returns:
            Quoted identifier

        Examples:
            >>> dialect.quote_identifier("my_table")
            '"my_table"'
        """
        return f'"{identifier}"'

    def limit_offset_clause(self, limit: Optional[int], offset: Optional[int]) -> str:
        """
        Generate LIMIT/OFFSET clause.

        Args:
            limit: Row limit
            offset: Row offset

        Returns:
            SQL clause

        Examples:
            >>> dialect.limit_offset_clause(10, 20)
            "LIMIT 10 OFFSET 20"
        """
        if limit is None:
            return ""

        clause = f"LIMIT {limit}"
        if offset:
            clause += f" OFFSET {offset}"

        return clause

    def supports_feature(self, feature: str) -> bool:
        """
        Check if dialect supports a feature.

        Args:
            feature: Feature name

        Returns:
            True if supported

        Examples:
            >>> dialect.supports_feature("window_functions")
            False
        """
        feature_map = {
            "limit_offset": self.supports_limit_offset,
            "window_functions": self.supports_window_functions,
            "cte": self.supports_cte,
        }
        return feature_map.get(feature, False)

    # Query Optimization
    # ==================

    def get_optimizer_hints(self, query_type: str) -> str:
        """
        Get optimizer hints for query type.

        Args:
            query_type: Type of query ("select", "join", "aggregate")

        Returns:
            Optimizer hint string

        Examples:
            >>> dialect.get_optimizer_hints("join")
            ""
        """
        return ""

    def optimize_join(self, join_type: str, tables: List[str]) -> str:
        """
        Get optimization hint for JOIN.

        Args:
            join_type: JOIN type ("INNER", "LEFT", etc.)
            tables: Tables being joined

        Returns:
            Optimization hint

        Examples:
            >>> dialect.optimize_join("INNER", ["t1", "t2"])
            ""
        """
        return ""

    # Data Type Conversions
    # =====================

    def format_value(self, value: Any, python_type: Type) -> str:
        """
        Format Python value for SQL.

        Args:
            value: Python value
            python_type: Python type

        Returns:
            SQL-formatted value

        Examples:
            >>> dialect.format_value("test", str)
            "'test'"
        """
        if value is None:
            return "NULL"

        if python_type == str:
            escaped = str(value).replace("'", "''")
            return f"'{escaped}'"

        if python_type == bool:
            return "1" if value else "0"

        return str(value)

    # Information Schema
    # ==================

    def get_table_list_query(self) -> str:
        """
        Get query to list all tables.

        Returns:
            SQL query

        Examples:
            >>> dialect.get_table_list_query()
            "SELECT table_name FROM information_schema.tables"
        """
        return """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
        """

    def get_table_info_query(self, table_name: str) -> str:
        """
        Get query to retrieve table column information.

        Args:
            table_name: Table name

        Returns:
            SQL query

        Examples:
            >>> dialect.get_table_info_query("my_table")
        """
        return f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """

    # String Functions
    # ================

    def concat_function(self, *args: str) -> str:
        """
        Generate CONCAT function call.

        Args:
            *args: Values to concatenate

        Returns:
            SQL function call

        Examples:
            >>> dialect.concat_function("col1", "'_'", "col2")
            "CONCAT(col1, '_', col2)"
        """
        return f"CONCAT({', '.join(args)})"

    def substring_function(self, string: str, start: int, length: Optional[int] = None) -> str:
        """
        Generate SUBSTRING function call.

        Args:
            string: String expression
            start: Start position (1-indexed)
            length: Length (optional)

        Returns:
            SQL function call

        Examples:
            >>> dialect.substring_function("col", 1, 10)
            "SUBSTRING(col FROM 1 FOR 10)"
        """
        if length:
            return f"SUBSTRING({string} FROM {start} FOR {length})"
        return f"SUBSTRING({string} FROM {start})"

    # Date Functions
    # ==============

    def current_timestamp(self) -> str:
        """
        Get current timestamp expression.

        Returns:
            SQL expression

        Examples:
            >>> dialect.current_timestamp()
            "CURRENT_TIMESTAMP"
        """
        return "CURRENT_TIMESTAMP"

    def date_add(self, date_expr: str, interval: int, unit: str = "DAY") -> str:
        """
        Generate date addition expression.

        Args:
            date_expr: Date expression
            interval: Interval value
            unit: Time unit ("DAY", "MONTH", "YEAR")

        Returns:
            SQL expression

        Examples:
            >>> dialect.date_add("date_col", 7, "DAY")
            "date_col + INTERVAL '7' DAY"
        """
        return f"{date_expr} + INTERVAL '{interval}' {unit}"

    # Feature Detection
    # =================

    def __str__(self) -> str:
        """String representation"""
        return f"<{self.__class__.__name__}>"

    def __repr__(self) -> str:
        """Detailed representation"""
        return f"<{self.__class__.__name__} name={self.name}>"
