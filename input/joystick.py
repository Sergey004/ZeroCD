"""
Joystick input handler for 5-way navigation switch
"""
import gpiod
import threading
import time
from enum import Enum
from typing import Callable, Optional, Tuple
from config import JOYSTICK_PINS, JOYSTICK_POLL_RATE
from system.logger import get_logger


class Direction(Enum):
    """Joystick directions."""
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    PRESS = "press"
    NONE = "none"


class Joystick:
    """
    Handles 5-way joystick input with debouncing.
    """

    DEBOUNCE_MS = 50
    POLL_INTERVAL = 1 / JOYSTICK_POLL_RATE

    def __init__(self, callback: Optional[Callable[[Direction], None]] = None):
        self.logger = get_logger("joystick")
        self.chip = gpiod.Chip('gpiochip0')
        self.lines = {}
        self._setup_lines()
        self.last_state = Direction.NONE
        self.callback = callback
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def _setup_lines(self):
        """Initialize GPIO lines for joystick."""
        for name, pin in JOYSTICK_PINS.items():
            line = self.chip.get_line(pin)
            line.request(
                consumer="zerocd-joystick",
                type=gpiod.LINE_REQ_EV_BOTH_EDGES
            )
            self.lines[name] = line

    def _read_pin(self, name: str) -> bool:
        """Read current state of a pin (active LOW)."""
        line = self.lines.get(name)
        if line:
            return line.get_value() == 0
        return False

    def _get_direction(self) -> Direction:
        """Determine current joystick direction."""
        if self._read_pin('press'):
            return Direction.PRESS
        if self._read_pin('up'):
            return Direction.UP
        if self._read_pin('down'):
            return Direction.DOWN
        if self._read_pin('left'):
            return Direction.LEFT
        if self._read_pin('right'):
            return Direction.RIGHT
        return Direction.NONE

    def get_direction(self, debounce: bool = True) -> Direction:
        """Get current joystick direction."""
        current = self._get_direction()

        if not debounce or current == self.last_state:
            self.last_state = current
            return current

        time.sleep(self.DEBOUNCE_MS / 1000)

        new_state = self._get_direction()
        if new_state == current:
            self.last_state = new_state
            return new_state

        return Direction.NONE

    def read_event(self) -> Tuple[Direction, float]:
        """Read next joystick event with timestamp."""
        direction = self.get_direction()
        return direction, time.time()

    def start_polling(self, callback: Callable[[Direction], None]):
        """Start background polling with callback."""
        self.callback = callback
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _poll_loop(self):
        """Background polling loop."""
        last_directions = {d: 0 for d in Direction}
        debounce_time = 0.1

        while self.running:
            direction = self._get_direction()
            now = time.time()

            if direction != Direction.NONE:
                if now - last_directions[direction] > debounce_time:
                    if self.callback:
                        self.callback(direction)
                    last_directions[direction] = now

            time.sleep(self.POLL_INTERVAL)

    def stop(self):
        """Stop polling and release GPIO."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)

        for line in self.lines.values():
            line.release()
        self.chip.close()
        self.logger.info("Joystick released")
