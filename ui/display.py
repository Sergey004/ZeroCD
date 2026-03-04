"""
ST7789 display controller for 1.3" HAT
ZeroCD - DIY USB CD-ROM and LAN adapter for Raspberry Pi Zero 2 W
Based on Raspyjack style (PIL + NumPy)
"""
import time
from typing import List, Optional

try:
    import spidev
    HAS_SPI = True
except ImportError:
    HAS_SPI = False

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False

from PIL import Image, ImageDraw, ImageFont
import numpy as np

from config import DISPLAY_PINS, DISPLAY_WIDTH, DISPLAY_HEIGHT
from system.logger import get_logger


ST7789_COLORS = {
    'BLACK': (0, 0, 0),
    'WHITE': (255, 255, 255),
    'CYAN': (0, 255, 255),
    'GREEN': (0, 255, 0),
    'RED': (255, 0, 0),
    'YELLOW': (255, 255, 0),
    'BLUE': (0, 0, 255),
    'DARK_BLUE': (0, 0, 127),
    'GRAY': (127, 127, 127),
}

LCD_RST_PIN = DISPLAY_PINS['rst']
LCD_DC_PIN = DISPLAY_PINS['dc']
LCD_CS_PIN = DISPLAY_PINS.get('ce0', 8)
LCD_BL_PIN = DISPLAY_PINS['bl']

SPI = None


def SPI_Init(bus: int = 0, device: int = 0, speed: int = 9000000):
    """Initialize SPI connection like Raspyjack."""
    global SPI
    if HAS_SPI:
        SPI = spidev.SpiDev(bus, device)
        SPI.max_speed_hz = speed
        SPI.mode = 0b00
        return True
    return False


def SPI_Write_Byte(data):
    """Write bytes to SPI like Raspyjack."""
    if SPI:
        SPI.writebytes(data)


def GPIO_Init():
    """Initialize GPIO like Raspyjack."""
    if HAS_GPIO:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(LCD_RST_PIN, GPIO.OUT)
        GPIO.setup(LCD_DC_PIN, GPIO.OUT)
        GPIO.setup(LCD_CS_PIN, GPIO.OUT)
        GPIO.setup(LCD_BL_PIN, GPIO.OUT)
        return True
    return False


