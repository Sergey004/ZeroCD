#!/usr/bin/env python3
"""
ZeroCD - DIY USB CD-ROM и LAN адаптер на Raspberry Pi Zero 2 W

Features:
- USB mass storage emulation with ISO files from microSD
- USB Ethernet (RNDIS + ECM)
- 1.3" ST7789 SPI display with 5-way joystick control
- Optional Wi-Fi hotspot with NAT
"""

import signal
import sys
import time
from typing import Optional

from config import ISO_DIR
from system.logger import setup_logger, get_logger
from ui.display import Display
from ui.menu import Menu
from input.joystick import Joystick, Direction
from usb.gadget import GadgetManager
from usb.iso_manager import ISOManager
from net.wifi import WiFiManager


class ZeroCDApp:
    """
    Main ZeroCD application controller.
    """

    def __init__(self):
        self.logger = get_logger("main")
        self.display: Optional[Display] = None
        self.joystick: Optional[Joystick] = None
        self.gadget: Optional[GadgetManager] = None
        self.iso_manager: Optional[ISOManager] = None
        self.menu: Optional[Menu] = None
        self.wifi: Optional[WiFiManager] = None

        self.iso_list: list = []
        self.active_iso: Optional[str] = None
        self.wifi_enabled: bool = False
        self.usb_connected: bool = False
        self.running: bool = False

    def init(self) -> bool:
        """Initialize all subsystems."""
        self.logger.info("Initializing ZeroCD")
        setup_logger()

        self.iso_manager = ISOManager(ISO_DIR)
        self.iso_list = self.iso_manager.list_isos()
        self.logger.info(f"Found {len(self.iso_list)} ISO files")

        self.display = Display()
        self.display.init()
        self.display.show_splash()

        self.menu = Menu(self.iso_list, self.on_iso_selected)
        if self.iso_list:
            self.active_iso = self.iso_list[0]

        self.gadget = GadgetManager()
        self.gadget.init()

        self.wifi = WiFiManager()

        self.joystick = Joystick(self.on_joystick_event)

        self.logger.info("ZeroCD initialization complete")
        return True

    def on_iso_selected(self, iso_name: str):
        """Handle ISO selection from menu."""
        self.logger.info(f"User selected ISO: {iso_name}")
        iso_path = self.iso_manager.get_iso_path(iso_name)
        if iso_path and self.gadget:
            self.gadget.set_iso(iso_path)
            self.active_iso = iso_name
            self.update_display()

    def on_joystick_event(self, direction: Direction):
        """Handle joystick input events."""
        self.logger.debug(f"Joystick: {direction.value}")

        if direction == Direction.UP:
            self.menu.prev()
        elif direction == Direction.DOWN:
            self.menu.next()
        elif direction == Direction.PRESS:
            self.menu.select()
        elif direction == Direction.RIGHT:
            self.toggle_wifi()
        elif direction == Direction.LEFT:
            pass

        self.update_display()

    def toggle_wifi(self):
        """Toggle Wi-Fi on/off."""
        if self.wifi_enabled:
            self.wifi.disable()
            self.wifi_enabled = False
            self.logger.info("Wi-Fi disabled")
        else:
            if self.wifi.enable():
                self.wifi_enabled = True
                self.logger.info("Wi-Fi enabled")

    def update_display(self):
        """Update display with current state."""
        if self.display:
            self.display.draw_menu(
                items=self.menu.get_visible_items() if self.menu else [],
                selected_index=self.menu.get_index() if self.menu else 0,
                active_iso=self.active_iso,
                wifi_on=self.wifi_enabled,
                usb_bound=self.usb_connected
            )
            self.display.update()

    def run(self):
        """Main application loop."""
        self.running = True
        self.logger.info("Starting ZeroCD main loop")

        self.gadget.bind()
        self.usb_connected = True

        if self.joystick:
            self.joystick.start_polling(self.on_joystick_event)

        self.update_display()

        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            self.shutdown()

    def shutdown(self):
        """Graceful shutdown."""
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
    """Entry point."""
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
