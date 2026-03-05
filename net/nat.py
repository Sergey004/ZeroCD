"""
NAT and network forwarding configuration
"""
import subprocess
from typing import Optional
from system.logger import get_logger


class NATManager:
    """
    Manages network address translation for USB Ethernet passthrough.
    """

    def __init__(self, lan_interface: str = "wlan0", usb_interface: str = "usb0"):
        self.logger = get_logger("nat")
        self.lan_interface = lan_interface
        self.usb_interface = usb_interface
        self.usb_ip = "192.168.7.1"
        self.host_ip = "192.168.7.2"

    def enable(self) -> bool:
        """Enable NAT for USB Ethernet passthrough."""
        self.logger.info(f"Enabling NAT: {self.usb_interface} -> {self.lan_interface}")
        try:
            self._configure_usb_interface()
            self._enable_ip_forwarding()
            self._add_iptables_rules()
            return True
        except Exception as e:
            self.logger.error(f"Failed to enable NAT: {e}")
            return False

    def disable(self) -> bool:
        """Disable NAT and remove rules."""
        self.logger.info("Disabling NAT")
        try:
            self._remove_iptables_rules()
            self._disable_ip_forwarding()
            return True
        except Exception as e:
            self.logger.error(f"Failed to disable NAT: {e}")
            return False

    def _enable_ip_forwarding(self):
        """Enable kernel IP forwarding."""
        subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=1"], check=True)

    def _disable_ip_forwarding(self):
        """Disable kernel IP forwarding."""
        subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=0"], check=True)

    def _configure_usb_interface(self):
        """Configure USB Ethernet interface with static IP."""
        # Поднимаем интерфейс usb0 и назначаем ему IP-адрес для Raspberry
        subprocess.run(["sudo", "ip", "addr", "flush", "dev", self.usb_interface], check=False)
        subprocess.run(["sudo", "ip", "addr", "add", f"{self.usb_ip}/24", "dev", self.usb_interface], check=False)
        subprocess.run(["sudo", "ip", "link", "set", self.usb_interface, "up"], check=False)

    def _add_iptables_rules(self):
        """Add NAT and forwarding rules."""
        # Очищаем старые правила на всякий случай
        self._remove_iptables_rules()

        # Разрешаем NAT (маскарадинг) из usb0 в wlan0
        subprocess.run(["sudo", "iptables", "-t", "nat", "-A", "POSTROUTING", "-o", self.lan_interface, "-j", "MASQUERADE"], check=True)
        
        # Разрешаем пересылку пакетов между интерфейсами
        subprocess.run(["sudo", "iptables", "-A", "FORWARD", "-i", self.lan_interface, "-o", self.usb_interface, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"], check=True)
        subprocess.run(["sudo", "iptables", "-A", "FORWARD", "-i", self.usb_interface, "-o", self.lan_interface, "-j", "ACCEPT"], check=True)

    def _remove_iptables_rules(self):
        """Remove NAT rules."""
        # Удаляем правила проброса
        subprocess.run(["sudo", "iptables", "-t", "nat", "-D", "POSTROUTING", "-o", self.lan_interface, "-j", "MASQUERADE"], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "iptables", "-D", "FORWARD", "-i", self.lan_interface, "-o", self.usb_interface, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "iptables", "-D", "FORWARD", "-i", self.usb_interface, "-o", self.lan_interface, "-j", "ACCEPT"], stderr=subprocess.DEVNULL)

    def get_status(self) -> dict:
        """Get NAT status."""
        return {
            'enabled': True,
            'lan_interface': self.lan_interface,
            'usb_interface': self.usb_interface,
        }

    def restart(self) -> bool:
        """Restart NAT configuration."""
        self.disable()
        return self.enable()