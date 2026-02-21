"""
PC Gadget emulator - simulates USB gadget for testing
"""
from enum import Enum
from typing import Optional, Dict, Any
from system.logger import get_logger


class GadgetState(Enum):
    UNBOUND = "unbound"
    CONFIGURED = "configured"
    ACTIVE = "active"


class GadgetManagerPC:
    """
    PC-based USB gadget emulator.

    Instead of configfs, logs actions to console/file.
    Useful for testing menu and ISO switching logic.
    """

    def __init__(self, test_mode: bool = True):
        self.logger = get_logger("gadget_pc")
        self.state = GadgetState.UNBOUND
        self.current_iso: Optional[str] = None
        self.test_mode = test_mode
        self.bind_count = 0
        self.unbind_count = 0

    def init(self) -> bool:
        self.logger.info("Initializing PC USB gadget emulator")
        return True

    def bind(self) -> bool:
        self.bind_count += 1
        self.state = GadgetState.ACTIVE
        print(f"[GADGET] BIND - ISO: {self.current_iso or 'none'} (bind #{self.bind_count})")
        self.logger.info(f"USB gadget bound, ISO: {self.current_iso}")
        return True

    def unbind(self) -> bool:
        self.unbind_count += 1
        self.state = GadgetState.UNBOUND
        print(f"[GADGET] UNBIND (unbind #{self.unbind_count})")
        self.logger.info("USB gadget unbound")
        return True

    def set_iso(self, iso_path: str) -> bool:
        import os
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

        print(f"[GADGET] SWITCH: {self.current_iso} → {iso_path}")
        self.unbind()
        self._set_lun_file(iso_path)
        self.bind()

        self.current_iso = iso_path
        return True

    def _set_lun_file(self, path: str):
        print(f"[GADGET] LUN.0/FILE = {path}")

    def get_status(self) -> Dict[str, Any]:
        return {
            'state': self.state.value,
            'current_iso': self.current_iso,
            'functions': ['mass_storage', 'rndis', 'ecm'],
            'bind_count': self.bind_count,
            'unbind_count': self.unbind_count,
        }

    def get_functions(self) -> Dict[str, bool]:
        return {
            'mass_storage': True,
            'rndis': True,
            'ecm': True,
        }

    def shutdown(self):
        print(f"[GADGET] SHUTDOWN (binds: {self.bind_count}, unbinds: {self.unbind_count})")
        self.unbind()
        self.state = GadgetState.UNBOUND
