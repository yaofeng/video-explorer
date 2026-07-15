import re
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .. import config
from ..scanner import _parse_filename

router = APIRouter()


class TestRuleRequest(BaseModel):
    rules: list[dict]  # [{name, pattern}, ...]
    cache_dir: str  # 缓存目录路径


class TestRuleResult(BaseModel):
    file_name: str
    matched_rule: str | None = None  # 匹配的规则名
    ext: dict | None = None  # 解析结果


class TestRuleResponse(BaseModel):
    results: list[TestRuleResult]
    field_names: list[str]  # 所有出现的 ext 字段名（用于表头）


@router.post("/parse-rules/test", response_model=TestRuleResponse)
def test_parse_rules(req: TestRuleRequest):
    """用给定的规则测试一个缓存目录下的所有 index.yaml 文件。

    规则按顺序匹配，第一条匹配成功的规则生效。
    返回每个视频文件的解析结果表格数据。
    """
    dir_path = Path(req.cache_dir)
    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(400, f"directory not found: {req.cache_dir}")

    # 收集所有 index.yaml 中的文件名
    file_names = []
    for yaml_file in dir_path.rglob("index.yaml"):
        try:
            import yaml
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if data and "videos" in data:
                for v in data["videos"]:
                    fn = v.get("file_name", "")
                    if fn:
                        file_names.append(fn)
        except Exception:
            continue

    if not file_names:
        raise HTTPException(400, "no index.yaml files found with videos in directory")

    # 去重并排序
    file_names = sorted(set(file_names))

    # 应用规则
    results = []
    all_fields = set()
    for fn in file_names:
        ext = _parse_filename(fn, req.rules)
        # 找到匹配的规则名
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
