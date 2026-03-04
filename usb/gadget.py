"""
USB Gadget manager for CD-ROM, Ethernet and MTP emulation
"""
import os
import subprocess
import signal
from enum import Enum
from typing import Optional, Dict, Any, List
from config import GADGET_DIR, GADGET_UDC, ISO_DIR
from system.logger import get_logger


class GadgetState(Enum):
    """USB gadget states."""
    UNBOUND = "unbound"
    CONFIGURED = "configured"
    ACTIVE = "active"


class GadgetManager:
    """
    Manages USB gadget configuration for mass storage, network and MTP.

    Gadget structure:
    - mass_storage.0: CD-ROM emulation with ISO files
    - rndis.usb0: RNDIS Ethernet
    - ecm.usb0: CDC ECM Ethernet
    - ffs.mtp: MTP via FunctionFS
    """

    def __init__(self):
        self.logger = get_logger("gadget")
        self.state = GadgetState.UNBOUND
        self.current_iso: Optional[str] = None
        self.udc_path = GADGET_UDC
        self.mtp_process: Optional[subprocess.Popen] = None
        self.mtp_enabled = False

    def init(self) -> bool:
        """Initialize USB gadget configuration."""
        self.logger.info("Initializing USB gadget")
        self._create_gadget_structure()
        return True

    def _create_gadget_structure(self):
        """Create gadget directory structure in configfs."""
        pass

    def bind(self) -> bool:
        """Bind gadget to UDC (USB Device Controller)."""
        self.logger.info("Binding USB gadget to UDC")
        self.state = GadgetState.ACTIVE
        return True

    def unbind(self) -> bool:
        """Unbind gadget from UDC."""
        self.logger.info("Unbinding USB gadget from UDC")
        self.state = GadgetState.UNBOUND
        return True

    def set_iso(self, iso_path: str) -> bool:
        """
        Switch active ISO image.

        Algorithm:
        1. Unbind from UDC
        2. Change lun.0/file to new ISO
        3. Rebind to UDC
        """
        self.logger.info(f"Switching ISO to: {iso_path}")

        if not os.path.exists(iso_path):
            self.logger.error(f"ISO file not found: {iso_path}")
            return False

        if not iso_path.endswith('.iso'):
            self.logger.error(f"Invalid file extension: {iso_path}")
            return False

        if os.path.getsize(iso_path) == 0:
            self.logger.error(f"ISO file is empty: {iso_path}")
            return False

        self.unbind()
        self._set_lun_file(iso_path)
        self.bind()

        self.current_iso = iso_path
        return True

    def _set_lun_file(self, path: str):
        """Set lun.0/file attribute."""
        pass

    def get_status(self) -> Dict[str, Any]:
        """Get current gadget status."""
        return {
            'state': self.state.value,
            'current_iso': self.current_iso,
            'functions': ['mass_storage', 'rndis', 'ecm', 'mtp'],
        }

    def get_functions(self) -> Dict[str, bool]:
        """Get enabled USB functions."""
        return {
            'mass_storage': True,
            'rndis': True,
            'ecm': True,
            'mtp': self.mtp_enabled,
        }

    def enable_function(self, name: str) -> bool:
        """Enable a USB function."""
        if name == 'mtp':
            return self.start_mtp()
        return True

    def disable_function(self, name: str) -> bool:
        """Disable a USB function."""
        if name == 'mtp':
            return self.stop_mtp()
        return True

    def shutdown(self):
        """Graceful shutdown of USB gadget."""
        self.logger.info("Shutting down USB gadget")
        self.unbind()
        self._cleanup()
        self.state = GadgetState.UNBOUND

    def _cleanup(self):
        """Remove gadget configuration."""
        if self.mtp_enabled:
            self.stop_mtp()

    def start_mtp(self, iso_dir: str = ISO_DIR) -> bool:
        """Start MTP responder via FunctionFS."""
        if self.mtp_enabled:
            self.logger.info("MTP already running")
            return True

        self.logger.info("Starting MTP responder")

        script_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "scripts", "setup_mtp.sh"
        )

        if not os.path.exists(script_path):
            self.logger.error(f"MTP setup script not found: {script_path}")
            return False

        try:
            result = subprocess.run(
                ["sudo", "bash", script_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                self.logger.error(f"MTP setup failed: {result.stderr}")
                return False

            self.mtp_enabled = True
            self.logger.info("MTP responder started successfully")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error("MTP setup timed out")
            return False
        except Exception as e:
            self.logger.error(f"Failed to start MTP: {e}")
            return False

    def stop_mtp(self) -> bool:
        """Stop MTP responder."""
        if not self.mtp_enabled:
            return True

        self.logger.info("Stopping MTP responder")

        try:
            subprocess.run(["pkill", "-9", "umtprd"], capture_output=True)
            subprocess.run(["sudo", "umount", "/dev/ffs-mtp"], capture_output=True)

            self.mtp_enabled = False
            self.mtp_process = None
            self.logger.info("MTP responder stopped")
            return True

        except Exception as e:
            self.logger.error(f"Failed to stop MTP: {e}")
            return False

    def get_mtp_status(self) -> Dict[str, Any]:
        """Get MTP responder status."""
        return {
            'enabled': self.mtp_enabled,
            'running': self.mtp_process is not None if self.mtp_process else False,
        }

    def set_functions(self, functions: List[str]) -> bool:
        """Set enabled USB functions."""
        self.logger.info(f"Setting USB functions: {functions}")

        if 'mtp' in functions and not self.mtp_enabled:
            return self.start_mtp()
        elif 'mtp' not in functions and self.mtp_enabled:
            return self.stop_mtp()

        return True