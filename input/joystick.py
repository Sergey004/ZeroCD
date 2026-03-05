"""
Joystick input handler for 5-way navigation switch
Uses gpiozero
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
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    PRESS = "press"
    NONE = "none"


class Joystick:
    DEBOUNCE_MS = 50
    POLL_INTERVAL = 1 / JOYSTICK_POLL_RATE

    def __init__(self, callback: Optional[Callable[[Direction], None]] = None):
        self.logger = get_logger("joystick")
        self._available = False
        self.pins = {}
        
        if HAS_GPIO:
            try:
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
            self.logger.warning("gpiozero not available.")

        self.last_state = Direction.NONE
        self.callback = callback
        self.running = False
        self._thread = None

    def _read_pin(self, name: str) -> bool:
        pin = self.pins.get(name)
        if pin:
            return not pin.value
        return False

    def _get_direction(self) -> Direction:
        if not self._available:
            return Direction.NONE
        if self._read_pin('press'): return Direction.PRESS
        if self._read_pin('up'): return Direction.UP
        if self._read_pin('down'): return Direction.DOWN
        if self._read_pin('left'): return Direction.LEFT
        if self._read_pin('right'): return Direction.RIGHT
        return Direction.NONE

    def _poll_loop(self):
        """Edge detection — больше НЕ СПАМИТ при удержании"""
        last_trigger = {d: 0.0 for d in Direction}
        self.last_state = Direction.NONE
        self.logger.info("Joystick polling started")

        while self.running:
            direction = self._get_direction()
            now = time.time()

            if direction != Direction.NONE and direction != self.last_state:
                # новое нажатие (rising edge)
                cooldown = 0.45 if direction == Direction.PRESS else 0.25
                if now - last_trigger[direction] > cooldown:
                    self.logger.info(f"Button triggered: {direction.value}")
                    if self.callback:
                        self.callback(direction)
                    last_trigger[direction] = now

            self.last_state = direction
            time.sleep(self.POLL_INTERVAL)

    def start_polling(self, callback: Callable[[Direction], None]):
        self.callback = callback
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)
        for pin in self.pins.values():
            try:
                pin.close()
            except:
                pass
        self.logger.info("Joystick released")