"""
ZeroCD Configuration
"""
import os

DISPLAY_PINS = {
    'mosi': 10,
    'sclk': 11,
    'ce0': 8,
    'dc': 25,
    'rst': 27,
    'bl': 24,
}

JOYSTICK_PINS = {
    'up': 6,
    'down': 19,
    'left': 5,
    'right': 26,
    'press': 13,
}

DISPLAY_WIDTH = 240
DISPLAY_HEIGHT = 240

ISO_DIR = "/images"

GADGET_DIR = "/sys/kernel/config/usb_gadget/zerocd"
GADGET_UDC = None

WIFI_INTERFACE = "wlan0"
USB_ETHERNET_INTERFACE = "usb0"
USB_ETHERNET_IP = "192.168.7.1"
HOST_IP = "192.168.7.2"

LOG_FILE = "/var/log/zerocd.log"
JOYSTICK_POLL_RATE = 50
MENU_ITEMS_PER_PAGE = 5
