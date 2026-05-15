"""API 请求/响应 Pydantic 模型。"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str = Field(description="健康状态，如 ok")
    service: str = Field(description="服务名")
    version: str = Field(description="语义化版本或服务版本号")


class NodeConfigFieldModel(BaseModel):
    """节点 config 单项的表单 schema。"""

    name: str
    label: str
    type: str
    required: bool = False
    default: Any = None
    options: Optional[List[Any]] = None
    placeholder: Optional[str] = None
    description: Optional[str] = None
    advanced: bool = False


class NodeMetadataModel(BaseModel):
    """节点库元数据（与 ``BaseNode.metadata()`` 序列化一致）。"""

    node_type: str
    display_name: str
    category: str
    description: str
    implementation_status: Literal["real", "partial", "placeholder"]
    is_placeholder: bool
    config_fields: List[NodeConfigFieldModel] = Field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class NodeInfoResponse(BaseModel):
    """可从注册表用于编排面板的节点目录。"""

    nodes: List[NodeMetadataModel] = Field(description="节点元数据列表（含 config_fields）")
    node_types: List[str] = Field(
        description="仅 node_type 字符串，升序；与 nodes[].node_type 一致，便于旧客户端兼容"
    )


class WorkflowNodeSpec(BaseModel):
    """工作流中单个节点的静态描述（与 WorkflowRunner 契约一致）。"""

    model_config = ConfigDict(populate_by_name=True)

    node_id: str = Field(alias="id", description="节点实例 id（DAG 顶点）")
    type: str = Field(description="节点类型，对应 NodeRegistry 注册的 key")
    config: Dict[str, Any] = Field(default_factory=dict, description="节点配置字典")


class WorkflowRunRequest(BaseModel):
    """提交执行的 DAG JSON。"""

    workflow_id: str = Field(description="工作流唯一标识（业务侧可追溯）")
    nodes: List[WorkflowNodeSpec] = Field(description="节点列表")
    edges: List[List[str]] = Field(
        description="边列表，每条为两个字符串 [from_node_id, to_node_id]"
    )
    entry_node_ids: List[str] = Field(
        default_factory=list,
        description="入口节点 id；若为空则由 Runner 依拓扑自动处理（全图入度 0）",
    )
    input_data: Any = Field(
        default=None,
        description="传入入口节点的初始 payload（通常 dict；多入口时可按约定键入）",
    )
    run_id: Optional[str] = Field(
        default=None,
        description="可选：客户端预生成 run_id（16位十六进制），用于实时追踪提前订阅。",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "workflow_id": "mock_demo",
                "nodes": [
                    {"id": "a", "type": "multimodal.process", "config": {}},
                    {
                        "id": "b",
                        "type": "llm.generate",
                        "config": {"query": "", "mock_answer": "占位回答"},
                    },
                ],
                "edges": [["a", "b"]],
                "entry_node_ids": ["a"],
                "input_data": {"seed": True},
            }
        }
    )


class SerializedNodeResult(BaseModel):
    """将 ``NodeResult`` 序列化为可 JSON 载荷。"""

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowSaveRequest(BaseModel):
    """保存画布到服务器的请求体（与运行契约同一拓扑，节点可含 ``position`` / ``label`` 等 UI 字段）。"""

    workflow_id: str = Field(description="工作流 id，兼作存储文件名")
    name: str = Field(default="", description="展示用名称")
    description: str = Field(default="", description="说明")
    nodes: List[Dict[str, Any]] = Field(description="节点列表，每项至少含 id、type、config")
    edges: List[List[str]] = Field(
        description="边列表，每条为两个字符串 [from_node_id, to_node_id]"
    )
    entry_node_ids: List[str] = Field(
        default_factory=list,
        description="入口节点 id；可与运行请求一致",
    )
    input_data: Any = Field(default=None, description="与 POST /workflows/run 的 input_data 相同语义")


class WorkflowSummary(BaseModel):
    """已存储工作流列表项。"""

    workflow_id: str
    name: str = ""
    description: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorkflowListResponse(BaseModel):
    """GET /workflows 列表。"""

    workflows: List[WorkflowSummary] = Field(default_factory=list)


class WorkflowStoredDocument(BaseModel):
    """磁盘上的完整工作流 JSON（保存响应与 GET 单条相同）。"""

    workflow_id: str
    name: str = ""
    description: str = ""
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[List[str]] = Field(default_factory=list)
    entry_node_ids: List[str] = Field(default_factory=list)
    input_data: Any = None
    created_at: str = ""
    updated_at: str = ""


class WorkflowTemplateSummary(BaseModel):
    """默认工作流模板列表项。"""

    template_id: str
    name: str
    description: str


class WorkflowTemplateListResponse(BaseModel):
    """默认工作流模板列表。"""

    templates: List[WorkflowTemplateSummary] = Field(default_factory=list)


class WorkflowRunResponse(BaseModel):
    """工作流异步执行结果的 HTTP 视图。"""

    success: bool
    workflow_id: str
    run_id: str
    error: Optional[str] = None
    failed_node_id: Optional[str] = None
    node_results: Dict[str, SerializedNodeResult] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list, description="ExecutionContext 中的顺序日志")


class WorkflowRunHistorySummary(BaseModel):
    """``GET /workflows/runs`` 列表项。"""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    workflow_id: str = ""
    workflow_name: str = ""
    success: bool = False
    duration_ms: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    failed_node_id: Optional[str] = None
    error: Optional[str] = None


class WorkflowRunHistoryListResponse(BaseModel):
    """运行记录列表。"""

    runs: List[WorkflowRunHistorySummary] = Field(default_factory=list)


class WorkflowRunHistoryDetail(BaseModel):
    """单次运行完整落盘 JSON（含 ``request_snapshot``）。"""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    workflow_id: str = ""
    workflow_name: str = ""
    success: bool = False
    duration_ms: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None
    failed_node_id: Optional[str] = None
    node_results: Dict[str, Any] = Field(default_factory=dict)
    logs: List[Any] = Field(default_factory=list)
    request_snapshot: Any = None


class ResumeCacheClearResponse(BaseModel):
    """断点缓存清理响应。"""

    cache_key_hash: str
    scope: Literal["all", "multimodal", "embedding"]
    deleted_count: int
    deleted_files: List[str] = Field(default_factory=list)
    missing_files: List[str] = Field(default_factory=list)


class RuntimeTraceEvent(BaseModel):
    run_id: str
    seq: int
    ts: str
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class RuntimeTraceNodeState(BaseModel):
    node_id: str
    node_name: str = ""
    node_type: str = ""
    status: Literal["pending", "running", "success", "error", "skipped"] = "pending"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    input_preview: Any = None
    output_preview: Any = None


class RuntimeTraceSnapshot(BaseModel):
    run_id: str
    workflow_id: str = ""
    workflow_name: str = ""
    running: bool = False
    phase: str = ""
    success: bool = False
    error: Optional[str] = None
    failed_node_id: Optional[str] = None
    current_node_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None
    node_states: List[RuntimeTraceNodeState] = Field(default_factory=list)
    timeline: List[Dict[str, Any]] = Field(default_factory=list)


class RuntimeTraceNodeDetail(BaseModel):
    run_id: str
    node_id: str
    node_name: str = ""
    node_type: str = ""
    status: str = "pending"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    input_preview: Any = None
    output_preview: Any = None
    input: Any = None
    output: Any = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)


def workflow_nodes_to_runner_dicts(nodes: List[WorkflowNodeSpec]) -> List[Dict[str, Any]]:
    """转为 ``WorkflowRunner`` 期望的 ``nodes`` dict 列表（键为 ``id`` / ``type`` / ``config``）。"""
    out: List[Dict[str, Any]] = []
    for n in nodes:
        out.append({"id": n.node_id, "type": n.type, "config": dict(n.config)})
    return out
