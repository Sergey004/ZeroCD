"""
Joystick для Waveshare ST7789 LCD HAT
Использует disp.digital_read + жёсткий анти-спам
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
        self.disp = disp                    # ← используем твой disp из ST7789
        self.callback = callback
        self.running = False
        self._thread = None
        self.last_direction = Direction.NONE
        self.last_trigger = {d: 0.0 for d in Direction}

    def _is_pressed(self, pin_attr: str) -> bool:
        """Читаем кнопку через disp (точно как в key_demo.py)"""
        try:
            return getattr(self.disp, pin_attr) and self.disp.digital_read(getattr(self.disp, pin_attr)) == 0
        except:
            return False

    def _get_direction(self) -> Direction:
        if self._is_pressed('GPIO_KEY_PRESS_PIN'): return Direction.PRESS
        if self._is_pressed('GPIO_KEY_UP_PIN'):    return Direction.UP
        if self._is_pressed('GPIO_KEY_DOWN_PIN'):  return Direction.DOWN
        if self._is_pressed('GPIO_KEY_LEFT_PIN'):  return Direction.LEFT
        if self._is_pressed('GPIO_KEY_RIGHT_PIN'): return Direction.RIGHT
        return Direction.NONE

    def _poll_loop(self):
        self.logger.info("Joystick polling started (анти-спам версия)")
        
        while self.running:
            direction = self._get_direction()
            now = time.time()

            # Только при новом нажатии + cooldown
            if direction != Direction.NONE:
                cooldown = 0.55 if direction == Direction.PRESS else 0.25   # PRESS — почти не спамит
                
                if direction != self.last_direction or (now - self.last_trigger[direction] > cooldown):
                    self.logger.info(f"Button triggered: {direction.value}")
                    if self.callback:
                        self.callback(direction)
                    self.last_trigger[direction] = now

            self.last_direction = direction
            time.sleep(0.025)  # 40 опросов/сек — плавно и без нагрузки

    def start_polling(self, callback: Callable[[Direction], None]):
        self.callback = callback
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self.logger.info("Joystick released")