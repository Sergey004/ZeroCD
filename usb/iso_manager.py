"""
ISO and IMG image manager for mass storage emulation
"""
import os
from typing import List, Optional
from pathlib import Path
from config import ISO_DIR
from system.logger import get_logger


class ISOManager:
    """
    Manages ISO and IMG image files for USB mass storage.
    """

    def __init__(self, directory: str = ISO_DIR):
        self.logger = get_logger("iso_manager")
        self.directory = Path(directory)
        
        # Поддерживаемые расширения файлов
        self.valid_extensions = ['.iso', '.img']

    def list_isos(self) -> List[str]:
        """List all valid ISO/IMG files in directory."""
        if not self.directory.exists():
            self.logger.warning(f"Image directory not found: {self.directory}")
            return []

        isos =[]
        for path in self.directory.iterdir():
            if path.suffix.lower() in self.valid_extensions and path.is_file():
                if path.stat().st_size > 0:
                    isos.append(path.name)
                    self.logger.debug(f"Found image: {path.name}")

        isos.sort()
        self.logger.info(f"Found {len(isos)} image files")
        return isos

    def get_iso_path(self, filename: str) -> Optional[str]:
        """Get full path for image filename."""
        path = self.directory / filename
        if path.exists() and path.suffix.lower() in self.valid_extensions:
            return str(path)
        return None

    def validate(self, filename: str) -> bool:
        """Validate image file."""
        path = self.directory / filename if not Path(filename).is_absolute() else Path(filename)

        if not path.exists():
            self.logger.error(f"File not found: {path}")
            return False

        if path.suffix.lower() not in self.valid_extensions:
            self.logger.error(f"Invalid extension: {path.suffix}")
            return False

        if path.stat().st_size == 0:
            self.logger.error(f"Empty file: {path}")
            return False

        return True

    def get_total_size(self) -> int:
        """Get total size of all images in bytes."""
        total = 0
        for path in self.directory.iterdir():
            if path.suffix.lower() in self.valid_extensions and path.is_file():
                total += path.stat().st_size
        return total

    def refresh(self) -> List[str]:
        """Refresh image list (re-read directory)."""
        return self.list_isos()

    def create_image(self, name: str, size_mb: int) -> Optional[str]:
        from usb.image_creator import ImageCreator
        creator = ImageCreator(str(self.directory))
        return creator.create_blank_img(name, size_mb)

    def get_available_space_mb(self) -> int:
        from usb.image_creator import ImageCreator
        creator = ImageCreator(str(self.directory))
        return creator.get_available_space_mb()

    def get_next_disk_name(self) -> str:
        from usb.image_creator import ImageCreator
        creator = ImageCreator(str(self.directory))
        return creator.get_next_disk_name()