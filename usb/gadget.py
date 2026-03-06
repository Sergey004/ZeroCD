"""
USB Gadget manager for CD-ROM, Ethernet and MTP emulation
Uses configfs to configure USB gadget on Raspberry Pi Zero
"""
import os
import subprocess
import time
import traceback
from enum import Enum
from typing import Optional, Dict, Any
from system.logger import get_logger


class GadgetState(Enum):
    """USB gadget states."""
    UNBOUND = "unbound"
    CONFIGURED = "configured"
    ACTIVE = "active"


class GadgetManager:
    """
    Manages USB gadget configuration for mass storage, network and MTP.
    Uses Linux USB Gadget ConfigFS.
    """

    def __init__(self):
        self.logger = get_logger("gadget")
        self.state = GadgetState.UNBOUND
        self.current_iso: Optional[str] = None
        self.gadget_name = "zerocd"
        self.config_name = "c.1"
        self.function_name = "mass_storage.usb0"
        self._udc = None

    def _check_module(self, module_name):
        try:
            result = subprocess.run(['lsmod'], capture_output=True, text=True)
            return module_name in result.stdout
        except:
            return False

    def _load_module(self, module_name):
        self.logger.info(f"Loading module: {module_name}")
        try:
            subprocess.run(['modprobe', module_name], check=True)
            time.sleep(0.5)
            self.logger.info(f"Module {module_name} loaded")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load {module_name}: {e}")
            return False

    def _mount_configfs(self):
        config_path = "/sys/kernel/config"
        if os.path.ismount(config_path):
            return True
        self.logger.info("Mounting configfs...")
        try:
            subprocess.run(['mount', '-t', 'configfs', 'none', config_path], check=True)
            return True
        except Exception as e:
            self.logger.error(f"Failed to mount configfs: {e}")
            return False

    def _get_udc(self) -> Optional[str]:
        try:
            udc_path = '/sys/class/udc/'
            if not os.path.exists(udc_path):
                return None
            udc_list =[d for d in os.listdir(udc_path) if os.path.isdir(os.path.join(udc_path, d))]
            if udc_list:
                return udc_list[0]
        except Exception as e:
            self.logger.error(f"Failed to get UDC: {e}")
        return None

    def _safe_cleanup_gadget(self):
        gadget_path = f"/sys/kernel/config/usb_gadget/{self.gadget_name}"
        if not os.path.exists(gadget_path):
            return True
        self.logger.info(f"Cleaning up {self.gadget_name}...")
        
        # Unbind
        udc_file = f"{gadget_path}/UDC"
        if os.path.exists(udc_file):
            try:
                with open(udc_file, 'w') as f: f.write("\n")
                time.sleep(0.5)
            except: pass

        # Config
        config_path = f"{gadget_path}/configs/{self.config_name}"
        if os.path.exists(config_path):
            try:
                for item in os.listdir(config_path):
                    item_path = os.path.join(config_path, item)
                    if os.path.islink(item_path):
                        os.unlink(item_path)
                strings_path = f"{config_path}/strings/0x409"
                if os.path.exists(strings_path): os.rmdir(strings_path)
                os.rmdir(config_path)
            except: pass

        # Functions (включая правильное удаление lun.1)
        functions_path = f"{gadget_path}/functions"
        if os.path.exists(functions_path):
            for item in os.listdir(functions_path):
                fp = f"{functions_path}/{item}"
                try:
                    if os.path.isdir(fp):
                        if 'mass_storage' in item:
                            if 'lun.0' in os.listdir(fp):
                                with open(f"{fp}/lun.0/file", 'w') as f: f.write('\n')
                            if 'lun.1' in os.listdir(fp):
                                with open(f"{fp}/lun.1/file", 'w') as f: f.write('\n')
                                # Если мы создали lun.1, мы обязаны сделать ему rmdir
                                try:
                                    os.rmdir(f"{fp}/lun.1")
                                except: pass
                        os.rmdir(fp)
                except Exception as e:
                    self.logger.error(f"Failed to remove function {item}: {e}")

        # Windows OS Descriptors Symlink (если остался)
        try:
            os.unlink(f"{gadget_path}/os_desc/c.1")
        except: pass

        # Strings
        try:
            os.rmdir(f"{gadget_path}/strings/0x409")
        except: pass

        # Gadget
        try:
            os.rmdir(gadget_path)
        except: pass
        
        return True

    def _write_file(self, path: str, content: str, retries=3):
        for attempt in range(retries):
            try:
                with open(path, 'w') as f:
                    f.write(content)
                return
            except OSError as e:
                if e.errno == 16 and attempt < retries - 1:
                    time.sleep(0.5)
                else:
                    raise
            except Exception:
                raise

    def _create_gadget_structure(self) -> bool:
        gadget_path = f'/sys/kernel/config/usb_gadget/{self.gadget_name}'
        try:
            self._safe_cleanup_gadget()
            time.sleep(0.5)
            os.makedirs(gadget_path, exist_ok=True)

            self._write_file(f'{gadget_path}/idVendor', '0x1d6b')
            self._write_file(f'{gadget_path}/idProduct', '0x0104')
            self._write_file(f'{gadget_path}/bcdDevice', '0x0100')
            self._write_file(f'{gadget_path}/bcdUSB', '0x0200')

            # Windows Composite Descriptor (IAD) - чтобы не было Ошибки 10
            self._write_file(f'{gadget_path}/bDeviceClass', '0xEF')
            self._write_file(f'{gadget_path}/bDeviceSubClass', '0x02')
            self._write_file(f'{gadget_path}/bDeviceProtocol', '0x01')

            # OS Descriptors (подсказка драйверов для Windows)
            self._write_file(f'{gadget_path}/os_desc/use', '1')
            self._write_file(f'{gadget_path}/os_desc/b_vendor_code', '0xcd')
            self._write_file(f'{gadget_path}/os_desc/qw_sign', 'MSFT100')

            os.makedirs(f'{gadget_path}/strings/0x409', exist_ok=True)
            self._write_file(f'{gadget_path}/strings/0x409/manufacturer', 'ZeroCD')
            self._write_file(f'{gadget_path}/strings/0x409/product', 'CD + Ethernet')
            self._write_file(f'{gadget_path}/strings/0x409/serialnumber', 'zero cd 2026')

            config_path = f'{gadget_path}/configs/{self.config_name}'
            os.makedirs(config_path, exist_ok=True)
            os.makedirs(f'{config_path}/strings/0x409', exist_ok=True)
            self._write_file(f'{config_path}/strings/0x409/configuration', 'CD-ROM + LAN')

            # --- Mass Storage с ДВУМЯ приводами ---
            ms_path = f'{gadget_path}/functions/mass_storage.usb0'
            os.makedirs(ms_path, exist_ok=True)
            time.sleep(0.1)
            self._write_file(f'{ms_path}/stall', '1')

            # LUN.0 (Виртуальный CD-ROM для .iso)
            lun0_path = f'{ms_path}/lun.0'
            os.makedirs(lun0_path, exist_ok=True)
            time.sleep(0.2)
            self._write_file(f'{lun0_path}/removable', '1')
            self._write_file(f'{lun0_path}/ro', '1')
            self._write_file(f'{lun0_path}/cdrom', '1')
            self._write_file(f'{lun0_path}/nofua', '0')
            
            # LUN.1 (Виртуальная Флешка для .img)
            lun1_path = f'{ms_path}/lun.1'
            os.makedirs(lun1_path, exist_ok=True)
            time.sleep(0.2)
            self._write_file(f'{lun1_path}/removable', '1')
            self._write_file(f'{lun1_path}/ro', '1')
            self._write_file(f'{lun1_path}/cdrom', '0')
            self._write_file(f'{lun1_path}/nofua', '0')

            os.symlink(ms_path, f'{config_path}/mass_storage.usb0')
            # -------------------------------------

            # Network
            rndis_path = f'{gadget_path}/functions/rndis.usb0'
            os.makedirs(rndis_path, exist_ok=True)
            self._write_file(f'{rndis_path}/host_addr', '02:00:00:00:00:01')
            self._write_file(f'{rndis_path}/dev_addr', '02:00:00:00:00:02')
            
            rndis_os_desc = f'{rndis_path}/os_desc/interface.rndis'
            if os.path.exists(rndis_os_desc):
                self._write_file(f'{rndis_os_desc}/compatible_id', 'RNDIS')
                self._write_file(f'{rndis_os_desc}/sub_compatible_id', '5162001')
            os.symlink(rndis_path, f'{config_path}/rndis.usb0')

            ecm_path = f'{gadget_path}/functions/ecm.usb0'
            os.makedirs(ecm_path, exist_ok=True)
            self._write_file(f'{ecm_path}/host_addr', '02:00:00:00:00:03')
            self._write_file(f'{ecm_path}/dev_addr', '02:00:00:00:00:04')
            os.symlink(ecm_path, f'{config_path}/ecm.usb0')

            try:
                os.symlink(config_path, f'{gadget_path}/os_desc/c.1')
            except FileExistsError:
                pass

            return True
        except Exception as e:
            self.logger.error(f"Gadget failed: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def init(self) -> bool:
        self.logger.info("Initializing USB gadget")
        if os.geteuid() != 0:
            return False
        if not self._check_module("dwc2"):
            if not self._load_module("dwc2"): return False
        if not self._check_module("libcomposite"):
            self._load_module("libcomposite")
        if not self._mount_configfs(): return False
        self._udc = self._get_udc()
        if not self._udc: return False
        if not self._create_gadget_structure(): return False
        self.state = GadgetState.CONFIGURED
        return True

    def bind(self) -> bool:
        if not self._udc: return False
        try:
            udc_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/UDC'
            self._write_file(udc_file, self._udc)
            self.state = GadgetState.ACTIVE
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
            return False
        
        iso_path = os.path.abspath(iso_path)
        
        try:
            ms_path = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/functions/{self.function_name}'
            lun0_file = f'{ms_path}/lun.0/file'
            lun1_file = f'{ms_path}/lun.1/file'
            
            is_cdrom = iso_path.lower().endswith('.iso')
            
            self.logger.info("Ejecting current images from all drives...")
            
            # Извлекаем диски только если файлы LUN существуют
            if os.path.exists(lun0_file):
                self._write_file(lun0_file, '\n')
            if os.path.exists(lun1_file):
                self._write_file(lun1_file, '\n')
                
            time.sleep(0.8)
            
            self.logger.info(f"Inserting new image: {iso_path} (CD-ROM mode: {is_cdrom})")
            if is_cdrom and os.path.exists(lun0_file):
                self._write_file(lun0_file, iso_path)
            elif not is_cdrom and os.path.exists(lun1_file):
                self._write_file(lun1_file, iso_path)
            
            self.current_iso = iso_path
            time.sleep(0.5)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set image: {e}")
            return False

    def shutdown(self):
        self.unbind()
        self._safe_cleanup_gadget()

    def get_status(self) -> Dict[str, Any]:
        return {
            'state': self.state.value,
            'current_iso': self.current_iso,
            'udc': self._udc,
            'functions': ['mass_storage']
        }