"""
PC Display emulator using curses TUI (with fallback)
"""
import curses
import os
import sys
from typing import List, Optional


class DisplayPC:
    """PC-based display emulator using curses TUI.

    Features:
    - Curses-based menu display
    - Colored output (if terminal supports)
    - Same layout as physical display will have
    - Falls back to simple console if curses unavailable
    """

    def __init__(self):
        self.stdscr = None
        self.active_iso = None
        self.wifi_on = False
        self.usb_bound = False
        self.use_curses = True

    def init(self) -> bool:
        """Initialize display (curses or fallback)."""
        if not sys.stdout.isatty():
            self.use_curses = False
            return True

        try:
            self.stdscr = curses.initscr()
            curses.start_color()
            curses.curs_set(0)
            curses.noecho()
            curses.cbreak()
            self.stdscr.keypad(True)
            curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
            curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
            curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
            curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)
            curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_GREEN)
            return True
        except:
            self.use_curses = False
            return True

    def show_splash(self):
        """Show ZeroCD splash screen."""
        if not self.use_curses:
            print("\n=== ZeroCD v1.0 ===")
            print("USB CD-ROM + LAN Adapter")
            print("Loading...")
            return

        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()

        title = "ZeroCD v1.0"
        subtitle = "USB CD-ROM + LAN Adapter"

        mid_y = height // 2
        mid_x = width // 2

        self.stdscr.addstr(mid_y - 2, mid_x - len(title) // 2, title, curses.A_BOLD | curses.color_pair(1))
        self.stdscr.addstr(mid_y, mid_x - len(subtitle) // 2, subtitle)
        self.stdscr.addstr(mid_y + 2, mid_x - 8, "Loading...")
        self.stdscr.refresh()
        import time
        time.sleep(1.5)

    def draw_menu(
        self,
        items: List[str],
        selected_index: int,
        scroll_offset: int = 0,
        active_iso: Optional[str] = None,
        wifi_on: bool = False,
        usb_bound: bool = False
    ):
        """Draw ISO selection menu."""
        if not self.use_curses:
            self._draw_console(items, selected_index, scroll_offset, active_iso, wifi_on, usb_bound)
            return

        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()

        usb_status = "BOUND" if usb_bound else "UNBOUND"
        wifi_status = "ON" if wifi_on else "OFF"

        title = " ZeroCD - USB CD-ROM Emulator "
        self.stdscr.attron(curses.color_pair(1) | curses.A_REVERSE)
        self.stdscr.addstr(0, 0, title.ljust(width - 1))
        self.stdscr.attroff(curses.color_pair(1) | curses.A_REVERSE)

        status = f" USB: {usb_status} Wi-Fi: {wifi_status} "
        self.stdscr.addstr(1, width - len(status) - 1, status)

        if active_iso:
            active_str = f" Active: {active_iso[:30]} "
            self.stdscr.attron(curses.color_pair(5) | curses.A_REVERSE)
            self.stdscr.addstr(2, 0, active_str.ljust(width - 1))
            self.stdscr.attroff(curses.color_pair(5) | curses.A_REVERSE)

        self.stdscr.addstr(4, 0, " Select ISO:", curses.A_BOLD)

        visible_items = items
        for i, item in enumerate(visible_items):
            y = 5 + i
            global_index = scroll_offset + i
            prefix = ">" if global_index == selected_index else " "
            is_active = item == active_iso

            display_item = item[:40]
            if global_index == selected_index:
                self.stdscr.attron(curses.color_pair(6) | curses.A_REVERSE)
                self.stdscr.addstr(y, 0, f" {prefix} {display_item:<40} ")
                self.stdscr.attroff(curses.color_pair(6) | curses.A_REVERSE)
            elif is_active:
                self.stdscr.attron(curses.color_pair(5))
                self.stdscr.addstr(y, 0, f" {display_item:<40} *")
                self.stdscr.attroff(curses.color_pair(5))
            else:
                self.stdscr.addstr(y, 0, f" {display_item:<40} ")

        remaining = 5 - len(visible_items)
        for i in range(remaining):
            self.stdscr.addstr(5 + len(visible_items) + i, 0, " " * 40)

        help_text = " w/s:up/down Enter:select d:Wi-Fi q:quit "
        help_y = height - 2
        if help_y >= 0:
            self.stdscr.attron(curses.color_pair(4))
            self.stdscr.addstr(help_y, 0, help_text.ljust(width - 1))
            self.stdscr.attroff(curses.color_pair(4))

        self.stdscr.refresh()

        self.active_iso = active_iso
        self.wifi_on = wifi_on
        self.usb_bound = usb_bound

    def _draw_console(self, items, selected_index, scroll_offset, active_iso, wifi_on, usb_bound):
        """Simple console fallback."""
        print("\n" + "=" * 50)
        print(" ZeroCD - USB CD-ROM Emulator ")
        print(f" USB: {usb_bound} Wi-Fi: {wifi_on} ")
        if active_iso:
            print(f" Active: {active_iso}")
        print("=" * 50)
        print(" Select ISO:")
        visible_items = items
        for i, item in enumerate(visible_items):
            global_index = scroll_offset + i
            prefix = ">" if global_index == selected_index else " "
            marker = "*" if item == active_iso else ""
            print(f" {prefix} {item:<40} {marker}")
        print("-" * 50)
        print(" w/s:up/down Enter:select d:Wi-Fi q:quit")
        print("-" * 50)

        self.active_iso = active_iso
        self.wifi_on = wifi_on
        self.usb_bound = usb_bound

    def draw_status(self, wifi_on: bool, usb_bound: bool, active_iso: str):
        """Draw status bar."""
        pass

    def update(self):
        """Refresh display."""
        if self.stdscr and self.use_curses:
            self.stdscr.refresh()

    def close(self):
        """Release display resources."""
        if self.stdscr and self.use_curses:
            try:
                curses.nocbreak()
                self.stdscr.keypad(False)
                curses.echo()
                curses.endwin()
            except:
                pass
        print("\nZeroCD stopped.\n")


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

    def draw_menu(self, items, selected_index, scroll_offset=0, active_iso=None, wifi_on=False, usb_bound=False):
        print(f"[MENU] Items: {len(items)}, Selected: {selected_index}, Offset: {scroll_offset}, Active: {active_iso}")

    def draw_status(self, wifi_on, usb_bound, active_iso):
        pass

    def update(self):
        pass

    def close(self):
        pass