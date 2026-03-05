"""  
ST7789 display controller for 1.3" HAT  
ZeroCD - DIY USB CD-ROM and LAN adapter for Raspberry Pi Zero 2 W  
Based on lcd_hat/Waveshare approach using gpiozero  
"""  
import time  
from typing import List, Optional  
  
try:  
    import spidev  
    import numpy as np  
    from gpiozero import DigitalOutputDevice, PWMOutputDevice  
    HAS_HARDWARE = True  
except ImportError:  
    HAS_HARDWARE = False  
  
from PIL import Image, ImageDraw, ImageFont  
  
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
  
  
class ST7789:  
    """ST7789 display controller using gpiozero like lcd_hat."""  
    
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
        """Send command byte."""  
        self.GPIO_DC_PIN.off()  
        self.SPI.writebytes([cmd])  
    
    def _data(self, val):  
        """Send data byte."""  
        self.GPIO_DC_PIN.on()  
        self.SPI.writebytes([val])  
    
    def _reset(self):  
        """Reset the display."""  
        self.GPIO_RST_PIN.on()  
        time.sleep(0.01)  
        self.GPIO_RST_PIN.off()  
        time.sleep(0.01)  
        self.GPIO_RST_PIN.on()  
        time.sleep(0.01)  
    
    def _module_init(self):  
        """Initialize SPI and GPIO like lcd_hat."""  
        if not HAS_HARDWARE:  
            return False  
        
        # Initialize GPIO pins using gpiozero  
        self.GPIO_RST_PIN = DigitalOutputDevice(self._rst_pin_num, active_high=True, initial_value=False)  
        self.GPIO_DC_PIN = DigitalOutputDevice(self._dc_pin_num, active_high=True, initial_value=False)  
        self.GPIO_BL_PIN = PWMOutputDevice(self._bl_pin_num, frequency=1000)  
        self.GPIO_BL_PIN.value = 0  # Backlight off initially  
        
        # Initialize SPI  
        self.SPI = spidev.SpiDev(0, 0)  
        self.SPI.max_speed_hz = self._spi_freq  
        self.SPI.mode = 0b00  
        
        return True  
    
    def init(self) -> bool:  
        """Initialize display hardware."""  
        if not HAS_HARDWARE:  
            self._initialized = False  
            return False  
        
        self.logger.info("Initializing ST7789 display")  
        
        if not self._module_init():  
            return False  
        
        self._reset()  
        
        # Initialize display registers (same as lcd_hat)  
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
        
        self._backlight(True)  
        
        self.image = Image.new("RGB", (self.width, self.height), "BLACK")  
        self.draw = ImageDraw.Draw(self.image)  
        
        self._initialized = True  
        self.logger.info("ST7789 initialization complete")  
        return True  
    
    def _set_window(self, x0: int, y0: int, x1: int, y1: int):  
        """Set draw window."""  
        # Set X coordinates  
        self._command(0x2A)  
        self._data(0x00)  
        self._data(x0 & 0xFF)  
        self._data(0x00)  
        self._data((x1 - 1) & 0xFF)  
        
        # Set Y coordinates  
        self._command(0x2B)  
        self._data(0x00)  
        self._data(y0 & 0xFF)  
        self._data(0x00)  
        self._data((y1 - 1) & 0xFF)  
        
        self._command(0x2C)  
    
    def _backlight(self, on: bool):  
        """Control backlight."""  
        if self.GPIO_BL_PIN:  
            self.GPIO_BL_PIN.value = 1.0 if on else 0.0  
    
    def bl_DutyCycle(self, duty: int):  
        """Set backlight duty cycle (0-100)."""  
        if self.GPIO_BL_PIN:  
            self.GPIO_BL_PIN.value = duty / 100.0  
    
    def clear(self, color=(0, 0, 0)):  
        """Clear display with color (RGB tuple)."""  
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
        """Draw ISO selection menu."""  
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
        """Send buffer to display like lcd_hat."""  
        if not HAS_HARDWARE or not self.SPI:  
            return  
        
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
        """Refresh display from buffer."""  
        self._update()  
    
    def close(self):  
        """Release display resources."""  
        self._backlight(False)  
        self.clear(ST7789_COLORS['BLACK'])  
        self._update()  
        
        if self.SPI:  
            self.SPI.close()  
            self.SPI = None  
        
        if self.GPIO_BL_PIN:  
            self.GPIO_BL_PIN.close()  
        if self.GPIO_DC_PIN:  
            self.GPIO_DC_PIN.close()  
        if self.GPIO_RST_PIN:  
            self.GPIO_RST_PIN.close()  
        
        self.logger.info("Display closed")  
  
  
class Display(ST7789):  
    """ZeroCD Display class (ST7789 wrapper)."""  
    def __init__(self):  
        super().__init__(  
            rst_pin=DISPLAY_PINS['rst'],  
            dc_pin=DISPLAY_PINS['dc'],  
            bl_pin=DISPLAY_PINS['bl'],  
            spi_freq=40000000  # 40MHz like lcd_hat  
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
