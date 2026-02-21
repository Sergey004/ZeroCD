"""
Wi-Fi manager for optional hotspot functionality
"""
from enum import Enum
from typing import Optional
from config import WIFI_INTERFACE, USB_ETHERNET_IP, HOST_IP
from system.logger import get_logger


class WiFiState(Enum):
    """Wi-Fi states."""
    OFF = "off"
    ON = "on"
    CONNECTED = "connected"


class WiFiManager:
    """
    Manages Wi-Fi state and network sharing.
    """

    def __init__(self):
        self.logger = get_logger("wifi")
        self.state = WiFiState.OFF

    def enable(self) -> bool:
        """Enable Wi-Fi with NAT for internet sharing."""
        self.logger.info("Enabling Wi-Fi")
        self._setup_wifi()
        self._enable_nat()
        self.state = WiFiState.ON
        return True

    def _setup_wifi(self):
        """Configure Wi-Fi interface."""
        pass

    def _enable_nat(self):
        """Enable IP forwarding and iptables NAT."""
        pass

    def disable(self) -> bool:
        """Disable Wi-Fi."""
        self.logger.info("Disabling Wi-Fi")
        self._disable_nat()
        self._stop_wifi()
        self.state = WiFiState.OFF
        return True

    def _disable_nat(self):
        """Remove NAT rules."""
        pass

    def _stop_wifi(self):
        """Stop Wi-Fi interface."""
        pass

    def status(self) -> WiFiState:
        """Get current Wi-Fi state."""
        return self.state

    def is_enabled(self) -> bool:
        """Check if Wi-Fi is enabled."""
        return self.state != WiFiState.OFF

    def get_ip(self) -> Optional[str]:
        """Get Wi-Fi interface IP address."""
        return None

    def restart(self) -> bool:
        """Restart Wi-Fi."""
        self.disable()
        return self.enable()
