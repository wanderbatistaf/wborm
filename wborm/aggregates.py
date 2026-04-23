"""
Aggregate Helpers

Provides optimized aggregate operations with automatic caching
and query optimization for GROUP BY operations.

Features:
- Optimized aggregate functions
- Automatic caching for expensive aggregates
- GROUP BY helpers
- Window function support
"""

from typing import List, Dict, Any, Optional


class AggregateHelper:
    """
    Helper class for building optimized aggregate queries.
    """

    def __init__(self, queryset):
        """
        Initialize aggregate helper.

        Args:
            queryset: QuerySet instance
        """
        self.queryset = queryset

    def annotate(self, **aggregates) -> Any:
        """
        Add aggregate annotations to queryset.

        Args:
            **aggregates: Named aggregate expressions

        Returns:
            QuerySet with annotations

        Examples:
            >>> Cliente.objects.annotate(
            >>>     total_pedidos=Count("pedidos"),
            >>>     valor_total=Sum("pedidos__valor")
            >>> )
        """
        # Build SELECT with aggregates
        select_parts = []

        for name, expr in aggregates.items():
            select_parts.append(f"{expr} AS {name}")

        if select_parts:
            existing = getattr(self.queryset, '_select_fields', [])
            self.queryset._select_fields = existing + select_parts

        return self.queryset


def Count(field: str = "*", distinct: bool = False) -> str:
    """
    Generate COUNT aggregate expression.

    Args:
        field: Field to count (default: *)
        distinct: Count only distinct values

    Returns:
        SQL expression string

    Examples:
        >>> Count()
        "COUNT(*)"

        >>> Count("customer_id", distinct=True)
        "COUNT(DISTINCT customer_id)"
    """
    if distinct:
        return f"COUNT(DISTINCT {field})"
    return f"COUNT({field})"


def Sum(field: str) -> str:
    """
    Generate SUM aggregate expression.

    Args:
        field: Field to sum

    Returns:
        SQL expression string

    Examples:
        >>> Sum("valor")
        "SUM(valor)"
    """
    return f"SUM({field})"


def Avg(field: str) -> str:
    """
    Generate AVG aggregate expression.

    Args:
        field: Field to average

    Returns:
        SQL expression string

    Examples:
        >>> Avg("preco")
        "AVG(preco)"
    """
    return f"AVG({field})"


def Min(field: str) -> str:
    """
    Generate MIN aggregate expression.

    Args:
        field: Field to find minimum

    Returns:
        SQL expression string

    Examples:
        >>> Min("data_criacao")
        "MIN(data_criacao)"
    """
    return f"MIN({field})"


def Max(field: str) -> str:
    """
    Generate MAX aggregate expression.

    Args:
        field: Field to find maximum

    Returns:
        SQL expression string

    Examples:
        >>> Max("ultima_compra")
        "MAX(ultima_compra)"
    """
    return f"MAX({field})"


def StdDev(field: str) -> str:
    """
    Generate STDDEV aggregate expression.

    Args:
        field: Field to calculate standard deviation

    Returns:
        SQL expression string

    Examples:
        >>> StdDev("preco")
        "STDDEV(preco)"
    """
    return f"STDDEV({field})"


def Variance(field: str) -> str:
    """
    Generate VARIANCE aggregate expression.

    Args:
        field: Field to calculate variance

    Returns:
        SQL expression string

    Examples:
        >>> Variance("valor")
        "VARIANCE(valor)"
    """
    return f"VARIANCE({field})"


