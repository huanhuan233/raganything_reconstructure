"""工艺约束提取规则。"""

from __future__ import annotations

CONSTRAINT_PATTERNS: list[dict[str, str]] = [
    {"name": "comparison", "pattern": r"(?P<parameter>[A-Za-z\u4e00-\u9fffØΦRaRz0-9_]+)\s*(?P<operator><=|>=|=|<|>|±)\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>μm|um|mm|cm|m|HBW|HRC|N·m|%)?"},
    {"name": "cn_limit", "pattern": r"(?P<parameter>[\u4e00-\u9fffA-Za-z0-9_]+)\s*(?P<operator>不大于|不小于|大于等于|小于等于)\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>μm|um|mm|cm|m|HBW|HRC|N·m|%)?"},
]
