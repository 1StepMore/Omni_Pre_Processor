from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    SlideData,
    TableData,
    TextBlockData,
)
from opp.utils.exceptions import (
    CorruptedFileError,
    OPPError,
    PasswordProtectedError,
    UnsupportedFormatError,
    ValidationError,
)
from opp.utils.cache import cache_root
from opp.utils.security import (
    BLOCKED_EXTENSIONS,
    SYSTEM_DIRS,
    PathValidationError,
    validate_path,
    validate_path_safe,
)
from opp.utils.mcp_errors import (
    MCPError,
    MAX_BATCH_FILES,
    MAX_BATCH_TEXTS,
    MAX_IMAGE_BYTES,
    ResourceExhausted,
    mcp_error_boundary,
    validate_batch_input,
    validate_file_paths,
)

__all__ = [
    "cache_root",
    "DocumentMetadata",
    "ExtractionResult",
    "ImageData",
    "ParagraphData",
    "SlideData",
    "TableData",
    "TextBlockData",
    "OPPError",
    "CorruptedFileError",
    "PasswordProtectedError",
    "UnsupportedFormatError",
    "ValidationError",
    "PathValidationError",
    "validate_path",
    "validate_path_safe",
    "SYSTEM_DIRS",
    "BLOCKED_EXTENSIONS",
    "MCPError",
    "ResourceExhausted",
    "MAX_BATCH_FILES",
    "MAX_BATCH_TEXTS",
    "MAX_IMAGE_BYTES",
    "mcp_error_boundary",
    "validate_batch_input",
    "validate_file_paths",
]
