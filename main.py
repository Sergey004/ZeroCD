#!/usr/bin/env python3
"""
ZeroCD - DIY USB CD-ROM and LAN adapter for Raspberry Pi Zero 2 W

PC Mode: Set ZEROCD_PLATFORM=pc to run with curses TUI
"""

import signal
import sys
import os

from config import ISO_DIR, USE_PC_EMULATION, TEST_ISO_DIR
from system.logger import setup_logger, get_logger

if USE_PC_EMULATION:
    from ui.display_pc import DisplayPC
    from ui.menu import Menu
    from input.joystick_pc import JoystickPC, Direction
    from usb.iso_manager import ISOManager
    from net.wifi import WiFiManager
    from usb.gadget_pc import GadgetManagerPC
    ISO_DIR = TEST_ISO_DIR
else:
    from ui.display import Display
    from ui.menu import Menu
    from input.joystick import Joystick, Direction
    from usb.iso_manager import ISOManager
    from net.wifi import WiFiManager
    from usb.gadget import GadgetManager


class ZeroCDApp:
    def __init__(self):
        self.logger = get_logger("main")
        self.display = None
        self.joystick = None
        self.gadget = None
        self.iso_manager = None
        self.menu = None
        self.wifi = None

        self.iso_list = []
        self.active_iso = None
        self.wifi_enabled = False
        self.usb_connected = False
        self.mtp_enabled = False
        self.running = False

    def init(self) -> bool:
        self.logger.info(f"Initializing ZeroCD (PC mode: {USE_PC_EMULATION})")
        setup_logger()

        self.iso_manager = ISOManager(ISO_DIR)
        self.iso_list = self.iso_manager.list_isos()
        self.logger.info(f"Found {len(self.iso_list)} ISO files")

        if USE_PC_EMULATION:
            self.display = DisplayPC()
            self.joystick = JoystickPC(self.on_joystick_event)
            self.gadget = GadgetManagerPC()
        else:
            self.display = Display()
            if not self.display.init():
                self.logger.error("Failed to initialize display")
                return False
            
            # Pass display to joystick for button reading
            self.joystick = Joystick(disp=self.display, callback=self.on_joystick_event)
            
            self.gadget = GadgetManager()
            if not self.gadget.init():
                self.logger.error("Failed to initialize USB gadget - continuing without USB support")
            else:
                self.logger.info("USB gadget initialized, binding to UDC...")
                if self.gadget.bind():
                    self.usb_connected = True
                    self.logger.info("USB gadget bound to UDC")
                else:
                    self.logger.error("Failed to bind USB gadget to UDC")

        self.display.show_splash()

        self.menu = Menu(self.iso_list, self.on_iso_selected)
        if self.iso_list:
            self.active_iso = self.iso_list[0]

        self.wifi = WiFiManager()

        self.logger.info("ZeroCD initialization complete")
        return True

    def on_iso_selected(self, iso_name: str):
        self.logger.info(f"User selected ISO: {iso_name}")
        iso_path = self.iso_manager.get_iso_path(iso_name)
        if iso_path and self.gadget:
            self.gadget.set_iso(iso_path)
            self.active_iso = iso_name
            self.update_display()

    def on_joystick_event(self, direction: Direction):
        if direction == Direction.PRESS:          # ← центральная кнопка джойстика
            self.logger.info("Центральная кнопка нажата — обработка QUIT/меню")
        # сюда вставь то, что раньше было под QUIT
        # например:
        # self.running = False
        # self.gadget.shutdown()
        # sys.exit(0)
            return

        if direction == Direction.UP:
            self.menu.prev()
        elif direction == Direction.DOWN:
            self.menu.next()
        elif direction == Direction.PRESS:
            self.menu.select()
        elif direction == Direction.RIGHT:
            self.toggle_wifi()
        elif direction == Direction.LEFT:
            self.toggle_mtp()

        self.update_display()

    def toggle_wifi(self):
        if self.wifi_enabled:
            self.wifi.disable()
            self.wifi_enabled = False
            self.logger.info("Wi-Fi disabled")
        else:
            if self.wifi.enable():
                self.wifi_enabled = True
                self.logger.info("Wi-Fi enabled")

    def toggle_mtp(self):
        # MTP not implemented yet
        self.logger.info("MTP not implemented")
        pass

    def update_display(self):
        if self.display:
            self.display.draw_menu(
                items=self.menu.get_visible_items() if self.menu else [],
                selected_index=self.menu.get_index() if self.menu else 0,
                active_iso=self.active_iso,
                wifi_on=self.wifi_enabled,
                usb_bound=self.usb_connected,
                mtp_on=self.mtp_enabled
            )
            if hasattr(self.display, 'update'):
                self.display.update()

    def run(self):
        self.running = True
        self.logger.info("Starting ZeroCD main loop")

        if USE_PC_EMULATION:
            if self.display and hasattr(self.display, 'stdscr') and self.display.stdscr:
                self.joystick.start_polling(self.on_joystick_event, self.display.stdscr)
            else:
                self.joystick.start_polling(self.on_joystick_event)
        else:
            # Start joystick polling - if it was created successfully, it should work
            try:
                self.joystick.start_polling(self.on_joystick_event)
                self.logger.info("Joystick polling started")
            except Exception as e:
                self.logger.warning(f"Joystick not available: {e}, USB CD-ROM mode only")

        self.update_display()

        if USE_PC_EMULATION:
            self._run_pc_loop()
        else:
            self._run_pi_loop()

    def _run_pc_loop(self):
        """PC mode: wait for quit."""
        import time
        while self.running:
            time.sleep(0.05)

    def _run_pi_loop(self):
        """Pi mode: just wait."""
        import time
        while self.running:
            time.sleep(0.1)

    def shutdown(self):
        self.logger.info("Shutting down ZeroCD")
        self.running = False

        if self.joystick:
            self.joystick.stop()

        if self.gadget:
            self.gadget.shutdown()

        if self.wifi and self.wifi_enabled:
            self.wifi.disable()

        if self.display:
            self.display.close()

        self.logger.info("ZeroCD shutdown complete")


def main():
    def signal_handler(signum, frame):
        app = globals().get('app')
        if app:
            app.logger.info(f"Received signal {signum}")
            app.shutdown()
            sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    if USE_PC_EMULATION and sys.stdout.isatty():
        import curses

        def curses_main(stdscr):
            global app
            app = ZeroCDApp()
            if app.init():
                app.run()
            else:
                app.logger.error("Failed to initialize ZeroCD")
                sys.exit(1)

        curses.wrapper(curses_main)
    else:
        global app
        app = ZeroCDApp()
        if app.init():
            app.run()
        else:
            app.logger.error("Failed to initialize ZeroCD")
            sys.exit(1)


if __name__ == "__main__":
    main()
