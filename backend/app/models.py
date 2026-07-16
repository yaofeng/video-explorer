from pydantic import BaseModel


class VideoItem(BaseModel):
    """视频条目（扁平结构，与 index.yaml 一致）。

    L1：仅有 file_name/file_size/group/level=1
    L2：附加 codec/width/height/duration/resolution_label
    L3：附加缩略图（thumb_file 仅在缓存中）
    """
    video_id: str
    file_name: str
    file_size: int  # 单位：MB（整数）
    group: str
    level: int = 1  # 1=filename, 2=+metadata, 3=+thumbnail
    modify_time: int | None = None  # 源文件修改时间（epoch 秒）
    ext: dict | None = None  # 文件名解析扩展信息（code/actress/title 等）
    # L2+ 元数据字段（level>=2 时存在）
    codec: str | None = None
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    resolution_label: str | None = None  # e.g. "4K", "FHD"


class Group(BaseModel):
    name: str
    videos: list[VideoItem]


class VideosResponse(BaseModel):
    groups: list[Group]
    scanning: bool
    progress: dict = {}  # {"total": N, "level1": N, "level2": N, "level3": N}


class ScanUpdate(BaseModel):
    """扫描增量更新条目（扁平结构）。"""
    seq: int
    video_id: str
    file_name: str
    file_size: int  # 单位：MB（整数）
    group: str
    level: int
    modify_time: int | None = None
    ext: dict | None = None
    codec: str | None = None
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    resolution_label: str | None = None


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
