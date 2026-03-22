"""
USB Gadget manager for CD-ROM, Ethernet and MTP emulation
"""
import os
import subprocess
import time
import threading
from enum import Enum
from typing import Optional, Dict, Any
from system.logger import get_logger

from usb.network import USBNetworkManager
from usb.builder import GadgetBuilder

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
        self.function_name = "mass_storage.usb0"
        self._udc = None
        self._gadget_lock = threading.Lock()
        
        self.net_mgr = USBNetworkManager()
        self.builder = GadgetBuilder(self.gadget_name)
        
        self._current_mode_is_cdrom = True
        self._current_pure_mode = False
        self._current_apple_mode = False

    def _check_and_load(self, mod):
        if mod not in subprocess.run(['lsmod'], capture_output=True, text=True).stdout:
            subprocess.run(['modprobe', mod], check=True)
            time.sleep(0.5)

    def _get_udc(self) -> Optional[str]:
        try:
            udc_list =[d for d in os.listdir('/sys/class/udc/') if os.path.isdir(os.path.join('/sys/class/udc/', d))]
            if udc_list: return udc_list[0]
        except: pass
        return None

    def init(self) -> bool:
        if os.geteuid() != 0: return False
        try:
            self._check_and_load("dwc2")
            self._check_and_load("libcomposite")
            if not os.path.ismount("/sys/kernel/config"):
                subprocess.run(['mount', '-t', 'configfs', 'none', '/sys/kernel/config'], check=True)
        except Exception as e:
            self.logger.error(f"Init failed: {e}")
            return False
            
        self._udc = self._get_udc()
        if not self._udc: return False
        
        if not self.builder.build(self.net_mgr, is_cdrom=True, pure_mode=False, apple_mode=False): 
            return False
            
        self.state = GadgetState.CONFIGURED
        return True

    def bind(self) -> bool:
        if not self._udc: return False
        try:
            udc_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/UDC'
            self.builder.write_file(udc_file, self._udc)
            self.state = GadgetState.ACTIVE
            
            if not self._current_pure_mode and not self._current_apple_mode:
                self.net_mgr.start_dhcp_and_nat(lambda: self.state == GadgetState.ACTIVE)
            return True
        except: return False

    def unbind(self) -> bool:
        try:
            udc_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/UDC'
            if os.path.exists(udc_file):
                with open(udc_file, 'r') as f:
                    if f.read().strip():
                        self.builder.write_file(udc_file, '\n')
                        time.sleep(0.5)
            self.state = GadgetState.UNBOUND
            return True
        except: return False

    def set_iso(self, iso_path: str) -> bool:
        if not os.path.exists(iso_path) or not os.access(iso_path, os.R_OK):
            return False
            
        iso_path = os.path.abspath(iso_path)
        if not self._gadget_lock.acquire(blocking=False):
            self.logger.warning("Swap in progress, ignoring...")
            return False
            
        try:
            if getattr(self, 'current_iso', None) == iso_path:
                return True
                
            is_cdrom = iso_path.lower().endswith('.iso')
            apple_mode = '.apple.' in iso_path.lower()
            pure_mode = '.pure.' in iso_path.lower()
            
            # УБРАЛИ ХАК network_first!
            needs_rebuild = (self._current_mode_is_cdrom != is_cdrom) or \
                            (self._current_pure_mode != pure_mode) or \
                            (self._current_apple_mode != apple_mode)
                            
            was_bound = (self.state == GadgetState.ACTIVE)
            lun0_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/functions/{self.function_name}/lun.0/file'
            lun1_file = f'/sys/kernel/config/usb_gadget/{self.gadget_name}/functions/{self.function_name}/lun.1/file'
            
            if was_bound:
                self.logger.info("Unbinding USB (Cold Swap)...")
                self.unbind()
                time.sleep(3.0)
            
            if needs_rebuild:
                self.logger.info("Rebuilding gadget structure...")
                if not self.builder.build(self.net_mgr, is_cdrom, pure_mode, apple_mode):
                    return False
                self._current_mode_is_cdrom = is_cdrom
                self._current_pure_mode = pure_mode
                self._current_apple_mode = apple_mode
                
            self.builder.write_file(lun0_file, '\n')
            self.builder.write_file(lun1_file, '\n')
            time.sleep(0.5)
            
            # 1. Вставляем основной образ ОС
            self.builder.write_file(lun0_file, iso_path)

            # 2. Автоматически вставляем флешку с драйверами (если файл есть)
            drivers_path = "/mnt/iso_storage/drivers.img"
            if os.path.exists(drivers_path):
                self.logger.info("Found drivers.img! Injecting into secondary USB slot...")
                self.builder.write_file(lun1_file, drivers_path)
            
            if was_bound:
                self.logger.info("Rebinding USB...")
                self.bind()
            
            self.current_iso = iso_path
            self.logger.info("Swap complete!")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set image: {e}")
            return False
        finally:
            self._gadget_lock.release()

    def shutdown(self):
        self.unbind()
        self.builder.cleanup()

    def get_status(self) -> Dict[str, Any]:
        return {'state': self.state.value, 'current_iso': self.current_iso, 'udc': self._udc, 'functions':['mass_storage']}