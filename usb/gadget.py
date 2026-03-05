"""
USB Gadget manager for CD-ROM, Ethernet and MTP emulation
Uses configfs to configure USB gadget on Raspberry Pi Zero
"""
import os
import subprocess
import time
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

    def _get_udc(self) -> Optional[str]:
        """Get available UDC (USB Device Controller)."""
        try:
            # List UDC directory - each subdirectory is a UDC device
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
                self.logger.error("No UDC devices found in /sys/class/udc/")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get UDC: {e}")
        return None

    def init(self) -> bool:
        """Initialize USB gadget configuration."""
        self.logger.info("Initializing USB gadget")
        
        # Check if configfs is mounted
        if not os.path.ismount('/sys/kernel/config'):
            self.logger.info("Mounting configfs")
            subprocess.run(['mount', '-t', 'configfs', 'none', '/sys/kernel/config'], check=False)
        
        # Get UDC
        self._udc = self._get_udc()
        if not self._udc:
            self.logger.error("No UDC found! Make sure dwc2 module is loaded")
            return False
        
        self.logger.info(f"Using UDC: {self._udc}")
        
        # Create gadget structure
        if not self._create_gadget_structure():
            return False
        
        self.state = GadgetState.CONFIGURED
        return True

    def _create_gadget_structure(self) -> bool:
        """Create gadget directory structure in configfs."""
        try:
            # Unbind if already active
            self._unbind_gadget()
            
            # Remove old gadget
            gadget_path = f'/sys/kernel/config/usb_gadget/{self.gadget_name}'
            if os.path.exists(gadget_path):
                self.logger.info("Removing old gadget configuration")
                subprocess.run(['rm', '-rf', gadget_path], check=False)
            
            # Create gadget directory
            os.makedirs(gadget_path, exist_ok=True)
            
            # Set USB device descriptors
            self._write_file(f'{gadget_path}/idVendor', '0x1d6b')  # Linux Foundation
            self._write_file(f'{gadget_path}/idProduct', '0x0104')  # Multifunction Composite Gadget
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
            
            # Create mass storage function
            func_path = f'{gadget_path}/functions/{self.function_name}'
            os.makedirs(func_path, exist_ok=True)
            
            # Set mass storage parameters
            self._write_file(f'{func_path}/stall', '1')
            self._write_file(f'{func_path}/removable', '1')
            self._write_file(f'{func_path}/nofua', '0')
            
            # Link function to config
            os.symlink(func_path, f'{config_path}/{self.function_name}')
            
            self.logger.info("Gadget structure created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create gadget structure: {e}")
            return False

    def _write_file(self, path: str, content: str):
        """Write content to a sysfs file."""
        try:
            with open(path, 'w') as f:
                f.write(content)
        except Exception as e:
            self.logger.error(f"Failed to write to {path}: {e}")
            raise

    def _unbind_gadget(self):
        """Unbind gadget from UDC if active."""
        udc_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/UDC'
        if os.path.exists(udc_file):
            try:
                with open(udc_file, 'r') as f:
                    if f.read().strip():
                        self._write_file(udc_file, '')
                        time.sleep(0.5)
                        self.logger.info("Gadget unbound")
            except Exception as e:
                self.logger.warning(f"Error unbinding gadget: {e}")

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
            self._unbind_gadget()
            self.state = GadgetState.UNBOUND
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
        
        # Get absolute path
        iso_path = os.path.abspath(iso_path)
        
        try:
            # Unbind current
            self.unbind()
            
            # Set new ISO file
            lun_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/functions/{self.function_name}/lun.0/file'
            
            # Clear current file
            self._write_file(lun_file, '')
            
            # Set new file
            self._write_file(lun_file, iso_path)
            
            # Rebind
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

    def get_status(self) -> Dict[str, Any]:
        """Get current gadget status."""
        return {
            'state': self.state.value,
            'current_iso': self.current_iso,
            'udc': self._udc,
            'functions': ['mass_storage']
        }
