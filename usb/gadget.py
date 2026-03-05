"""
USB Gadget manager for CD-ROM, Ethernet and MTP emulation
Uses configfs to configure USB gadget on Raspberry Pi Zero
"""
import os
import subprocess
import time
import glob
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
        """Safely cleanup existing gadget if exists — более надёжный порядок"""
        gadget_path = f"/sys/kernel/config/usb_gadget/{self.gadget_name}"
        
        if not os.path.exists(gadget_path):
            return True
        
        self.logger.info(f"Cleaning up existing gadget: {self.gadget_name}")
        
        # 1. Сначала всегда unbind UDC (если bound)
        udc_file = f"{gadget_path}/UDC"
        try:
            if os.path.exists(udc_file):
                with open(udc_file, 'r') as f:
                    current_udc = f.read().strip()
                if current_udc:
                    self.logger.info(f"Unbinding from UDC: {current_udc}")
                    with open(udc_file, 'w') as f:
                        f.write("\n")
                    time.sleep(1.0)  # даём kernel время отпустить
        except Exception as e:
            self.logger.warning(f"Failed to unbind UDC: {e}")
        
        # 2. Удаляем симлинки из configs/c.1/*
        config_path = f"{gadget_path}/configs/{self.config_name}"
        if os.path.exists(config_path):
            try:
                for item in os.listdir(config_path):
                    item_path = os.path.join(config_path, item)
                    if os.path.islink(item_path):
                        os.unlink(item_path)
                        self.logger.debug(f"Removed symlink: {item}")
                time.sleep(0.2)
            except Exception as e:
                self.logger.warning(f"Error removing symlinks: {e}")
        
        # 3. Удаляем lun.0 (если есть)
        func_path = f"{gadget_path}/functions/{self.function_name}"
        if os.path.exists(func_path):
            lun_path = f"{func_path}/lun.0"
            if os.path.exists(lun_path):
                try:
                    # Сначала очищаем file (на всякий)
                    file_attr = f"{lun_path}/file"
                    if os.path.exists(file_attr):
                        with open(file_attr, 'w') as f:
                            f.write("\n")
                    # Очищаем другие атрибуты, если нужно
                    os.rmdir(lun_path)
                    self.logger.debug("Removed lun.0")
                except Exception as e:
                    self.logger.warning(f"Could not remove lun.0: {e}")
            
            # Теперь сам function
            try:
                os.rmdir(func_path)
                self.logger.debug(f"Removed function: {self.function_name}")
            except Exception as e:
                self.logger.warning(f"Error removing function: {e}")
        
        # 4. Удаляем strings в config (если пусто)
        try:
            cfg_strings = f"{config_path}/strings/0x409"
            if os.path.exists(cfg_strings):
                for f in os.listdir(cfg_strings):
                    os.remove(os.path.join(cfg_strings, f))
                os.rmdir(cfg_strings)
            if os.path.exists(config_path):
                os.rmdir(config_path)
        except Exception as e:
            self.logger.warning(f"Error cleaning config/strings: {e}")
        
        # 5. Удаляем gadget strings
        gadget_strings = f"{gadget_path}/strings/0x409"
        if os.path.exists(gadget_strings):
            try:
                for f in os.listdir(gadget_strings):
                    os.remove(os.path.join(gadget_strings, f))
                os.rmdir(gadget_strings)
                os.rmdir(f"{gadget_path}/strings")
            except:
                pass
        
        # 6. Финально сам gadget
        try:
            if os.path.exists(gadget_path):
                os.rmdir(gadget_path)
                self.logger.info(f"Successfully removed gadget: {self.gadget_name}")
        except Exception as e:
            self.logger.warning(f"Final rmdir gadget failed (often benign): {e}")
        
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
            self._write_file(f'{gadget_path}/idVendor', '0x1d6b')  # Linux Foundation
            self._write_file(f'{gadget_path}/idProduct', '0x0104') # Multifunction Composite Gadget
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
            
            # stall можно оставить — полезно для отлова багов
            self._write_file(f'{func_path}/stall', '1')
            # nofua на уровне function обычно не пишется или игнорируется — убираем
            
            # lun.0 — создаём и сразу настраиваем
            lun_path = f'{func_path}/lun.0'
            os.makedirs(lun_path, exist_ok=True)
            time.sleep(0.1)  # маленький sleep — иногда sysfs тормозит
            
            self._write_file(f'{lun_path}/removable', '1')
            self._write_file(f'{lun_path}/cdrom', '1')
            self._write_file(f'{lun_path}/nofua', '0')   # теперь ок
            
            # Опционально: read-only для чистого CD-ROM поведения
            # self._write_file(f'{lun_path}/ro', '1')
            
            # Link function to config
            link_path = f'{config_path}/{self.function_name}'
            if not os.path.exists(link_path):
                os.symlink(func_path, link_path)
            
            self.logger.info("Gadget structure created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create gadget structure: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def init(self) -> bool:
        """Initialize USB gadget configuration."""
        self.logger.info("Initializing USB gadget")
        
        # Check root
        if os.geteuid() != 0:
            self.logger.error("Must run as root to create USB gadget!")
            return False
        
        # Check and load modules
        if not self._check_module("dwc2"):
            self.logger.info("Module dwc2 not loaded, loading...")
            if not self._load_module("dwc2"):
                self.logger.error("Failed to load dwc2. Add 'dtoverlay=dwc2' to /boot/config.txt")
                return False
        else:
            self.logger.info("Module dwc2 is loaded")
        
        if not self._check_module("libcomposite"):
            self._load_module("libcomposite")
        
        # Mount configfs
        if not self._mount_configfs():
            return False
        
        # Get UDC
        self._udc = self._get_udc()
        if not self._udc:
            self.logger.error("No UDC found! Check USB cable connection")
            return False
        
        # Create gadget structure
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
            # Unbind current
            was_bound = (self.state == GadgetState.ACTIVE)
            if was_bound:
                self.unbind()
            
            # Set new ISO file in lun.0
            lun_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/functions/{self.function_name}/lun.0/file'
            
            # Clear current file
            self._write_file(lun_file, '')
            
            # Set new file
            self._write_file(lun_file, iso_path)
            
            # Rebind if was active
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
