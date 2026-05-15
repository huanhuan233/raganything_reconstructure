"""工业图谱 schema 定义。"""

INDUSTRIAL_NODE_TYPES = [
    "Document",
    "Section",
    "ProcessStep",
    "Constraint",
    "Parameter",
    "Tool",
    "Material",
    "Inspection",
    "Figure",
    "Table",
]

INDUSTRIAL_REL_TYPES = [
    "contains",
    "before",
    "next_step",
    "requires",
    "uses",
    "references",
    "constraint_of",
]
