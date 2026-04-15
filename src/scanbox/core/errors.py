from __future__ import annotations


class ScanBoxError(Exception):
    """Base exception for ScanBox."""


class ConfigError(ScanBoxError):
    """Configuration is missing or invalid."""


class InputError(ScanBoxError):
    """The scan target is invalid or unsupported."""


class EngineMissingError(ScanBoxError):
    """An enabled engine or rule source could not be found."""


class EngineUnavailableError(ScanBoxError):
    """An engine exists but cannot currently be used."""


class EngineTimeoutError(ScanBoxError):
    """An engine did not complete before the configured timeout."""


class EngineExecutionError(ScanBoxError):
    """An engine failed to execute successfully."""


class QuarantineError(ScanBoxError):
    """The quarantine operation failed."""
