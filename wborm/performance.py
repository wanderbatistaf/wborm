"""
Performance Metrics and Logging

This module provides comprehensive performance monitoring for WBORM queries,
including query timing, slow query detection, and performance profiling.

Features:
- Automatic query timing
- Slow query logging
- Query statistics and aggregation
- Performance profiling
- Configurable thresholds
"""

import time
import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
import threading


# Configure logger
logger = logging.getLogger("wborm.performance")


@dataclass
class QueryMetrics:
    """
    Metrics for a single query execution.

    Attributes:
        sql: SQL query string
        duration: Execution time in seconds
        timestamp: When query was executed
        rows_returned: Number of rows returned
        cache_hit: Whether result was from cache
        connection_info: Optional connection metadata
    """
    sql: str
    duration: float
    timestamp: datetime = field(default_factory=datetime.now)
    rows_returned: int = 0
    cache_hit: bool = False
    connection_info: Optional[Dict[str, Any]] = None

    def __repr__(self):
        return (
            f"<QueryMetrics sql={self.sql[:50]}... "
            f"duration={self.duration:.3f}s rows={self.rows_returned}>"
        )


class PerformanceMonitor:
    """
    Monitors and tracks query performance.

    Provides query timing, slow query detection, and statistics aggregation.
    """

    def __init__(
        self,
        enabled: bool = True,
        slow_query_threshold: float = 1.0,
        log_all_queries: bool = False,
        log_slow_queries: bool = True,
        collect_statistics: bool = True
    ):
        """
        Initialize performance monitor.

        Args:
            enabled: Enable monitoring (default: True)
            slow_query_threshold: Threshold for slow queries in seconds (default: 1.0)
            log_all_queries: Log all queries (default: False)
            log_slow_queries: Log slow queries (default: True)
            collect_statistics: Collect aggregate statistics (default: True)

        Examples:
            >>> monitor = PerformanceMonitor(slow_query_threshold=0.5)
            >>> with monitor.measure("SELECT * FROM clientes") as metrics:
            >>>     # Execute query
            >>>     pass
        """
        self.enabled = enabled
        self.slow_query_threshold = slow_query_threshold
        self.log_all_queries = log_all_queries
        self.log_slow_queries = log_slow_queries
        self.collect_statistics = collect_statistics

        # Statistics storage
        self._query_history: List[QueryMetrics] = []
        self._query_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "total_time": 0.0,
                "min_time": float("inf"),
                "max_time": 0.0,
                "total_rows": 0,
                "cache_hits": 0,
            }
        )
        self._lock = threading.RLock()

    class _QueryContext:
        """Context manager for measuring query execution"""

        def __init__(self, monitor, sql: str):
            self.monitor = monitor
            self.sql = sql
            self.metrics: Optional[QueryMetrics] = None
            self.start_time: Optional[float] = None

        def __enter__(self):
            if self.monitor.enabled:
                self.start_time = time.time()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.monitor.enabled and self.start_time:
                duration = time.time() - self.start_time
                self.metrics = QueryMetrics(
                    sql=self.sql,
                    duration=duration
                )
                self.monitor._record_query(self.metrics)

        def set_rows(self, count: int):
            """Set number of rows returned"""
            if self.metrics:
                self.metrics.rows_returned = count

        def set_cache_hit(self, hit: bool):
            """Mark query as cache hit/miss"""
            if self.metrics:
                self.metrics.cache_hit = hit

    def measure(self, sql: str) -> _QueryContext:
        """
        Context manager to measure query execution time.

        Args:
            sql: SQL query string

        Returns:
            Query context manager

        Examples:
            >>> with monitor.measure("SELECT * FROM clientes") as ctx:
            >>>     results = conn.execute_query(sql)
            >>>     ctx.set_rows(len(results))
        """
        return self._QueryContext(self, sql)

    def _record_query(self, metrics: QueryMetrics) -> None:
        """
        Record query metrics.

        Args:
            metrics: Query metrics to record
        """
        with self._lock:
            # Add to history
            if self.collect_statistics:
                self._query_history.append(metrics)

            # Update aggregate statistics
            sql_key = self._normalize_sql(metrics.sql)
            stats = self._query_stats[sql_key]
            stats["count"] += 1
            stats["total_time"] += metrics.duration
            stats["min_time"] = min(stats["min_time"], metrics.duration)
            stats["max_time"] = max(stats["max_time"], metrics.duration)
            stats["total_rows"] += metrics.rows_returned
            if metrics.cache_hit:
                stats["cache_hits"] += 1

            # Logging
            if self.log_all_queries:
                logger.info(
                    f"Query executed: {metrics.sql[:100]}... "
                    f"({metrics.duration:.3f}s, {metrics.rows_returned} rows)"
                )

            if self.log_slow_queries and metrics.duration >= self.slow_query_threshold:
                logger.warning(
                    f"⚠️  SLOW QUERY ({metrics.duration:.3f}s): {metrics.sql[:200]}..."
                )

    def _normalize_sql(self, sql: str) -> str:
        """
        Normalize SQL for statistics grouping.

        Args:
            sql: SQL query string

        Returns:
            Normalized SQL string
        """
        # Simple normalization: remove extra whitespace and lowercase
        return " ".join(sql.split()).lower()[:200]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate query statistics.

        Returns:
            Dictionary with query statistics

        Examples:
            >>> stats = monitor.get_statistics()
            >>> print(f"Total queries: {stats['total_queries']}")
            >>> print(f"Slow queries: {stats['slow_queries']}")
        """
        with self._lock:
            total_queries = len(self._query_history)
            slow_queries = sum(
                1 for m in self._query_history
                if m.duration >= self.slow_query_threshold
            )

            if total_queries > 0:
                avg_duration = sum(m.duration for m in self._query_history) / total_queries
                total_rows = sum(m.rows_returned for m in self._query_history)
                cache_hits = sum(1 for m in self._query_history if m.cache_hit)
            else:
                avg_duration = 0.0
                total_rows = 0
                cache_hits = 0

            return {
                "total_queries": total_queries,
                "slow_queries": slow_queries,
                "slow_query_percentage": (
                    slow_queries / total_queries * 100 if total_queries > 0 else 0
                ),
                "average_duration": avg_duration,
                "total_rows_fetched": total_rows,
                "cache_hit_rate": (
                    cache_hits / total_queries if total_queries > 0 else 0
                ),
            }

    def get_slow_queries(self, limit: int = 10) -> List[QueryMetrics]:
        """
        Get slowest queries.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of slowest query metrics

        Examples:
            >>> slow = monitor.get_slow_queries(limit=5)
            >>> for query in slow:
            >>>     print(f"{query.duration:.3f}s: {query.sql[:50]}")
        """
        with self._lock:
            return sorted(
                self._query_history,
                key=lambda m: m.duration,
                reverse=True
            )[:limit]

    def get_query_stats(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get statistics for most common queries.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of query statistics

        Examples:
            >>> stats = monitor.get_query_stats(limit=5)
            >>> for stat in stats:
            >>>     print(f"{stat['count']}x: {stat['sql'][:50]}")
        """
        with self._lock:
            stats_list = []
            for sql, stats in self._query_stats.items():
                stats_list.append({
                    "sql": sql,
                    "count": stats["count"],
                    "total_time": stats["total_time"],
                    "avg_time": stats["total_time"] / stats["count"],
                    "min_time": stats["min_time"],
                    "max_time": stats["max_time"],
                    "total_rows": stats["total_rows"],
                    "cache_hit_rate": (
                        stats["cache_hits"] / stats["count"]
                        if stats["count"] > 0 else 0
                    ),
                })

            return sorted(
                stats_list,
                key=lambda s: s["total_time"],
                reverse=True
            )[:limit]

    def reset_statistics(self) -> None:
        """Reset all collected statistics"""
        with self._lock:
            self._query_history.clear()
            self._query_stats.clear()

    def print_report(self) -> None:
        """
        Print performance report to stdout.

        Examples:
            >>> monitor.print_report()
        """
        stats = self.get_statistics()

        print("\n" + "=" * 60)
        print("WBORM Performance Report")
        print("=" * 60)
        print(f"Total Queries:        {stats['total_queries']}")
        print(f"Slow Queries:         {stats['slow_queries']} "
              f"({stats['slow_query_percentage']:.1f}%)")
        print(f"Average Duration:     {stats['average_duration']:.3f}s")
        print(f"Total Rows Fetched:   {stats['total_rows_fetched']}")
        print(f"Cache Hit Rate:       {stats['cache_hit_rate']:.1%}")

        print("\n" + "-" * 60)
        print("Top 5 Slowest Queries:")
        print("-" * 60)

        for i, query in enumerate(self.get_slow_queries(limit=5), 1):
            print(f"\n{i}. {query.duration:.3f}s ({query.rows_returned} rows)")
            print(f"   {query.sql[:100]}...")

        print("\n" + "-" * 60)
        print("Top 5 Most Frequent Queries:")
        print("-" * 60)

        for i, stat in enumerate(self.get_query_stats(limit=5), 1):
            print(f"\n{i}. {stat['count']}x - Avg: {stat['avg_time']:.3f}s")
            print(f"   {stat['sql'][:100]}...")

        print("\n" + "=" * 60 + "\n")


