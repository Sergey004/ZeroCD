import os
import subprocess
import time
import threading
from system.logger import get_logger

class USBNetworkManager:
    def __init__(self):
        self.logger = get_logger("usb_net")
        self.dhcp_lock = threading.Lock()
        self.host_mac = "12:00:00:00:00:01"
        self.dev_mac  = "16:00:00:00:00:02"
        self.serial = "zerocd-123456"
        self._generate_hardware_ids()

    def _generate_hardware_ids(self):
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        serial = line.split(':')[1].strip()
                        self.serial = serial.zfill(16)
                        last_10 = self.serial[-10:]
                        pairs =[last_10[i:i+2] for i in range(0, 10, 2)]
                        base_mac = ":" + ":".join(pairs)
                        
                        self.host_mac = "12" + base_mac
                        self.dev_mac  = "16" + base_mac
                        break
        except: pass

    def start_dhcp_and_nat(self, is_active_callback):
        def task():
            with self.dhcp_lock:
                if not is_active_callback(): return
                
                # Ждем интерфейс NCM
                has_usb0 = False
                for _ in range(15):
                    has_usb0 = os.path.exists('/sys/class/net/usb0')
                    if has_usb0: break
                    time.sleep(0.5)

                if not is_active_callback() or not has_usb0: return

                self.logger.info("Initializing modern NCM Network...")
                
                try:
                    subprocess.run(["ip", "link", "set", "usb0", "up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["ip", "addr", "flush", "dev", "usb0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["ip", "addr", "add", "192.168.7.1/24", "dev", "usb0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["pkill", "-9", "-f", "zerocd_usb_dhcp.conf"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    commands = [["sysctl", "-w", "net.ipv4.ip_forward=1"],
                        ["iptables", "-t", "nat", "-F"],["iptables", "-F", "FORWARD"],
                        ["iptables", "-P", "FORWARD", "ACCEPT"],["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", "wlan0", "-j", "MASQUERADE"]
                    ]
                    for cmd in commands: 
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    conf = "/tmp/zerocd_usb_dhcp.conf"
                    with open(conf, "w") as f:
                        f.write("port=0\nbind-dynamic\n")
                        f.write("interface=usb0\n")
                        f.write("dhcp-range=192.168.7.2,192.168.7.2,255.255.255.0,1h\n")
                        f.write("dhcp-option=3,192.168.7.1\n")
                        f.write("dhcp-option=6,8.8.8.8,1.1.1.1\n")
                        
                    subprocess.run(["dnsmasq", "-C", conf], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.logger.info("NCM Network & NAT active! Host IP: 192.168.7.2")
                except Exception as e:
                    self.logger.error(f"Network Error: {e}")
                    
        threading.Thread(target=task, daemon=True).start()