"""
Joystick input handler for 5-way navigation switch
Uses gpiozero like lcd_hat
"""
import threading
import time
from enum import Enum
from typing import Callable, Optional
from config import JOYSTICK_PINS, JOYSTICK_POLL_RATE
from system.logger import get_logger

try:
    from gpiozero import DigitalInputDevice
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False


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
    Uses gpiozero like lcd_hat - buttons are active LOW with pull-up.
    """

    DEBOUNCE_MS = 50
    POLL_INTERVAL = 1 / JOYSTICK_POLL_RATE

    def __init__(self, callback: Optional[Callable[[Direction], None]] = None):
        self.logger = get_logger("joystick")
        self._available = False
        self.pins = {}
        
        if HAS_GPIO:
            try:
                # Initialize pins like lcd_hat - INPUT with pull_up=True, active_state=None
                # When button is pressed, value becomes 0 (LOW)
                self.pins['up'] = DigitalInputDevice(JOYSTICK_PINS['up'], pull_up=True)
                self.pins['down'] = DigitalInputDevice(JOYSTICK_PINS['down'], pull_up=True)
                self.pins['left'] = DigitalInputDevice(JOYSTICK_PINS['left'], pull_up=True)
                self.pins['right'] = DigitalInputDevice(JOYSTICK_PINS['right'], pull_up=True)
                self.pins['press'] = DigitalInputDevice(JOYSTICK_PINS['press'], pull_up=True)
                self._available = True
                self.logger.info("Joystick initialized with gpiozero")
            except Exception as e:
                self.logger.warning(f"Failed to initialize joystick GPIO: {e}")
        else:
            self.logger.warning("gpiozero not available. Joystick input disabled.")
        
        self.last_state = Direction.NONE
        self.callback = callback
        self.running = False
        self._thread = None

    def _read_pin(self, name: str) -> bool:
        """Read current state of a pin.
        Returns True if button is pressed.
        With pull-up: value is True when released, False when pressed.
        """
        pin = self.pins.get(name)
        if pin:
            pressed = not pin.value  # Invert: False = pressed
            if pressed:
                self.logger.debug(f"Button {name} pressed (raw={pin.value})")
            return pressed
        return False

    def _get_direction(self) -> Direction:
        """Determine current joystick direction."""
        if not self._available:
            return Direction.NONE
            
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

    def read_event(self):
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
        self.logger.info("Joystick polling started")

        while self.running:
            direction = self._get_direction()
            now = time.time()

            if direction != Direction.NONE:
                self.logger.debug(f"Button detected: {direction.value}")
                if now - last_directions[direction] > debounce_time:
                    self.logger.info(f"Button triggered: {direction.value}")
                    if self.callback:
                        self.callback(direction)
                    last_directions[direction] = now

            time.sleep(self.POLL_INTERVAL)

    def stop(self):
        """Stop polling and release GPIO."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)

        # Close all pin devices
        for pin in self.pins.values():
            try:
                pin.close()
            except:
                pass
        self.pins.clear()
        
        self.logger.info("Joystick released")
