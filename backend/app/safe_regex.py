"""对用户提交的正则做带超时的安全匹配（H3 ReDoS 防护）。

``re`` 没有原生超时；这里把匹配放到守护线程里跑，主线程 ``join(timeout)``。
超时则放弃结果（返回 None）。注意：Python 无法杀死线程，超时后工作线程
仍会继续跑直到结束——但调用方不会被无限阻塞。
"""
from __future__ import annotations

import re
import threading


def safe_match(pattern: str, string: str, timeout: float = 2.0) -> re.Match | None:
    """编译并匹配 *pattern*；超时或出错返回 ``None``。"""
    try:
        compiled = re.compile(pattern)
    except re.error:
        return None
    return safe_compiled_match(compiled, string, timeout=timeout)


def safe_compiled_match(compiled: re.Pattern, string: str,
                        timeout: float = 2.0) -> re.Match | None:
    """对已编译正则做带超时的匹配。"""
    box: dict = {"m": None}

    def _run():
        try:
            box["m"] = compiled.match(string)
        except Exception:
            box["m"] = None

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        # 仍在跑（灾难性回溯）——放弃结果
        return None
    return box["m"]
