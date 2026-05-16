"""ontology.object.define — 标准化工业本体对象写入 ContentPool（不落 Neo4j）。"""

from __future__ import annotations

import uuid
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult

from ..models.ontology_object import OntologyObject, OntologyObjectType
from ..utils import merge_named_bucket_models


class OntologyObjectDefineNode(BaseNode):
    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="ontology.object.define",
            display_name="工业本体对象定义",
            category="industrial_semantic_runtime",
            description=(
                "在 Runtime Kernel 注册标准化工业对象（Part/Process/Equipment 等），"
                "写入 content_pool['ontology_objects'] 并同步 ontology_state。"
            ),
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="ontology_type",
                    label="Ontology Type",
                    type="select",
                    required=True,
                    options=[{"label": t.value, "value": t.value} for t in OntologyObjectType],
                    default=OntologyObjectType.PART.value,
                ),
                NodeConfigField(
                    name="object_id",
                    label="Object Id",
                    type="string",
                    required=False,
                    default="",
                    description="留空自动生成",
                ),
                NodeConfigField(
                    name="label",
                    label="Label",
                    type="string",
                    required=False,
                    default="",
                ),
                NodeConfigField(name="attributes", label="Attributes", type="json", required=False, default={}),
                NodeConfigField(
                    name="source_refs",
                    label="Source Refs",
                    type="json",
                    required=False,
                    default=[],
                    description='["chunk:id", …] 溯源',
                ),
            ],
            semantic_inputs=["variable_pool.optional"],
            semantic_outputs=["ontology_objects", "ontology_state"],
            ontology_types=["Part", "Process", "Equipment"],
            runtime_state_dependencies=["ontology_state"],
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        oid = str(self.config.get("object_id") or "").strip() or uuid.uuid4().hex
        ot_raw = self.config.get("ontology_type") or OntologyObjectType.PART.value
        try:
            ot = OntologyObjectType(str(ot_raw))
        except ValueError:
            ot = OntologyObjectType.PART

        attrs = self.config.get("attributes") or {}
        if not isinstance(attrs, dict):
            attrs = {}

        refs = self.config.get("source_refs") or []
        if isinstance(refs, str):
            refs = [refs]
        if not isinstance(refs, list):
            refs = []

        payload_in = dict(input_data) if isinstance(input_data, dict) else {}

        obj = OntologyObject(
            object_id=oid,
            ontology_type=ot,
            label=str(self.config.get("label") or payload_in.get("label") or ot.value),
            attributes={str(k): v for k, v in attrs.items()},
            source_refs=[str(r) for r in refs],
        )
        dumped = obj.model_dump()
        merged = merge_named_bucket_models(context, "ontology_objects", [dumped], id_key="object_id")

        context.ontology_state.upsert_object(oid, dumped, node_id=self.node_id)

        payload = dict(payload_in)
        payload["ontology_objects"] = merged
        payload["ontology_object"] = dumped

        return NodeResult(
            success=True,
            data=payload,
            metadata={"ontology_defined": oid, "ontology_type": ot.value},
        )

    def build_node_output(self, result: NodeResult, context: ExecutionContext):
        oid = ""
        ot = ""
        if isinstance(result.data, dict):
            ob = result.data.get("ontology_object")
            if isinstance(ob, dict):
                oid = str(ob.get("object_id") or "")
                ot = str(ob.get("ontology_type") or "")
        out = super().build_node_output(result, context)
        out.trace_events.append(
            {
                "event_type": "ontology_object_defined",
                "object_id": oid,
                "ontology_type": ot,
                "node_id": self.node_id,
            },
        )
        return out
