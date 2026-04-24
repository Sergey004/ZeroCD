"""
ISO selection menu handler
"""
from typing import List, Optional, Callable
from config import PRESET_IMG_SIZES
from system.logger import get_logger


class Menu:
    """Manages ISO selection menu navigation.

    Usage:
        menu = Menu(iso_list)
        direction = menu.next()
        current = menu.get_current()
        menu.select()
    """

    MAX_VISIBLE = 5

    def __init__(self, items: List[str], on_select: Optional[Callable[[str], None]] = None):
        self.logger = get_logger("menu")
        self.items = items
        self.selected_index = 0
        self.on_select = on_select
        self.scroll_offset = 0
        self.in_create_img = False
        self._create_img_items = [s["label"] for s in PRESET_IMG_SIZES]
        self._create_img_mb = [s["mb"] for s in PRESET_IMG_SIZES]
        self._create_selected_index = 0
        self._create_scroll_offset = 0

    def next(self) -> Optional[str]:
        """Move selection to next item."""
        if self.in_create_img:
            self._create_selected_index = (self._create_selected_index + 1) % len(self._create_img_items)
            self._update_create_scroll()
            return self._create_img_items[self._create_selected_index]
        if self.items:
            self.selected_index = (self.selected_index + 1) % len(self.items)
            self._update_scroll()
            return self.get_current()
        return None

    def prev(self) -> Optional[str]:
        """Move selection to previous item."""
        if self.in_create_img:
            self._create_selected_index = (self._create_selected_index - 1) % len(self._create_img_items)
            self._update_create_scroll()
            return self._create_img_items[self._create_selected_index]
        if self.items:
            self.selected_index = (self.selected_index - 1) % len(self.items)
            self._update_scroll()
            return self.get_current()
        return None

    def select(self) -> Optional[str]:
        """Confirm selection."""
        if self.in_create_img:
            return self._create_img_items[self._create_selected_index]
        current = self.get_current()
        if current and self.on_select:
            self.on_select(current)
            self.logger.info(f"Selected ISO: {current}")
        return current

    def enter_create_img(self):
        """Enter Create IMG submenu."""
        self.in_create_img = True
        self._create_selected_index = 0
        self._create_scroll_offset = 0

    def exit_create_img(self):
        """Exit Create IMG submenu back to main menu."""
        self.in_create_img = False

    def get_create_img_mb(self) -> int:
        """Get selected image size in MB from Create IMG submenu."""
        if 0 <= self._create_selected_index < len(self._create_img_mb):
            return self._create_img_mb[self._create_selected_index]
        return 0

    def get_current(self) -> Optional[str]:
        """Get currently selected item."""
        if self.in_create_img:
            if 0 <= self._create_selected_index < len(self._create_img_items):
                return self._create_img_items[self._create_selected_index]
            return None
        if self.items and 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None

    def get_visible_items(self) -> List[str]:
        """Get items visible in viewport (max 5)."""
        if self.in_create_img:
            start = self._create_scroll_offset
            end = min(start + self.MAX_VISIBLE, len(self._create_img_items))
            return self._create_img_items[start:end]
        start = self.scroll_offset
        end = min(start + self.MAX_VISIBLE, len(self.items))
        return self.items[start:end]

    def get_scroll_offset(self) -> int:
        """Get current scroll offset."""
        if self.in_create_img:
            return self._create_scroll_offset
        return self.scroll_offset

    def _update_scroll(self):
        """Update scroll offset for visible range."""
        if not self.items:
            self.scroll_offset = 0
            return

        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + self.MAX_VISIBLE:
            self.scroll_offset = self.selected_index - self.MAX_VISIBLE + 1

    def _update_create_scroll(self):
        """Update scroll offset for Create IMG submenu."""
        if self._create_selected_index < self._create_scroll_offset:
            self._create_scroll_offset = self._create_selected_index
        elif self._create_selected_index >= self._create_scroll_offset + self.MAX_VISIBLE:
            self._create_scroll_offset = self._create_selected_index - self.MAX_VISIBLE + 1

    def set_items(self, items: List[str]):
        """Replace menu items."""
        self.items = items
        self.selected_index = 0
        self.scroll_offset = 0

    def get_index(self) -> int:
        """Get current selection index."""
        if self.in_create_img:
            return self._create_selected_index
        return self.selected_index

    def get_count(self) -> int:
        """Get total item count."""
        if self.in_create_img:
            return len(self._create_img_items)
        return len(self.items)
