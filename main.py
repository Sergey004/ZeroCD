#!/usr/bin/env python3
"""
ZeroCD - DIY USB CD-ROM и LAN адаптер на Raspberry Pi Zero 2 W

PC Mode: Set ZEROCD_PLATFORM=pc to run with keyboard/curses UI
"""

import signal
import sys
import os

from config import ISO_DIR, USE_PC_EMULATION, TEST_ISO_DIR
from system.logger import setup_logger, get_logger

if USE_PC_EMULATION:
    from ui.display_pc import DisplayPC
    from ui.menu import Menu
    from input.joystick_pc import JoystickPC
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
            from config import Direction
            self.display = Display()
            self.joystick = Joystick(self.on_joystick_event)
            self.gadget = GadgetManager()
            self.gadget.init()

        self.display.init()
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

    def on_joystick_event(self, direction):
        self.logger.debug(f"Joystick: {direction.value if hasattr(direction, 'value') else direction}")

        if str(direction) in ('Direction.UP', 'up', 'UP'):
            self.menu.prev()
        elif str(direction) in ('Direction.DOWN', 'down', 'DOWN'):
            self.menu.next()
        elif str(direction) in ('Direction.PRESS', 'press', 'PRESS', 'enter', 'space'):
            self.menu.select()
        elif str(direction) in ('Direction.RIGHT', 'right', 'RIGHT'):
            self.toggle_wifi()
        elif str(direction) in ('Direction.LEFT', 'left', 'LEFT'):
            pass

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

    def update_display(self):
        if self.display:
            self.display.draw_menu(
                items=self.menu.get_visible_items() if self.menu else [],
                selected_index=self.menu.get_index() if self.menu else 0,
                active_iso=self.active_iso,
                wifi_on=self.wifi_enabled,
                usb_bound=self.usb_connected
            )
            if hasattr(self.display, 'update'):
                self.display.update()

    def run(self):
        self.running = True
        self.logger.info("Starting ZeroCD main loop")

        if USE_PC_EMULATION:
            print("\n[ZeroCD] Running in PC mode. Use arrow keys to navigate.\n")
        else:
            self.gadget.bind()
            self.usb_connected = True

        if self.joystick:
            self.joystick.start_polling(self.on_joystick_event)

        self.update_display()

        try:
            import time
            while self.running:
                if USE_PC_EMULATION:
                    import keyboard
                    if keyboard.is_pressed('q'):
                        self.logger.info("Quit key pressed")
                        break
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            self.shutdown()

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
    app = ZeroCDApp()

    def signal_handler(signum, frame):
        app.logger.info(f"Received signal {signum}")
        app.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    if app.init():
        app.run()
    else:
        app.logger.error("Failed to initialize ZeroCD")
        sys.exit(1)


if __name__ == "__main__":
    main()
