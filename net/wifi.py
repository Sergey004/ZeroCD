"""
WiFi Manager for ZeroCD
Manages WiFi connections, networks, and AP mode
"""
import os
import json
import time
import random
import string
import subprocess
from enum import Enum
from typing import Optional, List, Dict
from datetime import datetime

from config import (
    WIFI_INTERFACE, 
    WIFI_AP_SSID_PREFIX, 
    WIFI_AP_IP,
    ZEROCD_DATA_DIR,
    WIFI_NETWORKS_FILE,
    is_gadget_mode
)
from system.logger import get_logger


class WiFiState(Enum):
    """WiFi states."""
    OFF = "off"
    SCANNING = "scanning"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AP_MODE = "ap_mode"
    ERROR = "error"


class WiFiNetwork:
    """WiFi network data."""
    def __init__(self, ssid: str, password: str = "", connected: bool = False):
        self.ssid = ssid
        self.password = password
        self.connected = connected
        self.last_connected = None

    def to_dict(self) -> dict:
        return {
            "ssid": self.ssid,
            "password": self.password,
            "connected": self.connected,
            "last_connected": self.last_connected
        }

    @staticmethod
    def from_dict(data: dict) -> 'WiFiNetwork':
        net = WiFiNetwork(data.get("ssid", ""), data.get("password", ""), data.get("connected", False))
        net.last_connected = data.get("last_connected")
        return net


