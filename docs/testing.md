# Testing Guide

Complete guide for testing WBORM.

---

## Table of Contents

1. [Overview](#overview)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Running Tests](#running-tests)
5. [Test Coverage](#test-coverage)
6. [Test Structure](#test-structure)
7. [Writing Tests](#writing-tests)

---

## Overview

WBORM has a comprehensive test suite covering:

- ✅ **Core Features**: Model generation, queries, field mapping
- ✅ **Performance Features**: Caching, lazy loading, pagination
- ✅ **Multi-Database**: Dialect system (Informix, DB2, Oracle)
- ✅ **Global Connection**: Optional global connection feature
- ✅ **Window Functions**: ROW_NUMBER, RANK, LAG, LEAD
- ✅ **Set Operations**: UNION, INTERSECT, EXCEPT

**Test Coverage**: ~90%+

---

## Requirements

### Python Version
- Python 3.8+

### Dependencies

Install test dependencies:

```bash
pip install -r requirements-dev.txt
```

Or manually:

```bash
pip install pytest pytest-cov pytest-mock unittest-mock tabulate termcolor tqdm colorama
```

### Core Dependencies

```bash
pip install jaydebeapi tabulate termcolor tqdm colorama cryptography
```

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/wanderbatistaf/wbormC.git
cd wbormC
```

### 2. Install Dependencies

```bash
# Install core dependencies
pip install -r requirements.txt

# Install test dependencies
pip install -r requirements-dev.txt
```

### 3. Verify Installation

```bash
python -c "import wborm; print(wborm.__version__)"
```

---

## Running Tests

### Run All Tests

```bash
# Using pytest (recommended)
pytest

# With verbose output
pytest -v

# With coverage report
pytest --cov=wborm --cov-report=html
```

### Run Specific Test Files

```bash
# Test global connection
pytest wborm/tests/test_global_connection.py -v

# Test dialects
pytest wborm/tests/test_dialects.py -v

# Test cache system
pytest wborm/tests/test_cache_config.py -v
```

### Run Specific Test Classes

```bash
# Test a specific class
pytest wborm/tests/test_dialects.py::TestInformixDialect -v

# Test a specific method
pytest wborm/tests/test_dialects.py::TestInformixDialect::test_informix_limit_offset_clause -v
```

### Run Validation Script

For a quick validation without pytest:

```bash
python wborm/tests/validate_features.py
```

This runs basic checks on all new features.

---

## Test Coverage

### Current Coverage

| Module | Coverage |
|--------|----------|
| **wborm/dialects/** | ~95% |
| **wborm/utils.py** | ~90% |
| **wborm/cache_config.py** | ~92% |
| **wborm/pagination.py** | ~88% |
| **wborm/performance.py** | ~90% |
| **wborm/query_optimizer.py** | ~85% |

### Generate Coverage Report

```bash
# HTML report
pytest --cov=wborm --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Terminal Coverage Report

```bash
pytest --cov=wborm --cov-report=term-missing
```

---

## Test Structure

### Test Directory Layout

```
wborm/tests/
├── __init__.py
├── test_type_mapper.py          # Core Refactoring: Type mapping
├── test_file_utils.py            # Core Refactoring: File utilities
├── test_cache_manager.py         # Core Refactoring: Cache management
├── test_cache_config.py          # Performance: Cache configuration
├── test_dialects.py              # Multi-Database Support: Dialect system
├── test_global_connection.py     # Multi-Database Support: Global connection
└── validate_features.py          # Quick validation script
```

### Test Files

#### 1. **test_type_mapper.py**
Tests type mapping from database types to Python types.

```python
def test_map_informix_integer():
    """Test Informix INTEGER → Python int"""
    result = map_coltype_to_python(2)  # Informix INTEGER
    assert result == int
```

#### 2. **test_file_utils.py**
Tests file operations (cache directory, model storage).

```python
def test_get_cache_dir():
    """Test cache directory creation"""
    cache_dir = get_cache_dir()
    assert os.path.exists(cache_dir)
    assert cache_dir.endswith(".wbmodels")
```

#### 3. **test_cache_manager.py**
Tests cache backends (Memory, LRU, Disk).

```python
def test_lru_cache_eviction():
    """Test LRU cache evicts oldest items"""
    cache = LRUCacheBackend(max_size=2)
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")  # Should evict key1

    assert cache.get("key1") is None
    assert cache.get("key2") == "value2"
    assert cache.get("key3") == "value3"
```

#### 4. **test_cache_config.py**
Tests cache configuration API.

```python
def test_configure_cache():
    """Test global cache configuration"""
    configure_cache(
        enabled=True,
        backend=MemoryCacheBackend(),
        default_ttl=300
    )

    config = get_cache_config()
    assert config.enabled is True
    assert config.default_ttl == 300
```

#### 5. **test_dialects.py**
Tests multi-database dialect system.

```python
def test_informix_limit_offset_clause():
    """Test Informix SKIP/FIRST syntax"""
    dialect = InformixDialect()

    clause = dialect.limit_offset_clause(10, 20)
    assert clause == "SKIP 20 FIRST 10"
```

#### 6. **test_global_connection.py**
Tests optional global connection feature.

```python
def test_register_and_get_global_connection():
    """Test registering and retrieving global connection"""
    register_global_connection(mock_conn)

    retrieved = get_global_connection()
    assert retrieved is mock_conn
```

#### 7. **validate_features.py**
Quick validation script for all new features.

```python
python wborm/tests/validate_features.py
```

Validates:
- ✅ Dialect system
- ✅ Global connection
- ✅ Type mapping
- ✅ SQL functions
- ✅ Exports
- ✅ Backward compatibility

---

## Writing Tests

### Test Template

```python
"""
Test Module Name

Brief description of what this module tests.
"""

import pytest
from unittest.mock import Mock


class TestFeatureName:
    """Test suite for FeatureName"""

    def setup_method(self):
        """Setup before each test"""
        # Reset state, create mocks, etc.
        pass

    def teardown_method(self):
        """Cleanup after each test"""
        # Clean up resources
        pass

    def test_basic_functionality(self):
        """Test basic functionality works"""
        # Arrange
        expected = "expected value"

        # Act
        result = function_to_test()

        # Assert
        assert result == expected

    def test_error_handling(self):
        """Test error conditions"""
        with pytest.raises(ValueError) as exc_info:
            function_that_should_raise()

        assert "error message" in str(exc_info.value)
```

### Best Practices

#### 1. **Use Descriptive Names**

```python
# ✅ Good
def test_global_connection_fails_without_registration():
    ...

# ❌ Bad
def test_conn():
    ...
```

#### 2. **Follow AAA Pattern**

```python
def test_cache_get_and_set():
    # Arrange
    cache = MemoryCacheBackend()
    key = "test_key"
    value = "test_value"

    # Act
    cache.set(key, value)
    result = cache.get(key)

    # Assert
    assert result == value
```

#### 3. **Use Fixtures for Common Setup**

```python
@pytest.fixture
def mock_connection():
    """Create mock database connection"""
    conn = Mock()
    conn.db_type = "informix"
    return conn

def test_with_fixture(mock_connection):
    """Test using fixture"""
    model = generate_model("table", mock_connection)
    assert model._connection is mock_connection
```

#### 4. **Test Edge Cases**

```python
def test_limit_offset_with_none_limit():
    """Test when limit is None"""
    dialect = InformixDialect()
    clause = dialect.limit_offset_clause(None, 20)
    assert clause == ""  # Should return empty string

def test_limit_offset_with_none_offset():
    """Test when offset is None"""
    dialect = InformixDialect()
    clause = dialect.limit_offset_clause(10, None)
    assert clause == "FIRST 10"  # Should handle None offset
```

#### 5. **Use Mocks for External Dependencies**

```python
from unittest.mock import Mock, patch

def test_generate_model_with_mock_introspect():
    """Test model generation with mocked introspection"""

    # Mock the introspect_table function
    with patch('wborm.utils.introspect_table') as mock_introspect:
        mock_introspect.return_value = [
            {"name": "id", "type": 0},
            {"name": "name", "type": 13},
        ]

        model = generate_model("test_table", mock_conn)

        assert model is not None
        mock_introspect.assert_called_once()
```

---

## Continuous Integration

### GitHub Actions

Tests run automatically on every push and pull request.

See `.github/workflows/ci.yml`:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run tests
        run: pytest --cov=wborm --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## Test Database Setup

### Informix Test Database

For integration tests with real Informix database:

```bash
# Start Informix Docker container
docker run -d \
  --name informix \
  -p 9088:9088 \
  -p 9089:9089 \
  -e LICENSE=accept \
  ibmcom/informix-developer-database:latest

# Wait for database to be ready
sleep 30

# Run tests
pytest wborm/tests/test_integration.py
```

### DB2 Test Database

```bash
# Start DB2 Docker container
docker run -d \
  --name db2 \
  -p 50000:50000 \
  -e LICENSE=accept \
  -e DB2INST1_PASSWORD=password \
  ibmcom/db2:latest
```

### Oracle Test Database

```bash
# Start Oracle Docker container
docker run -d \
  --name oracle \
  -p 1521:1521 \
  -e ORACLE_PWD=password \
  container-registry.oracle.com/database/express:latest
```

---

## Debugging Tests

### Run Tests with Debugging

```bash
# Stop on first failure
pytest -x

# Drop into debugger on failure
pytest --pdb

# Show local variables on failure
pytest -l

# Verbose output
pytest -vv
```

### Using Python Debugger

```python
def test_something():
    import pdb; pdb.set_trace()  # Add breakpoint

    result = function_to_test()
    assert result == expected
```

---

## Test Environment Variables

Set these environment variables for tests:

```bash
# Informix
export INFORMIX_HOST=localhost
export INFORMIX_PORT=9088
export INFORMIX_DATABASE=stores_demo
export INFORMIX_USER=informix
export INFORMIX_PASSWORD=informix

# DB2
export DB2_HOST=localhost
export DB2_PORT=50000
export DB2_DATABASE=testdb
export DB2_USER=db2inst1
export DB2_PASSWORD=password

# Oracle
export ORACLE_HOST=localhost
export ORACLE_PORT=1521
export ORACLE_DATABASE=XE
export ORACLE_USER=system
export ORACLE_PASSWORD=password
```

---

## Common Issues

### Issue 1: Import Errors

**Problem**: `ModuleNotFoundError: No module named 'wborm'`

**Solution**:
```bash
# Add project root to PYTHONPATH
export PYTHONPATH=/path/to/wbormC:$PYTHONPATH

# Or install in development mode
pip install -e .
```

### Issue 2: Missing Dependencies

**Problem**: `ModuleNotFoundError: No module named 'pytest'`

**Solution**:
```bash
pip install pytest pytest-cov pytest-mock
```

### Issue 3: Connection Errors

**Problem**: Tests fail with connection errors

**Solution**:
- Ensure test database is running
- Check environment variables
- Verify network connectivity
- Use mock connections for unit tests

---

## Summary

**To run all tests:**
```bash
pip install -r requirements-dev.txt
pytest --cov=wborm
```

**For quick validation:**
```bash
python wborm/tests/validate_features.py
```

**For coverage report:**
```bash
pytest --cov=wborm --cov-report=html
open htmlcov/index.html
```

---

## Next Steps

- [Contributing Guide](https://github.com/wanderbatistaf/wborm/blob/main/CONTRIBUTING.md) - How to contribute
- [Project Summary](https://github.com/wanderbatistaf/wborm/blob/main/PROJECT_SUMMARY.md) - Complete overview
- [Documentation Index](index.md) - All documentation

---

**Need help?** → [GitHub Issues](https://github.com/wanderbatistaf/wbormC/issues)
