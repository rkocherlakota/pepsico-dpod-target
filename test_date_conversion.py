#!/usr/bin/env python3
"""
Test script to verify date conversion functionality
"""

import sys
import os
sys.path.append('pepsico_dpod_target_main')

from ocr_preprocessor import OCRProcessor

def test_date_conversion():
    """Test the date conversion method with various formats"""
    processor = OCRProcessor()
    
    # Test cases
    test_cases = [
        ("07.Jul.2025", "07/07/2025"),  # DD.MMM.YYYY -> MM/DD/YYYY
        ("15.Dec.2024", "12/15/2024"),  # DD.MMM.YYYY -> MM/DD/YYYY
        ("01.Jan.2026", "01/01/2026"),  # DD.MMM.YYYY -> MM/DD/YYYY
        ("Jul 07, 2025", "07/07/2025"),  # MMM DD, YYYY -> MM/DD/YYYY
        ("December 25, 2024", "12/25/2024"),  # MMM DD, YYYY -> MM/DD/YYYY
        ("07/07/2025", "07/07/2025"),  # MM/DD/YYYY -> MM/DD/YYYY (no change)
        ("25/12/2024", "12/25/2024"),  # DD/MM/YYYY -> MM/DD/YYYY
        ("2024-12-25", "12/25/2024"),  # YYYY-MM-DD -> MM/DD/YYYY
        ("invalid_date", "invalid_date"),  # Invalid format -> no change
        ("", ""),  # Empty string -> no change
        (None, None),  # None -> no change
    ]
    
    print("Testing date conversion functionality:")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for input_date, expected_output in test_cases:
        try:
            result = processor._convert_date_format(input_date)
            if result == expected_output:
                print(f"✓ PASS: '{input_date}' -> '{result}'")
                passed += 1
            else:
                print(f"✗ FAIL: '{input_date}' -> '{result}' (expected: '{expected_output}')")
                failed += 1
        except Exception as e:
            print(f"✗ ERROR: '{input_date}' -> Exception: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False

if __name__ == "__main__":
    success = test_date_conversion()
    sys.exit(0 if success else 1)
