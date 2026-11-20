"""Domain errors. Messages are written to be shown to the user."""


class BejitechError(Exception):
    """Base class for expected, user-facing errors."""


class ValidationError(BejitechError):
    pass


class NotFoundError(BejitechError):
    pass


class OversellError(BejitechError):
    pass


class LicenseUnavailableError(BejitechError):
    pass


class AuthError(BejitechError):
    pass


class KeyStoreError(BejitechError):
    pass


class BackupError(BejitechError):
    pass
