# ZeroCD

DIY USB CD-ROM и LAN адаптер на Raspberry Pi Zero 2 W

![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%20Zero%202%20W-green)
![Python](https://img.shields.io/badge/python-3.9+-blue)
![License](https://img.shields.io/badge/license-MIT-orange)

## Возможности

- **USB Gadget Mode** - эмуляция CD-ROM через USB
- **USB Ethernet** - сетевой адаптер через USB (RNDIS)
- **1.3" ST7789 LCD** - отображение меню и статуса
- **WiFi управление** - загрузка ISO через WebUI
- **Captive Portal** - настройка WiFi без подключения к сети

## Требования

### Аппаратное обеспечение
- Raspberry Pi Zero 2 W
- ST7789 1.3" LCD HAT (240x240)
- USB кабель (для питания и данных)
- MicroSD карта

### Программное обеспечение
- Raspberry Pi OS Lite (или совместимая)
- Python 3.9+

## Установка

```bash
# Клонировать репозиторий
cd /opt
sudo git clone https://github.com/your-repo/ZeroCD.git
cd ZeroCD

# Запустить установщик
sudo ./install.sh
```

Установщик автоматически:
- Установит системные зависимости (hostapd, dnsmasq, iptables)
- Установит Python пакеты (Flask, Pillow, numpy)
- Скачает шрифты (Font Awesome, DejaVu Sans)
- Включит SPI интерфейс
- Создаст systemd сервис (опционально)

## Использование

### Запуск на Raspberry Pi

```bash
sudo python3 main.py
```

### Режим эмуляции на PC

```bash
ZEROCD_PLATFORM=pc python3 main.py
```

### Управление

| Кнопка | Действие |
|--------|----------|
| w/s | Навигация вверх/вниз |
| Enter | Выбрать ISO |
| d | Меню WiFi |
| q | Выход |

## WebUI

WebUI доступен только при подключённом WiFi и **НЕ** в режиме USB Gadget (для экономии питания).

### Доступ

```
http://<IP>:8080
```

IP адрес отображается на дисплее при подключении к WiFi.

### Функции WebUI

- **Список ISO** - просмотр и выбор загруженных образов
- **Загрузка файлов** - загрузка ISO с компьютера (drag&drop)
- **Скачивание по URL** - загрузка образов из интернета
- **Настройки WiFi** - подключение к сети, управление точками доступа

### Популярные образы для загрузки

- Ubuntu Desktop 22.04/24.04
- Debian 12 Live
- Fedora Workstation
- Arch Linux
- Kali Linux
- Linux Mint
- Netboot.xyz

## WiFi и Captive Portal

### Автозапуск Captive Portal

Если при загрузке не найдена сохранённая сеть, автоматически запускается точка доступа (Captive Portal).

### Подключение к WiFi

1. Подключитесь к точке доступа `ZeroCD-XXXX`
2. Введите пароль (отображается на LCD)
3. Откройте браузер - откроется страница настройки
4. Введите данные вашей WiFi сети
5. После подключения Captive Portal остановится

### QR код

На LCD отображается QR код для быстрого подключения к точке доступа.

## Структура проекта

```
ZeroCD/
├── config.py          # Конфигурация
├── main.py            # Главная программа
├── install.sh         # Скрипт установки
├── requirements.txt   # Python зависимости
├── ui/                # UI для LCD
│   ├── display.py     # ST7789 драйвер
│   ├── display_pc.py # Эмулятор для PC
│   ├── renderer.py   # Рендеринг текста и иконок
│   └── menu.py       # Обработка меню
├── net/               # Сетевые функции
│   ├── wifi.py       # WiFi менеджер
│   └── captive.py    # Captive Portal
├── web/               # WebUI
│   ├── server.py     # Flask сервер
│   └── templates/    # HTML шаблоны
├── usb/               # USB Gadget
│   ├── gadget.py     # USB настройка
│   └── iso_manager.py# Управление ISO
├── input/             # Ввод
│   └── joystick.py   # GPIO джойстик
└── system/            # Система
    └── logger.py     # Логирование
```

## Известные ограничения

1. **Pi Zero 2 W only** - требуется встроенный WiFi адаптер
2. **USB Gadget Mode** - WebUI недоступен для экономии питания
3. **Один сетевой профиль** - сохраняется только одна WiFi сеть

## Разработка

### Тестирование UI на PC

```bash
python test_display.py --interactive
```

### Тестирование рендерера

```bash
python test_display.py --renderer
```

## Лицензия

MIT License

## Благодарности

- [Raspyjack](https://github.com/who-is-hu/Raspyjack) - вдохновение для UI и WebUI
- [Waveshare](https://www.waveshare.com) - драйвер ST7789
- [Font Awesome](https://fontawesome.com) - иконки