"""
USB Gadget manager for CD-ROM, Ethernet and MTP emulation
Uses configfs to configure USB gadget on Raspberry Pi Zero
"""
import os
import subprocess
import time
import threading
import traceback
from enum import Enum
from typing import Optional, Dict, Any
from system.logger import get_logger


class GadgetState(Enum):
    UNBOUND = "unbound"
    CONFIGURED = "configured"
    ACTIVE = "active"


class GadgetManager:
    def __init__(self):
        self.logger = get_logger("gadget")
        self.state = GadgetState.UNBOUND
        self.current_iso: Optional[str] = None
        self.gadget_name = "zerocd"
        self.config_name = "c.1"
        self.function_name = "mass_storage.usb0"
        self._udc = None
        self._current_mode_is_cdrom = True
        
        # Генерируем постоянные MAC и Серийник (чтобы Windows не сходила с ума)
        self._generate_hardware_ids()

    def _generate_hardware_ids(self):
        self._serial = "zerocd-123456"
        self._host_mac_rndis = "02:00:00:00:00:01"
        self._dev_mac_rndis  = "06:00:00:00:00:02"
        self._host_mac_ecm   = "12:00:00:00:00:03"
        self._dev_mac_ecm    = "16:00:00:00:00:04"
        
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        serial = line.split(':')[1].strip()
                        self._serial = serial.zfill(16)
                        last_10 = self._serial[-10:]
                        pairs =[last_10[i:i+2] for i in range(0, 10, 2)]
                        base_mac = ":" + ":".join(pairs)
                        
                        self._host_mac_rndis = "02" + base_mac
                        self._dev_mac_rndis  = "06" + base_mac
                        self._host_mac_ecm   = "12" + base_mac
                        self._dev_mac_ecm    = "16" + base_mac
                        self.logger.info(f"Hardware IDs generated from Serial: {serial}")
                        break
        except Exception as e:
            self.logger.warning(f"Could not read Pi Serial: {e}")

    def _check_module(self, module_name):
        try:
            result = subprocess.run(['lsmod'], capture_output=True, text=True)
            return module_name in result.stdout
        except: return False

    def _load_module(self, module_name):
        self.logger.info(f"Loading module: {module_name}")
        try:
            subprocess.run(['modprobe', module_name], check=True)
            time.sleep(0.5)
            return True
        except: return False

    def _mount_configfs(self):
        config_path = "/sys/kernel/config"
        if os.path.ismount(config_path): return True
        try:
            subprocess.run(['mount', '-t', 'configfs', 'none', config_path], check=True)
            return True
        except: return False

    def _get_udc(self) -> Optional[str]:
        try:
            udc_path = '/sys/class/udc/'
            if not os.path.exists(udc_path): return None
            udc_list =[d for d in os.listdir(udc_path) if os.path.isdir(os.path.join(udc_path, d))]
            if udc_list: return udc_list[0]
        except: pass
        return None

    def _safe_cleanup_gadget(self):
        gadget_path = f"/sys/kernel/config/usb_gadget/{self.gadget_name}"
        if not os.path.exists(gadget_path): return True
        
        self.logger.info("Cleaning up old USB structure...")
        udc_file = f"{gadget_path}/UDC"
        if os.path.exists(udc_file):
            try:
                with open(udc_file, 'w') as f: f.write("\n")
                time.sleep(0.5)
            except: pass

        config_path = f"{gadget_path}/configs/{self.config_name}"
        if os.path.exists(config_path):
            try:
                for item in os.listdir(config_path):
                    item_path = os.path.join(config_path, item)
                    if os.path.islink(item_path): os.unlink(item_path)
                strings_path = f"{config_path}/strings/0x409"
                if os.path.exists(strings_path): os.rmdir(strings_path)
                os.rmdir(config_path)
            except: pass

        functions_path = f"{gadget_path}/functions"
        if os.path.exists(functions_path):
            for item in os.listdir(functions_path):
                fp = f"{functions_path}/{item}"
                try:
                    if os.path.isdir(fp):
                        if 'mass_storage' in item:
                            if 'lun.0' in os.listdir(fp):
                                with open(f"{fp}/lun.0/file", 'w') as f: f.write('\n')
                        os.rmdir(fp)
                except: pass

        for p in[f"{gadget_path}/os_desc/c.1", f"{gadget_path}/strings/0x409", gadget_path]:
            try: os.unlink(p) if os.path.islink(p) else os.rmdir(p)
            except: pass
        return True

    def _write_file(self, path: str, content: str, retries=3):
        for attempt in range(retries):
            try:
                with open(path, 'w') as f: f.write(content)
                return
            except OSError as e:
                if e.errno == 16 and attempt < retries - 1:
                    time.sleep(0.5)
                else: raise

    def _create_gadget_structure(self, is_cdrom: bool = True) -> bool:
        gadget_path = f'/sys/kernel/config/usb_gadget/{self.gadget_name}'
        try:
            self._safe_cleanup_gadget()
            time.sleep(0.5)
            os.makedirs(gadget_path, exist_ok=True)

            self._write_file(f'{gadget_path}/idVendor', '0x1d6b')
            self._write_file(f'{gadget_path}/idProduct', '0x0104')
            self._write_file(f'{gadget_path}/bcdDevice', '0x0100')
            self._write_file(f'{gadget_path}/bcdUSB', '0x0200')

            self._write_file(f'{gadget_path}/bDeviceClass', '0xEF')
            self._write_file(f'{gadget_path}/bDeviceSubClass', '0x02')
            self._write_file(f'{gadget_path}/bDeviceProtocol', '0x01')

            self._write_file(f'{gadget_path}/os_desc/use', '1')
            self._write_file(f'{gadget_path}/os_desc/b_vendor_code', '0xcd')
            self._write_file(f'{gadget_path}/os_desc/qw_sign', 'MSFT100')

            os.makedirs(f'{gadget_path}/strings/0x409', exist_ok=True)
            self._write_file(f'{gadget_path}/strings/0x409/manufacturer', 'ZeroCD')
            self._write_file(f'{gadget_path}/strings/0x409/product', 'CD + Ethernet')
            self._write_file(f'{gadget_path}/strings/0x409/serialnumber', self._serial)

            config_path = f'{gadget_path}/configs/{self.config_name}'
            os.makedirs(config_path, exist_ok=True)
            os.makedirs(f'{config_path}/strings/0x409', exist_ok=True)
            self._write_file(f'{config_path}/strings/0x409/configuration', 'CD-ROM + LAN')
            self._write_file(f'{config_path}/MaxPower', '250')

            # Сначала линкуем RNDIS (помогает Windows)
            rndis_path = f'{gadget_path}/functions/rndis.usb0'
            os.makedirs(rndis_path, exist_ok=True)
            self._write_file(f'{rndis_path}/host_addr', self._host_mac_rndis)
            self._write_file(f'{rndis_path}/dev_addr', self._dev_mac_rndis)
            rndis_os_desc = f'{rndis_path}/os_desc/interface.rndis'
            if os.path.exists(rndis_os_desc):
                self._write_file(f'{rndis_os_desc}/compatible_id', 'RNDIS')
                self._write_file(f'{rndis_os_desc}/sub_compatible_id', '5162001')
            os.symlink(rndis_path, f'{config_path}/rndis.usb0')

            # Затем ECM (Для Mac/Linux)
            ecm_path = f'{gadget_path}/functions/ecm.usb0'
            os.makedirs(ecm_path, exist_ok=True)
            self._write_file(f'{ecm_path}/host_addr', self._host_mac_ecm)
            self._write_file(f'{ecm_path}/dev_addr', self._dev_mac_ecm)
            os.symlink(ecm_path, f'{config_path}/ecm.usb0')

            # Наконец Mass Storage
            ms_path = f'{gadget_path}/functions/mass_storage.usb0'
            os.makedirs(ms_path, exist_ok=True)
            time.sleep(0.1)
            self._write_file(f'{ms_path}/stall', '1')

            lun0_path = f'{ms_path}/lun.0'
            os.makedirs(lun0_path, exist_ok=True)
            time.sleep(0.2)

            if is_cdrom:
                self._write_file(f'{lun0_path}/removable', '1')
                self._write_file(f'{lun0_path}/ro', '1')
                self._write_file(f'{lun0_path}/cdrom', '1')
                self._write_file(f'{lun0_path}/nofua', '0')
            else:
                self._write_file(f'{lun0_path}/removable', '0')
                self._write_file(f'{lun0_path}/ro', '0')
                self._write_file(f'{lun0_path}/cdrom', '0')
                self._write_file(f'{lun0_path}/nofua', '1')
            os.symlink(ms_path, f'{config_path}/mass_storage.usb0')

            # Привязываем Windows OS Descriptors
            try: os.symlink(config_path, f'{gadget_path}/os_desc/c.1')
            except: pass

            return True
        except Exception as e:
            self.logger.error(f"Gadget structure failed: {e}")
            return False

    def _setup_usb_network_dhcp(self):
        """Поднимаем интерфейс usb0 и запускаем DHCP для ПК (Mac/Windows)"""
        def task():
            # Ждем появления интерфейса usb0 (после bind() он создается ядром не мгновенно)
            for _ in range(10):
                time.sleep(0.5)
                if os.path.exists('/sys/class/net/usb0'):
                    break
                    
            try:
                # Убиваем старые процессы dnsmasq, чтобы они не конфликтовали
                subprocess.run(['sudo', 'pkill', '-f', 'zerocd_usb_dhcp.conf'], stderr=subprocess.DEVNULL)
                
                # Назначаем IP самой Малинке
                subprocess.run(['sudo', 'ip', 'addr', 'flush', 'dev', 'usb0'], stderr=subprocess.DEVNULL)
                subprocess.run(['sudo', 'ip', 'addr', 'add', '192.168.7.1/24', 'dev', 'usb0'], stderr=subprocess.DEVNULL)
                subprocess.run(['sudo', 'ip', 'link', 'set', 'usb0', 'up'], stderr=subprocess.DEVNULL)

                # === ВКЛЮЧАЕМ РАЗДАЧУ ИНТЕРНЕТА (NAT / РОУТИНГ) ===
                # 1. Разрешаем ядру пересылать пакеты
                subprocess.run(['sudo', 'sysctl', '-w', 'net.ipv4.ip_forward=1'], stderr=subprocess.DEVNULL)
                # 2. Маскируем трафик с USB так, будто он идет с Wi-Fi малинки
                subprocess.run(['sudo', 'iptables', '-t', 'nat', '-A', 'POSTROUTING', '-o', 'wlan0', '-j', 'MASQUERADE'], stderr=subprocess.DEVNULL)
                # 3. Разрешаем двусторонний обмен данными между usb0 и wlan0
                subprocess.run(['sudo', 'iptables', '-A', 'FORWARD', '-i', 'wlan0', '-o', 'usb0', '-m', 'state', '--state', 'RELATED,ESTABLISHED', '-j', 'ACCEPT'], stderr=subprocess.DEVNULL)
                subprocess.run(['sudo', 'iptables', '-A', 'FORWARD', '-i', 'usb0', '-o', 'wlan0', '-j', 'ACCEPT'], stderr=subprocess.DEVNULL)
                # ==================================================

                # Создаем конфиг для выдачи IP компьютеру
                conf_path = "/tmp/zerocd_usb_dhcp.conf"
                with open(conf_path, "w") as f:
                    f.write("port=0\n")  # Отключает DNS, предотвращая ошибку занятого 53 порта
                    f.write("interface=usb0\n")
                    f.write("dhcp-range=192.168.7.2,192.168.7.2,255.255.255.0,1h\n")
                    f.write("dhcp-option=3,192.168.7.1\n") # Шлюз
                    f.write("dhcp-option=6,8.8.8.8,1.1.1.1\n") # Публичный DNS
                
                # Запускаем новый dnsmasq
                subprocess.run(['sudo', 'dnsmasq', '-C', conf_path], stderr=subprocess.DEVNULL)
                self.logger.info("USB DHCP & NAT Router configured successfully!")
            except Exception as e:
                self.logger.error(f"Failed to start USB DHCP: {e}")
                
        threading.Thread(target=task, daemon=True).start()
        
    def init(self) -> bool:
        if os.geteuid() != 0: return False
        if not self._check_module("dwc2"):
            if not self._load_module("dwc2"): return False
        if not self._check_module("libcomposite"): self._load_module("libcomposite")
        if not self._mount_configfs(): return False
        self._udc = self._get_udc()
        if not self._udc: return False
        
        if not self._create_gadget_structure(is_cdrom=True): return False
        self._current_mode_is_cdrom = True
        self.state = GadgetState.CONFIGURED
        return True

    def bind(self) -> bool:
        if not self._udc: return False
        try:
            udc_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/UDC'
            self._write_file(udc_file, self._udc)
            self.state = GadgetState.ACTIVE
            
            # ЗАПУСКАЕМ DHCP СЕРВЕР СРАЗУ ПОСЛЕ ПОДКЛЮЧЕНИЯ КАБЕЛЯ
            self._setup_usb_network_dhcp()
            return True
        except: return False

    def unbind(self) -> bool:
        try:
            udc_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/UDC'
            if os.path.exists(udc_file):
                with open(udc_file, 'r') as f:
                    if f.read().strip():
                        self._write_file(udc_file, '\n')
                        time.sleep(0.5)
            self.state = GadgetState.UNBOUND
            return True
        except: return False

    def set_iso(self, iso_path: str) -> bool:
        if not os.path.exists(iso_path) or not os.access(iso_path, os.R_OK):
            self.logger.error(f"Cannot access file: {iso_path}")
            return False
            
        iso_path = os.path.abspath(iso_path)
        if getattr(self, 'current_iso', None) == iso_path:
            return True
            
        is_cdrom = iso_path.lower().endswith('.iso')
        
        try:
            needs_rebuild = getattr(self, '_current_mode_is_cdrom', None) != is_cdrom
            was_bound = (self.state == GadgetState.ACTIVE)
            lun0_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/functions/{self.function_name}/lun.0/file'
            
            # --- ВСЕГДА ОТКЛЮЧАЕМ USB ---
            # Это единственный способ заставить Windows/Mac перечитать диск 100% раз из 100
            if was_bound:
                self.logger.info("Unbinding USB to force host to re-read device...")
                self.unbind()
                time.sleep(1.2)
            
            if needs_rebuild:
                self.logger.info(f"Rebuilding gadget for {'CD-ROM' if is_cdrom else 'HDD'} mode...")
                if not self._create_gadget_structure(is_cdrom=is_cdrom):
                    return False
                self._current_mode_is_cdrom = is_cdrom
                
            # Записываем файл диска в слот
            self.logger.info("Ejecting medium...")
            self._write_file(lun0_file, '\n')
            time.sleep(0.5)
            self.logger.info(f"Inserting new medium: {iso_path}")
            self._write_file(lun0_file, iso_path)
            
            # --- ПОДКЛЮЧАЕМ ОБРАТНО ---
            if was_bound:
                self.logger.info("Rebinding USB...")
                self.bind()
                time.sleep(1.0)
            
            self.current_iso = iso_path
            self.logger.info("Swap complete!")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set image: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def shutdown(self):
        self.unbind()
        self._safe_cleanup_gadget()

    def get_status(self) -> Dict[str, Any]:
        return {'state': self.state.value, 'current_iso': self.current_iso, 'udc': self._udc, 'functions': ['mass_storage']}