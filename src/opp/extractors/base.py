import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

from opp.utils.dataclasses import DocumentMetadata, ExtractionResult
from opp.utils.exceptions import CorruptedFileError, ValidationError


class ExtractorBase(ABC):
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        pass

    @abstractmethod
    def extract(self, input_path: Path) -> ExtractionResult:
        pass

    def validate_file(self, path: Path) -> bool:
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        if path.stat().st_size == 0:
            raise CorruptedFileError(f"文件为空: {path}")
        ext = path.suffix.lower()
        if ext not in self.supported_extensions():
            raise ValidationError(f"不支持的文件格式: {ext}")
        return True

    def get_file_info(self, path: Path) -> DocumentMetadata:
        stat = path.stat()
        return DocumentMetadata(
            file_size=stat.st_size,
            format_type=path.suffix.lower()[1:],
        )

    def compute_hash(self, data: bytes) -> str:
        return hashlib.md5(data).hexdigest()