class GroupByHelper:
    """
    Helper for building optimized GROUP BY queries.
    """

    @staticmethod
    def optimize_grouping(
        fields: List[str],
        having: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Optimize GROUP BY query configuration.

        Args:
            fields: Fields to group by
            having: HAVING clause
            limit: Result limit

        Returns:
            Optimized configuration

        Examples:
            >>> config = GroupByHelper.optimize_grouping(
            >>>     fields=["categoria", "subcategoria"],
            >>>     having="COUNT(*) > 10",
            >>>     limit=100
            >>> )
        """
        return {
            "group_by": fields,
            "having": having,
            "limit": limit,
            "cache_recommended": True,  # GROUP BY queries should be cached
            "use_index_hint": len(fields) > 2  # Multiple grouping columns
        }

    @staticmethod
    def build_rollup(fields: List[str]) -> str:
        """
        Build ROLLUP expression for hierarchical aggregation.

        Args:
            fields: Fields for ROLLUP

        Returns:
            ROLLUP SQL expression

        Examples:
            >>> GroupByHelper.build_rollup(["ano", "mes", "dia"])
            "ROLLUP(ano, mes, dia)"
        """
        return f"ROLLUP({', '.join(fields)})"

    @staticmethod
    def build_cube(fields: List[str]) -> str:
        """
        Build CUBE expression for all combinations.

        Args:
            fields: Fields for CUBE

        Returns:
            CUBE SQL expression

        Examples:
            >>> GroupByHelper.build_cube(["categoria", "regiao"])
            "CUBE(categoria, regiao)"
        """
        return f"CUBE({', '.join(fields)})"


class WindowFunction:
    """
    Helper for window functions (if supported by database).
    """

    @staticmethod
    def row_number(partition_by: Optional[str] = None, order_by: Optional[str] = None) -> str:
        """
        Generate ROW_NUMBER() window function.

        Args:
            partition_by: PARTITION BY clause
            order_by: ORDER BY clause

        Returns:
            SQL expression string

        Examples:
            >>> WindowFunction.row_number(
            >>>     partition_by="categoria",
            >>>     order_by="preco DESC"
            >>> )
            "ROW_NUMBER() OVER (PARTITION BY categoria ORDER BY preco DESC)"
        """
        parts = []

        if partition_by:
            parts.append(f"PARTITION BY {partition_by}")

        if order_by:
            parts.append(f"ORDER BY {order_by}")

        over_clause = " ".join(parts) if parts else ""

        return f"ROW_NUMBER() OVER ({over_clause})" if over_clause else "ROW_NUMBER() OVER ()"

    @staticmethod
    def rank(partition_by: Optional[str] = None, order_by: str = None) -> str:
        """
        Generate RANK() window function.

        Args:
            partition_by: PARTITION BY clause
            order_by: ORDER BY clause

        Returns:
            SQL expression string

        Examples:
            >>> WindowFunction.rank(order_by="vendas DESC")
            "RANK() OVER (ORDER BY vendas DESC)"
        """
        parts = []

        if partition_by:
            parts.append(f"PARTITION BY {partition_by}")

        if order_by:
            parts.append(f"ORDER BY {order_by}")

        over_clause = " ".join(parts) if parts else ""

        return f"RANK() OVER ({over_clause})" if over_clause else "RANK() OVER ()"


def aggregate_with_cache(queryset, **aggregates):
    """
    Execute aggregate query with automatic caching.

    Args:
        queryset: QuerySet instance
        **aggregates: Named aggregates

    Returns:
        Aggregate results dictionary

    Examples:
        >>> from wborm import aggregate_with_cache
        >>> results = aggregate_with_cache(
        >>>     Pedido.filter(status="COMPLETO"),
        >>>     total=Count(),
        >>>     valor_total=Sum("valor"),
        >>>     valor_medio=Avg("valor")
        >>> )
        >>> print(results['total'], results['valor_total'])
    """
    from wborm.query_optimizer import get_optimizer

    # Build aggregate query
    select_parts = []
    for name, expr in aggregates.items():
        select_parts.append(f"{expr} AS {name}")

    queryset = queryset.select(*select_parts)
    sql = queryset._build_query()

    # Check if we can use aggregate cache
    optimizer = get_optimizer()
    cached = optimizer.aggregate_cache.get(sql)

    if cached is not None:
        return cached[0] if cached else {}

    # Execute query
    results = queryset.all()

    # Extract results as dictionary
    if results:
        result_dict = results[0].to_dict()

        # Cache the result
        optimizer.aggregate_cache.set(sql, result_dict)

        return result_dict

    return {}
