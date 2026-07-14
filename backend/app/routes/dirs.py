from fastapi import APIRouter, HTTPException
from pathlib import Path
from .. import config
from ..models import DirEntry
from ..path_id import path_id

router = APIRouter()


@router.get("/roots", response_model=list[DirEntry])
def list_roots():
    cfg = config.load_config()
    entries = []
    for p in cfg.video_path_list:
        if Path(p).exists():
            entries.append(DirEntry(
                id=path_id(p),
                name=Path(p).name,
                path=p,
            ))
    return entries


@router.get("/roots/{root_id}/l2", response_model=list[DirEntry])
def list_l2(root_id: str):
    cfg = config.load_config()
    root = None
    for p in cfg.video_path_list:
        if path_id(p) == root_id:
            root = Path(p).resolve()
            break

    if root is None:
        raise HTTPException(404, "未找到根目录")

    entries = []
    for item in root.iterdir():
        if item.is_dir():
            entries.append(DirEntry(
                id=path_id(str(item)),
                name=item.name,
                path=str(item),
            ))
    return sorted(entries, key=lambda e: e.name)
