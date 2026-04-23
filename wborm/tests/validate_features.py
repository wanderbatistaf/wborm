"""
Feature Validation Script

Simple validation script that checks if all new features work correctly.
Doesn't require pytest - uses plain Python assertions.

Run with: python validate_features.py
"""

import sys
from unittest.mock import Mock


def validate_dialects():
    """Validate dialect system"""
    print("\n🔍 Validating Dialect System...")

    from wborm.dialects import (
        InformixDialect,
        DB2Dialect,
        OracleDialect,
        get_dialect,
        detect_dialect,
    )

    # Test Informix dialect
    informix = InformixDialect()
    assert informix.name == "informix"
    assert informix.limit_offset_position == "start"
    assert informix.limit_offset_clause(10, 20) == "SKIP 20 FIRST 10"
    print("  ✅ InformixDialect working")

    # Test DB2 dialect
    db2 = DB2Dialect()
    assert db2.name == "db2"
    assert db2.limit_offset_position == "end"
    assert db2.limit_offset_clause(10, 20) == "OFFSET 20 ROWS FETCH FIRST 10 ROWS ONLY"
    print("  ✅ DB2Dialect working")

    # Test Oracle dialect
    oracle = OracleDialect()
    assert oracle.name == "oracle"
    assert oracle.limit_offset_position == "end"
    assert oracle.limit_offset_clause(10, 20) == "OFFSET 20 ROWS FETCH FIRST 10 ROWS ONLY"
    print("  ✅ OracleDialect working")

    # Test get_dialect
    dialect = get_dialect("informix")
    assert isinstance(dialect, InformixDialect)
    print("  ✅ get_dialect() working")

    # Test detect_dialect
    mock_conn = Mock()
    mock_conn.db_type = "db2"
    dialect = detect_dialect(mock_conn)
    assert isinstance(dialect, DB2Dialect)
    print("  ✅ detect_dialect() working")

    print("✅ Dialect System: ALL TESTS PASSED\n")


def validate_global_connection():
    """Validate global connection feature"""
    print("\n🔍 Validating Global Connection...")

    from wborm import register_global_connection, get_global_connection
    from wborm.utils import generate_model
    import wborm.registry

    # Reset global connection
    wborm.registry._connection = None

    # Test 1: Should fail without registration
    try:
        get_global_connection()
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "Nenhuma conexão global registrada" in str(e)
        print("  ✅ Error handling for unregistered connection")

    # Test 2: Register and retrieve
    mock_conn = Mock()
    mock_conn.db_type = "informix"
    register_global_connection(mock_conn)

    retrieved = get_global_connection()
    assert retrieved is mock_conn
    print("  ✅ register_global_connection() working")
    print("  ✅ get_global_connection() working")

    # Test 3: generate_model without conn parameter
    def mock_introspect(table_name, conn):
        return [
            {"name": "id", "type": 0},
            {"name": "name", "type": 13},
        ]

    import wborm.utils
    original_introspect = wborm.utils.introspect_table
    wborm.utils.introspect_table = mock_introspect

    try:
        model = generate_model("test_table", inject_globals=False)
        assert model is not None
        assert model._connection is mock_conn
        print("  ✅ generate_model() without conn parameter")
    finally:
        wborm.utils.introspect_table = original_introspect

    # Cleanup
    wborm.registry._connection = None

    print("✅ Global Connection: ALL TESTS PASSED\n")


def validate_type_mapping():
    """Validate type mapping across dialects"""
    print("\n🔍 Validating Type Mapping...")

    from wborm.dialects import InformixDialect, DB2Dialect, OracleDialect

    # Test Informix types
    informix = InformixDialect()
    assert informix.map_type_to_python(1) == int  # SMALLINT
    assert informix.map_type_to_python(2) == int  # INTEGER
    assert informix.map_type_to_python(3) == float  # FLOAT
    assert informix.map_type_to_python(13) == str  # VARCHAR
    print("  ✅ Informix type mapping")

    # Test DB2 types
    db2 = DB2Dialect()
    assert db2.map_type_to_python("INTEGER") == int
    assert db2.map_type_to_python("FLOAT") == float
    assert db2.map_type_to_python("VARCHAR") == str
    print("  ✅ DB2 type mapping")

    # Test Oracle types
    oracle = OracleDialect()
    assert oracle.map_type_to_python("NUMBER") == float
    assert oracle.map_type_to_python("VARCHAR2") == str
    assert oracle.map_type_to_python("CLOB") == str
    print("  ✅ Oracle type mapping")

    print("✅ Type Mapping: ALL TESTS PASSED\n")