class WiFiManager:
    """
    Manages WiFi state, connections, and network storage.
    Supports: Pi Zero 2 W (with WiFi), Pi Zero 2 (without WiFi - gracefully handles)
    """

    def __init__(self):
        self.logger = get_logger("wifi")
        self.state = WiFiState.OFF
        self.wifi_interface = WIFI_INTERFACE
        self.current_network: Optional[WiFiNetwork] = None
        self.ap_ssid = ""
        self.ap_password = ""
        self.has_wifi = False
        self._check_wifi()

    def _check_wifi(self):
        """Check if WiFi hardware is available."""
        try:
            result = subprocess.run(
                ["ip", "link", "show", self.wifi_interface],
                capture_output=True,
                text=True,
                timeout=5
            )
            self.has_wifi = self.wifi_interface in result.stdout
            if not self.has_wifi:
                self.logger.warning(f"WiFi interface {self.wifi_interface} not found")
        except Exception as e:
            self.logger.warning(f"Cannot check WiFi: {e}")
            self.has_wifi = False

    def has_wifi_support(self) -> bool:
        """Check if device has WiFi support."""
        return self.has_wifi

    def load_networks(self) -> bool:
        """Load saved networks from file."""
        if not os.path.exists(WIFI_NETWORKS_FILE):
            self._create_default_config()
            return True

        try:
            with open(WIFI_NETWORKS_FILE, 'r') as f:
                data = json.load(f)
            
            if "network" in data and data["network"]:
                self.current_network = WiFiNetwork.from_dict(data["network"])
            
            self.ap_ssid = data.get("ap_ssid", "")
            self.ap_password = data.get("ap_password", "")
            
            self.logger.info(f"Loaded network: {self.current_network.ssid if self.current_network else 'None'}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load networks: {e}")
            return False

    def _create_default_config(self):
        """Create default config file."""
        os.makedirs(ZEROCD_DATA_DIR, exist_ok=True)
        
        mac = self._get_mac_last4()
        self.ap_ssid = f"{WIFI_AP_SSID_PREFIX}-{mac}"
        self.ap_password = self._generate_password()
        
        data = {
            "primary_ssid": None,
            "current_ssid": None,
            "network": None,
            "ap_ssid": self.ap_ssid,
            "ap_password": self.ap_password
        }
        
        with open(WIFI_NETWORKS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.logger.info(f"Created default config with AP: {self.ap_ssid}")

    def _get_mac_last4(self) -> str:
        """Get last 4 characters of MAC address for AP SSID."""
        try:
            with open(f"/sys/class/net/{self.wifi_interface}/address", "r") as f:
                mac = f.read().strip().replace(":", "").upper()
                return mac[-4:]
        except:
            return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

    def _generate_password(self) -> str:
        """Generate random 8 character password."""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choices(chars, k=8))

    def save_network(self, ssid: str, password: str) -> bool:
        """Save network as primary."""
        try:
            self.current_network = WiFiNetwork(ssid, password, connected=False)
            self.current_network.last_connected = datetime.now().isoformat()
            
            data = {
                "primary_ssid": ssid,
                "current_ssid": ssid,
                "network": self.current_network.to_dict(),
                "ap_ssid": self.ap_ssid,
                "ap_password": self.ap_password
            }
            
            with open(WIFI_NETWORKS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Saved network: {ssid}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save network: {e}")
            return False

    def forget_network(self) -> bool:
        """Remove saved network."""
        try:
            self.current_network = None
            data = {
                "primary_ssid": None,
                "current_ssid": None,
                "network": None,
                "ap_ssid": self.ap_ssid,
                "ap_password": self.ap_password
            }
            
            with open(WIFI_NETWORKS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info("Network forgotten")
            return True
        except Exception as e:
            self.logger.error(f"Failed to forget network: {e}")
            return False

    def scan(self) -> List[str]:
        """Scan for available networks."""
        if not self.has_wifi:
            return []
        
        try:
            result = subprocess.run(
                ["sudo", "iwlist", self.wifi_interface, "scan"],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            networks = []
            for line in result.stdout.split('\n'):
                if 'ESSID:' in line:
                    ssid = line.split('ESSID:')[1].strip().strip('"')
                    if ssid and ssid not in networks:
                        networks.append(ssid)
            
            return networks
        except Exception as e:
            self.logger.error(f"Scan failed: {e}")
            return []

    def connect(self, ssid: Optional[str] = None) -> bool:
        """Connect to network (ssid or saved primary)."""
        if not self.has_wifi:
            self.logger.error("No WiFi hardware")
            return False
        
        target_ssid = ssid or (self.current_network.ssid if self.current_network else None)
        if not target_ssid:
            self.logger.error("No network to connect to")
            return False
        
        self.state = WiFiState.CONNECTING
        self.logger.info(f"Connecting to {target_ssid}...")
        
        try:
            wpa_supplicant_conf = "/tmp/zerocd_wpa.conf"
            with open(wpa_supplicant_conf, 'w') as f:
                f.write(f'''ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US
network={{
    ssid="{target_ssid}"
    psk="{self.current_network.password if self.current_network and self.current_network.ssid == target_ssid else ''}"
}}
''')
            
            subprocess.run(["sudo", "wpa_supplicant", "-B", "-i", self.wifi_interface, 
                          "-c", wpa_supplicant_conf], check=True, capture_output=True)
            
            time.sleep(3)
            
            subprocess.run(["sudo", "dhclient", "-r", self.wifi_interface], capture_output=True)
            subprocess.run(["sudo", "dhclient", self.wifi_interface], check=True, capture_output=True)
            
            if self.current_network:
                self.current_network.connected = True
                self.current_network.last_connected = datetime.now().isoformat()
                self._save_network_state()
            
            self.state = WiFiState.CONNECTED
            self.logger.info(f"Connected to {target_ssid}")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.state = WiFiState.ERROR
            return False

    def _save_network_state(self):
        """Save current network state to file."""
        if not self.current_network:
            return
        
        try:
            with open(WIFI_NETWORKS_FILE, 'r') as f:
                data = json.load(f)
            
            data["current_ssid"] = self.current_network.ssid
            data["network"] = self.current_network.to_dict()
            
            with open(WIFI_NETWORKS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")

    def disconnect(self) -> bool:
        """Disconnect from WiFi."""
        if not self.has_wifi:
            return False
        
        try:
            subprocess.run(["sudo", "wpa_cli", "-i", self.wifi_interface, "disconnect"], capture_output=True)
            subprocess.run(["sudo", "dhclient", "-r", self.wifi_interface], capture_output=True)
            
            if self.current_network:
                self.current_network.connected = False
                self._save_network_state()
            
            self.state = WiFiState.OFF
            self.logger.info("Disconnected")
            return True
        except Exception as e:
            self.logger.error(f"Disconnect failed: {e}")
            return False

    def get_ip(self) -> Optional[str]:
        """Get WiFi interface IP address."""
        try:
            result = subprocess.run(
                ["ip", "-4", "addr", "show", self.wifi_interface],
                capture_output=True,
                text=True,
                timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'inet ' in line:
                    return line.strip().split()[1].split('/')[0]
        except:
            pass
        return None

    def get_status(self) -> WiFiState:
        """Get current WiFi state."""
        if not self.has_wifi:
            return WiFiState.OFF
        
        if self.state == WiFiState.AP_MODE:
            return WiFiState.AP_MODE
        
        # Если у нас есть IP-адрес на wlan0, значит мы 100% подключены (даже если Linux сделал это сам)
        ip = self.get_ip()
        if ip:
            self.state = WiFiState.CONNECTED
            return WiFiState.CONNECTED
        
        return WiFiState.OFF

    def get_current_ssid(self) -> Optional[str]:
        """Get current SSID directly from Linux OS."""
        if not self.has_wifi:
            return None
            
        try:
            # Пытаемся спросить у утилиты iwgetid (самый надежный способ)
            result = subprocess.run(["iwgetid", "-r"], capture_output=True, text=True)
            ssid = result.stdout.strip()
            if ssid:
                return ssid
                
            # Запасной вариант через iw
            result = subprocess.run(["iw", "dev", self.wifi_interface, "link"], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'SSID:' in line:
                    return line.split('SSID:')[1].strip()
        except:
            pass
            
        # Если команды не сработали, но мы знаем, что подключены
        if self.state == WiFiState.CONNECTED and self.current_network:
            return self.current_network.ssid
            
        return None

    def is_connected(self) -> bool:
        """Check if connected to WiFi."""
        return self.get_status() == WiFiState.CONNECTED

    def get_current_ssid(self) -> Optional[str]:
        """Get current SSID."""
        if self.state == WiFiState.CONNECTED:
            return self.current_network.ssid if self.current_network else None
        return None

    def get_primary_ssid(self) -> Optional[str]:
        """Get primary (saved) SSID."""
        if self.current_network:
            return self.current_network.ssid
        return None

    def start_ap_mode(self) -> bool:
        """Start AP mode (requires WiFi hardware)."""
        if not self.has_wifi:
            self.logger.error("No WiFi hardware for AP mode")
            return False
        
        if not self.ap_ssid:
            mac = self._get_mac_last4()
            self.ap_ssid = f"{WIFI_AP_SSID_PREFIX}-{mac}"
            self.ap_password = self._generate_password()
        
        self.logger.info(f"Starting AP: {self.ap_ssid}")
        self.state = WiFiState.AP_MODE
        return True

    def stop_ap_mode(self) -> bool:
        """Stop AP mode."""
        self.state = WiFiState.OFF
        return True

    def get_ap_config(self) -> Dict[str, str]:
        """Get AP configuration for captive portal."""
        return {
            "ssid": self.ap_ssid,
            "password": self.ap_password,
            "ip": WIFI_AP_IP
        }

    def get_qr_data(self) -> str:
        """Get WiFi QR code data."""
        return f"WIFI:T:WPA;S:{self.ap_ssid};P:{self.ap_password};;"


# Singleton instance
_wifi_manager: Optional[WiFiManager] = None


def get_wifi_manager() -> WiFiManager:
    """Get WiFi manager singleton."""
    global _wifi_manager
    if _wifi_manager is None:
        _wifi_manager = WiFiManager()
    return _wifi_manager