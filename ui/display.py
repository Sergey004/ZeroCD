"""
ST7789 display controller for 1.3" HAT
ZeroCD - DIY USB CD-ROM and LAN adapter for Raspberry Pi Zero 2 W
"""
import time
from typing import List, Optional

try:
    import spidev
    import numpy as np
    from gpiozero import DigitalOutputDevice, Button
    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False

from PIL import Image, ImageDraw, ImageFont

from config import DISPLAY_PINS, DISPLAY_WIDTH, DISPLAY_HEIGHT, JOYSTICK_PINS
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

class ST7789:
    width = DISPLAY_WIDTH
    height = DISPLAY_HEIGHT

    def __init__(self, rst_pin: int = DISPLAY_PINS['rst'],
                 dc_pin: int = DISPLAY_PINS['dc'],
                 bl_pin: int = DISPLAY_PINS['bl'],
                 spi_freq: int = 40000000):
        self._rst_pin_num = rst_pin
        self._dc_pin_num = dc_pin
        self._bl_pin_num = bl_pin
        self._spi_freq = spi_freq
        self.SPI = None
        self.GPIO_RST_PIN = None
        self.GPIO_DC_PIN = None
        self.GPIO_BL_PIN = None
        self.image = None
        self.draw = None
        self._initialized = False
        self.logger = get_logger("st7789")

    def _command(self, cmd):
        self.GPIO_DC_PIN.off()
        self.SPI.writebytes([cmd])

    def _data(self, val):
        self.GPIO_DC_PIN.on()
        self.SPI.writebytes([val])

    def _reset(self):
        self.GPIO_RST_PIN.on()
        time.sleep(0.01)
        self.GPIO_RST_PIN.off()
        time.sleep(0.01)
        self.GPIO_RST_PIN.on()
        time.sleep(0.01)

    def _module_init(self):
        if not HAS_HARDWARE:
            return False

        # Жесткое управление пинами (никакого ШИМ = никакого мерцания)
        self.GPIO_RST_PIN = DigitalOutputDevice(self._rst_pin_num, active_high=True, initial_value=False)
        self.GPIO_DC_PIN = DigitalOutputDevice(self._dc_pin_num, active_high=True, initial_value=False)
        self.GPIO_BL_PIN = DigitalOutputDevice(self._bl_pin_num, active_high=True, initial_value=False)

        self.SPI = spidev.SpiDev(0, 0)
        self.SPI.max_speed_hz = self._spi_freq
        self.SPI.mode = 0b00

        # Умный класс Button для 100% надежного опроса
        self.GPIO_KEY_UP_PIN = Button(JOYSTICK_PINS['up'], pull_up=True)
        self.GPIO_KEY_DOWN_PIN = Button(JOYSTICK_PINS['down'], pull_up=True)
        self.GPIO_KEY_LEFT_PIN = Button(JOYSTICK_PINS['left'], pull_up=True)
        self.GPIO_KEY_RIGHT_PIN = Button(JOYSTICK_PINS['right'], pull_up=True)
        self.GPIO_KEY_PRESS_PIN = Button(JOYSTICK_PINS['press'], pull_up=True)
        
        # Доп кнопки, если они есть
        self.GPIO_KEY1_PIN = Button(JOYSTICK_PINS['key1'], pull_up=True)
        self.GPIO_KEY2_PIN = Button(JOYSTICK_PINS['key2'], pull_up=True)
        self.GPIO_KEY3_PIN = Button(JOYSTICK_PINS['key3'], pull_up=True)

        return True

    def init(self) -> bool:
        if not HAS_HARDWARE:
            self._initialized = False
            return False

        self.logger.info("Initializing ST7789 display")

        if not self._module_init():
            return False

        self._reset()

        self._command(0x36)
        self._data(0x70)

        self._command(0x3A)
        self._data(0x05)

        self._command(0xB2)
        self._data(0x0C)
        self._data(0x0C)
        self._data(0x00)
        self._data(0x33)
        self._data(0x33)

        self._command(0xB7)
        self._data(0x35)

        self._command(0xBB)
        self._data(0x19)

        self._command(0xC0)
        self._data(0x2C)

        self._command(0xC2)
        self._data(0x01)

        self._command(0xC3)
        self._data(0x12)

        self._command(0xC4)
        self._data(0x20)

        self._command(0xC6)
        self._data(0x0F)

        self._command(0xD0)
        self._data(0xA4)
        self._data(0xA1)

        self._command(0xE0)
        self._data(0xD0)
        self._data(0x04)
        self._data(0x0D)
        self._data(0x11)
        self._data(0x13)
        self._data(0x2B)
        self._data(0x3F)
        self._data(0x54)
        self._data(0x4C)
        self._data(0x18)
        self._data(0x0D)
        self._data(0x0B)
        self._data(0x1F)
        self._data(0x23)

        self._command(0xE1)
        self._data(0xD0)
        self._data(0x04)
        self._data(0x0C)
        self._data(0x11)
        self._data(0x13)
        self._data(0x2C)
        self._data(0x3F)
        self._data(0x44)
        self._data(0x51)
        self._data(0x2F)
        self._data(0x1F)
        self._data(0x1F)
        self._data(0x20)
        self._data(0x23)

        self._command(0x21)
        self._command(0x11)
        self._command(0x29)

        self._backlight(False) # Ждем команды от main.py на включение

        self.image = Image.new("RGB", (self.width, self.height), "BLACK")
        self.draw = ImageDraw.Draw(self.image)

        self._initialized = True
        self.logger.info("ST7789 initialization complete")
        return True

    def _set_window(self, x0: int, y0: int, x1: int, y1: int):
        self._command(0x2A)
        self._data(0x00)
        self._data(x0 & 0xFF)
        self._data(0x00)
        self._data((x1 - 1) & 0xFF)

        self._command(0x2B)
        self._data(0x00)
        self._data(y0 & 0xFF)
        self._data(0x00)
        self._data((y1 - 1) & 0xFF)

        self._command(0x2C)

    def _backlight(self, on: bool):
        if getattr(self, 'GPIO_BL_PIN', None):
            if on:
                self.GPIO_BL_PIN.on()
            else:
                self.GPIO_BL_PIN.off()

    def fade_out(self, steps: int = 20, step_delay_ms: int = 50):
        # Жесткое отключение
        self._backlight(False)

    def fade_in(self, target_duty: int = 50, steps: int = 20, step_delay_ms: int = 50):
        # Жесткое включение
        self._backlight(True)

    def bl_DutyCycle(self, duty: int):
        self._backlight(duty > 0)

    def digital_read(self, pin):
        """Legacy support"""
        if hasattr(pin, 'is_pressed'):
            return 0 if pin.is_pressed else 1
        return 1

    def clear(self, color=(0, 0, 0)):
        self.image.paste(color, (0, 0, self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)

    def _draw_centered_text(self, y: int, text: str, color=(255, 255, 255), size: int = 1):
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16 * size)
        except:
            font = ImageFont.load_default()
        bbox = self.draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) // 2
        self.draw.text((x, y), text, fill=color, font=font)

    def _draw_text(self, x: int, y: int, text: str, color=(255, 255, 255), size: int = 1):
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16 * size)
        except:
            font = ImageFont.load_default()
        self.draw.text((x, y), text, fill=color, font=font)

    def show_splash(self):
        self.clear(ST7789_COLORS['BLACK'])
        self._draw_centered_text(80, "ZeroCD v1.0", ST7789_COLORS['CYAN'], 2)
        self._draw_centered_text(110, "USB CD-ROM + LAN", ST7789_COLORS['WHITE'])
        self._draw_centered_text(150, "Loading...", ST7789_COLORS['GREEN'])
        self._update()
        time.sleep(1.5)

    def draw_menu(self, items: List[str], selected_index: int, scroll_offset: int = 0,
                  active_iso: Optional[str] = None, wifi_on: bool = False,
                  usb_bound: bool = False, mtp_on: bool = False):
        self.clear(ST7789_COLORS['BLACK'])

        self.draw.rectangle((0, 0, 240, 24), fill=ST7789_COLORS['CYAN'])
        self._draw_text(5, 6, " ZeroCD ", ST7789_COLORS['BLACK'])

        status = f"Wi-Fi:{'ON' if wifi_on else 'OFF'} MTP:{'ON' if mtp_on else 'OFF'}"
        char_width = 10
        text_width = len(status) * char_width
        self._draw_text(240 - text_width - 5, 6, status, ST7789_COLORS['BLACK'])

        if active_iso:
            self.draw.rectangle((0, 24, 240, 40), fill=ST7789_COLORS['BLUE'])
            self._draw_text(5, 28, f" Active: {active_iso[:20]}", ST7789_COLORS['WHITE'])

        self._draw_text(5, 48, "Select ISO:", ST7789_COLORS['YELLOW'])

        visible_items = items
        menu_y = 62
        item_height = 30

        for i, item in enumerate(visible_items):
            global_index = scroll_offset + i
            y = menu_y + i * item_height
            is_selected = (global_index == selected_index)
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

        self._update()

    def draw_create_img_menu(self, items: List[str], selected_index: int, scroll_offset: int = 0,
                             free_space_mb: int = 0):
        self.clear(ST7789_COLORS['BLACK'])

        self.draw.rectangle((0, 0, 240, 24), fill=ST7789_COLORS['YELLOW'])
        self._draw_text(5, 6, " Create IMG ", ST7789_COLORS['BLACK'])

        if free_space_mb > 0:
            free_str = f"Free: {free_space_mb}MB" if free_space_mb < 1024 else f"Free: {free_space_mb // 1024}GB"
            self._draw_text(240 - len(free_str) * 10 - 5, 6, free_str, ST7789_COLORS['BLACK'])

        self._draw_text(5, 28, "Select size:", ST7789_COLORS['CYAN'])

        menu_y = 46
        item_height = 28

        for i, item in enumerate(visible_items := items):
            global_index = scroll_offset + i
            y = menu_y + i * item_height
            is_selected = (global_index == selected_index)

            if is_selected:
                self.draw.rectangle((0, y, 240, y + item_height), fill=ST7789_COLORS['GREEN'])
                prefix = ">"
                text_color = ST7789_COLORS['BLACK']
            else:
                self.draw.rectangle((0, y, 240, y + item_height), fill=ST7789_COLORS['BLACK'])
                prefix = " "
                text_color = ST7789_COLORS['WHITE']

            self._draw_text(10, y + 6, f"{prefix} {item}", text_color)

        self._draw_text(5, 220, "PRESS=create LEFT=back", ST7789_COLORS['GRAY'])

        self._update()

    def _update(self):
        if not HAS_HARDWARE or not self.SPI: return

        img = np.asarray(self.image)
        pix = np.zeros((self.width, self.height, 2), dtype=np.uint8)
        pix[..., [0]] = np.add(np.bitwise_and(img[..., [0]], 0xF8), np.right_shift(img[..., [1]], 5))
        pix[..., [1]] = np.add(np.bitwise_and(np.left_shift(img[..., [1]], 3), 0xE0), np.right_shift(img[..., [2]], 3))
        pix = pix.flatten().tolist()

        self._set_window(0, 0, self.width, self.height)
        self.GPIO_DC_PIN.on()
        for i in range(0, len(pix), 4096):
            self.SPI.writebytes(pix[i:i+4096])

    def update(self):
        self._update()

    def close(self):
        self._backlight(False)
        self.clear(ST7789_COLORS['BLACK'])
        self._update()
        if self.SPI:
            self.SPI.close()
            self.SPI = None
        for pin_attr in['GPIO_KEY_UP_PIN', 'GPIO_KEY_DOWN_PIN', 'GPIO_KEY_LEFT_PIN',
                         'GPIO_KEY_RIGHT_PIN', 'GPIO_KEY_PRESS_PIN', 'GPIO_KEY1_PIN',
                         'GPIO_KEY2_PIN', 'GPIO_KEY3_PIN', 'GPIO_BL_PIN', 'GPIO_DC_PIN',
                         'GPIO_RST_PIN']:
            try:
                pin = getattr(self, pin_attr, None)
                if pin and hasattr(pin, 'close'):
                    pin.close()
            except: pass
        self.logger.info("Display closed")

class Display(ST7789):
    def __init__(self):
        super().__init__(rst_pin=DISPLAY_PINS['rst'], dc_pin=DISPLAY_PINS['dc'], bl_pin=DISPLAY_PINS['bl'])
        self.logger = get_logger("display")