from fastapi import APIRouter, HTTPException
from ..routes.videos import scanner
from ..models import ScanStatus

router = APIRouter()


@router.get("/scan-status", response_model=ScanStatus)
def scan_status(l2_id: str, since: int = 0):
    """Get scan progress and updates since given seq number."""
    l2_path = _find_l2_path(l2_id)
    if l2_path is None:
        raise HTTPException(404, "l2 directory not found")

    status = scanner.status(l2_path, since)
    return ScanStatus(**status)


def _find_l2_path(l2_id: str) -> str | None:
    """Helper: resolve l2_id to absolute path."""
    from .. import config, path_id
    from pathlib import Path

    cfg = config.load_config()
    for root_p in cfg.video_path_list:
        root = Path(root_p).resolve()
        if not root.exists():
            continue
        for l1_item in root.iterdir():
            if not l1_item.is_dir():
                continue
            for l2_item in l1_item.iterdir():
                if l2_item.is_dir() and path_id.path_id(str(l2_item)) == l2_id:
                    return str(l2_item)
    return None