class ST7789:
    """ST7789 display controller using PIL + NumPy like Raspyjack."""

    def __init__(self, dc_pin: int = LCD_DC_PIN, rst_pin: int = LCD_RST_PIN, bl_pin: int = LCD_BL_PIN):
        self.dc_pin = dc_pin
        self.rst_pin = rst_pin
        self.bl_pin = bl_pin
        self.width = DISPLAY_WIDTH
        self.height = DISPLAY_HEIGHT
        self.image = None
        self.draw = None
        self._initialized = False

    def init(self) -> bool:
        """Initialize display hardware."""
        if not HAS_SPI or not HAS_GPIO:
            self._initialized = False
            return False

        self.logger = get_logger("st7789")
        self.logger.info("Initializing ST7789 display")

        GPIO_Init()
        SPI_Init()

        self._reset()
        self._init_display()

        self.image = Image.new("RGB", (self.width, self.height), "BLACK")
        self.draw = ImageDraw.Draw(self.image)

        self._backlight(True)
        self._initialized = True
        self.logger.info("ST7789 initialization complete")
        return True

    def _reset(self):
        """Hard reset display."""
        GPIO.output(self.rst_pin, GPIO.HIGH)
        time.sleep(0.1)
        GPIO.output(self.rst_pin, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(self.rst_pin, GPIO.HIGH)
        time.sleep(0.15)

    def _init_display(self):
        """Initialize ST7789 display settings."""
        commands = [
            (0x36, [0x70]),
            (0x3A, [0x05]),
            (0xB2, [0x0C, 0x0C, 0x00, 0x33, 0x33]),
            (0xB7, [0x35]),
            (0xBB, [0x19]),
            (0xC0, [0x2C]),
            (0xC2, [0x01, 0x01]),
            (0xC3, [0x12]),
            (0xC4, [0x20]),
            (0xC6, [0x0F]),
            (0xD0, [0xA4, 0xA1]),
            (0xE0, [0xD0, 0x04, 0x0D, 0x11, 0x13, 0x2B, 0x3F, 0x54, 0x4C, 0x18, 0x0D, 0x0B, 0x1F, 0x23]),
            (0xE1, [0xD0, 0x04, 0x0C, 0x11, 0x13, 0x2B, 0x3F, 0x44, 0x51, 0x2F, 0x1F, 0x1F, 0x20, 0x23]),
            (0x21, []),
            (0x11, []),
            (0x29, []),
        ]

        for cmd, data in commands:
            self._write_command(cmd)
            if data:
                self._write_data(bytes(data))
                time.sleep(0.01)

    def _write_command(self, cmd: int):
        """Write command byte."""
        GPIO.output(self.dc_pin, GPIO.LOW)
        SPI_Write_Byte([cmd])

    def _write_data(self, data):
        """Write data bytes."""
        GPIO.output(self.dc_pin, GPIO.HIGH)
        SPI_Write_Byte(list(data))

    def _set_window(self, x0: int, y0: int, x1: int, y1: int):
        """Set draw window."""
        self._write_command(0x2A)
        self._write_data([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])
        self._write_command(0x2B)
        self._write_data([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])
        self._write_command(0x2C)

    def _backlight(self, on: bool):
        """Control backlight."""
        if self.bl_pin:
            GPIO.output(self.bl_pin, GPIO.HIGH if on else GPIO.LOW)

    def clear(self, color=(0, 0, 0)):
        """Clear display with color (RGB tuple like Raspyjack)."""
        self.image.paste(color, (0, 0, self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)

    def _draw_centered_text(self, y: int, text: str, color=(255, 255, 255), size: int = 1):
        """Draw centered text at Y position."""
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 9 * size)
        except:
            font = ImageFont.load_default()

        bbox = self.draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) // 2
        self.draw.text((x, y), text, fill=color, font=font)

    def _draw_text(self, x: int, y: int, text: str, color=(255, 255, 255), size: int = 1):
        """Draw text at position."""
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 9 * size)
        except:
            font = ImageFont.load_default()
        self.draw.text((x, y), text, fill=color, font=font)

    def show_splash(self):
        """Show ZeroCD splash screen."""
        self.clear(ST7789_COLORS['BLACK'])
        self._draw_centered_text(80, "ZeroCD v1.0", ST7789_COLORS['CYAN'], 2)
        self._draw_centered_text(110, "USB CD-ROM + LAN", ST7789_COLORS['WHITE'])
        self._draw_centered_text(150, "Loading...", ST7789_COLORS['GREEN'])
        self._update()
        time.sleep(1.5)

    def draw_menu(
        self,
        items: List[str],
        selected_index: int,
        active_iso: Optional[str] = None,
        wifi_on: bool = False,
        usb_bound: bool = False,
        mtp_on: bool = False
    ):
        """Draw ISO selection menu like Raspyjack."""
        self.clear(ST7789_COLORS['BLACK'])

        self.draw.rectangle((0, 0, 240, 24), fill=ST7789_COLORS['CYAN'])
        self._draw_text(5, 6, " ZeroCD ", ST7789_COLORS['BLACK'])

        status = f"Wi-Fi:{'ON' if wifi_on else 'OFF'} MTP:{'ON' if mtp_on else 'OFF'}"
        self._draw_text(240 - len(status) * 9 - 5, 6, status, ST7789_COLORS['WHITE'])

        if active_iso:
            self.draw.rectangle((0, 24, 240, 40), fill=ST7789_COLORS['BLUE'])
            self._draw_text(5, 28, f" Active: {active_iso[:20]}", ST7789_COLORS['WHITE'])

        self._draw_text(5, 48, "Select ISO:", ST7789_COLORS['YELLOW'])

        visible_items = items[:5]
        menu_y = 62
        item_height = 30

        for i, item in enumerate(visible_items):
            y = menu_y + i * item_height
            is_selected = (i == selected_index)
            is_active = (item == active_iso)

            if is_selected:
                self.draw.rectangle((0, y, 240, y + item_height), fill=ST7789_COLORS['GREEN'])
                prefix = ">"
                text_color = ST7789_COLORS['BLACK']
            elif is_active:
                self.draw.rectangle((0, y, 240, y + item_height), fill=ST7789_COLORS['BLUE'])
                prefix = " "
                text_color = ST7789_COLORS['WHITE']
            else:
                self.draw.rectangle((0, y, 240, y + item_height), fill=ST7789_COLORS['BLACK'])
                prefix = " "
                text_color = ST7789_COLORS['WHITE']

            display_item = item[:28]
            self._draw_text(10, y + 8, f"{prefix} {display_item}", text_color)

            if is_active:
                self._draw_text(200, y + 8, "*", ST7789_COLORS['YELLOW'])

        self._draw_text(5, 220, "w/s:nav Enter:sel d:Wi-Fi a:MTP", ST7789_COLORS['YELLOW'])
        self._update()

    def _update(self):
        """Send buffer to display like Raspyjack."""
        img = np.asarray(self.image)
        pix = np.zeros((self.width, self.height, 2), dtype=np.uint8)
        pix[...,[0]] = np.add(np.bitwise_and(img[...,[0]], 0xF8), np.right_shift(img[...,[1]], 5))
        pix[...,[1]] = np.add(np.bitwise_and(np.left_shift(img[...,[1]], 3), 0xE0), np.right_shift(img[...,[2]], 3))
        pix = pix.flatten().tolist()

        self._set_window(0, 0, self.width, self.height)
        GPIO.output(self.dc_pin, GPIO.HIGH)
        for i in range(0, len(pix), 4096):
            SPI_Write_Byte(pix[i:i+4096])

    def update(self):
        """Refresh display from buffer."""
        self._update()

    def close(self):
        """Release display resources."""
        self._backlight(False)
        self.clear(ST7789_COLORS['BLACK'])
        self._update()
        if SPI:
            SPI.close()
        if HAS_GPIO:
            GPIO.cleanup([self.dc_pin, self.rst_pin, self.bl_pin])


class Display(ST7789):
    """ZeroCD Display class (ST7789 wrapper)."""
    def __init__(self):
        super().__init__(
            dc_pin=DISPLAY_PINS['dc'],
            rst_pin=DISPLAY_PINS['rst'],
            bl_pin=DISPLAY_PINS['bl']
        )
        self.logger = get_logger("display")

    def init(self) -> bool:
        """Initialize display hardware."""
        return super().init()

    def clear(self, color=(0, 0, 0)):
        """Clear display with color."""
        super().clear(color)

    def show_splash(self):
        """Show ZeroCD splash screen."""
        super().show_splash()

    def draw_menu(
        self,
        items: List[str],
        selected_index: int,
        active_iso: Optional[str] = None,
        wifi_on: bool = False,
        usb_bound: bool = False,
        mtp_on: bool = False
    ):
        """Draw ISO selection menu."""
        super().draw_menu(items, selected_index, active_iso, wifi_on, usb_bound, mtp_on)

    def draw_status(self, wifi_on: bool, usb_bound: bool, active_iso: str):
        """Draw status bar."""
        pass

    def update(self):
        """Refresh display from buffer."""
        super().update()

    def close(self):
        """Release display resources."""
        super().close()