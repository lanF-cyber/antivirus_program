from __future__ import annotations

import hashlib
from pathlib import Path

from scanbox.core.models import FileHashes


class HashingService:
    def compute(self, file_path: Path, include_sha1: bool = True, chunk_size: int = 1024 * 1024) -> FileHashes:
        sha256 = hashlib.sha256()
        md5 = hashlib.md5()
        sha1 = hashlib.sha1() if include_sha1 else None

        with file_path.open("rb") as handle:
            while chunk := handle.read(chunk_size):
                sha256.update(chunk)
                md5.update(chunk)
                if sha1 is not None:
                    sha1.update(chunk)

        return FileHashes(
            sha256=sha256.hexdigest(),
            md5=md5.hexdigest(),
            sha1=sha1.hexdigest() if sha1 is not None else None,
        )
