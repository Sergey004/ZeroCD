"""
ZeroCD USB Gadget — CD-ROM + Ethernet (RNDIS + ECM)
"""
import os
import subprocess
import time
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
            udc_list = [d for d in os.listdir('/sys/class/udc/') if os.path.isdir(f'/sys/class/udc/{d}')]
            if udc_list:
                self.logger.info(f"Found UDC: {udc_list}")
                return udc_list[0]
            return None
        except Exception as e:
            self.logger.error(f"UDC error: {e}")
            return None

    def _safe_cleanup_gadget(self):
        gadget_path = f"/sys/kernel/config/usb_gadget/{self.gadget_name}"
        if not os.path.exists(gadget_path):
            return True
        self.logger.info(f"Cleaning up {self.gadget_name}...")

        udc_file = f"{gadget_path}/UDC"
        try:
            if os.path.exists(udc_file):
                with open(udc_file, 'r') as f:
                    if f.read().strip():
                        with open(udc_file, 'w') as f:
                            f.write("\n")
                        time.sleep(1.5)
        except:
            pass

        functions_path = f"{gadget_path}/functions"
        if os.path.exists(functions_path):
            for item in list(os.listdir(functions_path)):
                try:
                    fp = f"{functions_path}/{item}"
                    if os.path.isdir(fp) and 'lun.0' in os.listdir(fp):
                        with open(f"{fp}/lun.0/file", 'w') as f:
                            f.write('')
                    os.rmdir(fp)
                except:
                    pass

        config_path = f"{gadget_path}/configs/{self.config_name}"
        if os.path.exists(config_path):
            try:
                os.rmdir(config_path)
            except:
                pass
        try:
            os.rmdir(gadget_path)
        except:
            pass
        time.sleep(0.5)
        return True

    def _write_file(self, path: str, content: str):
        try:
            with open(path, 'w') as f:
                f.write(content)
        except Exception as e:
            self.logger.error(f"Write failed {path}: {e}")
            raise

    def _create_gadget_structure(self) -> bool:
        gadget_path = f'/sys/kernel/config/usb_gadget/{self.gadget_name}'
        try:
            self._safe_cleanup_gadget()
            os.makedirs(gadget_path, exist_ok=True)

            self._write_file(f'{gadget_path}/idVendor', '0x1d6b')
            self._write_file(f'{gadget_path}/idProduct', '0x0104')
            self._write_file(f'{gadget_path}/bcdDevice', '0x0100')
            self._write_file(f'{gadget_path}/bcdUSB', '0x0200')

            os.makedirs(f'{gadget_path}/strings/0x409', exist_ok=True)
            self._write_file(f'{gadget_path}/strings/0x409/manufacturer', 'ZeroCD')
            self._write_file(f'{gadget_path}/strings/0x409/product', 'CD + Ethernet')
            self._write_file(f'{gadget_path}/strings/0x409/serialnumber', 'zero cd 2026')

            config_path = f'{gadget_path}/configs/{self.config_name}'
            os.makedirs(config_path, exist_ok=True)
            os.makedirs(f'{config_path}/strings/0x409', exist_ok=True)
            self._write_file(f'{config_path}/strings/0x409/configuration', 'CD-ROM + LAN')

            # CD-ROM
            ms_path = f'{gadget_path}/functions/mass_storage.usb0'
            os.makedirs(ms_path, exist_ok=True)
            self._write_file(f'{ms_path}/stall', '1')
            lun_path = f'{ms_path}/lun.0'
            os.makedirs(lun_path, exist_ok=True)
            time.sleep(0.2)
            self._write_file(f'{lun_path}/removable', '1')
            self._write_file(f'{lun_path}/cdrom', '1')
            self._write_file(f'{lun_path}/nofua', '0')
            os.symlink(ms_path, f'{config_path}/mass_storage.usb0')

            # Ethernet RNDIS (Windows)
            rndis_path = f'{gadget_path}/functions/rndis.usb0'
            os.makedirs(rndis_path, exist_ok=True)
            self._write_file(f'{rndis_path}/host_addr', '02:00:00:00:00:01')
            self._write_file(f'{rndis_path}/dev_addr', '02:00:00:00:00:02')
            os.symlink(rndis_path, f'{config_path}/rndis.usb0')

            # Ethernet ECM (Mac/Linux)
            ecm_path = f'{gadget_path}/functions/ecm.usb0'
            os.makedirs(ecm_path, exist_ok=True)
            self._write_file(f'{ecm_path}/host_addr', '02:00:00:00:00:03')
            self._write_file(f'{ecm_path}/dev_addr', '02:00:00:00:00:04')
            os.symlink(ecm_path, f'{config_path}/ecm.usb0')

            self.logger.info("Gadget (CD + LAN) created")
            return True
        except Exception as e:
            self.logger.error(f"Gadget failed: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def init(self) -> bool:
        if os.geteuid() != 0:
            self.logger.error("Run as root!")
            return False
        if not self._check_module("dwc2"):
            self._load_module("dwc2")
        self._load_module("libcomposite")
        self._mount_configfs()
        self._udc = self._get_udc()
        if not self._udc:
            return False
        if not self._create_gadget_structure():
            return False
        self.state = GadgetState.CONFIGURED
        return True

    def bind(self) -> bool:
        try:
            udc_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/UDC'
            self._write_file(udc_file, self._udc)
            self.state = GadgetState.ACTIVE
            self.logger.info(f"Bound to {self._udc}")
            return True
        except Exception as e:
            self.logger.error(f"Bind failed: {e}")
            return False

    def unbind(self) -> bool:
        try:
            udc_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/UDC'
            self._write_file(udc_file, '')
            time.sleep(0.5)
            self.state = GadgetState.UNBOUND
            return True
        except:
            return False

    def set_iso(self, iso_path: str) -> bool:
        self.logger.info(f"Set ISO: {iso_path}")
        if not os.path.exists(iso_path):
            return False
        try:
            was_bound = (self.state == GadgetState.ACTIVE)
            if was_bound:
                self.unbind()
            lun_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/functions/mass_storage.usb0/lun.0/file'
            self._write_file(lun_file, '')
            self._write_file(lun_file, os.path.abspath(iso_path))
            if was_bound:
                self.bind()
            self.current_iso = iso_path
            return True
        except Exception as e:
            self.logger.error(f"Set ISO failed: {e}")
            return False

    def shutdown(self):
        self.unbind()
        self._safe_cleanup_gadget()

    def get_status(self) -> Dict[str, Any]:
        return {'state': self.state.value, 'current_iso': self.current_iso, 'udc': self._udc}