"""
Text rendering utilities for ST7789 display
ZeroCD - DIY USB CD-ROM and LAN adapter for Raspberry Pi Zero 2 W
Using Font Awesome like Raspyjack
"""
from typing import List, Tuple, Optional

from PIL import Image, ImageDraw, ImageFont

from config import DISPLAY_WIDTH, DISPLAY_HEIGHT


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


MENU_ICONS = {
    "ubuntu": "\uf31b",      # Ubuntu logo
    "debian": "\uf4c5",      # Debian logo  
    "fedora": "\uf4c2",      # Fedora logo
    "arch": "\uf17c",        # Arch Linux
    "kali": "\ue1e2",        # Kali (shield)
    "iso": "\uf4c4",         # compact disc / ISO
    "wifi": "\uf1eb",        # wifi
    "network": "\uf6ff",     # network wired
    "usb": "\uf287",         # usb
    "settings": "\uf013",    # cog / settings
    "info": "\uf129",        # question circle
    "check": "\uf00c",       # check
    "error": "\uf00d",       # times
    "arrow_up": "\uf062",    # arrow up
    "arrow_down": "\uf063",  # arrow down
    "arrow_left": "\uf060",  # arrow left
    "arrow_right": "\uf061", # arrow right
    "select": "\uf054",      # chevron right
    "menu": "\uf0c9",        # bars / menu
    "back": "\uf060",        # arrow left
    "home": "\uf015",        # home
    "power": "\uf011",       # power off
    "active": "\uf192",      # dot circle
    "disk": "\uf0c0",        # hdd
}


def get_icon_font(size: int = 12):
    """Get Font Awesome icon font like Raspyjack."""
    try:
        return ImageFont.truetype('/usr/share/fonts/truetype/fontawesome/fa-solid-900.ttf', size)
    except:
        return None


def get_text_font(size: int = 9):
    """Get DejaVu Sans text font."""
    try:
        return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', size)
    except:
        return ImageFont.load_default()


class IconRenderer:
    """Renders icons using Font Awesome like Raspyjack."""

    def __init__(self, draw: ImageDraw.ImageDraw = None, width: int = DISPLAY_WIDTH, height: int = DISPLAY_HEIGHT):
        self.width = width
        self.height = height
        self.draw = draw

    def set_draw(self, draw: ImageDraw.ImageDraw):
        """Set the PIL draw object."""
        self.draw = draw

    def draw_icon(self, name: str, x: int, y: int, color: Tuple[int, int, int] = (255, 255, 255), size: int = 12):
        """Draw Font Awesome icon by name."""
        if self.draw is None:
            return
        
        icon_char = MENU_ICONS.get(name, "")
        if not icon_char:
            return

        font = get_icon_font(size)
        if font is None:
            return

        self.draw.text((x, y), icon_char, fill=color, font=font)

    def draw_menu_icon(self, x: int, y: int, icon_name: str, color: Tuple[int, int, int] = (255, 255, 255), size: int = 12):
        """Draw icon for menu item."""
        self.draw_icon(icon_name, x, y, color, size)


class TextRenderer:
    """Renders text using PIL like Raspyjack."""

    def __init__(self, draw: ImageDraw.ImageDraw = None, width: int = DISPLAY_WIDTH, height: int = DISPLAY_HEIGHT):
        self.width = width
        self.height = height
        self.draw = draw

    def set_draw(self, draw: ImageDraw.ImageDraw):
        """Set the PIL draw object."""
        self.draw = draw

    def draw_text(self, x: int, y: int, text: str, color: Tuple[int, int, int] = (255, 255, 255), size: int = 9):
        """Draw text at position."""
        if self.draw is None:
            return
        
        font = get_text_font(size)
        self.draw.text((x, y), text, fill=color, font=font)

    def draw_centered_text(self, y: int, text: str, color: Tuple[int, int, int] = (255, 255, 255), size: int = 9):
        """Draw centered text at Y position."""
        if self.draw is None:
            return
        
        font = get_text_font(size)
        bbox = self.draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) // 2
        self.draw.text((x, y), text, fill=color, font=font)

    def measure_text(self, text: str, size: int = 9) -> int:
        """Get text width in pixels."""
        font = get_text_font(size)
        bbox = (0, 0, 0, 0)
        if font:
            bbox = font.getbbox(text)
        return bbox[2] - bbox[0]

    def wrap_text(self, text: str, max_width: int, size: int = 9) -> List[str]:
        """Wrap text to fit width. Returns list of lines."""
        if not self.draw:
            return [text]
        
        font = get_text_font(size)
        char_width = self.measure_text("A", size)
        max_chars = max_width // char_width if char_width > 0 else 20
        if max_chars <= 0:
            max_chars = 20

        words = text.split(' ')
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if len(test_line) <= max_chars:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines if lines else [""]

    def draw_multiline(self, x: int, y: int, lines: List[str], color: Tuple[int, int, int] = (255, 255, 255), size: int = 9):
        """Draw multiple lines of text."""
        if self.draw is None:
            return
        
        line_height = size + 2
        for i, line in enumerate(lines):
            self.draw_text(x, y + i * line_height, line, color, size)


