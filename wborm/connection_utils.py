"""Compatibility helpers for connection APIs from wbjdbc and test doubles."""

from wborm.exceptions import ORMConcurrencyError, ORMDatabaseError


def can_use_execute_batch(connection):
    if not hasattr(connection, "execute_batch"):
        return False
    return connection.__class__.__name__ != "OptimizedJDBCConnection"


def _call_with_optional_params(fn, sql, params=None):
    if params:
        try:
            return fn(sql, params)
        except TypeError:
            return fn(sql)
    return fn(sql)


def _normalize_db_exception(exc):
    message = str(exc)
    lowered = message.lower()
    if "unique constraint" in lowered or "duplicate value" in lowered:
        return ORMConcurrencyError(message)
    return ORMDatabaseError(message)


def run_query(connection, sql, params=None):
    try:
        if hasattr(connection, "execute_query"):
            return _call_with_optional_params(connection.execute_query, sql, params)
        cursor = getattr(connection, "cursor", None)
        if cursor and hasattr(cursor, "execute"):
            result = _call_with_optional_params(cursor.execute, sql, params)
            return result
    except Exception as exc:
        raise _normalize_db_exception(exc) from exc
    raise AttributeError("Connection does not support query execution")


def execute_sql(connection, sql, params=None):
    try:
        if hasattr(connection, "execute"):
            return _call_with_optional_params(connection.execute, sql, params)
        if hasattr(connection, "execute_query"):
            return _call_with_optional_params(connection.execute_query, sql, params)
        cursor = getattr(connection, "cursor", None)
        if cursor and hasattr(cursor, "execute"):
            return _call_with_optional_params(cursor.execute, sql, params)
    except Exception as exc:
        raise _normalize_db_exception(exc) from exc
    raise AttributeError("Connection does not support SQL execution")


def begin_transaction(connection):
    return execute_sql(connection, "BEGIN WORK")


def commit_transaction(connection):
    if hasattr(connection, "commit"):
        return connection.commit()
    return execute_sql(connection, "COMMIT WORK")


def rollback_transaction(connection):
    if hasattr(connection, "rollback"):
        try:
            return connection.rollback()
        except Exception as exc:
            if "Not in transaction" in str(exc):
                return None
            raise
    return execute_sql(connection, "ROLLBACK WORK")
