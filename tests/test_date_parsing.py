import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from proto.calendar_tools import find_best_slot

def test_parsing():
    print("🧪 Testing Date Parsing Fix...")
    
    test_cases = [
        ("Sunday, 4pm-5pm", "Sunday", "04:00 PM"),
        ("Tuesday 3-4pm", "Tuesday", "03:00 PM"),
        ("Wednesday, 2-3pm", "Wednesday", "02:00 PM"),
        ("Monday 10am-11am", "Monday", "10:00 AM"),
        ("Thursday 10-11am", "Thursday", "10:00 AM"),
        ("Friday 2pm", "Friday", "02:00 PM"),
    ]

    now = datetime.now()
    print(f"Current year for test: {now.year}")

    all_passed = True
    for slots_text, expected_day, expected_time in test_cases:
        result = find_best_slot(f"• {slots_text}")
        if result:
            start_dt, end_dt = result
            actual_day = start_dt.strftime("%A")
            actual_time = start_dt.strftime("%I:%M %p")
            actual_year = start_dt.year
            
            # Basic validation
            day_match = actual_day == expected_day
            time_match = actual_time == expected_time
            year_match = actual_year == now.year or (actual_year == now.year + 1 and now.month == 12)
            
            if day_match and time_match and year_match:
                print(f"  ✅ \"{slots_text}\" -> {actual_day} {actual_time} ({actual_year})")
            else:
                print(f"  ❌ \"{slots_text}\" -> {actual_day} {actual_time} ({actual_year}) | Expected: {expected_day} {expected_time}")
                all_passed = False
        else:
            print(f"  ❌ \"{slots_text}\" -> FAILED TO PARSE")
            all_passed = False

    if all_passed:
        print("\n✨ ALL TESTS PASSED!")
    else:
        print("\n⚠️ SOME TESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    test_parsing()
