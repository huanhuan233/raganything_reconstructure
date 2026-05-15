"""节点配置 schema 元数据：供 ``GET /api/nodes`` 与前端表单生成使用。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, List, Literal, Optional


@dataclass
class NodeConfigField:
    """单个 config 键的表单描述。"""

    name: str
    label: str
    type: str  # string | number | boolean | select | json | path
    required: bool = False
    default: Any = None
    options: Optional[List[Any]] = None
    placeholder: Optional[str] = None
    description: Optional[str] = None
    advanced: bool = False


@dataclass
class NodeMetadata:
    """注册节点在编排面板中的展示与配置说明。"""

    node_type: str
    display_name: str
    category: str
    description: str
    implementation_status: Literal["real", "partial", "placeholder"]
    is_placeholder: bool
    config_fields: List[NodeConfigField] = field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


def config_field_as_dict(f: NodeConfigField) -> Dict[str, Any]:
    return asdict(f)


def metadata_as_dict(m: NodeMetadata) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "node_type": m.node_type,
        "display_name": m.display_name,
        "category": m.category,
        "description": m.description,
        "implementation_status": m.implementation_status,
        "is_placeholder": m.is_placeholder,
        "config_fields": [config_field_as_dict(f) for f in m.config_fields],
    }
    if m.input_schema is not None:
        out["input_schema"] = m.input_schema
    if m.output_schema is not None:
        out["output_schema"] = m.output_schema
    return out


def with_node_type(meta: NodeMetadata, node_type: str) -> NodeMetadata:
    """使用注册表中的 ``node_type`` 覆盖类上声明的占位值。"""
    return replace(meta, node_type=node_type)
