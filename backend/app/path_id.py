import hashlib
from pathlib import Path


def path_id(abs_path: str | Path) -> str:
    p = Path(abs_path)
    if not p.is_absolute():
        raise ValueError(f"Expected an absolute path, got: {abs_path}")
    return hashlib.md5(str(p).encode("utf-8")).hexdigest()[:16]
