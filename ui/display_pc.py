"""
PC Display emulator using console/curses
"""
import os
import sys
from typing import List, Optional


class DisplayPC:
    """
    PC-based display emulator using console output.

    Features:
    - Console-based menu display
    - Colored output support (ANSI)
    - Clear screen and position cursor
    """

    COLORS = {
        'reset': '\033[0m',
        'bold': '\033[1m',
        'selected': '\033[42m',
        'active': '\033[44m',
        'header': '\033[36m',
        'green': '\033[32m',
        'red': '\033[31m',
        'yellow': '\033[33m',
    }

    def __init__(self):
        self.lines = []
        self.active_iso = None
        self.wifi_on = False
        self.usb_bound = False

    def clear(self):
        """Clear console screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def cursor_home(self):
        """Move cursor to home position."""
        sys.stdout.write('\033[H')
        sys.stdout.flush()

    def cursor_up(self, n: int = 1):
        """Move cursor up n lines."""
        sys.stdout.write(f'\033[{n}A')
        sys.stdout.flush()

    def cursor_down(self, n: int = 1):
        """Move cursor down n lines."""
        sys.stdout.write(f'\033[{n}B')
        sys.stdout.flush()

    def init(self) -> bool:
        """Initialize display."""
        self.clear()
        return True

    def show_splash(self):
        """Show ZeroCD splash screen."""
        self.clear()
        print(f"{self.COLORS['bold']}{self.COLORS['header']}")
        print("╔══════════════════════════════════╗")
        print("║         ZeroCD v1.0              ║")
        print("║    USB CD-ROM + LAN Adapter      ║")
        print("╚══════════════════════════════════╝")
        print(f"{self.COLORS['reset']}")
        print("Loading...")
        import time
        time.sleep(1)

    def draw_menu(
        self,
        items: List[str],
        selected_index: int,
        active_iso: Optional[str] = None,
        wifi_on: bool = False,
        usb_bound: bool = False
    ):
        """Draw ISO selection menu."""
        self.clear()
        self.cursor_home()

        header_color = self.COLORS['header']
        selected_color = self.COLORS['selected']
        active_color = self.COLORS['active']
        reset = self.COLORS['reset']
        green = self.COLORS['green']
        red = self.COLORS['red']
        yellow = self.COLORS['yellow']

        print(f"{header_color}╔═══════════════════════════════════════════╗{reset}")
        print(f"{header_color}║ ZeroCD - USB CD-ROM Emulator              ║{reset}")

        usb_status = f"{green}BOUND{reset}" if usb_bound else f"{red}UNBOUND{reset}"
        wifi_status = f"{green}ON{reset}" if wifi_on else f"{red}OFF{reset}"

        print(f"{header_color}║ USB: {usb_status:<8}  Wi-Fi: {wifi_status:<6}      ║{reset}")
        print(f"{header_color}╠═══════════════════════════════════════════╣{reset}")

        if active_iso:
            print(f"{active_color}║ Active: {active_iso[:37]:<37} ║{reset}")

        print(f"{header_color}╠═══════════════════════════════════════════╣{reset}")
        print(f"{header_color}║ Select ISO:                                ║{reset}")

        visible_items = items[:5]
        for i, item in enumerate(visible_items):
            prefix = "►" if i == selected_index else " "
            is_active = item == active_iso

            if i == selected_index:
                line_color = selected_color
            elif is_active:
                line_color = active_color
            else:
                line_color = reset

            display_item = item[:38]
            if is_active:
                marker = "★"
            else:
                marker = " "
            print(f"{line_color}║ {prefix} {marker} {display_item:<35} ║{reset}")

        remaining = 5 - len(visible_items)
        for _ in range(remaining):
            print(f"{header_color}║                                          ║{reset}")

        print(f"{header_color}╚═══════════════════════════════════════════╝{reset}")
        print(f"{yellow}Controls: ↑/↓ Navigate | Enter Select | → Wi-Fi{reset}")

        self.active_iso = active_iso
        self.wifi_on = wifi_on
        self.usb_bound = usb_bound

    def draw_status(self, wifi_on: bool, usb_bound: bool, active_iso: str):
        """Draw status bar."""
        pass

    def update(self):
        """Refresh display."""
        sys.stdout.flush()

    def close(self):
        """Release display resources."""
        print(f"\n{self.COLORS['reset']}ZeroCD stopped.\n")


class DisplayDummy:
    """Dummy display for testing without output."""

    def __init__(self):
        self.active_iso = None

    def init(self) -> bool:
        return True

    def clear(self):
        pass

    def show_splash(self):
        print("[SPLASH] ZeroCD v1.0")

    def draw_menu(self, items, selected_index, active_iso=None, wifi_on=False, usb_bound=False):
        print(f"[MENU] Items: {len(items)}, Selected: {selected_index}, Active: {active_iso}")

    def draw_status(self, wifi_on, usb_bound, active_iso):
        pass

    def update(self):
        pass

    def close(self):
        pass
