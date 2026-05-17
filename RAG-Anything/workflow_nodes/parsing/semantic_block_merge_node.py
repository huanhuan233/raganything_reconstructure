"""semantic.block.merge：content.route 之后、chunk.split 之前的跨块语义合并。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.runtime_state.content_access import ContentAccess

from .semantic_merge_engine import merge_routed_blocks


class SemanticBlockMergeNode(BaseNode):
    """将碎片 routed blocks 合并为 semantic_blocks，写入 ContentPool。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="语义块合并",
            category="content",
            description=(
                "在 content.route 与 chunk.split 之间，将短 layout block 按类型、标题、页序与工业边界"
                "合并为更大的 semantic block，减少 chunk / 实体抽取碎片。"
            ),
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="semantic_merge_token_limit",
                    label="语义合并 token 上限",
                    type="number",
                    required=False,
                    default=2048,
                    description="单个 semantic block 合并文本的估算 token 上限（非 chunk.split 切片上限）。",
                ),
                NodeConfigField(
                    name="require_same_page",
                    label="同页优先合并",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="protect_multimodal_boundaries",
                    label="保护多模态边界",
                    type="boolean",
                    required=False,
                    default=True,
                    description="table / image / equation 不与普通段落合并。",
                ),
                NodeConfigField(
                    name="protect_industrial_boundaries",
                    label="保护工业语义边界",
                    type="boolean",
                    required=False,
                    default=True,
                    description="工序、约束、状态等边界处切断合并。",
                ),
            ],
            input_schema={"type": "object", "description": "requires routes from content.route"},
            output_schema={
                "type": "object",
                "description": "semantic_blocks, semantic_merge_summary; 透传 routes",
            },
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        if not isinstance(input_data, dict):
            return NodeResult(success=False, error="semantic.block.merge expects dict input")

        payload = dict(input_data)
        routes = payload.get("routes")
        if not isinstance(routes, dict) or not routes:
            return NodeResult(
                success=False,
                error="semantic.block.merge requires routes from content.route",
                data=payload,
            )

        token_limit = max(256, int(self.config.get("semantic_merge_token_limit") or 2048))
        require_same_page = bool(self.config.get("require_same_page", True))
        protect_mm = bool(self.config.get("protect_multimodal_boundaries", True))
        protect_ind = bool(self.config.get("protect_industrial_boundaries", True))

        blocks, summary = merge_routed_blocks(
            payload,
            semantic_merge_token_limit=token_limit,
            require_same_page=require_same_page,
            protect_multimodal_boundaries=protect_mm,
            protect_industrial_boundaries=protect_ind,
        )

        semantic_dicts = [b.to_dict() for b in blocks]
        out = dict(payload)
        out["semantic_blocks"] = semantic_dicts
        out["semantic_merge_summary"] = summary

        ContentAccess.set_semantic_blocks(context, self.node_id, semantic_dicts)

        context.log(
            "[SemanticBlockMergeNode] "
            f"units={summary.get('input_routed_units')} "
            f"semantic_blocks={summary.get('output_semantic_blocks')} "
            f"merge_groups={summary.get('merge_groups')} "
            f"token_limit={token_limit}"
        )
        return NodeResult(
            success=True,
            data=out,
            metadata={"node": "semantic.block.merge"},
        )
