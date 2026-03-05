"""
Joystick для Waveshare ST7789 LCD HAT
Использует disp.digital_read как в key_demo.py
"""
import threading
import time
from enum import Enum
from typing import Callable, Optional
from config import JOYSTICK_POLL_RATE
from system.logger import get_logger


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    PRESS = "press"
    NONE = "none"


class Joystick:
    def __init__(self, disp, callback: Optional[Callable[[Direction], None]] = None):
        self.logger = get_logger("joystick")
        self.disp = disp
        self.callback = callback
        self.running = False
        self._thread = None
        self.last_direction = Direction.NONE
        self.last_trigger = {d: 0.0 for d in Direction}
        
        # Verify display has required attributes
        required_pins = ['GPIO_KEY_UP_PIN', 'GPIO_KEY_DOWN_PIN', 'GPIO_KEY_LEFT_PIN', 
                      'GPIO_KEY_RIGHT_PIN', 'GPIO_KEY_PRESS_PIN']
        missing = []
        for pin in required_pins:
            if not hasattr(self.disp, pin) or getattr(self.disp, pin) is None:
                missing.append(pin)
        
        if missing:
            self.logger.error(f"Missing joystick pins in display: {missing}")
            raise RuntimeError(f"Display missing joystick pins: {missing}")
        
        self.logger.info("Joystick initialized successfully")

    def _is_pressed(self, pin_attr: str) -> bool:
        """Check if button is pressed (like key_demo.py: != 0 means pressed)"""
        try:
            pin = getattr(self.disp, pin_attr)
            if pin is None:
                return False
            value = self.disp.digital_read(pin)
            # Like key_demo.py: == 0 is released, != 0 is pressed
            return value != 0
        except Exception as e:
            self.logger.debug(f"Error reading {pin_attr}: {e}")
            return False

    def _get_direction(self) -> Direction:
        if self._is_pressed('GPIO_KEY_PRESS_PIN'): return Direction.PRESS
        if self._is_pressed('GPIO_KEY_UP_PIN'): return Direction.UP
        if self._is_pressed('GPIO_KEY_DOWN_PIN'): return Direction.DOWN
        if self._is_pressed('GPIO_KEY_LEFT_PIN'): return Direction.LEFT
        if self._is_pressed('GPIO_KEY_RIGHT_PIN'): return Direction.RIGHT
        return Direction.NONE

    def _poll_loop(self):
        self.logger.info("Joystick polling started")
        
        while self.running:
            direction = self._get_direction()
            now = time.time()
            
            # Only trigger on new press with cooldown
            if direction != Direction.NONE:
                cooldown = 0.3 if direction == Direction.PRESS else 0.15
                
                if direction != self.last_direction or (now - self.last_trigger[direction] > cooldown):
                    self.logger.debug(f"Button triggered: {direction.value}")
                    if self.callback:
                        self.callback(direction)
                    self.last_trigger[direction] = now
            
            self.last_direction = direction
            time.sleep(1.0 / JOYSTICK_POLL_RATE)

    def start_polling(self, callback: Callable[[Direction], None] = None):
        """Start background polling with callback."""
        if callback:
            self.callback = callback
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        self.logger.info("Joystick polling thread started")

    def stop(self):
        """Stop polling."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self.logger.info("Joystick stopped")
