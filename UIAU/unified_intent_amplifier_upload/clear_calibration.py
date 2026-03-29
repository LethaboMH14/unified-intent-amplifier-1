"""
clear_calibration.py — Run this ONCE to clear the bad calibration.
After this, gaze will use sensitivity-based mapping which works correctly.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from user_profile import init_db, save_setting
init_db()
save_setting("gaze_calibration", None)
print("Done — old gaze calibration cleared.")
print("Restart main.py and gaze will use sensitivity defaults.")
