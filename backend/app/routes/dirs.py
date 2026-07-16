from fastapi import APIRouter, HTTPException
from pathlib import Path
from .. import config, paths
from ..models import DirEntry
from ..path_id import path_id
from ..routes.videos import scanner

router = APIRouter()


@router.get("/roots", response_model=list[DirEntry])
def list_roots():
    """List all video library root directories (from video_path_list config)."""
    entries = []
    for p in paths.list_roots():
        resolved = Path(p)
        if resolved.exists():
            entries.append(DirEntry(
                id=path_id(str(resolved)),
                name=resolved.name,
                path=str(resolved),
            ))
    return entries


@router.get("/roots/{root_id}/l1", response_model=list[DirEntry])
def list_l1(root_id: str):
    """List L1 directories (top menu) under a given root."""
    if paths.resolve_root(root_id) is None:
        raise HTTPException(404, "root not found")

    entries = []
    for item in sorted(paths.list_l1_dirs(root_id), key=lambda p: p.name):
        entries.append(DirEntry(
            id=path_id(str(item)),
            name=item.name,
            path=str(item),
        ))
    return entries


@router.get("/l1/{l1_id}/l2", response_model=list[DirEntry])
def list_l2(l1_id: str):
    """List L2 directories (left menu) under a given L1 directory."""
    if paths.resolve_l1(l1_id) is None:
        raise HTTPException(404, "l1 directory not found")

    entries = []
    for item in sorted(paths.list_l2_dirs(l1_id), key=lambda p: p.name):
        entries.append(DirEntry(
            id=path_id(str(item)),
            name=item.name,
            path=str(item),
        ))
    return entries


@router.post("/roots/{root_id}/build")
def build_index(root_id: str):
    """为整个视频库根目录构建索引（所有 L2 子目录）。后台执行，立即返回。"""
    root_path = paths.resolve_root(root_id)
    if root_path is None:
        raise HTTPException(404, "root not found")
    return scanner.build_index(root_path)


@router.get("/tasks")
def list_tasks():
    """返回所有运行中的索引任务进度（供前端浮窗显示）。"""
    return scanner.get_tasks()

