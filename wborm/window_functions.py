"""
Window Functions

Provides complete window function support for analytical queries.

Features:
- ROW_NUMBER, RANK, DENSE_RANK
- LAG, LEAD (previous/next values)
- FIRST_VALUE, LAST_VALUE
- SUM, AVG, COUNT over windows
- PARTITION BY and ORDER BY support
"""

from typing import Optional


class Window:
    """
    Window function builder with fluent API.

    Examples:
        >>> Window.row_number().over(partition_by="categoria", order_by="preco DESC")
        "ROW_NUMBER() OVER (PARTITION BY categoria ORDER BY preco DESC)"
    """

    def __init__(self, function: str):
        """
        Initialize window function.

        Args:
            function: Window function name (e.g., "ROW_NUMBER()")
        """
        self.function = function
        self.partition = None
        self.order = None
        self.frame = None

    def over(self, partition_by: Optional[str] = None, order_by: Optional[str] = None):
        """
        Add OVER clause to window function.

        Args:
            partition_by: PARTITION BY clause
            order_by: ORDER BY clause

        Returns:
            SQL expression string

        Examples:
            >>> Window.row_number().over(partition_by="categoria", order_by="preco DESC")
        """
        parts = []

        if partition_by:
            parts.append(f"PARTITION BY {partition_by}")

        if order_by:
            parts.append(f"ORDER BY {order_by}")

        over_clause = " ".join(parts) if parts else ""

        return f"{self.function} OVER ({over_clause})" if over_clause else f"{self.function} OVER ()"

    @staticmethod
    def row_number():
        """
        ROW_NUMBER() window function.

        Assigns unique sequential integer to rows within partition.

        Returns:
            Window instance

        Examples:
            >>> Window.row_number().over(partition_by="categoria", order_by="preco DESC")
            "ROW_NUMBER() OVER (PARTITION BY categoria ORDER BY preco DESC)"
        """
        return Window("ROW_NUMBER()")

    @staticmethod
    def rank():
        """
        RANK() window function.

        Assigns rank with gaps for ties.

        Returns:
            Window instance

        Examples:
            >>> Window.rank().over(order_by="vendas DESC")
            "RANK() OVER (ORDER BY vendas DESC)"
        """
        return Window("RANK()")

    @staticmethod
    def dense_rank():
        """
        DENSE_RANK() window function.

        Assigns rank without gaps for ties.

        Returns:
            Window instance

        Examples:
            >>> Window.dense_rank().over(order_by="pontos DESC")
            "DENSE_RANK() OVER (ORDER BY pontos DESC)"
        """
        return Window("DENSE_RANK()")

    @staticmethod
    def lag(field: str, offset: int = 1, default: Optional[str] = None):
        """
        LAG() window function.

        Access value from previous row.

        Args:
            field: Field name
            offset: Number of rows back (default: 1)
            default: Default value if no previous row

        Returns:
            Window instance

        Examples:
            >>> Window.lag("preco", 1).over(order_by="data")
            "LAG(preco, 1) OVER (ORDER BY data)"
        """
        if default:
            func = f"LAG({field}, {offset}, {default})"
        else:
            func = f"LAG({field}, {offset})"
        return Window(func)

    @staticmethod
    def lead(field: str, offset: int = 1, default: Optional[str] = None):
        """
        LEAD() window function.

        Access value from next row.

        Args:
            field: Field name
            offset: Number of rows ahead (default: 1)
            default: Default value if no next row

        Returns:
            Window instance

        Examples:
            >>> Window.lead("preco", 1).over(order_by="data")
            "LEAD(preco, 1) OVER (ORDER BY data)"
        """
        if default:
            func = f"LEAD({field}, {offset}, {default})"
        else:
            func = f"LEAD({field}, {offset})"
        return Window(func)

    @staticmethod
    def first_value(field: str):
        """
        FIRST_VALUE() window function.

        Returns first value in window frame.

        Args:
            field: Field name

        Returns:
            Window instance

        Examples:
            >>> Window.first_value("preco").over(partition_by="categoria", order_by="data")
        """
        return Window(f"FIRST_VALUE({field})")

    @staticmethod
    def last_value(field: str):
        """
        LAST_VALUE() window function.

        Returns last value in window frame.

        Args:
            field: Field name

        Returns:
            Window instance

        Examples:
            >>> Window.last_value("preco").over(partition_by="categoria", order_by="data")
        """
        return Window(f"LAST_VALUE({field})")

    @staticmethod
    def sum(field: str):
        """
        SUM() over window.

        Running sum within partition.

        Args:
            field: Field to sum

        Returns:
            Window instance

        Examples:
            >>> Window.sum("valor").over(partition_by="cliente", order_by="data")
        """
        return Window(f"SUM({field})")

    @staticmethod
    def avg(field: str):
        """
        AVG() over window.

        Moving average within partition.

        Args:
            field: Field to average

        Returns:
            Window instance

        Examples:
            >>> Window.avg("preco").over(partition_by="categoria", order_by="data")
        """
        return Window(f"AVG({field})")

    @staticmethod
    def count(field: str = "*"):
        """
        COUNT() over window.

        Running count within partition.

        Args:
            field: Field to count (default: *)

        Returns:
            Window instance

        Examples:
            >>> Window.count().over(partition_by="loja", order_by="data")
        """
        return Window(f"COUNT({field})")

    @staticmethod
    def min(field: str):
        """
        MIN() over window.

        Minimum value in window frame.

        Args:
            field: Field name

        Returns:
            Window instance
        """
        return Window(f"MIN({field})")

    @staticmethod
    def max(field: str):
        """
        MAX() over window.

        Maximum value in window frame.

        Args:
            field: Field name

        Returns:
            Window instance
        """
        return Window(f"MAX({field})")


# Aliases for convenience
ROW_NUMBER = Window.row_number
RANK = Window.rank
DENSE_RANK = Window.dense_rank
LAG = Window.lag
LEAD = Window.lead
FIRST_VALUE = Window.first_value
LAST_VALUE = Window.last_value
