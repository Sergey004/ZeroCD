"""
ISO selection menu handler
"""
from typing import List, Optional, Callable
from system.logger import get_logger


class Menu:
    """
    Manages ISO selection menu navigation.

    Usage:
        menu = Menu(iso_list)
        direction = menu.next()
        current = menu.get_current()
        menu.select()
    """

    def __init__(self, items: List[str], on_select: Optional[Callable[[str], None]] = None):
        self.logger = get_logger("menu")
        self.items = items
        self.selected_index = 0
        self.on_select = on_select
        self.scroll_offset = 0

    def next(self) -> str:
        """Move selection to next item."""
        if self.items:
            self.selected_index = (self.selected_index + 1) % len(self.items)
            self._update_scroll()
        return self.get_current()

    def prev(self) -> str:
        """Move selection to previous item."""
        if self.items:
            self.selected_index = (self.selected_index - 1) % len(self.items)
            self._update_scroll()
        return self.get_current()

    def select(self) -> str:
        """Confirm selection."""
        current = self.get_current()
        if current and self.on_select:
            self.on_select(current)
        self.logger.info(f"Selected ISO: {current}")
        return current

    def get_current(self) -> Optional[str]:
        """Get currently selected item."""
        if self.items and 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None

    def get_visible_items(self) -> List[str]:
        """Get items visible in viewport (max 5)."""
        return self.items[:5]

    def _update_scroll(self):
        """Update scroll offset for visible range."""
        pass

    def set_items(self, items: List[str]):
        """Replace menu items."""
        self.items = items
        self.selected_index = 0
        self.scroll_offset = 0

    def get_index(self) -> int:
        """Get current selection index."""
        return self.selected_index

    def get_count(self) -> int:
        """Get total item count."""
        return len(self.items)
