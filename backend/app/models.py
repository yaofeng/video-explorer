from pydantic import BaseModel


class VideoMeta(BaseModel):
    codec: str
    duration: float
    width: int
    height: int
    resolution_label: str


class VideoItem(BaseModel):
    video_id: str
    file_name: str
    file_size: int
    group: str
    ready: bool
    meta: VideoMeta | None = None


class Group(BaseModel):
    name: str
    videos: list[VideoItem]


class VideosResponse(BaseModel):
    groups: list[Group]
    scanning: bool


class ScanUpdate(BaseModel):
    seq: int
    video_id: str
    file_name: str
    file_size: int
    group: str
    meta: VideoMeta


class ScanStatus(BaseModel):
    scanning: bool
    total: int
    ready: int
    last_seq: int
    updates: list[ScanUpdate]


class ConfigModel(BaseModel):
    video_path_list: list[str]
    page_size: int
    column_size: int


class DirEntry(BaseModel):
    id: str
    name: str
    path: str
