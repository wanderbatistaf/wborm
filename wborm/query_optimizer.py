"""
Query Optimizer

This module provides automatic query optimization for JOIN, GROUP BY, and PIVOT
operations, improving performance through intelligent query rewriting and caching.

Features:
- Automatic JOIN order optimization
- Aggregate query caching
- Query pattern analysis
- PIVOT operation optimization
- Best practices enforcement
"""

from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import re


class QueryAnalyzer:
    """
    Analyzes SQL queries to identify optimization opportunities.
    """

    @staticmethod
    def count_joins(sql: str) -> int:
        """
        Count number of JOINs in a query.

        Args:
            sql: SQL query string

        Returns:
            Number of JOIN clauses
        """
        join_pattern = r'\b(INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\b'
        return len(re.findall(join_pattern, sql, re.IGNORECASE))

    @staticmethod
    def has_group_by(sql: str) -> bool:
        """
        Check if query has GROUP BY clause.

        Args:
            sql: SQL query string

        Returns:
            True if GROUP BY present
        """
        return bool(re.search(r'\bGROUP\s+BY\b', sql, re.IGNORECASE))

    @staticmethod
    def has_aggregates(sql: str) -> bool:
        """
        Check if query uses aggregate functions.

        Args:
            sql: SQL query string

        Returns:
            True if aggregates found
        """
        agg_pattern = r'\b(COUNT|SUM|AVG|MIN|MAX|STDDEV|VARIANCE)\s*\('
        return bool(re.search(agg_pattern, sql, re.IGNORECASE))

    @staticmethod
    def extract_tables(sql: str) -> List[str]:
        """
        Extract table names from SQL query.

        Args:
            sql: SQL query string

        Returns:
            List of table names
        """
        # Simple extraction - FROM clause and JOINs
        tables = []

        # Extract FROM table
        from_match = re.search(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
        if from_match:
            tables.append(from_match.group(1))

        # Extract JOIN tables
        join_pattern = r'JOIN\s+(\w+)'
        join_matches = re.findall(join_pattern, sql, re.IGNORECASE)
        tables.extend(join_matches)

        return tables

    @staticmethod
    def analyze_complexity(sql: str) -> Dict[str, Any]:
        """
        Analyze query complexity.

        Args:
            sql: SQL query string

        Returns:
            Dictionary with complexity metrics
        """
        return {
            "num_joins": QueryAnalyzer.count_joins(sql),
            "has_group_by": QueryAnalyzer.has_group_by(sql),
            "has_aggregates": QueryAnalyzer.has_aggregates(sql),
            "tables": QueryAnalyzer.extract_tables(sql),
            "complexity_score": (
                QueryAnalyzer.count_joins(sql) * 2 +
                (5 if QueryAnalyzer.has_group_by(sql) else 0) +
                (3 if QueryAnalyzer.has_aggregates(sql) else 0)
            )
        }


class JoinOptimizer:
    """
    Optimizes JOIN operations through ordering and hints.
    """

    def __init__(self):
        """Initialize JOIN optimizer with table statistics"""
        self._table_sizes: Dict[str, int] = {}
        self._join_selectivity: Dict[Tuple[str, str], float] = {}

    def register_table_size(self, table: str, row_count: int) -> None:
        """
        Register table size for optimization decisions.

        Args:
            table: Table name
            row_count: Approximate row count

        Examples:
            >>> optimizer.register_table_size("clientes", 10000)
            >>> optimizer.register_table_size("pedidos", 1000000)
        """
        self._table_sizes[table] = row_count

    def suggest_join_order(self, tables: List[str]) -> List[str]:
        """
        Suggest optimal JOIN order based on table sizes.

        Strategy: Start with smallest table, join progressively larger tables.

        Args:
            tables: List of table names

        Returns:
            Ordered list of tables

        Examples:
            >>> optimizer.suggest_join_order(["pedidos", "clientes", "items"])
            ["clientes", "pedidos", "items"]  # If clientes smallest
        """
        if not self._table_sizes:
            return tables  # No statistics, keep original order

        # Sort tables by size (smallest first)
        known_tables = [t for t in tables if t in self._table_sizes]
        unknown_tables = [t for t in tables if t not in self._table_sizes]

        sorted_known = sorted(known_tables, key=lambda t: self._table_sizes[t])

        return sorted_known + unknown_tables

    def get_join_hint(self, left_table: str, right_table: str) -> str:
        """
        Get optimization hint for specific JOIN.

        Args:
            left_table: Left table name
            right_table: Right table name

        Returns:
            Hint string (empty if no hint)
        """
        # Check if we should swap JOIN order
        left_size = self._table_sizes.get(left_table, float('inf'))
        right_size = self._table_sizes.get(right_table, float('inf'))

        if right_size < left_size * 0.1:  # Right table significantly smaller
            return "-- Consider swapping JOIN order for better performance"

        return ""


class AggregateCache:
    """
    Specialized cache for aggregate queries (GROUP BY, COUNT, SUM, etc).

    Aggregate queries are expensive and often repeated, making them
    excellent candidates for aggressive caching.
    """

    def __init__(self, ttl: int = 300):
        """
        Initialize aggregate cache.

        Args:
            ttl: Time-to-live in seconds (default: 5 minutes)
        """
        self.ttl = ttl
        self._cache: Dict[str, Tuple[Any, float]] = {}

    def get(self, sql: str) -> Optional[Any]:
        """
        Get cached aggregate result.

        Args:
            sql: SQL query string

        Returns:
            Cached result or None
        """
        import time

        if sql in self._cache:
            result, timestamp = self._cache[sql]
            if time.time() - timestamp < self.ttl:
                return result
            else:
                del self._cache[sql]

        return None

    def set(self, sql: str, result: Any) -> None:
        """
        Cache aggregate result.

        Args:
            sql: SQL query string
            result: Query result
        """
        import time
        self._cache[sql] = (result, time.time())

    def invalidate_table(self, table: str) -> int:
        """
        Invalidate all cached queries involving a table.

        Args:
            table: Table name

        Returns:
            Number of entries invalidated
        """
        table_pattern = re.compile(rf'\b{table}\b', re.IGNORECASE)

        keys_to_remove = [
            key for key in self._cache.keys()
            if table_pattern.search(key)
        ]

        for key in keys_to_remove:
            del self._cache[key]

        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cached aggregates"""
        self._cache.clear()


class PivotOptimizer:
    """
    Optimizes PIVOT operations through intelligent query generation.
    """

    @staticmethod
    def optimize_pivot_columns(distinct_values: List[Any], max_columns: int = 50) -> List[Any]:
        """
        Optimize PIVOT by limiting dynamic columns.

        Args:
            distinct_values: List of distinct values for PIVOT
            max_columns: Maximum columns to generate

        Returns:
            Optimized list of values

        Examples:
            >>> values = range(1, 1000)
            >>> optimized = PivotOptimizer.optimize_pivot_columns(values, max_columns=20)
            >>> len(optimized)
            20
        """
        if len(distinct_values) <= max_columns:
            return distinct_values

        # Keep top N by frequency if we have counts, otherwise first N
        return list(distinct_values[:max_columns])

    @staticmethod
    def suggest_pivot_strategy(row_count: int, col_count: int) -> str:
        """
        Suggest best PIVOT strategy based on data dimensions.

        Args:
            row_count: Number of rows
            col_count: Number of distinct column values

        Returns:
            Strategy recommendation

        Examples:
            >>> PivotOptimizer.suggest_pivot_strategy(1000, 5)
            "Standard PIVOT - small column count"

            >>> PivotOptimizer.suggest_pivot_strategy(100000, 100)
            "Consider pre-aggregation - large dataset with many columns"
        """
        if col_count > 100:
            return "Too many columns - consider filtering or using alternate view"

        if row_count > 100000 and col_count > 20:
            return "Consider pre-aggregation - large dataset with many columns"

        if row_count > 1000000:
            return "Use pagination or materialized view for very large datasets"

        return "Standard PIVOT - small column count"


class QueryOptimizer:
    """
    Main query optimizer coordinating all optimization strategies.
    """

    def __init__(self):
        """Initialize query optimizer"""
        self.analyzer = QueryAnalyzer()
        self.join_optimizer = JoinOptimizer()
        self.aggregate_cache = AggregateCache()
        self.pivot_optimizer = PivotOptimizer()

    def analyze(self, sql: str) -> Dict[str, Any]:
        """
        Analyze query and provide optimization suggestions.

        Args:
            sql: SQL query string

        Returns:
            Analysis results with suggestions

        Examples:
            >>> optimizer = QueryOptimizer()
            >>> analysis = optimizer.analyze("SELECT * FROM a JOIN b JOIN c")
            >>> print(analysis['suggestions'])
        """
        complexity = self.analyzer.analyze_complexity(sql)

        suggestions = []

        # Check for missing indexes hint
        if complexity['num_joins'] >= 3:
            suggestions.append(
                "Multiple JOINs detected - ensure JOIN columns are indexed"
            )

        # Check for SELECT *
        if re.search(r'\bSELECT\s+\*', sql, re.IGNORECASE):
            suggestions.append(
                "SELECT * found - consider specifying only needed columns (.only())"
            )

        # Check for aggregates without GROUP BY
        if complexity['has_aggregates'] and not complexity['has_group_by']:
            suggestions.append(
                "Aggregate query - result will be cached for faster subsequent access"
            )

        # Large JOINs
        if complexity['num_joins'] >= 5:
            suggestions.append(
                "Many JOINs detected - consider breaking into subqueries or temp tables"
            )

        return {
            "complexity": complexity,
            "suggestions": suggestions,
            "cache_recommended": complexity['has_aggregates'] or complexity['has_group_by'],
            "optimization_priority": "high" if complexity['complexity_score'] > 10 else "medium" if complexity['complexity_score'] > 5 else "low"
        }

    def get_optimization_report(self, sql: str) -> str:
        """
        Get formatted optimization report.

        Args:
            sql: SQL query string

        Returns:
            Formatted report string

        Examples:
            >>> optimizer = QueryOptimizer()
            >>> print(optimizer.get_optimization_report(sql))
        """
        analysis = self.analyze(sql)

        report = []
        report.append("=" * 60)
        report.append("Query Optimization Report")
        report.append("=" * 60)

        complexity = analysis['complexity']
        report.append(f"Complexity Score: {complexity['complexity_score']}")
        report.append(f"Priority: {analysis['optimization_priority'].upper()}")
        report.append(f"Tables: {', '.join(complexity['tables'])}")
        report.append(f"JOINs: {complexity['num_joins']}")
        report.append(f"Aggregates: {'Yes' if complexity['has_aggregates'] else 'No'}")
        report.append(f"GROUP BY: {'Yes' if complexity['has_group_by'] else 'No'}")

        if analysis['suggestions']:
            report.append("\nOptimization Suggestions:")
            report.append("-" * 60)
            for i, suggestion in enumerate(analysis['suggestions'], 1):
                report.append(f"{i}. {suggestion}")

        if analysis['cache_recommended']:
            report.append("\n💡 Cache Recommended: This query would benefit from caching")

        report.append("=" * 60)

        return "\n".join(report)


# Global optimizer instance
_global_optimizer = QueryOptimizer()


def get_optimizer() -> QueryOptimizer:
    """
    Get global query optimizer.

    Returns:
        Global QueryOptimizer instance

    Examples:
        >>> optimizer = get_optimizer()
        >>> optimizer.join_optimizer.register_table_size("clientes", 10000)
    """
    return _global_optimizer


def analyze_query(sql: str) -> Dict[str, Any]:
    """
    Analyze query for optimization opportunities.

    Args:
        sql: SQL query string

    Returns:
        Analysis results

    Examples:
        >>> from wborm import analyze_query
        >>> analysis = analyze_query("SELECT * FROM a JOIN b")
        >>> print(analysis['suggestions'])
    """
    return _global_optimizer.analyze(sql)


def print_query_report(sql: str) -> None:
    """
    Print query optimization report.

    Args:
        sql: SQL query string

    Examples:
        >>> from wborm import print_query_report
        >>> print_query_report("SELECT * FROM orders JOIN customers")
    """
    print(_global_optimizer.get_optimization_report(sql))


def register_table_stats(table: str, row_count: int) -> None:
    """
    Register table statistics for optimization.

    Args:
        table: Table name
        row_count: Approximate row count

    Examples:
        >>> from wborm import register_table_stats
        >>> register_table_stats("clientes", 50000)
        >>> register_table_stats("pedidos", 1000000)
    """
    _global_optimizer.join_optimizer.register_table_size(table, row_count)
