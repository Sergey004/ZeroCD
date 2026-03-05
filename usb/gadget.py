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
from config import GADGET_DIR, ISO_DIR
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
        """Check if kernel module is loaded"""
        try:
            result = subprocess.run(['lsmod'], capture_output=True, text=True)
            return module_name in result.stdout
        except:
            return False

    def _load_module(self, module_name):
        """Load kernel module"""
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
        """Mount configfs if not already mounted"""
        config_path = "/sys/kernel/config"
        if os.path.ismount(config_path):
            return True
        
        self.logger.info("Mounting configfs...")
        try:
            subprocess.run(['mount', '-t', 'configfs', 'none', config_path], check=True)
            self.logger.info("configfs mounted")
            return True
        except Exception as e:
            self.logger.error(f"Failed to mount configfs: {e}")
            return False

    def _get_udc(self) -> Optional[str]:
        """Get available UDC (USB Device Controller)."""
        try:
            udc_path = '/sys/class/udc/'
            if not os.path.exists(udc_path):
                self.logger.error(f"UDC path not found: {udc_path}")
                return None
            
            udc_list = [d for d in os.listdir(udc_path) 
                       if os.path.isdir(os.path.join(udc_path, d))]
            
            if udc_list:
                self.logger.info(f"Found UDC devices: {udc_list}")
                return udc_list[0]
            else:
                self.logger.error("No UDC devices found")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get UDC: {e}")
        return None

    def _safe_cleanup_gadget(self):
        """Агрессивная очистка gadget — решает 99% 'directory not empty' и 'Operation not permitted'"""
        gadget_path = f"/sys/kernel/config/usb_gadget/{self.gadget_name}"
        
        if not os.path.exists(gadget_path):
            return True
        
        self.logger.info(f"Cleaning up existing gadget: {self.gadget_name}")
        
        # 1. Жёстко отцепляем UDC
        udc_file = f"{gadget_path}/UDC"
        try:
            if os.path.exists(udc_file):
                with open(udc_file, 'r') as f:
                    if f.read().strip():
                        self.logger.debug("Unbinding UDC...")
                        with open(udc_file, 'w') as f:
                            f.write("\n")
                        time.sleep(1.5)
        except Exception as e:
            self.logger.warning(f"UDC unbind failed: {e}")
        
        # 2. Удаляем симлинки из конфига
        config_path = f"{gadget_path}/configs/{self.config_name}"
        if os.path.exists(config_path):
            try:
                for item in list(os.listdir(config_path)):
                    item_path = os.path.join(config_path, item)
                    if os.path.islink(item_path):
                        os.unlink(item_path)
            except Exception as e:
                self.logger.warning(f"Symlink cleanup: {e}")
        
        # 3. Чистим lun.0 (самая упрямая часть)
        func_path = f"{gadget_path}/functions/{self.function_name}"
        if os.path.exists(func_path):
            lun_path = f"{func_path}/lun.0"
            if os.path.exists(lun_path):
                try:
                    file_path = f"{lun_path}/file"
                    if os.path.exists(file_path):
                        with open(file_path, 'w') as f:
                            f.write('')
                    time.sleep(0.3)
                    os.rmdir(lun_path)
                    self.logger.debug("lun.0 removed")
                except Exception as e:
                    self.logger.warning(f"lun.0 removal (benign): {e}")
            
            try:
                os.rmdir(func_path)
            except Exception as e:
                self.logger.warning(f"Function removal: {e}")
        
        # 4. Чистим config и его строки
        if os.path.exists(config_path):
            try:
                strings_path = f"{config_path}/strings/0x409"
                if os.path.exists(strings_path):
                    for f in os.listdir(strings_path):
                        os.remove(os.path.join(strings_path, f))
                    os.rmdir(strings_path)
                os.rmdir(config_path)
            except Exception as e:
                self.logger.warning(f"Config cleanup: {e}")
        
        # 5. Строки гаджета
        strings_path = f"{gadget_path}/strings/0x409"
        if os.path.exists(strings_path):
            try:
                for f in os.listdir(strings_path):
                    os.remove(os.path.join(strings_path, f))
                os.rmdir(strings_path)
                os.rmdir(f"{gadget_path}/strings")
            except:
                pass
        
        # 6. Финал
        try:
            if os.path.exists(gadget_path):
                os.rmdir(gadget_path)
                self.logger.info("Gadget fully cleaned")
        except Exception as e:
            self.logger.warning(f"Final rmdir (usually harmless): {e}")
        
        time.sleep(0.5)
        return True

    def _write_file(self, path: str, content: str):
        """Write content to a sysfs file."""
        try:
            with open(path, 'w') as f:
                f.write(content)
        except Exception as e:
            self.logger.error(f"Failed to write to {path}: {e}")
            raise

    def _create_gadget_structure(self) -> bool:
        """Create gadget directory structure in configfs."""
        gadget_path = f'/sys/kernel/config/usb_gadget/{self.gadget_name}'
        
        try:
            # Remove old gadget if exists
            self._safe_cleanup_gadget()
            
            # Create gadget directory
            os.makedirs(gadget_path, exist_ok=True)
            
            # Set USB device descriptors
            self._write_file(f'{gadget_path}/idVendor', '0x1d6b')
            self._write_file(f'{gadget_path}/idProduct', '0x0104')
            self._write_file(f'{gadget_path}/bcdDevice', '0x0100')
            self._write_file(f'{gadget_path}/bcdUSB', '0x0200')
            
            # Create strings
            os.makedirs(f'{gadget_path}/strings/0x409', exist_ok=True)
            self._write_file(f'{gadget_path}/strings/0x409/serialnumber', '1234567890')
            self._write_file(f'{gadget_path}/strings/0x409/manufacturer', 'ZeroCD')
            self._write_file(f'{gadget_path}/strings/0x409/product', 'USB CD-ROM Drive')
            
            # Create configuration
            config_path = f'{gadget_path}/configs/{self.config_name}'
            os.makedirs(config_path, exist_ok=True)
            os.makedirs(f'{config_path}/strings/0x409', exist_ok=True)
            self._write_file(f'{config_path}/strings/0x409/configuration', 'CD-ROM')
            
            # Mass storage function
            func_path = f'{gadget_path}/functions/{self.function_name}'
            os.makedirs(func_path, exist_ok=True)
            
            self._write_file(f'{func_path}/stall', '1')
            
            # lun.0 — создаём и сразу настраиваем
            lun_path = f'{func_path}/lun.0'
            os.makedirs(lun_path, exist_ok=True)
            time.sleep(0.15)  # sysfs иногда тормозит
            
            self._write_file(f'{lun_path}/removable', '1')
            self._write_file(f'{lun_path}/cdrom', '1')
            self._write_file(f'{lun_path}/nofua', '0')
            # self._write_file(f'{lun_path}/ro', '1')  # раскомменти если хочешь строго read-only
            
            # Link function to config
            link_path = f'{config_path}/{self.function_name}'
            if not os.path.exists(link_path):
                os.symlink(func_path, link_path)
            
            self.logger.info("Gadget structure created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create gadget structure: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def init(self) -> bool:
        """Initialize USB gadget configuration."""
        self.logger.info("Initializing USB gadget")
        
        if os.geteuid() != 0:
            self.logger.error("Must run as root to create USB gadget!")
            return False
        
        if not self._check_module("dwc2"):
            self.logger.info("Module dwc2 not loaded, loading...")
            if not self._load_module("dwc2"):
                self.logger.error("Failed to load dwc2. Add 'dtoverlay=dwc2' to /boot/config.txt")
                return False
        else:
            self.logger.info("Module dwc2 is loaded")
        
        if not self._check_module("libcomposite"):
            self._load_module("libcomposite")
        
        if not self._mount_configfs():
            return False
        
        self._udc = self._get_udc()
        if not self._udc:
            self.logger.error("No UDC found! Check USB cable connection")
            return False
        
        if not self._create_gadget_structure():
            return False
        
        self.state = GadgetState.CONFIGURED
        return True

    def bind(self) -> bool:
        """Bind gadget to UDC."""
        if not self._udc:
            self.logger.error("No UDC available")
            return False
        
        try:
            udc_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/UDC'
            self._write_file(udc_file, self._udc)
            self.state = GadgetState.ACTIVE
            self.logger.info(f"Gadget bound to UDC: {self._udc}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to bind gadget: {e}")
            return False

    def unbind(self) -> bool:
        """Unbind gadget from UDC."""
        try:
            udc_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/UDC'
            if os.path.exists(udc_file):
                with open(udc_file, 'r') as f:
                    if f.read().strip():
                        self._write_file(udc_file, '')
                        time.sleep(0.5)
            self.state = GadgetState.UNBOUND
            self.logger.info("Gadget unbound")
            return True
        except Exception as e:
            self.logger.error(f"Failed to unbind gadget: {e}")
            return False

    def set_iso(self, iso_path: str) -> bool:
        """Switch active ISO image."""
        self.logger.info(f"Setting ISO: {iso_path}")
        
        if not os.path.exists(iso_path):
            self.logger.error(f"ISO not found: {iso_path}")
            return False
        
        iso_path = os.path.abspath(iso_path)
        
        try:
            was_bound = (self.state == GadgetState.ACTIVE)
            if was_bound:
                self.unbind()
            
            lun_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/functions/{self.function_name}/lun.0/file'
            
            self._write_file(lun_file, '')
            self._write_file(lun_file, iso_path)
            
            if was_bound:
                self.bind()
            
            self.current_iso = iso_path
            self.logger.info(f"ISO switched to: {iso_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set ISO: {e}")
            return False

    def shutdown(self):
        """Clean up gadget."""
        self.logger.info("Shutting down gadget")
        self.unbind()
        self._safe_cleanup_gadget()

    def get_status(self) -> Dict[str, Any]:
        """Get current gadget status."""
        return {
            'state': self.state.value,
            'current_iso': self.current_iso,
            'udc': self._udc,
            'functions': ['mass_storage']
        }