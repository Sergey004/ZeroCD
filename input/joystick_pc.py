"""
PC Joystick emulator using keyboard
"""
import sys
import select
import tty
import termios
from enum import Enum
from typing import Optional, Callable, Dict


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    PRESS = "press"
    NONE = "none"


class JoystickPC:
    """
    PC-based joystick emulator using keyboard.

    Controls:
    - Arrow UP / W: Up
    - Arrow DOWN / S: Down
    - Arrow LEFT / A: Left
    - Arrow RIGHT / D: Right
    - Enter / Space: Press

    Usage:
        joystick = JoystickPC()
        joystick.start_polling(callback)
        # Or: direction = joystick.get_keypress()
    """

    KEY_MAP: Dict[str, Direction] = {
        'w': Direction.UP,
        'k': Direction.UP,
        '\x1b[A': Direction.UP,
        's': Direction.DOWN,
        'j': Direction.DOWN,
        '\x1b[B': Direction.DOWN,
        'a': Direction.LEFT,
        'h': Direction.LEFT,
        '\x1b[D': Direction.LEFT,
        'd': Direction.RIGHT,
        'l': Direction.RIGHT,
        '\x1b[C': Direction.RIGHT,
        '\n': Direction.PRESS,
        ' ': Direction.PRESS,
        '\r': Direction.PRESS,
    }

    def __init__(self, callback: Optional[Callable[[Direction], None]] = None):
        self.callback = callback
        self.running = False
        self._thread = None

    def get_keypress(self, timeout: float = 0.1) -> Direction:
        """
        Get single keypress with timeout.

        Returns:
            Direction or NONE if timeout
        """
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())

            dr, dw, de = select.select([sys.stdin], [], [], [] if timeout is None else timeout)
            if dr:
                key = sys.stdin.read(1)
                if key == '\x1b':
                    seq = key + sys.stdin.read(2)
                    return self.KEY_MAP.get(seq, Direction.NONE)
                return self.KEY_MAP.get(key, Direction.NONE)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        return Direction.NONE

    def start_polling(self, callback: Callable[[Direction], None]):
        """Start polling keyboard in background."""
        self.callback = callback
        self.running = True
        import threading
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _poll_loop(self):
        """Background polling loop."""
        import time
        debounce_time = 0.15
        last_direction_time = 0

        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            while self.running:
                direction = self.get_keypress(timeout=0.05)
                if direction != Direction.NONE:
                    now = time.time()
                    if now - last_direction_time > debounce_time:
                        if self.callback:
                            self.callback(direction)
                        last_direction_time = now
                time.sleep(0.01)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    def stop(self):
        """Stop polling."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)

    def read_event(self):
        """Read single event (blocking)."""
        return self.get_keypress(timeout=-1)


def is_key_pressed() -> bool:
    """Check if any key is currently pressed."""
    result = select.select([sys.stdin], [], [], 0)
    return len(result[0]) > 0
