class OPPError(Exception):
    pass


class CorruptedFileError(OPPError):
    pass


class PasswordProtectedError(OPPError):
    pass


class UnsupportedFormatError(OPPError):
    pass


class ValidationError(OPPError):
    pass
