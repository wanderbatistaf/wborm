"""
Tests for Database Dialect System

Tests the multi-database dialect system (Informix, DB2, Oracle).
"""

import pytest
from wborm.dialects import (
    BaseDialect,
    InformixDialect,
    DB2Dialect,
    OracleDialect,
    get_dialect,
    detect_dialect,
    register_dialect,
)


class TestBaseDialect:
    """Test suite for BaseDialect"""

    def test_base_dialect_initialization(self):
        """Test BaseDialect initialization"""
        dialect = BaseDialect()

        assert dialect.name == "base"
        assert dialect.supports_limit_offset is True
        assert dialect.supports_window_functions is False
        assert dialect.supports_cte is False
        assert dialect.limit_offset_position == "end"

    def test_base_dialect_limit_offset_clause(self):
        """Test base dialect limit/offset clause generation"""
        dialect = BaseDialect()

        # Test with limit only
        clause = dialect.limit_offset_clause(10, None)
        assert clause == "LIMIT 10"

        # Test with limit and offset
        clause = dialect.limit_offset_clause(10, 20)
        assert clause == "LIMIT 10 OFFSET 20"

        # Test with None limit
        clause = dialect.limit_offset_clause(None, 20)
        assert clause == ""

    def test_base_dialect_quote_identifier(self):
        """Test identifier quoting"""
        dialect = BaseDialect()

        quoted = dialect.quote_identifier("table_name")
        assert quoted == '"table_name"'

    def test_base_dialect_supports_feature(self):
        """Test feature support checking"""
        dialect = BaseDialect()

        assert dialect.supports_feature("limit_offset") is True
        assert dialect.supports_feature("window_functions") is False
        assert dialect.supports_feature("cte") is False
        assert dialect.supports_feature("unknown_feature") is False


class TestInformixDialect:
    """Test suite for InformixDialect"""

    def test_informix_dialect_initialization(self):
        """Test InformixDialect initialization"""
        dialect = InformixDialect()

        assert dialect.name == "informix"
        assert dialect.supports_limit_offset is True
        assert dialect.supports_window_functions is True
        assert dialect.supports_cte is True
        assert dialect.limit_offset_position == "start"

    def test_informix_limit_offset_clause(self):
        """Test Informix SKIP/FIRST syntax"""
        dialect = InformixDialect()

        # Test with limit only
        clause = dialect.limit_offset_clause(10, None)
        assert clause == "FIRST 10"

        # Test with limit and offset
        clause = dialect.limit_offset_clause(10, 20)
        assert clause == "SKIP 20 FIRST 10"

        # Test with None limit
        clause = dialect.limit_offset_clause(None, 20)
        assert clause == ""

    def test_informix_type_mapping(self):
        """Test Informix type to Python mapping"""
        dialect = InformixDialect()

        # Test integer types
        assert dialect.map_type_to_python(0) == str  # CHAR
        assert dialect.map_type_to_python(1) == int  # SMALLINT
        assert dialect.map_type_to_python(2) == int  # INTEGER
        assert dialect.map_type_to_python(6) == int  # SERIAL

        # Test float types
        assert dialect.map_type_to_python(3) == float  # FLOAT
        assert dialect.map_type_to_python(5) == float  # DECIMAL

        # Test string types
        assert dialect.map_type_to_python(13) == str  # VARCHAR

        # Test string type names
        assert dialect.map_type_to_python("INTEGER") == int
        assert dialect.map_type_to_python("VARCHAR") == str
        assert dialect.map_type_to_python("DECIMAL") == float

    def test_informix_concat_function(self):
        """Test Informix concatenation"""
        dialect = InformixDialect()

        concat = dialect.concat_function("first_name", "' '", "last_name")
        assert concat == "first_name || ' ' || last_name"

    def test_informix_current_timestamp(self):
        """Test Informix current timestamp"""
        dialect = InformixDialect()

        ts = dialect.current_timestamp()
        assert ts == "CURRENT"


