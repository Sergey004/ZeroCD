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
            
            udc_list =[d for d in os.listdir(udc_path) 
                       if os.path.isdir(os.path.join(udc_path, d))]
            
            if udc_list:
                self.logger.info(f"Found UDC: {udc_list}")
                return udc_list[0]
            else:
                self.logger.error("No UDC devices found")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get UDC: {e}")
        return None

    def _safe_cleanup_gadget(self):
        """Safely cleanup existing gadget if exists"""
        gadget_path = f"/sys/kernel/config/usb_gadget/{self.gadget_name}"
        
        if not os.path.exists(gadget_path):
            return True
        
        self.logger.info(f"Cleaning up {self.gadget_name}...")
        
        # Unbind from UDC
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

        # Remove config symlinks and config
        config_path = f"{gadget_path}/configs/{self.config_name}"
        if os.path.exists(config_path):
            try:
                # Remove symlinks
                for item in os.listdir(config_path):
                    item_path = os.path.join(config_path, item)
                    if os.path.islink(item_path):
                        os.unlink(item_path)
                
                # Remove config strings
                strings_path = f"{config_path}/strings/0x409"
                if os.path.exists(strings_path):
                    os.rmdir(strings_path)
                
                os.rmdir(config_path)
            except Exception as e:
                self.logger.error(f"Failed to remove config: {e}")

        # Remove functions
        functions_path = f"{gadget_path}/functions"
        if os.path.exists(functions_path):
            for item in os.listdir(functions_path):
                fp = f"{functions_path}/{item}"
                try:
                    if os.path.isdir(fp):
                        if 'mass_storage' in item and 'lun.0' in os.listdir(fp):
                            with open(f"{fp}/lun.0/file", 'w') as f:
                                f.write('\n')
                        os.rmdir(fp)
                except Exception as e:
                    self.logger.error(f"Failed to remove function {item}: {e}")
        
        # Remove gadget strings
        gadget_strings = f"{gadget_path}/strings/0x409"
        if os.path.exists(gadget_strings):
            try:
                os.rmdir(gadget_strings)
            except:
                pass

        # Remove gadget
        try:
            os.rmdir(gadget_path)
        except Exception as e:
            self.logger.error(f"Failed to remove gadget dir: {e}")
            pass
        
        time.sleep(0.5)
        return True

    def _write_file(self, path: str, content: str, retries=3):
        """Write to file with retry on busy errors"""
        for attempt in range(retries):
            try:
                with open(path, 'w') as f:
                    f.write(content)
                return
            except OSError as e:
                if e.errno == 16 and attempt < retries - 1:
                    self.logger.warning(f"Device busy, retrying {path} ({attempt+1}/{retries})")
                    time.sleep(0.5)
                else:
                    raise
            except Exception as e:
                self.logger.error(f"Write failed {path}: {e}")
                raise

    def _create_gadget_structure(self) -> bool:
        """Create gadget directory structure in configfs."""
        gadget_path = f'/sys/kernel/config/usb_gadget/{self.gadget_name}'
        
        try:
            self._safe_cleanup_gadget()
            time.sleep(0.5)
            os.makedirs(gadget_path, exist_ok=True)
            
            # USB descriptors
            self._write_file(f'{gadget_path}/idVendor', '0x1d6b')
            self._write_file(f'{gadget_path}/idProduct', '0x0104')
            self._write_file(f'{gadget_path}/bcdDevice', '0x0100')
            self._write_file(f'{gadget_path}/bcdUSB', '0x0200')
            
            # Strings
            os.makedirs(f'{gadget_path}/strings/0x409', exist_ok=True)
            self._write_file(f'{gadget_path}/strings/0x409/manufacturer', 'ZeroCD')
            self._write_file(f'{gadget_path}/strings/0x409/product', 'CD + Ethernet')
            self._write_file(f'{gadget_path}/strings/0x409/serialnumber', 'zero cd 2026')
            
            # Config
            config_path = f'{gadget_path}/configs/{self.config_name}'
            os.makedirs(config_path, exist_ok=True)
            os.makedirs(f'{config_path}/strings/0x409', exist_ok=True)
            self._write_file(f'{config_path}/strings/0x409/configuration', 'CD-ROM + LAN')
            
            # CD-ROM
            ms_path = f'{gadget_path}/functions/mass_storage.usb0'
            os.makedirs(ms_path, exist_ok=True)
            time.sleep(0.1)
            self._write_file(f'{ms_path}/stall', '1')
            
            lun_path = f'{ms_path}/lun.0'
            os.makedirs(lun_path, exist_ok=True)
            time.sleep(0.2)
            
            # ИСПРАВЛЕНО: Добавлен ro=1. Без него ядро не дает примонтировать ISO!
            self._write_file(f'{lun_path}/removable', '1')
            self._write_file(f'{lun_path}/ro', '1')     
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
            self.logger.info(f"Bound to {self._udc}")
            return True
        except Exception as e:
            self.logger.error(f"Bind failed: {e}")
            return False

    def unbind(self) -> bool:
        """Unbind gadget from UDC."""
        try:
            udc_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/UDC'
            if os.path.exists(udc_file):
                with open(udc_file, 'r') as f:
                    if f.read().strip():
                        self._write_file(udc_file, '\n')
                        time.sleep(0.5)
            self.state = GadgetState.UNBOUND
            return True
        except Exception as e:
            self.logger.error(f"Unbind failed: {e}")
            return False

    def set_iso(self, iso_path: str) -> bool:
        """Switch active ISO image."""
        self.logger.info(f"Setting ISO: {iso_path}")
        
        if not os.path.exists(iso_path):
            self.logger.error(f"ISO not found: {iso_path}")
            return False
        
        # Check file is readable
        if not os.access(iso_path, os.R_OK):
            self.logger.error(f"ISO not readable: {iso_path}")
            return False
        
        # Get absolute path
        iso_path = os.path.abspath(iso_path)
        
        # Get file size for logging
        try:
            size_mb = os.path.getsize(iso_path) / (1024 * 1024)
            self.logger.info(f"ISO size: {size_mb:.1f} MB")
        except:
            pass
        
        try:
            lun_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/functions/{self.function_name}/lun.0/file'
            
            # ИСПРАВЛЕНО: Полный unbind/bind больше не нужен!
            # Эмулируем извлечение диска
            self.logger.info("Ejecting current ISO...")
            self._write_file(lun_file, '\n')
            time.sleep(0.8) # Даем ОС время понять, что дисковод открылся
            
            # Эмулируем вставку нового диска
            self.logger.info(f"Inserting new ISO: {iso_path}")
            self._write_file(lun_file, iso_path)
            time.sleep(0.5) # Даем ОС время на чтение нового диска
            
            # Verify file was set
            with open(lun_file, 'r') as f:
                set_path = f.read().strip()
                if set_path != iso_path:
                    self.logger.error(f"ISO path not set correctly. Got: {set_path}")
                    return False
                self.logger.info(f"ISO verified: {set_path}")
            
            self.current_iso = iso_path
            self.logger.info(f"ISO switched successfully to: {iso_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set ISO: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
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