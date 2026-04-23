#!/usr/bin/env python3
"""
Test runner for WBORM utility modules
Run all unit tests without requiring pytest
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import test modules
from wborm.tests import test_type_mapper, test_file_utils, test_cache_manager


def main():
    """Run all test suites"""
    print("\n" + "="*60)
    print("🧪 WBORM Utility Modules Test Suite")
    print("="*60)

    failed = False

    try:
        test_type_mapper.run_all_tests()
    except Exception as e:
        print(f"❌ test_type_mapper failed: {e}")
        failed = True

    try:
        test_file_utils.run_all_tests()
    except Exception as e:
        print(f"❌ test_file_utils failed: {e}")
        failed = True

    try:
        test_cache_manager.run_all_tests()
    except Exception as e:
        print(f"❌ test_cache_manager failed: {e}")
        failed = True

    print("="*60)
    if not failed:
        print("✅ ALL TEST SUITES PASSED!")
        print("="*60 + "\n")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("="*60 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
