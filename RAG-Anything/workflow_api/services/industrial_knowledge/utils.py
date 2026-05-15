"""工业知识服务通用工具。"""

from __future__ import annotations

import re
from typing import Any


_CN_SPLIT = re.compile(r"[；;。,\n]+")


def clean_text(v: Any) -> str:
    return str(v or "").replace("\u3000", " ").strip()


def compact_text(v: Any) -> str:
    return re.sub(r"\s+", " ", clean_text(v))


def split_sentences(v: Any) -> list[str]:
    text = clean_text(v)
    if not text:
        return []
    return [x.strip() for x in _CN_SPLIT.split(text) if x.strip()]


def safe_float(v: Any) -> float | None:
    try:
        return float(v)
    except Exception:  # noqa: BLE001
        return None


def first_non_empty(*vals: Any) -> str:
    for one in vals:
        s = clean_text(one)
        if s:
            return s
    return ""