class UIRenderer:
    """
    Complete UI renderer like Raspyjack.
    Uses PIL ImageDraw + Font Awesome icons.
    """
    
    ICONS = MENU_ICONS
    
    COLORS = ST7789_COLORS
    
    def __init__(self, image: Image.Image = None, width: int = DISPLAY_WIDTH, height: int = DISPLAY_HEIGHT):
        self.width = width
        self.height = height
        self.image = image
        self.draw = None
        self.icon_renderer = IconRenderer()
        self.text_renderer = TextRenderer()
        
        if image:
            self.set_image(image)
    
    def set_image(self, image: Image.Image):
        """Set the PIL image and create draw object."""
        self.image = image
        self.draw = ImageDraw.Draw(image)
        self.icon_renderer.set_draw(self.draw)
        self.text_renderer.set_draw(self.draw)
    
    def clear(self, color: Tuple[int, int, int] = (0, 0, 0)):
        """Clear the display with a color."""
        if self.image:
            self.image.paste(color, (0, 0, self.width, self.height))
    
    def draw_rect(self, x0: int, y0: int, x1: int, y1: int, fill: Tuple[int, int, int] = None, outline: Tuple[int, int, int] = None):
        """Draw a rectangle."""
        if self.draw:
            self.draw.rectangle((x0, y0, x1, y1), fill=fill, outline=outline)
    
    def draw_text(self, x: int, y: int, text: str, color: Tuple[int, int, int] = (255, 255, 255), size: int = 9):
        """Draw text at position."""
        if self.text_renderer:
            self.text_renderer.draw_text(x, y, text, color, size)
    
    def draw_centered_text(self, y: int, text: str, color: Tuple[int, int, int] = (255, 255, 255), size: int = 9):
        """Draw centered text."""
        if self.text_renderer:
            self.text_renderer.draw_centered_text(y, text, color, size)
    
    def draw_icon(self, name: str, x: int, y: int, color: Tuple[int, int, int] = (255, 255, 255), size: int = 12):
        """Draw Font Awesome icon."""
        if self.icon_renderer:
            self.icon_renderer.draw_icon(name, x, y, color, size)
    
    def draw_menu_item(self, x: int, y: int, text: str, is_selected: bool = False, is_active: bool = False, 
                       icon: str = None, text_size: int = 9, icon_size: int = 12):
        """Draw a menu item like Raspyjack."""
        if not self.draw:
            return
        
        bg_color = self.COLORS['BLACK']
        text_color = self.COLORS['WHITE']
        
        if is_selected:
            bg_color = self.COLORS['GREEN']
            text_color = self.COLORS['BLACK']
        elif is_active:
            bg_color = self.COLORS['BLUE']
            text_color = self.COLORS['WHITE']
        
        self.draw.rectangle((x, y, self.width - 1, y + 28), fill=bg_color)
        
        offset_x = x + 5
        
        if icon and self.icon_renderer:
            self.icon_renderer.draw_icon(icon, offset_x, y + 6, text_color, icon_size)
            offset_x += icon_size + 4
        
        prefix = ">" if is_selected else " "
        self.draw_text(offset_x, y + 8, f"{prefix} {text}", text_color, text_size)
        
        if is_active:
            self.draw_text(self.width - 20, y + 8, "*", self.COLORS['YELLOW'], text_size)
    
    def draw_toolbar(self, title: str, wifi_on: bool = False, usb_connected: bool = False):
        """Draw top toolbar like Raspyjack."""
        self.draw_rect(0, 0, self.width, 20, fill=self.COLORS['CYAN'])
        self.draw_text(5, 4, title, self.COLORS['BLACK'], 10)
        
        status_parts = []
        if wifi_on:
            status_parts.append("Wi-Fi:ON")
        if usb_connected:
            status_parts.append("USB:1")
        
        if status_parts:
            status_text = " ".join(status_parts)
            status_width = self.text_renderer.measure_text(status_text, 8) if self.text_renderer else 60
            self.draw_text(self.width - status_width - 5, 5, status_text, self.COLORS['WHITE'], 8)
    
    def draw_help_bar(self, text: str, size: int = 8):
        """Draw bottom help bar."""
        self.draw_rect(0, self.height - 18, self.width, self.height, fill=self.COLORS['BLACK'])
        self.draw_text(5, self.height - 14, text, self.COLORS['YELLOW'], size)


def create_renderer(image: Image.Image = None, width: int = DISPLAY_WIDTH, height: int = DISPLAY_HEIGHT) -> UIRenderer:
    """Create a UIRenderer instance like Raspyjack."""
    return UIRenderer(image, width, height)