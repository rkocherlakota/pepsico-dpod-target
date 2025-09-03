#!/usr/bin/env python3

# Test script to verify date conversion logic
import re

def test_date_conversion():
    """Test the date conversion logic"""
    
    def _convert_date_format(date_str: str) -> str:
        """Convert various date formats to MM/DD/YYYY format"""
        if not date_str:
            return date_str
        
        print(f"\nTesting date: {date_str}")
        
        # Handle DD.MMM.YYYY format (e.g., "04.Jul.2025" -> "07/04/2025")
        dd_mmm_yyyy_pattern = r"(\d{1,2})\.(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.(\d{4})"
        match = re.match(dd_mmm_yyyy_pattern, date_str, re.IGNORECASE)
        if match:
            day, month, year = match.groups()
            print(f"DD.MMM.YYYY pattern matched: day={day}, month={month}, year={year}")
            month_map = {
                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
            }
            month_num = month_map.get(month.lower(), '01')
            # Ensure two-digit format for day and month
            day = day.zfill(2)
            month_num = month_num.zfill(2)
            # Convert DD.MMM.YYYY to MM/DD/YYYY (swap day and month)
            result = f"{month_num}/{day}/{year}"
            print(f"DD.MMM.YYYY conversion result: {result}")
            return result
        
        # Handle DD/MM/YYYY format (convert to MM/DD/YYYY)
        dd_mm_yyyy_pattern = r"(\d{1,2})/(\d{1,2})/(\d{4})"
        match = re.match(dd_mm_yyyy_pattern, date_str)
        if match:
            day, month, year = match.groups()
            print(f"DD/MM/YYYY pattern matched: day={day}, month={month}, year={year}")
            # Ensure two-digit format for day and month
            day = day.zfill(2)
            month = month.zfill(2)
            # Convert DD/MM/YYYY to MM/DD/YYYY (swap day and month)
            result = f"{month}/{day}/{year}"
            print(f"DD/MM/YYYY conversion result: {result}")
            return result
        
        # Handle MMM DD, YYYY format (e.g., "Jul 04, 2025" -> "07/04/2025")
        mmm_dd_yyyy_pattern = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})"
        match = re.match(mmm_dd_yyyy_pattern, date_str, re.IGNORECASE)
        if match:
            month, day, year = match.groups()
            print(f"MMM DD, YYYY pattern matched: month={month}, day={day}, year={year}")
            month_map = {
                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
            }
            month_num = month_map.get(month.lower(), '01')
            # Ensure two-digit format for day and month
            day = day.zfill(2)
            month_num = month_num.zfill(2)
            result = f"{month_num}/{day}/{year}"
            print(f"MMM DD, YYYY conversion result: {result}")
            return result
        
        # Handle YYYY-MM-DD format
        yyyy_mm_dd_pattern = r"(\d{4})-(\d{1,2})-(\d{1,2})"
        match = re.match(yyyy_mm_dd_pattern, date_str)
        if match:
            year, month, day = match.groups()
            print(f"YYYY-MM-DD pattern matched: year={year}, month={month}, day={day}")
            # Ensure two-digit format for day and month
            day = day.zfill(2)
            month = month.zfill(2)
            result = f"{month}/{day}/{year}"
            print(f"YYYY-MM-DD conversion result: {result}")
            return result
        
        # Handle MM/DD/YYYY format (ensure consistent formatting)
        mm_dd_yyyy_pattern = r"(\d{1,2})/(\d{1,2})/(\d{4})"
        match = re.match(mm_dd_yyyy_pattern, date_str)
        if match:
            month, day, year = match.groups()
            print(f"MM/DD/YYYY pattern matched: month={month}, day={day}, year={year}")
            # Ensure two-digit format for day and month
            day = day.zfill(2)
            month = month.zfill(2)
            result = f"{month}/{day}/{year}"
            print(f"MM/DD/YYYY conversion result: {result}")
            return result
        
        # If no conversion needed, return as-is
        print(f"No pattern matched, returning as-is: {date_str}")
        return date_str

    # Test cases
    test_dates = [
        "04.Jul.2025",  # Should become "07/04/2025"
        "07.Jul.2025",  # Should become "07/07/2025"
        "25.Dec.2025",  # Should become "12/25/2025"
        "04/07/2025",   # Should become "07/04/2025" (DD/MM/YYYY)
        "07/04/2025",   # Should become "07/04/2025" (MM/DD/YYYY)
        "Jul 04, 2025", # Should become "07/04/2025"
        "2025-07-04",   # Should become "07/04/2025"
        "7/4/2025",     # Should become "07/04/2025"
    ]
    
    print("Testing Date Conversion Logic")
    print("=" * 50)
    
    for test_date in test_dates:
        result = _convert_date_format(test_date)
        print(f"Final result: {test_date} -> {result}")
        print("-" * 30)

if __name__ == "__main__":
    test_date_conversion()
