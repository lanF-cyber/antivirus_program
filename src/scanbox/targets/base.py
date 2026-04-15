from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class ScanTarget(ABC):
    @property
    @abstractmethod
    def path(self) -> Path:
        raise NotImplementedError
