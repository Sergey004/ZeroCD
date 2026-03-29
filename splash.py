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
    from ui.display import Display
    
    disp = Display()
    
    if disp.init():
        # === 1. ПОКАЗЫВАЕМ КАРТИНКУ ===
        if os.path.exists(IMAGE_PATH):
            try:
                # Открываем изображение
                image = Image.open(IMAGE_PATH)
                
                # Получаем размеры дисплея
                width = disp.width
                height = disp.height
                
                # Меняем размер картинки под экран, чтобы не было искажений
                image = image.resize((width, height), Image.Resampling.LANCZOS)
                
                # Конвертируем в RGB, как того требует драйвер ST7789
                image = image.convert('RGB')
                
                # Поворачиваем на 270 градусов (совместимо с драйвером ST7789)
                image = image.rotate(270, expand=False)
                
                # Отправляем в буфер дисплея через объект Display
                disp.image = image
                disp.update()
                    
                print(f"Loaded and displayed custom image: {IMAGE_PATH}")
                
            except Exception as img_e:
                print(f"Failed to load image: {img_e}")
                disp.show_splash()
        else:
            print(f"Image {IMAGE_PATH} not found. Using default splash.")
            disp.show_splash()

        # === 2. ВКЛЮЧАЕМ ПОДСВЕТКУ ===
        # Display класс управляет подсветкой через GPIO, просто включаем яркость
        disp.bl_DutyCycle(50)
        
        print("Splash screen running with backlight.")
        print("Press Ctrl+C to stop.")
        
        # === 3. ДЕРЖИМ ЭКРАН ВКЛЮЧЕННЫМ ===
        while True:
            time.sleep(1)
            
except KeyboardInterrupt:
    print("\nStopping splash screen...")
    # При выходе выключаем подсветку
    try:
        disp.close()
    except:
        pass
    os._exit(0)
except Exception as e:
    print(f"Splash error: {e}")
    os._exit(1)