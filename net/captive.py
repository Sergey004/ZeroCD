"""
Captive Portal for ZeroCD
Provides WiFi AP mode with web configuration portal
"""
import os
import subprocess
import time
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional

from config import (
    WIFI_INTERFACE,
    WIFI_AP_IP,
    WIFI_AP_DHCP_START,
    WIFI_AP_DHCP_END,
    ZEROCD_DATA_DIR
)
from net.wifi import get_wifi_manager
from system.logger import get_logger


class CaptivePortal:
    """
    Manages WiFi Access Point and captive portal web server.
    Starts automatically when no known networks are available.
    """

    def __init__(self):
        self.logger = get_logger("captive")
        self.wifi_manager = get_wifi_manager()
        self.hostapd_process: Optional[subprocess.Popen] = None
        self.dnsmasq_process: Optional[subprocess.Popen] = None
        self.http_server: Optional[HTTPServer] = None
        self.running = False

    def start(self) -> bool:
        """Start captive portal (AP mode + web server)."""
        if self.running:
            self.logger.warning("Captive portal already running")
            return True

        ap_config = self.wifi_manager.get_ap_config()
        
        self.logger.info(f"Starting captive portal: {ap_config['ssid']}")
        
        if not self._start_hostapd(ap_config['ssid'], ap_config['password']):
            return False
        
        time.sleep(2)
        
        if not self._start_dnsmasq():
            self._stop_hostapd()
            return False
        
        time.sleep(1)
        
        if not self._setup_ip_forwarding():
            self._stop_all()
            return False
        
        self._start_http_server()
        
        self.running = True
        self.wifi_manager.state = "ap_mode"
        self.logger.info("Captive portal started successfully")
        
        return True

    def stop(self) -> bool:
        """Stop captive portal."""
        if not self.running:
            return True
        
        self.logger.info("Stopping captive portal...")
        
        self._stop_http_server()
        self._stop_dnsmasq()
        self._stop_hostapd()
        self._stop_ip_forwarding()
        
        self.running = False
        self.wifi_manager.state = "off"
        self.logger.info("Captive portal stopped")
        
        return True

    def _start_hostapd(self, ssid: str, password: str) -> bool:
        """Start hostapd for WiFi AP."""
        hostapd_conf = "/tmp/zerocd_hostapd.conf"
        
        with open(hostapd_conf, 'w') as f:
            f.write(f'''interface={WIFI_INTERFACE}
driver=nl80211
ssid={ssid}
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
''')

        try:
            subprocess.run(["sudo", "ip", "addr", "flush", "dev", WIFI_INTERFACE], check=True)
            subprocess.run(["sudo", "ip", "addr", "add", f"{WIFI_AP_IP}/24", "dev", WIFI_INTERFACE], check=True)
            subprocess.run(["sudo", "ip", "link", "set", WIFI_INTERFACE, "up"], check=True)
            
            self.hostapd_process = subprocess.Popen(
                ["sudo", "hostapd", hostapd_conf],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            time.sleep(3)
            
            if self.hostapd_process.poll() is not None:
                self.logger.error("hostapd failed to start")
                return False
            
            self.logger.info("hostapd started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start hostapd: {e}")
            return False

    def _stop_hostapd(self):
        """Stop hostapd."""
        if self.hostapd_process:
            self.hostapd_process.terminate()
            try:
                self.hostapd_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.hostapd_process.kill()
            self.hostapd_process = None
        
        subprocess.run(["sudo", "pkill", "hostapd"], capture_output=True)
        self.logger.info("hostapd stopped")

    def _start_dnsmasq(self) -> bool:
        """Start dnsmasq for DHCP and DNS."""
        dnsmasq_conf = "/tmp/zerocd_dnsmasq.conf"
        
        with open(dnsmasq_conf, 'w') as f:
            f.write(f'''interface={WIFI_INTERFACE}
bind-interfaces
dhcp-range={WIFI_AP_DHCP_START},{WIFI_AP_DHCP_END},12h
dhcp-option=3,{WIFI_AP_IP}
dhcp-option=6,{WIFI_AP_IP}
address=/#/{WIFI_AP_IP}
no-resolv
no-poll
''')

        try:
            subprocess.run(["sudo", "pkill", "dnsmasq"], capture_output=True)
            time.sleep(1)
            
            self.dnsmasq_process = subprocess.Popen(
                ["sudo", "dnsmasq", "-C", dnsmasq_conf],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            time.sleep(1)
            
            if self.dnsmasq_process.poll() is not None:
                self.logger.error("dnsmasq failed to start")
                return False
            
            self.logger.info("dnsmasq started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start dnsmasq: {e}")
            return False

    def _stop_dnsmasq(self):
        """Stop dnsmasq."""
        if self.dnsmasq_process:
            self.dnsmasq_process.terminate()
            try:
                self.dnsmasq_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.dnsmasq_process.kill()
            self.dnsmasq_process = None
        
        subprocess.run(["sudo", "pkill", "dnsmasq"], capture_output=True)
        self.logger.info("dnsmasq stopped")

    def _setup_ip_forwarding(self) -> bool:
        """Enable IP forwarding and NAT."""
        try:
            subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=1"], check=True)
            
            subprocess.run(["sudo", "iptables", "-t", "nat", "-F"], check=True)
            subprocess.run([
                "sudo", "iptables", "-t", "nat", "-A", "POSTROUTING",
                "-o", "usb0", "-j", "MASQUERADE"
            ], check=True)
            
            self.logger.info("IP forwarding enabled")
            return True
        except Exception as e:
            self.logger.error(f"Failed to setup IP forwarding: {e}")
            return False

    def _stop_ip_forwarding(self):
        """Disable IP forwarding."""
        try:
            subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=0"], check=True)
            subprocess.run(["sudo", "iptables", "-t", "nat", "-F"], check=True)
        except:
            pass

    def _start_http_server(self):
        """Start simple HTTP server for captive portal."""
        portal_dir = os.path.join(os.path.dirname(__file__), "..", "web", "templates")
        if not os.path.exists(portal_dir):
            portal_dir = "/opt/zerocd/web/templates"
        if not os.path.exists(portal_dir):
            portal_dir = ZEROCD_DATA_DIR
        
        class CaptiveHandler(SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/" or self.path == "/index.html":
                    self.send_response(302)
                    self.send_header("Location", "/captive.html")
                    self.end_headers()
                else:
                    super().do_GET()
            
            def log_message(self, format, *args):
                pass  # Suppress logging

        try:
            self.http_server = HTTPServer((WIFI_AP_IP, 80), CaptiveHandler)
            thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            thread.start()
            self.logger.info(f"HTTP server started on {WIFI_AP_IP}:80")
        except Exception as e:
            self.logger.error(f"Failed to start HTTP server: {e}")

    def _stop_http_server(self):
        """Stop HTTP server."""
        if self.http_server:
            self.http_server.shutdown()
            self.http_server = None

    def _stop_all(self):
        """Stop all services."""
        self._stop_http_server()
        self._stop_dnsmasq()
        self._stop_hostapd()
        self._stop_ip_forwarding()

    def is_running(self) -> bool:
        """Check if captive portal is running."""
        return self.running

    def get_status(self) -> dict:
        """Get captive portal status."""
        return {
            "running": self.running,
            "ap_ssid": self.wifi_manager.ap_ssid,
            "ap_password": self.wifi_manager.ap_password,
            "ap_ip": WIFI_AP_IP
        }


# Singleton instance
_captive_portal: Optional[CaptivePortal] = None


def get_captive_portal() -> CaptivePortal:
    """Get captive portal singleton."""
    global _captive_portal
    if _captive_portal is None:
        _captive_portal = CaptivePortal()
    return _captive_portal