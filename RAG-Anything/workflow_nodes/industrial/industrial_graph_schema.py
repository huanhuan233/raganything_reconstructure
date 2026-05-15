"""工业原生图谱 Schema 常量。"""

from __future__ import annotations

ALLOWED_NODE_LABELS: list[str] = [
    "Document",
    "Section",
    "ProcessStep",
    "Constraint",
    "Tool",
    "Material",
    "Inspection",
    "Table",
    "Figure",
]

ALLOWED_EDGE_TYPES: list[str] = [
    "CONTAINS",
    "NEXT_STEP",
    "BEFORE",
    "REQUIRES",
    "USES",
    "REFERENCES",
    "CONSTRAINT_OF",
]

