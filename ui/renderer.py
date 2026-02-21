"""
Text rendering utilities for ST7789 display
"""
from typing import List, Tuple


class TextRenderer:
    """Renders text on ST7789 display."""

    def __init__(self, display):
        self.display = display
        self.font = None

    def draw_text(self, x: int, y: int, text: str, color: int = 0xFFFF):
        """Draw text at position."""
        pass

    def draw_centered_text(self, y: int, text: str, color: int = 0xFFFF):
        """Draw centered text at Y position."""
        pass

    def measure_text(self, text: str) -> Tuple[int, int]:
        """Get text dimensions."""
        return 0, 0

    def wrap_text(self, text: str, max_width: int) -> List[str]:
        """Wrap text to fit width."""
        return [text]


class IconRenderer:
    """Renders icons and symbols."""

    ICONS = {
        'iso': '💿',
        'wifi_on': '📶',
        'wifi_off': '📵',
        'usb': '🔌',
        'check': '✓',
        'arrow_up': '▲',
        'arrow_down': '▼',
        'select': '▶',
    }

    def __init__(self, display):
        self.display = display

    def draw_icon(self, name: str, x: int, y: int, color: int = 0xFFFF):
        """Draw icon by name."""
        pass
