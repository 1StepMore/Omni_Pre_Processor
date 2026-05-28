import hashlib
import threading
import uuid
from pathlib import Path
from shutil import copy2, move
from typing import Dict, Tuple

from opp.utils.exceptions import OPPError


class DuplicateResourceError(OPPError):
    pass


class ResourceManager:

    def __init__(self, storage_dir: Path):
        self.storage_dir = Path(storage_dir)
        self._mapping: Dict[str, Tuple[Path, str]] = {}
        self._cross_ref: Dict[str, str] = {}
        self._lock = threading.RLock()

    def add_image(self, source_path: Path) -> Path:
        """Add an image resource to the storage.

        Images are stored with UUID-based filenames (e.g., ``a1b2c3d4.png``)
        rather than the original filename. This ensures unique storage names
        regardless of filename conflicts in source documents.

        The mapping between the original filename and the stored file is tracked
        internally in the ``_mapping`` dict, keyed by MD5 hash. Each entry stores
        the ``(stored_path, original_name)`` tuple, preserving the original
        filename for reference lookups via :meth:`get_resource_path`.

        Args:
            source_path: Path to the source image file.

        Returns:
            Path to the stored image file (UUID-based filename).
        """
        source_path = Path(source_path)
        if not source_path.exists():
            raise FileNotFoundError(f"文件不存在: {source_path}")

        md5_hash = self._compute_file_md5(source_path)

        with self._lock:
            if md5_hash in self._mapping:
                stored_path, _ = self._mapping[md5_hash]
                return stored_path

            ext = source_path.suffix or ".bin"
            stored_filename = f"{uuid.uuid4()}{ext}"
            stored_path = self.storage_dir / stored_filename

            self.storage_dir.mkdir(parents=True, exist_ok=True)

            copy2(source_path, stored_path)

            self._mapping[md5_hash] = (stored_path, source_path.name)

            return stored_path

    def get_mapping(self) -> Dict[str, Path]:
        with self._lock:
            return {original_name: stored_path for stored_path, original_name in self._mapping.values()}

    def relocate_resources(self, output_dir: Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        with self._lock:
            for md5_hash, (stored_path, original_name) in self._mapping.items():
                new_path = output_dir / stored_path.name
                move(str(stored_path), str(new_path))
                self._mapping[md5_hash] = (new_path, original_name)

    def get_resource_path(self, original_name: str) -> Path:
        with self._lock:
            for stored_path, orig_name in self._mapping.values():
                if orig_name == original_name:
                    return stored_path
            raise KeyError(f"No resource found with original name: {original_name}")

    def set_cross_ref(self, md5_hash: str, position_marker: str) -> None:
        with self._lock:
            self._cross_ref[md5_hash] = position_marker

    def _compute_file_md5(self, file_path: Path) -> str:
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()