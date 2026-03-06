#!/usr/bin/env python3
import sys
import os
import time
from PIL import Image

# Динамически получаем путь к папке
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Укажите точное имя файла вашей картинки!
IMAGE_PATH = os.path.join(BASE_DIR, "splash.png") 

try:
    import RPi.GPIO as GPIO
    from ui.display import Display
    
    disp = Display()
    
    if disp.init():
        # === 1. ПОКАЗЫВАЕМ КАРТИНКУ ===
        if os.path.exists(IMAGE_PATH):
            try:
                # Открываем изображение
                image = Image.open(IMAGE_PATH)
                
                # Получаем размеры дисплея (для 1.3" HAT это обычно 240x240)
                width = getattr(disp, 'width', 240)
                height = getattr(disp, 'height', 240)
                
                # Меняем размер картинки под экран, чтобы не было искажений
                # Image.Resampling.LANCZOS обеспечивает лучшее сглаживание
                image = image.resize((width, height), Image.Resampling.LANCZOS)
                
                # Конвертируем в RGB, как того требует драйвер ST7789
                image = image.convert('RGB')
                
                # Отправляем в буфер дисплея. 
                # У Waveshare метод обычно спрятан внутри объекта disp.disp
                if hasattr(disp, 'disp') and hasattr(disp.disp, 'display'):
                    disp.disp.display(image)
                elif hasattr(disp, 'show_image'):  # Запасной вариант, если у вас написана обертка
                    disp.show_image(image)
                else:
                    print("Не могу найти метод вывода картинки на экран.")
                    disp.show_splash()
                    
                print(f"Loaded and displayed custom image: {IMAGE_PATH}")
                
            except Exception as img_e:
                print(f"Failed to load image: {img_e}")
                disp.show_splash() # Если картинка битая - рисуем стандартный сплеш
        else:
            print(f"Image {IMAGE_PATH} not found. Using default splash.")
            disp.show_splash()

        # === 2. НАСТРАИВАЕМ ЯРКОСТЬ 50% ===
        BL_PIN = 24  # Стандартный пин подсветки
        
        # Пытаемся взять пин из драйвера, если он там переопределен
        if hasattr(disp, 'disp') and hasattr(disp.disp, '_bl'):
            BL_PIN = disp.disp._bl
            
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(BL_PIN, GPIO.OUT)
        
        # ШИМ на 500 Гц, скважность 50% (можно менять от 0 до 100)
        pwm = GPIO.PWM(BL_PIN, 500)
        pwm.start(5) 
        
        print("Splash screen running at 50% brightness.")
        print("Press Ctrl+C to stop.")
        
        # === 3. ДЕРЖИМ ЭКРАН ВКЛЮЧЕННЫМ ===
        while True:
            time.sleep(1)
            
except KeyboardInterrupt:
    print("\nStopping splash screen...")
    # При выходе выключаем ШИМ, чтобы экран не светился
    try:
        GPIO.cleanup()
    except:
        pass
    os._exit(0)
except Exception as e:
    print(f"Splash error: {e}")
    os._exit(1)