# Global performance monitor instance
_global_monitor = PerformanceMonitor()


def get_monitor() -> PerformanceMonitor:
    """
    Get global performance monitor.

    Returns:
        Global PerformanceMonitor instance

    Examples:
        >>> monitor = get_monitor()
        >>> monitor.print_report()
    """
    return _global_monitor


def configure_monitoring(
    enabled: Optional[bool] = None,
    slow_query_threshold: Optional[float] = None,
    log_all_queries: Optional[bool] = None,
    log_slow_queries: Optional[bool] = None,
    collect_statistics: Optional[bool] = None
) -> None:
    """
    Configure global performance monitoring.

    Args:
        enabled: Enable/disable monitoring
        slow_query_threshold: Threshold for slow queries in seconds
        log_all_queries: Log all queries
        log_slow_queries: Log slow queries
        collect_statistics: Collect aggregate statistics

    Examples:
        >>> # Enable monitoring with 0.5s threshold
        >>> configure_monitoring(enabled=True, slow_query_threshold=0.5)

        >>> # Log all queries
        >>> configure_monitoring(log_all_queries=True)

        >>> # Disable monitoring
        >>> configure_monitoring(enabled=False)
    """
    global _global_monitor

    if enabled is not None:
        _global_monitor.enabled = enabled

    if slow_query_threshold is not None:
        _global_monitor.slow_query_threshold = slow_query_threshold

    if log_all_queries is not None:
        _global_monitor.log_all_queries = log_all_queries

    if log_slow_queries is not None:
        _global_monitor.log_slow_queries = log_slow_queries

    if collect_statistics is not None:
        _global_monitor.collect_statistics = collect_statistics


def get_performance_stats() -> Dict[str, Any]:
    """
    Get current performance statistics.

    Returns:
        Dictionary with performance statistics

    Examples:
        >>> stats = get_performance_stats()
        >>> print(f"Average query time: {stats['average_duration']:.3f}s")
    """
    return _global_monitor.get_statistics()


def print_performance_report() -> None:
    """
    Print performance report.

    Examples:
        >>> print_performance_report()
    """
    _global_monitor.print_report()


def reset_performance_stats() -> None:
    """
    Reset performance statistics.

    Examples:
        >>> reset_performance_stats()
    """
    _global_monitor.reset_statistics()
