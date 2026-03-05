"""
ZeroCD Configuration
"""
import os
import uuid

# Display pins (ST7789 1.3" HAT)
DISPLAY_PINS = {
    'mosi': 10,
    'sclk': 11,
    'ce0': 8,
    'dc': 25,
    'rst': 27,
    'bl': 24,
}

# Joystick pins
JOYSTICK_PINS = {
    'up': 6,
    'down': 19,
    'left': 5,
    'right': 26,
    'press': 13,
}

# Display dimensions
DISPLAY_WIDTH = 240
DISPLAY_HEIGHT = 240

# ISO storage
ISO_DIR = "/mnt/iso_storage"
TEST_ISO_DIR = "/tmp/iso_storage"

# USB Gadget configuration
GADGET_DIR = "/sys/kernel/config/usb_gadget/zerocd"
GADGET_UDC = None

# Network interfaces
WIFI_INTERFACE = "wlan0"
USB_ETHERNET_INTERFACE = "usb0"
USB_ETHERNET_IP = "192.168.7.1"
HOST_IP = "192.168.7.2"

# WiFi AP settings
WIFI_AP_SSID_PREFIX = "ZeroCD"
WIFI_AP_CHANNEL = 6
WIFI_AP_IP = "192.168.4.1"
WIFI_AP_DHCP_START = "192.168.4.10"
WIFI_AP_DHCP_END = "192.168.4.50"

# WebUI settings
WEBUI_PORT = 8080
WEBUI_HOST = "0.0.0.0"
WEBUI_SECRET_KEY = os.environ.get("ZEROCD_SECRET_KEY", str(uuid.uuid4()))

# ZeroCD data directory
ZEROCD_DATA_DIR = "/opt/zerocd"
WIFI_NETWORKS_FILE = os.path.join(ZEROCD_DATA_DIR, "wifi_networks.json")
WEBUI_AUTH_FILE = os.path.join(ZEROCD_DATA_DIR, "webui_auth.json")
WEBUI_SESSION_SECRET = os.path.join(ZEROCD_DATA_DIR, ".webui_session_secret")

# Logging
LOG_FILE = "zerocd.log"
JOYSTICK_POLL_RATE = 50
MENU_ITEMS_PER_PAGE = 5

# Platform detection
PLATFORM = os.environ.get("ZEROCD_PLATFORM", "pi")
USE_PC_EMULATION = PLATFORM == "pc"

# Popular ISO URLs for download
POPULAR_ISOS = [
    {"name": "Ubuntu Desktop 22.04", "url": "https://releases.ubuntu.com/22.04/ubuntu-22.04.3-desktop-amd64.iso", "size": "4.2GB"},
    {"name": "Ubuntu Desktop 24.04", "url": "https://releases.ubuntu.com/24.04/ubuntu-24.04-desktop-amd64.iso", "size": "4.7GB"},
    {"name": "Debian 12 Live", "url": "https://cdimage.debian.org/debian-cd/12.7.0 live/amd64/iso-hybrid/debian-live-12.7.0-amd64-desktop.iso", "size": "3.2GB"},
    {"name": "Fedora Workstation 40", "url": "https://download.fedoraproject.org/pub/fedora/linux/releases/40/Workstation/x86_64/iso/Fedora-Workstation-40-1.6.0-x86_64.iso", "size": "2.2GB"},
    {"name": "Arch Linux", "url": "https://mirror.rackspace.com/archlinux/iso/2024.03.01/archlinux-2024.03.01-x86_64.iso", "size": "1.1GB"},
    {"name": "Kali Linux", "url": "https://cdimage.kali.org/kali-2024.1/kali-linux-2024.1-live-amd64.iso", "size": "4.3GB"},
    {"name": "Linux Mint 21", "url": "https://mirror.mintlinuxaustralia.org.uk/release/linuxmint-21.3/linuxmint-21.3-cinnamon-64bit.iso", "size": "2.5GB"},
    {"name": "Netboot.xyz", "url": "https://boot.netboot.xyz/ipxe/netboot.xyz-multiarch.iso", "size": "80MB"},
]

# Check if running in USB Gadget mode
def is_gadget_mode() -> bool:
    """Check if USB gadget is active (device mode)."""
    return os.path.exists(GADGET_DIR)

# Ensure data directory exists
def ensure_data_dir():
    """Create data directory if it doesn't exist."""
    os.makedirs(ZEROCD_DATA_DIR, exist_ok=True)