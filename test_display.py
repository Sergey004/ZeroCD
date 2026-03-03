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

from ui.display_pc import DisplayPC
from ui.display import Display
from config import USE_PC_EMULATION

KEYS = {
    'w': 'UP',
    's': 'DOWN',
    'a': 'LEFT',
    'd': 'RIGHT',
    '\n': 'PRESS',
    'q': 'QUIT',
}


def test_pc_display():
    """Test PC display - shows menu for 5 seconds."""
    print("ZeroCD Display Test")
    print("=" * 50)

    display = DisplayPC()
    if not display.init():
        print("[FAILED] DisplayPC init failed")
        return False

    display.show_splash()

    test_items = [
        "ubuntu-22.04-desktop.iso",
        "debian-11-live.iso",
        "fedora-workstation.iso",
        "archlinux.iso",
        "kali-linux.iso",
    ]

    selected_index = 0
    active_iso = None
    wifi_on = True
    usb_bound = True

    display.draw_menu(test_items, selected_index, active_iso, wifi_on, usb_bound)

    print("\n[VIEW] Showing menu for 5 seconds...")
    print("Controls: w/s=up/down, Enter=select, d=Wi-Fi toggle, q=quit\n")

    try:
        import tty
        import termios
        import select

        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno(), termios.TCSANOW)

        start = time.time()
        running = True

        while running and (time.time() - start) < 5:
            dr, dw, de = select.select([sys.stdin], [], [], 0.1)
            if dr:
                running = False
                break

        if running:
            print("\n[TIMEOUT] Test complete (5 seconds)")
        else:
            print("\n[KEY] Key pressed")

        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    except Exception as e:
        print(f"Note: {e}")
        time.sleep(5)

    display.close()
    return True


def test_pc_display_interactive():
    """Full interactive mode with keyboard controls."""
    print("ZeroCD Display - Interactive Mode")
    print("=" * 50)
    print("Controls: w/s=up/down, Enter=select, d=toggle Wi-Fi, q=quit")
    print("=" * 50)

    display = DisplayPC()
    if not display.init():
        print("[FAILED] DisplayPC init failed")
        return False

    test_items = [
        "ubuntu-22.04-desktop.iso",
        "debian-11-live.iso",
        "fedora-workstation.iso",
        "archlinux.iso",
        "kali-linux.iso",
        "centos-stream.iso",
        "opensuse.iso",
        "linux-mint.iso",
        "fedora-kde.iso",
        "ubuntu-server.iso",
    ]

    selected_index = 0
    active_iso = None
    wifi_on = False
    usb_bound = True

    display.draw_menu(test_items, selected_index, active_iso, wifi_on, usb_bound)

    print("\n[INTERACTIVE] Use keyboard controls. Press 'q' to quit.\n")

    try:
        import tty
        import termios
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

        running = True
        while running:
            ch = sys.stdin.read(1)
            if not ch:
                continue

            if ch not in KEYS:
                continue

            key = KEYS[ch]

            if key == 'QUIT':
                running = False
                print("\n[QUIT] Exiting...")
            elif key == 'UP':
                selected_index = max(0, selected_index - 1)
            elif key == 'DOWN':
                selected_index = min(len(test_items) - 1, selected_index + 1)
            elif key == 'PRESS':
                active_iso = test_items[selected_index]
                print(f"\n[SELECT] {active_iso}")
            elif key == 'RIGHT':
                wifi_on = not wifi_on
                print(f"\n[Wi-Fi] {'ON' if wifi_on else 'OFF'}")

            display.draw_menu(test_items, selected_index, active_iso, wifi_on, usb_bound)

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    display.close()
    return True


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

    interactive = "--interactive" in sys.argv
    hardware = not USE_PC_EMULATION

    if hardware:
        success = test_pi_display() if not interactive else test_pc_display_interactive()
    else:
        success = test_pc_display_interactive() if interactive else test_pc_display()

    sys.exit(0 if success else 1)