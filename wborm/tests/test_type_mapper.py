"""
Unit tests for wborm.type_mapper module
"""
import sys
import os
from datetime import date, datetime
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wborm.type_mapper import map_coltype_to_python, get_python_type_name, INFORMIX_TYPE_MAP


def test_map_coltype_int_codes():
    """Test mapping of Informix integer type codes"""
    # Test CHAR (0) -> str
    assert map_coltype_to_python(0) == str

    # Test SMALLINT (1) -> int
    assert map_coltype_to_python(1) == int

    # Test INTEGER (2) -> int
    assert map_coltype_to_python(2) == int

    # Test FLOAT (3) -> float
    assert map_coltype_to_python(3) == float

    # Test DECIMAL (5) -> Decimal
    assert map_coltype_to_python(5) == Decimal

    # Test DATE (7) -> date
    assert map_coltype_to_python(7) == date

    # Test DATETIME (10) -> datetime
    assert map_coltype_to_python(10) == datetime

    # Test VARCHAR (13) -> str
    assert map_coltype_to_python(13) == str

    print("✅ Integer type code mapping tests passed")


def test_map_coltype_string_names():
    """Test mapping of string type names"""
    # Integer types
    assert map_coltype_to_python("SMALLINT") == int
    assert map_coltype_to_python("INTEGER") == int
    assert map_coltype_to_python("INT8") == int
    assert map_coltype_to_python("SERIAL") == int
    assert map_coltype_to_python("SERIAL8") == int

    # Float types
    assert map_coltype_to_python("FLOAT") == float
    assert map_coltype_to_python("SMALLFLOAT") == float
    assert map_coltype_to_python("REAL") == float
    assert map_coltype_to_python("DECIMAL") == Decimal
    assert map_coltype_to_python("MONEY") == Decimal

    # String types
    assert map_coltype_to_python("VARCHAR") == str
    assert map_coltype_to_python("CHAR") == str
    assert map_coltype_to_python("DATE") == date
    assert map_coltype_to_python("DATETIME") == datetime

    # Boolean type
    assert map_coltype_to_python("BOOLEAN") == bool

    # Binary type
    assert map_coltype_to_python("BLOB") == bytes

    print("✅ String type name mapping tests passed")


def test_map_coltype_case_insensitive():
    """Test that string type mapping is case-insensitive"""
    assert map_coltype_to_python("varchar") == str
    assert map_coltype_to_python("VARCHAR") == str
    assert map_coltype_to_python("VarChar") == str

    print("✅ Case-insensitive mapping tests passed")


def test_map_coltype_unknown_defaults_to_str():
    """Test that unknown types default to str"""
    assert map_coltype_to_python("UNKNOWN_TYPE") == str
    assert map_coltype_to_python(999) == str

    print("✅ Unknown type default tests passed")


def test_get_python_type_name():
    """Test getting Python type names as strings"""
    assert get_python_type_name(int) == "int"
    assert get_python_type_name(str) == "str"
    assert get_python_type_name(float) == "float"
    assert get_python_type_name(bool) == "bool"

    print("✅ Python type name tests passed")


def test_informix_type_map_reference():
    """Test that INFORMIX_TYPE_MAP is complete"""
    assert "SMALLINT" in INFORMIX_TYPE_MAP
    assert "VARCHAR" in INFORMIX_TYPE_MAP
    assert "FLOAT" in INFORMIX_TYPE_MAP
    assert "BOOLEAN" in INFORMIX_TYPE_MAP
    assert "DATE" in INFORMIX_TYPE_MAP

    # Check some mappings
    assert INFORMIX_TYPE_MAP["SMALLINT"] == int
    assert INFORMIX_TYPE_MAP["VARCHAR"] == str
    assert INFORMIX_TYPE_MAP["FLOAT"] == float
    assert INFORMIX_TYPE_MAP["BOOLEAN"] == bool
    assert INFORMIX_TYPE_MAP["DECIMAL"] == Decimal
    assert INFORMIX_TYPE_MAP["DATE"] == date

    print("✅ INFORMIX_TYPE_MAP reference tests passed")


def run_all_tests():
    """Run all tests"""
    print("\n🧪 Running type_mapper tests...\n")

    test_map_coltype_int_codes()
    test_map_coltype_string_names()
    test_map_coltype_case_insensitive()
    test_map_coltype_unknown_defaults_to_str()
    test_get_python_type_name()
    test_informix_type_map_reference()

    print("\n✅ All type_mapper tests passed!\n")


if __name__ == "__main__":
    run_all_tests()
