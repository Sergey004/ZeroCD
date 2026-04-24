"""
RAW IMG image creator for USB mass storage.
Creates blank disk images that hosts can format themselves.
"""
import os
import subprocess
from pathlib import Path
from typing import Optional

from config import ISO_DIR
from system.logger import get_logger


class ImageCreator:
    MAX_SIZE_MB = 8192

    def __init__(self, directory: str = ISO_DIR):
        self.logger = get_logger("image_creator")
        self.directory = Path(directory)

    def create_blank_img(self, name: str, size_mb: int) -> Optional[str]:
        if size_mb < 1 or size_mb > self.MAX_SIZE_MB:
            self.logger.error(f"Size {size_mb}MB out of range (1-{self.MAX_SIZE_MB})")
            return None

        if not name:
            self.logger.error("Empty name")
            return None

        safe_name = "".join(c for c in name if c.isalnum() or c in ('_', '-', '.')).strip()
        if not safe_name:
            safe_name = "disk"
        if not safe_name.endswith('.img'):
            safe_name += '.img'

        output_path = self.directory / safe_name

        if output_path.exists():
            self.logger.error(f"File already exists: {output_path}")
            return None

        available = self.get_available_space_mb()
        if size_mb > available:
            self.logger.error(f"Not enough space: need {size_mb}MB, available {available}MB")
            return None

        try:
            self.logger.info(f"Creating {safe_name} ({size_mb}MB)...")
            result = subprocess.run(
                ['fallocate', '-l', f'{size_mb}M', str(output_path)],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                self.logger.warning(f"fallocate failed ({result.stderr}), falling back to dd...")
                result = subprocess.run(
                    ['dd', 'if=/dev/zero', f'of={output_path}', 'bs=1M', f'count={size_mb}',
                     'status=progress'],
                    capture_output=True, text=True, timeout=600
                )
                if result.returncode != 0:
                    self.logger.error(f"dd failed: {result.stderr}")
                    if output_path.exists():
                        output_path.unlink()
                    return None

            self.logger.info(f"Created {safe_name} ({size_mb}MB)")
            return str(output_path)

        except subprocess.TimeoutExpired:
            self.logger.error("Image creation timed out")
            if output_path.exists():
                output_path.unlink()
            return None
        except Exception as e:
            self.logger.error(f"Failed to create image: {e}")
            if output_path.exists():
                output_path.unlink()
            return None

    def get_available_space_mb(self) -> int:
        try:
            if not self.directory.exists():
                return 0
            stat = os.statvfs(self.directory)
            return (stat.f_bavail * stat.f_frsize) // (1024 * 1024)
        except Exception:
            return 0

    def get_next_disk_name(self) -> str:
        existing = set()
        if self.directory.exists():
            for p in self.directory.iterdir():
                if p.suffix.lower() == '.img' and p.is_file():
                    existing.add(p.stem.lower())

        idx = 1
        while True:
            name = f"disk_{idx:03d}"
            if name not in existing:
                return name
            idx += 1
