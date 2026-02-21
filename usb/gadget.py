"""
USB Gadget manager for CD-ROM and Ethernet emulation
"""
import os
from enum import Enum
from typing import Optional, Dict, Any
from config import GADGET_DIR, GADGET_UDC, ISO_DIR
from system.logger import get_logger


class GadgetState(Enum):
    """USB gadget states."""
    UNBOUND = "unbound"
    CONFIGURED = "configured"
    ACTIVE = "active"


class GadgetManager:
    """
    Manages USB gadget configuration for mass storage and network.

    Gadget structure:
    - mass_storage.0: CD-ROM emulation with ISO files
    - rndis.usb0: RNDIS Ethernet
    - ecm.usb0: CDC ECM Ethernet
    """

    def __init__(self):
        self.logger = get_logger("gadget")
        self.state = GadgetState.UNBOUND
        self.current_iso: Optional[str] = None
        self.udc_path = GADGET_UDC

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
            'functions': ['mass_storage', 'rndis', 'ecm'],
        }

    def get_functions(self) -> Dict[str, bool]:
        """Get enabled USB functions."""
        return {
            'mass_storage': True,
            'rndis': True,
            'ecm': True,
        }

    def enable_function(self, name: str) -> bool:
        """Enable a USB function."""
        return True

    def disable_function(self, name: str) -> bool:
        """Disable a USB function."""
        return True

    def shutdown(self):
        """Graceful shutdown of USB gadget."""
        self.logger.info("Shutting down USB gadget")
        self.unbind()
        self._cleanup()
        self.state = GadgetState.UNBOUND

    def _cleanup(self):
        """Remove gadget configuration."""
        pass
