"""
Tests for Global Connection Feature

Tests the optional global connection functionality introduced in WBORM.
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock


class TestGlobalConnection:
    """Test suite for global connection functionality"""

    def setup_method(self):
        """Reset global connection before each test"""
        import wborm.registry
        wborm.registry._connection = None

    def teardown_method(self):
        """Clean up after each test"""
        import wborm.registry
        wborm.registry._connection = None

    def test_get_global_connection_not_registered(self):
        """Test error when no global connection is registered"""
        from wborm.utils import get_global_connection

        with pytest.raises(RuntimeError) as exc_info:
            get_global_connection()

        assert "Nenhuma conexão global registrada" in str(exc_info.value)

    def test_register_and_get_global_connection(self):
        """Test registering and retrieving global connection"""
        from wborm import register_global_connection, get_global_connection

        # Create mock connection
        mock_conn = Mock()
        mock_conn.db_type = "informix"

        # Register it
        register_global_connection(mock_conn)

        # Retrieve it
        retrieved_conn = get_global_connection()

        assert retrieved_conn is mock_conn

    def test_generate_model_without_conn_not_registered(self):
        """Test generate_model fails without conn when not registered"""
        from wborm.utils import generate_model

        with pytest.raises(RuntimeError) as exc_info:
            generate_model("test_table")

        assert "Nenhuma conexão fornecida" in str(exc_info.value)
        assert "register_global_connection" in str(exc_info.value)

    def test_generate_model_with_global_connection(self):
        """Test generate_model works with global connection"""
        from wborm import register_global_connection
        from wborm.utils import generate_model
        from wborm.introspect import introspect_table

        # Create mock connection
        mock_conn = Mock()
        mock_conn.db_type = "informix"

        # Mock introspect_table to return sample metadata
        def mock_introspect(table_name, conn):
            return [
                {"name": "id", "type": 0, "length": 4},  # INTEGER
                {"name": "name", "type": 13, "length": 50},  # VARCHAR
            ]

        # Patch introspect_table
        import wborm.utils
        original_introspect = wborm.utils.introspect_table
        wborm.utils.introspect_table = mock_introspect

        try:
            # Register global connection
            register_global_connection(mock_conn)

            # Generate model without passing conn
            model = generate_model("test_table", refresh=True, inject_globals=False)

            assert model is not None
            assert model.__tablename__ == "test_table"
            assert model._connection is mock_conn
            assert model._fields["name"].max_length == 50

        finally:
            # Restore original function
            wborm.utils.introspect_table = original_introspect

    def test_generate_model_explicit_conn_overrides_global(self):
        """Test explicit conn parameter overrides global connection"""
        from wborm import register_global_connection
        from wborm.utils import generate_model

        # Create two mock connections
        global_conn = Mock()
        global_conn.db_type = "informix"

        explicit_conn = Mock()
        explicit_conn.db_type = "db2"

        # Mock introspect_table
        def mock_introspect(table_name, conn):
            return [{"name": "id", "type": 0}]

        import wborm.utils
        original_introspect = wborm.utils.introspect_table
        wborm.utils.introspect_table = mock_introspect

        try:
            # Register global connection
            register_global_connection(global_conn)

            # Generate model with explicit connection
            model = generate_model("test_table", explicit_conn, inject_globals=False)

            # Should use explicit connection, not global
            assert model._connection is explicit_conn
            assert model._connection is not global_conn

        finally:
            wborm.utils.introspect_table = original_introspect

    def test_get_model_with_global_connection(self):
        """Test get_model works with global connection"""
        from wborm import register_global_connection, get_model

        mock_conn = Mock()
        mock_conn.db_type = "informix"

        def mock_introspect(table_name, conn):
            return [{"name": "id", "type": 0}]

        import wborm.utils
        original_introspect = wborm.utils.introspect_table
        wborm.utils.introspect_table = mock_introspect

        try:
            register_global_connection(mock_conn)
            model = get_model("test_table")

            assert model is not None
            assert model._connection is mock_conn

        finally:
            wborm.utils.introspect_table = original_introspect

    def test_generate_all_models_without_conn_fails(self):
        """Test generate_all_models fails without conn when not registered"""
        from wborm.utils import generate_all_models

        with pytest.raises(RuntimeError) as exc_info:
            generate_all_models()

        assert "Nenhuma conexão fornecida" in str(exc_info.value)

    def test_generate_all_models_with_global_connection(self):
        """Test generate_all_models works with global connection"""
        from wborm import register_global_connection
        from wborm.utils import generate_all_models

        mock_conn = Mock()
        mock_conn.db_type = "informix"

        # Mock execute_query to return sample tables
        mock_conn.execute_query = Mock(return_value=[
            {"tabname": "customers"},
            {"tabname": "orders"},
        ])

        def mock_introspect(table_name, conn):
            return [{"name": "id", "type": 0}]

        import wborm.utils
        original_introspect = wborm.utils.introspect_table
        wborm.utils.introspect_table = mock_introspect

        try:
            register_global_connection(mock_conn)

            # Should not raise
            models = generate_all_models(verbose=False)

            # Should have generated 2 models
            assert len(models) == 2
            assert "customers" in models
            assert "orders" in models

        finally:
            wborm.utils.introspect_table = original_introspect

    def test_multiple_register_global_connection(self):
        """Test that registering again updates the global connection"""
        from wborm import register_global_connection, get_global_connection

        conn1 = Mock()
        conn1.db_type = "informix"

        conn2 = Mock()
        conn2.db_type = "db2"

        # Register first connection
        register_global_connection(conn1)
        assert get_global_connection() is conn1

        # Register second connection (should override)
        register_global_connection(conn2)
        assert get_global_connection() is conn2
        assert get_global_connection() is not conn1


class TestGlobalConnectionIntegration:
    """Integration tests for global connection"""

    def setup_method(self):
        """Reset global connection before each test"""
        import wborm.registry
        wborm.registry._connection = None

    def teardown_method(self):
        """Clean up after each test"""
        import wborm.registry
        wborm.registry._connection = None

    def test_workflow_register_generate_query(self):
        """Test complete workflow: register -> generate -> query"""
        from wborm import register_global_connection
        from wborm.utils import generate_model
        from wborm.query import QuerySet

        # Create mock connection
        mock_conn = Mock()
        mock_conn.db_type = "informix"

        # Mock introspect
        def mock_introspect(table_name, conn):
            return [
                {"name": "id", "type": 0},
                {"name": "name", "type": 13},
            ]

        import wborm.utils
        original_introspect = wborm.utils.introspect_table
        wborm.utils.introspect_table = mock_introspect

        try:
            # Step 1: Register connection
            register_global_connection(mock_conn)

            # Step 2: Generate model (no conn needed)
            Customer = generate_model("customers", inject_globals=False)

            # Step 3: Create queryset
            qs = QuerySet(Customer, mock_conn)

            # Verify everything is connected
            assert Customer._connection is mock_conn
            assert qs.conn is mock_conn

        finally:
            wborm.utils.introspect_table = original_introspect


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
