from fastapi import APIRouter, HTTPException
from ..routes.videos import scanner
from .. import paths
from ..models import ScanStatus

router = APIRouter()


@router.get("/scan-status", response_model=ScanStatus)
def scan_status(l2_id: str, since: int = 0):
    """Get scan progress and updates since given seq number."""
    l2_path = paths.resolve_l2(l2_id)
    if l2_path is None:
        raise HTTPException(404, "l2 directory not found")

    status = scanner.status(l2_path, since)
    return ScanStatus(**status)
