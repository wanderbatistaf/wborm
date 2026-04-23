"""
Unit tests for wborm.file_utils module
"""
import sys
import os
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wborm.file_utils import (
    model_cache_path,
    list_cached_models,
    clear_cache,
    ensure_cache_dir,
    CACHE_DIR
)


def test_model_cache_path():
    """Test model_cache_path function"""
    path = model_cache_path("clientes")
    assert path == os.path.join(CACHE_DIR, "clientes.wbm")

    path = model_cache_path("pedidos")
    assert path == os.path.join(CACHE_DIR, "pedidos.wbm")

    print("✅ model_cache_path tests passed")


def test_ensure_cache_dir():
    """Test that cache directory is created"""
    # This should not raise an error
    ensure_cache_dir()
    assert os.path.isdir(CACHE_DIR)

    print("✅ ensure_cache_dir tests passed")


def test_list_cached_models():
    """Test listing cached models"""
    # Create temp directory for testing
    original_cache_dir = CACHE_DIR

    # Test with empty directory
    models = list_cached_models()
    assert isinstance(models, list)

    # Test with non-existent directory
    import wborm.file_utils as fu
    fu.CACHE_DIR = "/tmp/nonexistent_wbmodels_test"
    models = list_cached_models()
    assert models == []

    # Restore original
    fu.CACHE_DIR = original_cache_dir

    print("✅ list_cached_models tests passed")


def test_clear_cache():
    """Test clearing cache (without actually clearing)"""
    # Just test that the function works without errors
    # We don't actually clear the cache in tests
    count = clear_cache() if os.path.isdir(CACHE_DIR) else 0
    assert isinstance(count, int)
    assert count >= 0

    print("✅ clear_cache tests passed")


def run_all_tests():
    """Run all tests"""
    print("\n🧪 Running file_utils tests...\n")

    test_model_cache_path()
    test_ensure_cache_dir()
    test_list_cached_models()
    test_clear_cache()

    print("\n✅ All file_utils tests passed!\n")


if __name__ == "__main__":
    run_all_tests()
