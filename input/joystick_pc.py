"""
PC Joystick emulator using curses
"""
import curses
from enum import Enum
from typing import Optional, Callable


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    PRESS = "press"
    QUIT = "quit"
    NONE = "none"


class JoystickPC:
    """
    PC-based joystick emulator using curses keyboard input.

    Controls:
    - Arrow UP / W / K: Up
    - Arrow DOWN / S / J: Down
    - Arrow LEFT / A / H: Left
    - Arrow RIGHT / D / L: Right
    - Enter / Space: Press
    - Q: Quit
    """

    def __init__(self, callback: Optional[Callable[[Direction], None]] = None):
        self.callback = callback
        self.running = False
        self._thread = None
        self.stdscr = None

    def _map_key(self, key: int) -> Direction:
        """Map curses key to Direction."""
        if key in (ord('w'), ord('W'), ord('k'), ord('K'), curses.KEY_UP):
            return Direction.UP
        elif key in (ord('s'), ord('S'), ord('j'), ord('J'), curses.KEY_DOWN):
            return Direction.DOWN
        elif key in (ord('a'), ord('A'), ord('h'), ord('H'), curses.KEY_LEFT):
            return Direction.LEFT
        elif key in (ord('d'), ord('D'), ord('l'), ord('L'), curses.KEY_RIGHT):
            return Direction.RIGHT
        elif key in (ord('\n'), ord(' '), ord('\r')):
            return Direction.PRESS
        elif key in (ord('q'), ord('Q'), 27):
            return Direction.QUIT
        return Direction.NONE

    def get_key(self) -> Direction:
        """Get single key (blocking)."""
        if not self.stdscr:
            return Direction.NONE
        key = self.stdscr.getch()
        return self._map_key(key)

    def start_polling(self, callback: Callable[[Direction], None], stdscr=None):
        """Start polling with callback."""
        self.callback = callback
        self.stdscr = stdscr
        self.running = True
        import threading
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _poll_loop(self):
        """Background polling loop."""
        import time
        debounce_time = 0.15
        last_time = 0

        while self.running:
            if self.stdscr:
                try:
                    self.stdscr.nodelay(True)
                    key = self.stdscr.getch()
                    if key != -1:
                        direction = self._map_key(key)
                        if direction != Direction.NONE:
                            now = time.time()
                            if now - last_time > debounce_time:
                                if self.callback:
                                    self.callback(direction)
                                last_time = now
                except:
                    pass
            time.sleep(0.02)

    def stop(self):
        """Stop polling."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)
