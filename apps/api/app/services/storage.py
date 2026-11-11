import os
import tempfile
from pathlib import Path


class FileStorage:
    """Content-addressed local storage for original uploads."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, content_hash: str) -> Path:
        return self.root / content_hash[:2] / content_hash

    def save(self, content_hash: str, data: bytes) -> str:
        path = self.path_for(content_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            fd, tmp = tempfile.mkstemp(dir=path.parent)
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, path)
        return str(path.relative_to(self.root))

    def read(self, relative_path: str) -> bytes:
        return (self.root / relative_path).read_bytes()

    def delete(self, relative_path: str) -> None:
        (self.root / relative_path).unlink(missing_ok=True)