class TestDB2Dialect:
    """Test suite for DB2Dialect"""

    def test_db2_dialect_initialization(self):
        """Test DB2Dialect initialization"""
        dialect = DB2Dialect()

        assert dialect.name == "db2"
        assert dialect.supports_limit_offset is True
        assert dialect.supports_window_functions is True
        assert dialect.supports_cte is True
        assert dialect.limit_offset_position == "end"

    def test_db2_limit_offset_clause(self):
        """Test DB2 OFFSET/FETCH syntax"""
        dialect = DB2Dialect()

        # Test with limit only
        clause = dialect.limit_offset_clause(10, None)
        assert clause == "FETCH FIRST 10 ROWS ONLY"

        # Test with limit and offset
        clause = dialect.limit_offset_clause(10, 20)
        assert clause == "OFFSET 20 ROWS FETCH FIRST 10 ROWS ONLY"

        # Test with None limit
        clause = dialect.limit_offset_clause(None, 20)
        assert clause == ""

    def test_db2_type_mapping(self):
        """Test DB2 type to Python mapping"""
        dialect = DB2Dialect()

        # Test integer types
        assert dialect.map_type_to_python("SMALLINT") == int
        assert dialect.map_type_to_python("INTEGER") == int
        assert dialect.map_type_to_python("BIGINT") == int

        # Test float types
        assert dialect.map_type_to_python("DECIMAL") == float
        assert dialect.map_type_to_python("FLOAT") == float
        assert dialect.map_type_to_python("DOUBLE") == float

        # Test string types
        assert dialect.map_type_to_python("VARCHAR") == str
        assert dialect.map_type_to_python("CHAR") == str
        assert dialect.map_type_to_python("CLOB") == str

        # Test binary types
        assert dialect.map_type_to_python("BLOB") == bytes

    def test_db2_concat_function(self):
        """Test DB2 concatenation"""
        dialect = DB2Dialect()

        concat = dialect.concat_function("first_name", "' '", "last_name")
        assert concat == "first_name || ' ' || last_name"


class TestOracleDialect:
    """Test suite for OracleDialect"""

    def test_oracle_dialect_initialization(self):
        """Test OracleDialect initialization"""
        dialect = OracleDialect()

        assert dialect.name == "oracle"
        assert dialect.supports_limit_offset is True
        assert dialect.supports_window_functions is True
        assert dialect.supports_cte is True
        assert dialect.limit_offset_position == "end"

    def test_oracle_limit_offset_clause(self):
        """Test Oracle OFFSET/FETCH syntax"""
        dialect = OracleDialect()

        # Test with limit only
        clause = dialect.limit_offset_clause(10, None)
        assert clause == "FETCH FIRST 10 ROWS ONLY"

        # Test with limit and offset
        clause = dialect.limit_offset_clause(10, 20)
        assert clause == "OFFSET 20 ROWS FETCH FIRST 10 ROWS ONLY"

        # Test with None limit
        clause = dialect.limit_offset_clause(None, 20)
        assert clause == ""

    def test_oracle_type_mapping(self):
        """Test Oracle type to Python mapping"""
        dialect = OracleDialect()

        # Test numeric types
        assert dialect.map_type_to_python("NUMBER") == float
        assert dialect.map_type_to_python("INTEGER") == int
        assert dialect.map_type_to_python("FLOAT") == float

        # Test string types
        assert dialect.map_type_to_python("VARCHAR2") == str
        assert dialect.map_type_to_python("CHAR") == str
        assert dialect.map_type_to_python("CLOB") == str

        # Test binary types
        assert dialect.map_type_to_python("BLOB") == bytes
        assert dialect.map_type_to_python("RAW") == bytes

    def test_oracle_concat_function(self):
        """Test Oracle concatenation"""
        dialect = OracleDialect()

        concat = dialect.concat_function("first_name", "' '", "last_name")
        assert concat == "first_name || ' ' || last_name"

    def test_oracle_current_timestamp(self):
        """Test Oracle current timestamp"""
        dialect = OracleDialect()

        ts = dialect.current_timestamp()
        assert ts == "SYSTIMESTAMP"

    def test_oracle_substring_function(self):
        """Test Oracle SUBSTR function"""
        dialect = OracleDialect()

        # With length
        substr = dialect.substring_function("name", 1, 5)
        assert substr == "SUBSTR(name, 1, 5)"

        # Without length
        substr = dialect.substring_function("name", 1)
        assert substr == "SUBSTR(name, 1)"

    def test_oracle_date_add(self):
        """Test Oracle date addition"""
        dialect = OracleDialect()

        # Add days
        date_expr = dialect.date_add("hire_date", 30, "DAY")
        assert date_expr == "hire_date + INTERVAL '30' DAY"

        # Add months
        date_expr = dialect.date_add("hire_date", 1, "MONTH")
        assert date_expr == "hire_date + INTERVAL '1' MONTH"

    def test_oracle_supports_returning(self):
        """Test Oracle RETURNING clause support"""
        dialect = OracleDialect()

        assert dialect.supports_returning() is True


