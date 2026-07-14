import hashlib
from pathlib import Path


def path_id(abs_path: str | Path) -> str:
    p = str(Path(abs_path).resolve())
    return hashlib.md5(p.encode("utf-8")).hexdigest()[:16]
