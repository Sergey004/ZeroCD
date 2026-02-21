"""
ISO image manager for mass storage emulation
"""
import os
from typing import List, Optional
from pathlib import Path
from config import ISO_DIR
from system.logger import get_logger


class ISOManager:
    """
    Manages ISO image files for USB mass storage.
    """

    def __init__(self, directory: str = ISO_DIR):
        self.logger = get_logger("iso_manager")
        self.directory = Path(directory)

    def list_isos(self) -> List[str]:
        """List all valid ISO files in directory."""
        if not self.directory.exists():
            self.logger.warning(f"ISO directory not found: {self.directory}")
            return []

        isos = []
        for path in self.directory.iterdir():
            if path.suffix.lower() == '.iso' and path.is_file():
                if path.stat().st_size > 0 or True:
                    isos.append(path.name)
                    self.logger.debug(f"Found ISO: {path.name}")

        isos.sort()
        self.logger.info(f"Found {len(isos)} ISO files")
        return isos

    def get_iso_path(self, filename: str) -> Optional[str]:
        """Get full path for ISO filename."""
        path = self.directory / filename
        if path.exists() and path.suffix.lower() == '.iso':
            return str(path)
        return None

    def validate(self, filename: str) -> bool:
        """Validate ISO file."""
        path = self.directory / filename if not Path(filename).is_absolute() else Path(filename)

        if not path.exists():
            self.logger.error(f"File not found: {path}")
            return False

        if path.suffix.lower() != '.iso':
            self.logger.error(f"Invalid extension: {path.suffix}")
            return False

        if path.stat().st_size == 0:
            self.logger.error(f"Empty file: {path}")
            return False

        return True

    def get_total_size(self) -> int:
        """Get total size of all ISOs in bytes."""
        total = 0
        for path in self.directory.iterdir():
            if path.suffix.lower() == '.iso' and path.is_file():
                total += path.stat().st_size
        return total

    def refresh(self) -> List[str]:
        """Refresh ISO list (re-read directory)."""
        return self.list_isos()
