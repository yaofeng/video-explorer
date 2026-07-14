from fastapi import APIRouter, HTTPException
from ..routes.videos import scanner
from ..models import ScanStatus

router = APIRouter()


@router.get("/scan-status", response_model=ScanStatus)
def scan_status(l2_id: str, since: int = 0):
    from ..path_id import path_id
    from pathlib import Path
    from .. import config

    cfg = config.load_config()
    l2_path = None
    for root_p in cfg.video_path_list:
        root = Path(root_p).resolve()
        if not root.exists():
            continue
        for item in root.iterdir():
            if item.is_dir() and path_id(str(item)) == l2_id:
                l2_path = str(item)
                break
        if l2_path:
            break

    if l2_path is None:
        raise HTTPException(404, "未找到 l2 目录")

    status = scanner.status(l2_path, since)
    return ScanStatus(**status)
