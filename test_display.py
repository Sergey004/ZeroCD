#!/usr/bin/env python3
"""
Interactive test for ZeroCD display implementation
Usage:
    python test_display.py              # Shows menu for 5 seconds
    python test_display.py --interactive # Full interactive mode
    ZEROCD_PLATFORM=pi python test_display.py --interactive # On Pi
"""
import sys
import os
import time

os.environ["ZEROCD_PLATFORM"] = "pc"

from ui.display import Display
from config import USE_PC_EMULATION

def test_pi_display():
    """Test ST7789 display (requires hardware)."""
    print("ZeroCD ST7789 Display Test")
    print("=" * 50)

    display = Display()
    if not display.init():
        print("[FAILED] Display init failed")
        return False

    display.show_splash()

    test_items = ["ubuntu.iso", "debian.iso", "fedora.iso"]
    display.draw_menu(test_items, 0, None, False, True)

    print("\n[VIEW] Showing menu for 3 seconds on hardware...")
    time.sleep(3)

    display.close()
    return True


if __name__ == "__main__":
    print("ZeroCD Display Test Suite")
    print("=" * 50)
    test_pi_display() 
    sys.exit(1)