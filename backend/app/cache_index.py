import yaml
from pathlib import Path
from typing import Optional

from app.path_id import path_id
from app.config import data_path


def root_cache_dir(root_path: str) -> Path:
    """Create the root-level cache directory identifier.

    Returns ``{data_path}/cache/{root_dir_name}-{md5(root_path)[:4]}``.
    """
    root_name = Path(root_path).resolve().name
    md5_prefix = path_id(root_path)[:4]
    return data_path() / "cache" / f"{root_name}-{md5_prefix}"


def video_cache_path(root_path: str, video_abs_path: str) -> tuple[Path, Path]:
    """Return ``(index_yaml_path, thumb_png_path)`` for the given video.

    Parent directories are created on demand; the caller can safely write to
    either returned path immediately.
    """
    root = Path(root_path).resolve()
    video = Path(video_abs_path).resolve()
    rel = video.relative_to(root)
    parent_dir = root_cache_dir(root_path) / rel.parent
    parent_dir.mkdir(parents=True, exist_ok=True)
    index_path = parent_dir / "index.yaml"
    thumb_path = parent_dir / f"{video.name}.png"
    return index_path, thumb_path


def load_index(index_path: Path) -> list[dict]:
    """Load the ``videos`` list from *index_path*, or return ``[]``."""
    if not index_path.exists():
        return []
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError:
        return []
    if not data or "videos" not in data:
        return []
    return data["videos"]


def save_index(index_path: Path, videos: list[dict]) -> None:
    """Save a list of video dicts to *index_path* as YAML."""
    data = {"videos": videos}
    with open(index_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def update_video_in_index(index_path: Path, video_info: dict) -> None:
    """Add *video_info* to the index, or replace an existing entry with the
    same ``file_name``."""
    videos = load_index(index_path)
    file_name = video_info.get("file_name")
    for i, v in enumerate(videos):
        if v.get("file_name") == file_name:
            videos[i] = video_info
            break
    else:
        videos.append(video_info)
    save_index(index_path, videos)


def remove_video_from_index(index_path: Path, file_name: str) -> None:
    """Remove the entry with *file_name* from the index, if present."""
    videos = load_index(index_path)
    videos = [v for v in videos if v.get("file_name") != file_name]
    save_index(index_path, videos)


def get_thumb_path(index_path: Path, file_name: str) -> Optional[Path]:
    """Return the path to the thumbnail ``.png`` for *file_name*.

    Returns ``None`` when the entry or the actual file is not found.
    """
    videos = load_index(index_path)
    for v in videos:
        if v.get("file_name") == file_name:
            thumb_file = v.get("thumb_file")
            if thumb_file:
                thumb = index_path.parent / thumb_file
                if thumb.exists():
                    return thumb
    return None
