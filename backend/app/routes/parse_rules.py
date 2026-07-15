import re
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .. import config
from ..scanner import _parse_filename, find_root
from ..cache_index import video_cache_path

router = APIRouter()


class TestRuleRequest(BaseModel):
    rules: list[dict]
    source_dir: str  # 源视频目录路径（非缓存路径），API 自动映射到缓存


class TestRuleResult(BaseModel):
    file_name: str
    matched_rule: str | None = None
    ext: dict | None = None


class TestRuleResponse(BaseModel):
    results: list[TestRuleResult]
    field_names: list[str]


@router.post("/parse-rules/test", response_model=TestRuleResponse)
def test_parse_rules(req: TestRuleRequest):
    """用给定的规则测试指定源视频目录下的文件名解析。

    内部将 source_dir 映射到缓存目录后读取 index.yaml。
    规则按顺序匹配，第一条匹配成功的规则生效。
    """
    source = Path(req.source_dir).resolve()
    if not source.exists() or not source.is_dir():
        raise HTTPException(400, f"directory not found: {req.source_dir}")

    # 从配置文件加载根目录列表
    cfg = config.load_config()
    root = find_root(str(source), cfg.video_path_list)
    if root is None:
        raise HTTPException(400, f"directory not under any configured video root: {req.source_dir}")

    # 取该目录下的第一个视频文件（任何扩展名）来获取缓存路径
    # 缓存路径是按根目录划分的，同一目录下的视频共享同一 index.yaml
    first_video = None
    exts = {".mp4", ".mkv", ".mov", ".avi", ".m4v", ".flv", ".webm", ".wmv", ".ts", ".mpg", ".mpeg", ".3gp", ".rm", ".rmvb"}
    for f in source.iterdir():
        if f.is_file() and f.suffix.lower() in exts:
            first_video = str(f)
            break

    if first_video is None:
        raise HTTPException(400, f"no video files found in source directory: {req.source_dir}")

    index_path, _ = video_cache_path(str(root), first_video)
    if not index_path.exists():
        raise HTTPException(400, f"cache not built yet for this directory (no index.yaml at {index_path.parent}). Run '构建索引' first.")

    import yaml
    file_names = []
    try:
        data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
        if data and "videos" in data:
            for v in data["videos"]:
                fn = v.get("file_name", "")
                if fn:
                    file_names.append(fn)
    except Exception as e:
        raise HTTPException(400, f"failed to read index.yaml: {e}")

    if not file_names:
        raise HTTPException(400, f"no videos found in {index_path}")

    file_names = sorted(set(file_names))

    results = []
    all_fields = set()
    for fn in file_names:
        ext = _parse_filename(fn, req.rules)
        matched_rule = None
        if ext:
            for rule in req.rules:
                try:
                    m = re.match(rule.get("pattern", ""), fn)
                    if m:
                        g = {k: v for k, v in m.groupdict().items() if v is not None}
                        if g:
                            matched_rule = rule.get("name", "")
                            break
                except re.error:
                    continue
        if ext:
            all_fields.update(ext.keys())
        results.append(TestRuleResult(
            file_name=fn,
            matched_rule=matched_rule,
            ext=ext,
        ))

    return TestRuleResponse(
        results=results,
        field_names=sorted(all_fields),
    )