class TestDialectRegistry:
    """Test suite for dialect registry functions"""

    def test_get_dialect_informix(self):
        """Test getting Informix dialect"""
        dialect = get_dialect("informix")

        assert isinstance(dialect, InformixDialect)
        assert dialect.name == "informix"

    def test_get_dialect_db2(self):
        """Test getting DB2 dialect"""
        dialect = get_dialect("db2")

        assert isinstance(dialect, DB2Dialect)
        assert dialect.name == "db2"

    def test_get_dialect_oracle(self):
        """Test getting Oracle dialect"""
        dialect = get_dialect("oracle")

        assert isinstance(dialect, OracleDialect)
        assert dialect.name == "oracle"

    def test_get_dialect_case_insensitive(self):
        """Test dialect lookup is case-insensitive"""
        dialect1 = get_dialect("INFORMIX")
        dialect2 = get_dialect("Informix")
        dialect3 = get_dialect("informix")

        assert all(isinstance(d, InformixDialect) for d in [dialect1, dialect2, dialect3])

    def test_get_dialect_unknown(self):
        """Test error for unknown dialect"""
        with pytest.raises(ValueError) as exc_info:
            get_dialect("mysql")

        assert "Unsupported database type: mysql" in str(exc_info.value)

    def test_detect_dialect_with_db_type(self):
        """Test dialect detection from connection with db_type"""
        from unittest.mock import Mock

        mock_conn = Mock()
        mock_conn.db_type = "db2"

        dialect = detect_dialect(mock_conn)

        assert isinstance(dialect, DB2Dialect)

    def test_detect_dialect_from_conn_str(self):
        """Test dialect detection from connection string"""
        from unittest.mock import Mock

        # Test Oracle detection
        mock_conn = Mock()
        mock_conn._conn_str = "jdbc:oracle:thin:@localhost:1521:XE"
        delattr(mock_conn, "db_type")

        dialect = detect_dialect(mock_conn)

        assert isinstance(dialect, OracleDialect)

    def test_detect_dialect_default(self):
        """Test default dialect when detection fails"""
        from unittest.mock import Mock

        mock_conn = Mock()
        # Remove db_type and _conn_str
        delattr(mock_conn, "db_type")

        dialect = detect_dialect(mock_conn)

        # Should default to Informix
        assert isinstance(dialect, InformixDialect)

    def test_register_custom_dialect(self):
        """Test registering a custom dialect"""

        class CustomDialect(BaseDialect):
            def __init__(self):
                super().__init__()
                self.name = "custom"

            def map_type_to_python(self, db_type):
                return str

        # Register custom dialect
        register_dialect("custom", CustomDialect)

        # Should be able to get it
        dialect = get_dialect("custom")

        assert isinstance(dialect, CustomDialect)
        assert dialect.name == "custom"


class TestDialectComparison:
    """Compare dialects to ensure they follow the same interface"""

    def test_all_dialects_have_name(self):
        """Test all dialects have a name"""
        dialects = [InformixDialect(), DB2Dialect(), OracleDialect()]

        for dialect in dialects:
            assert hasattr(dialect, "name")
            assert isinstance(dialect.name, str)
            assert len(dialect.name) > 0

    def test_all_dialects_have_limit_offset_clause(self):
        """Test all dialects implement limit_offset_clause"""
        dialects = [InformixDialect(), DB2Dialect(), OracleDialect()]

        for dialect in dialects:
            # Should not raise
            clause = dialect.limit_offset_clause(10, 20)
            assert isinstance(clause, str)

    def test_all_dialects_have_type_mapping(self):
        """Test all dialects implement map_type_to_python"""
        dialects = [InformixDialect(), DB2Dialect(), OracleDialect()]

        for dialect in dialects:
            # Should not raise
            py_type = dialect.map_type_to_python("VARCHAR")
            assert py_type is not None

    def test_limit_offset_position_consistency(self):
        """Test limit_offset_position is consistent with syntax"""
        # Informix uses SKIP/FIRST after SELECT
        informix = InformixDialect()
        assert informix.limit_offset_position == "start"
        assert "SKIP" in informix.limit_offset_clause(10, 20)

        # DB2 uses OFFSET/FETCH at end
        db2 = DB2Dialect()
        assert db2.limit_offset_position == "end"
        assert "FETCH FIRST" in db2.limit_offset_clause(10, None)

        # Oracle uses OFFSET/FETCH at end
        oracle = OracleDialect()
        assert oracle.limit_offset_position == "end"
        assert "FETCH FIRST" in oracle.limit_offset_clause(10, None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
