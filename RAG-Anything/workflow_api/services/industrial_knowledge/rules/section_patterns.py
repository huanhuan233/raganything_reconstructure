"""章节层级标题识别规则。"""

from __future__ import annotations

SECTION_TITLE_PATTERNS: list[str] = [
    r"^\s*(\d+)\s+(.+)$",
    r"^\s*(\d+\.\d+)\s+(.+)$",
    r"^\s*(\d+\.\d+\.\d+)\s+(.+)$",
    r"^\s*第([一二三四五六七八九十百零\d]+)[章节部分]\s*(.+)$",
]
