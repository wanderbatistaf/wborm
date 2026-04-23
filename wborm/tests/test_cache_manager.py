"""
Unit tests for wborm.cache_manager module
"""
import sys
import os
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wborm.cache_manager import (
    get_or_create_key,
    encrypt_data,
    decrypt_data,
    save_to_cache,
    load_from_cache,
    cache_exists,
    invalidate_cache
)


def test_get_or_create_key():
    """Test key generation and retrieval"""
    key1 = get_or_create_key()
    assert isinstance(key1, bytes)
    assert len(key1) == 44  # Fernet keys are 44 bytes when base64 encoded

    # Second call should return same key
    key2 = get_or_create_key()
    assert key1 == key2

    print("✅ get_or_create_key tests passed")


def test_encrypt_decrypt_data():
    """Test data encryption and decryption"""
    original_data = {
        "name": "test",
        "values": [1, 2, 3],
        "nested": {"key": "value"}
    }

    # Encrypt
    encrypted = encrypt_data(original_data)
    assert isinstance(encrypted, bytes)
    assert encrypted != original_data

    # Decrypt
    decrypted = decrypt_data(encrypted)
    assert decrypted == original_data

    print("✅ encrypt_data and decrypt_data tests passed")


def test_encrypt_decrypt_various_types():
    """Test encryption/decryption with various data types"""
    test_cases = [
        42,
        "string",
        [1, 2, 3],
        {"key": "value"},
        (1, 2, 3),
        True,
        None,
    ]

    for data in test_cases:
        encrypted = encrypt_data(data)
        decrypted = decrypt_data(encrypted)
        assert decrypted == data

    print("✅ Various data types encryption tests passed")


def test_cache_exists():
    """Test cache_exists function"""
    # Test with non-existent table
    exists = cache_exists("nonexistent_table_xyz_123")
    assert exists == False

    print("✅ cache_exists tests passed")


def test_save_and_load_cache():
    """Test saving and loading from cache"""
    test_table = "test_table_xyz_123"
    test_data = {
        "fields": {"id": "int", "name": "str"},
        "relations": {}
    }

    # Save to cache
    save_to_cache(test_table, test_data)

    # Check it exists
    assert cache_exists(test_table) == True

    # Load from cache
    loaded_data = load_from_cache(test_table)
    assert loaded_data == test_data

    # Clean up
    invalidate_cache(test_table)

    print("✅ save_to_cache and load_from_cache tests passed")


def test_invalidate_cache():
    """Test cache invalidation"""
    test_table = "test_invalidate_xyz_123"
    test_data = {"test": "data"}

    # Save, then invalidate
    save_to_cache(test_table, test_data)
    assert cache_exists(test_table) == True

    result = invalidate_cache(test_table)
    assert result == True
    assert cache_exists(test_table) == False

    # Invalidating non-existent cache
    result = invalidate_cache(test_table)
    assert result == False

    print("✅ invalidate_cache tests passed")


def test_load_from_nonexistent_cache():
    """Test loading from non-existent cache"""
    data = load_from_cache("nonexistent_xyz_123")
    assert data is None

    print("✅ load_from_cache (non-existent) tests passed")


def run_all_tests():
    """Run all tests"""
    print("\n🧪 Running cache_manager tests...\n")

    test_get_or_create_key()
    test_encrypt_decrypt_data()
    test_encrypt_decrypt_various_types()
    test_cache_exists()
    test_save_and_load_cache()
    test_invalidate_cache()
    test_load_from_nonexistent_cache()

    print("\n✅ All cache_manager tests passed!\n")


if __name__ == "__main__":
    run_all_tests()
