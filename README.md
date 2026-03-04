# ZeroCD

DIY USB CD-ROM and LAN adapter for Raspberry Pi Zero 2 W

![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%20Zero%202%20W-green)
![Python](https://img.shields.io/badge/python-3.9+-blue)
![License](https://img.shields.io/badge/license-MIT-orange)

## Features

- **USB Gadget Mode** - CD-ROM emulation via USB
- **USB Ethernet** - Network adapter via USB (RNDIS)
- **1.3" ST7789 LCD** - Menu and status display
- **WiFi Management** - ISO upload via WebUI
- **Captive Portal** - WiFi setup without network connection

## Requirements

### Hardware
- Raspberry Pi Zero 2 W
- ST7789 1.3" LCD HAT (240x240)
- USB cable (for power and data)
- MicroSD card

### Software
- Raspberry Pi OS Lite (or compatible)
- Python 3.9+

## Installation

```bash
# Clone repository
cd /opt
sudo git clone https://github.com/Sergey004/ZeroCD
cd ZeroCD

# Run installer
sudo ./install.sh
```

Installer will automatically:
- Install system dependencies (hostapd, dnsmasq, iptables)
- Install Python packages (Flask, Pillow, numpy)
- Download fonts (Font Awesome, DejaVu Sans)
- Enable SPI interface
- Create systemd service (optional)

## Usage

### Run on Raspberry Pi

```bash
sudo python3 main.py
```

### PC Emulation Mode

```bash
ZEROCD_PLATFORM=pc python3 main.py
```

### Controls

| Button | Action |
|--------|--------|
| w/s | Navigate up/down |
| Enter | Select ISO |
| d | WiFi menu |
| q | Quit |

## WebUI

WebUI is only available when WiFi is connected and NOT in USB Gadget mode (to save power).

### Access

```
http://<IP>:8080
```

IP address is shown on display when connected to WiFi.

### WebUI Features

- **ISO List** - View and select uploaded images
- **File Upload** - Upload ISO from computer (drag&drop)
- **Download from URL** - Download images from internet
- **WiFi Settings** - Network connection, access point management

### Popular Images for Download

- Ubuntu Desktop 22.04/24.04
- Debian 12 Live
- Fedora Workstation
- Arch Linux
- Kali Linux
- Linux Mint
- Netboot.xyz

## WiFi and Captive Portal

### Auto-start Captive Portal

If no saved network is found at boot, access point (Captive Portal) starts automatically.

### Connect to WiFi

1. Connect to access point `ZeroCD-XXXX`
2. Enter password (shown on LCD)
3. Open browser - setup page opens
4. Enter your WiFi network credentials
5. After connection, Captive Portal stops

### QR Code

LCD displays QR code for quick connection to access point.

## Project Structure

```
ZeroCD/
├── config.py          # Configuration
├── main.py            # Main program
├── install.sh         # Installation script
├── requirements.txt   # Python dependencies
├── ui/                # LCD UI
│   ├── display.py     # ST7789 driver
│   ├── display_pc.py # PC emulator
│   ├── renderer.py   # Text and icon rendering
│   └── menu.py       # Menu handling
├── net/               # Network functions
│   ├── wifi.py       # WiFi manager
│   └── captive.py    # Captive Portal
├── web/               # WebUI
│   ├── server.py     # Flask server
│   └── templates/    # HTML templates
├── usb/               # USB Gadget
│   ├── gadget.py     # USB setup
│   └── iso_manager.py# ISO management
├── input/             # Input
│   └── joystick.py   # GPIO joystick
└── system/            # System
    └── logger.py     # Logging
```

## Known Limitations

1. **Pi Zero 2 W only** - requires built-in WiFi adapter
2. **USB Gadget Mode** - WebUI disabled to save power
3. **Single network profile** - only one WiFi network is saved

## Development

### Test UI on PC

```bash
python test_display.py --interactive
```

### Test renderer

```bash
python test_display.py --renderer
```

## License

GPL-3.0 license

## Credits

- [Raspyjack](https://github.com/7h30th3r0n3/Raspyjack) - UI and WebUI inspiration
- [Waveshare](https://www.waveshare.com) - ST7789 driver
- [Font Awesome](https://fontawesome.com) - Icons
