from pydantic import BaseModel


class VideoL1(BaseModel):
    """Level 1: filename + size only (from filesystem scan)"""
    video_id: str
    file_name: str
    file_size: int
    group: str
    level: int = 1  # 1=filename, 2=+metadata, 3=+thumbnail


class VideoMeta(BaseModel):
    """Level 2: ffprobe metadata"""
    codec: str
    duration: float
    width: int
    height: int
    resolution_str: str  # e.g. "3840x2160"
    file_size: int


class VideoDetail(VideoL1):
    """Full video info (L1 + L2 + L3)"""
    meta: VideoMeta | None = None
    level: int = 1


class Group(BaseModel):
    name: str
    videos: list


class VideosResponse(BaseModel):
    groups: list[Group]
    scanning: bool
    progress: dict = {}  # {"total": N, "level1": N, "level2": N, "level3": N}


class ScanUpdate(BaseModel):
    seq: int
    video_id: str
    file_name: str
    file_size: int
    group: str
    level: int
    meta: VideoMeta | None = None


class ScanStatus(BaseModel):
    scanning: bool
    total: int
    ready: int
    last_seq: int
    progress: dict = {}
    updates: list[ScanUpdate]


class ConfigModel(BaseModel):
    video_path_list: list[str]
    page_size: int
    column_size: int
    parse_rules: list = []


class DirEntry(BaseModel):
    id: str
    name: str
    path: str