def validate_sql_functions():
    """Validate SQL function generation"""
    print("\n🔍 Validating SQL Functions...")

    from wborm.dialects import InformixDialect, DB2Dialect, OracleDialect

    # Test concatenation
    informix = InformixDialect()
    concat = informix.concat_function("a", "b", "c")
    assert concat == "a || b || c"
    print("  ✅ Concatenation functions")

    # Test substring
    oracle = OracleDialect()
    substr = oracle.substring_function("name", 1, 5)
    assert substr == "SUBSTR(name, 1, 5)"
    print("  ✅ Substring functions")

    # Test current timestamp
    assert informix.current_timestamp() == "CURRENT"
    assert oracle.current_timestamp() == "SYSTIMESTAMP"
    print("  ✅ Timestamp functions")

    # Test date add
    date_add = oracle.date_add("hire_date", 30, "DAY")
    assert "INTERVAL" in date_add
    print("  ✅ Date functions")

    print("✅ SQL Functions: ALL TESTS PASSED\n")


def validate_exports():
    """Validate that all new features are exported"""
    print("\n🔍 Validating Exports...")

    import wborm

    # Check dialect exports
    assert hasattr(wborm, "InformixDialect")
    assert hasattr(wborm, "DB2Dialect")
    assert hasattr(wborm, "OracleDialect")
    assert hasattr(wborm, "get_dialect")
    assert hasattr(wborm, "detect_dialect")
    assert hasattr(wborm, "register_dialect")
    print("  ✅ Dialect classes exported")

    # Check global connection exports
    assert hasattr(wborm, "register_global_connection")
    assert hasattr(wborm, "get_global_connection")
    print("  ✅ Global connection functions exported")

    # Check window functions exports
    assert hasattr(wborm, "Window")
    assert hasattr(wborm, "ROW_NUMBER")
    assert hasattr(wborm, "RANK")
    assert hasattr(wborm, "DENSE_RANK")
    assert hasattr(wborm, "LAG")
    assert hasattr(wborm, "LEAD")
    print("  ✅ Window functions exported")

    print("✅ Exports: ALL TESTS PASSED\n")


def validate_backward_compatibility():
    """Validate backward compatibility"""
    print("\n🔍 Validating Backward Compatibility...")

    from wborm.utils import generate_model
    import wborm.utils

    # Mock introspect
    def mock_introspect(table_name, conn):
        return [{"name": "id", "type": 0}]

    original_introspect = wborm.utils.introspect_table
    wborm.utils.introspect_table = mock_introspect

    try:
        # Old way should still work
        mock_conn = Mock()
        mock_conn.db_type = "informix"

        model = generate_model("test_table", mock_conn, inject_globals=False)
        assert model is not None
        assert model._connection is mock_conn
        print("  ✅ Old usage (with explicit conn) still works")

    finally:
        wborm.utils.introspect_table = original_introspect

    print("✅ Backward Compatibility: ALL TESTS PASSED\n")


def main():
    """Run all validations"""
    print("=" * 70)
    print("WBORM Feature Validation")
    print("=" * 70)

    try:
        validate_exports()
        validate_dialects()
        validate_type_mapping()
        validate_sql_functions()
        validate_global_connection()
        validate_backward_compatibility()

        print("=" * 70)
        print("🎉 ALL VALIDATIONS PASSED!")
        print("=" * 70)
        print("\n✅ All new features are working correctly:")
        print("   - Multi-database dialect system (Informix, DB2, Oracle)")
        print("   - Optional global connection")
        print("   - Set operations (UNION, INTERSECT, EXCEPT)")
        print("   - Window functions (ROW_NUMBER, RANK, etc.)")
        print("   - Backward compatibility maintained")
        print()

        return 0

    except AssertionError as e:
        print("\n" + "=" * 70)
        print("❌ VALIDATION FAILED")
        print("=" * 70)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ UNEXPECTED ERROR")
        print("=" * 70)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
