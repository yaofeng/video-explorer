from fastapi import APIRouter, HTTPException
from pathlib import Path
from .. import config
from ..models import DirEntry
from ..path_id import path_id

router = APIRouter()


@router.get("/roots", response_model=list[DirEntry])
def list_roots():
    """List all video library root directories (from video_path_list config)."""
    cfg = config.load_config()
    entries = []
    for p in cfg.video_path_list:
        if Path(p).exists():
            resolved = Path(p).resolve()
            entries.append(DirEntry(
                id=path_id(str(resolved)),
                name=resolved.name,
                path=str(resolved),
            ))
    return entries


@router.get("/roots/{root_id}/l1", response_model=list[DirEntry])
def list_l1(root_id: str):
    """List L1 directories (top menu) under a given root."""
    cfg = config.load_config()
    root_path = None
    for p in cfg.video_path_list:
        rp = Path(p).resolve()
        if path_id(str(rp)) == root_id:
            root_path = rp
            break

    if root_path is None:
        raise HTTPException(404, "root not found")

    entries = []
    for item in sorted(root_path.iterdir()):
        if item.is_dir():
            entries.append(DirEntry(
                id=path_id(str(item)),
                name=item.name,
                path=str(item),
            ))
    return entries


@router.get("/l1/{l1_id}/l2", response_model=list[DirEntry])
def list_l2(l1_id: str):
    """List L2 directories (left menu) under a given L1 directory."""
    cfg = config.load_config()
    l1_path = None
    for root_p in cfg.video_path_list:
        rp = Path(root_p).resolve()
        if not rp.exists():
            continue
        for item in rp.iterdir():
            if item.is_dir() and path_id(str(item)) == l1_id:
                l1_path = item.resolve()
                break
        if l1_path:
            break

    if l1_path is None:
        raise HTTPException(404, "l1 directory not found")

    entries = []
    for item in sorted(l1_path.iterdir()):
        if item.is_dir():
            entries.append(DirEntry(
                id=path_id(str(item)),
                name=item.name,
                path=str(item),
            ))
    return entries
