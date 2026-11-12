"""Small shared helpers: atomic IO, safe names, tolerant JSON parsing, tokenizing."""
from __future__ import annotations
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Set


def atomic_write_text(path: Path, text: str) -> None:
    """先写临时文件再 os.replace，避免进程在写入中途被杀导致 JSON 半截损坏。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        # 损坏文件不静默吞掉：保留现场供人工检查，再回退默认值
        p = Path(path)
        try:
            p.replace(p.with_name(p.name + ".corrupt"))
        except OSError:
            pass
        return default


_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def is_safe_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_SAFE_ID.match(value))


def safe_slug(name: Any, fallback: str = "general", max_len: int = 48) -> str:
    """把模型/用户给的名字压成安全文件名：不允许路径分隔符、点号、空白。保留字母数字下划线连字符与中日韩字符。"""
    s = str(name or "").strip()
    s = re.sub(r"[^0-9A-Za-z_\-一-鿿]+", "_", s).strip("_-")
    s = s[:max_len]
    return s or fallback


def one_line(text: Any, limit: int = 300) -> str:
    """压成单行并截断：防止模型输出里的换行 / Markdown 标题注入到常驻记忆文件里。"""
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


_CJK = re.compile(r"[一-鿿]+")
_WORD = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> Set[str]:
    """英文按完整单词（小写）、中文按相邻二字组切分。'go' 不会再命中 'good'。"""
    text = text or ""
    tokens: Set[str] = {w.lower() for w in _WORD.findall(text) if len(w) >= 2}
    for run in _CJK.findall(text):
        if len(run) == 1:
            continue
        tokens.update(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


def parse_json_response(text: str) -> Any:
    """容忍 ```json 围栏、<think> 推理块与前后废话，提取第一个完整 JSON 对象。失败抛 ValueError。"""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("模型返回为空")
    s = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, flags=re.S | re.I)
    if fence:
        s = fence.group(1).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    if start < 0:
        raise ValueError("模型返回中找不到 JSON 对象")
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(s[start:])
        return obj
    except json.JSONDecodeError as e:
        raise ValueError(f"模型返回的 JSON 无法解析: {e}") from e


def in_quiet_hours(hour: int, start: int, end: int) -> bool:
    """免打扰窗口，支持跨午夜（23→8）与不跨午夜（1→6）两种写法。"""
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end
