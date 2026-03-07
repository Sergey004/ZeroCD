"""
Joystick handler for Waveshare ST7789 LCD HAT
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
        
        required_pins =['GPIO_KEY_UP_PIN', 'GPIO_KEY_DOWN_PIN', 'GPIO_KEY_LEFT_PIN', 
                      'GPIO_KEY_RIGHT_PIN', 'GPIO_KEY_PRESS_PIN']
        
        missing =[pin for pin in required_pins if not hasattr(self.disp, pin) or getattr(self.disp, pin) is None]
        
        if missing:
            self.logger.error(f"Missing joystick pins in display: {missing}")
            raise RuntimeError(f"Display missing joystick pins: {missing}")
        
        self.logger.info("Joystick initialized successfully")

    def _is_pressed(self, pin_attr: str) -> bool:
        """Самый надежный способ проверки нажатия кнопки"""
        try:
            pin = getattr(self.disp, pin_attr, None)
            if pin is None:
                return False
                
            # Идеальный вариант (gpiozero.Button)
            if hasattr(pin, 'is_pressed'):
                return pin.is_pressed
                
            # Запасной вариант
            if hasattr(pin, 'value'):
                return not pin.value
                
            return False
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
            
            if direction != Direction.NONE:
                cooldown = 0.3 if direction == Direction.PRESS else 0.15
                
                if direction != self.last_direction or (now - self.last_trigger[direction] > cooldown):
                    if self.callback:
                        try:
                            self.callback(direction)
                        except Exception as e:
                            self.logger.error(f"Error in joystick callback: {e}")
                    self.last_trigger[direction] = now
            
            self.last_direction = direction
            time.sleep(1.0 / JOYSTICK_POLL_RATE)

    def start_polling(self, callback: Callable[[Direction], None] = None):
        if callback:
            self.callback = callback
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        self.logger.info("Joystick polling thread started")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self.logger.info("Joystick stopped")