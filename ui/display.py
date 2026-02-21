"""
ST7789 display controller for 1.3" HAT
"""
from typing import List, Optional
from config import DISPLAY_WIDTH, DISPLAY_HEIGHT
from system.logger import get_logger


class Display:
    """
    Controls ST7789 SPI display.

    Usage:
        display = Display()
        display.clear()
        display.draw_menu(['iso1.iso', 'iso2.iso'], 0, 'iso1.iso')
    """

    def __init__(self):
        self.logger = get_logger("display")
        self.width = DISPLAY_WIDTH
        self.height = DISPLAY_HEIGHT
        self.initialized = False

    def init(self) -> bool:
        """Initialize display hardware."""
        self.logger.info("Initializing ST7789 display")
        self.initialized = True
        return True

    def clear(self, color: int = 0x0000):
        """Clear display with color."""
        pass

    def show_splash(self):
        """Show ZeroCD splash screen."""
        pass

    def draw_menu(
        self,
        items: List[str],
        selected_index: int,
        active_iso: Optional[str] = None,
        wifi_on: bool = False,
        usb_bound: bool = False
    ):
        """Draw ISO selection menu."""
        pass

    def draw_status(self, wifi_on: bool, usb_bound: bool, active_iso: str):
        """Draw status bar."""
        pass

    def update(self):
        """Refresh display from buffer."""
        pass

    def close(self):
        """Release display resources."""
        pass


class ST7789Driver:
    """Low-level ST7789 display driver."""

    def __init__(self, dc_pin: int, rst_pin: int, bl_pin: int):
        self.dc_pin = dc_pin
        self.rst_pin = rst_pin
        self.bl_pin = bl_pin

    def write_command(self, cmd: int):
        """Write command byte."""
        pass

    def write_data(self, data: bytes):
        """Write data bytes."""
        pass

    def reset(self):
        """Hard reset display."""
        pass

    def backlight(self, on: bool):
        """Control backlight."""
        pass
