"""state.transition.validate — 工艺状态变迁合法性（黑名单 + 依赖序）。"""

from __future__ import annotations

import json
from typing import Any

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.runtime_state.runtime_constraint import RuntimeConstraintEngine

from ..models.state_transition import TransitionPolicy


class IndustrialStateTransitionValidateNode(BaseNode):
    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="state.transition.validate",
            display_name="工业状态变迁校验",
            category="industrial_semantic_runtime",
            description="Forbidden Transition / Required Ordering / Dependency Validation（轻量化）。",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="transition_policy_json",
                    label="Transition Policy JSON",
                    type="json",
                    required=False,
                    default={},
                    description='{"forbidden_edges":[["粗加工","精加工"],...],"required_order":[["粗加工","热处理"],...]}',
                ),
            ],
            semantic_inputs=["from_state", "to_state"],
            ontology_types=["State", "Operation"],
            runtime_state_dependencies=["semantic_plan", "constraint_state"],
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}

        from_st = str(payload.get("from_state") or payload.get("from") or "").strip()
        to_st = str(payload.get("to_state") or payload.get("to") or "").strip()
        if not from_st or not to_st:
            return NodeResult(
                success=False,
                error="state.transition.validate 需要 from_state / to_state",
                data=payload,
            )

        policy_cfg = self.config.get("transition_policy_json") or {}
        if isinstance(policy_cfg, str) and policy_cfg.strip():
            try:
                policy_cfg = json.loads(policy_cfg)
            except json.JSONDecodeError:
                policy_cfg = {}
        if not isinstance(policy_cfg, dict):
            policy_cfg = {}

        traj = payload.get("emitted_sequence") or payload.get("trajectory") or []
        if not isinstance(traj, list):
            traj = []

        pol = TransitionPolicy.model_validate(policy_cfg)
        forb = [(str(a).strip(), str(b).strip()) for a, b in pol.forbidden_edges]
        req_order = [(str(a).strip(), str(b).strip()) for a, b in pol.required_order]

        engine = RuntimeConstraintEngine()
        verdict = engine.validate_transition(
            from_state=from_st,
            to_state=to_st,
            forbidden_edges=forb,
            required_order=req_order if req_order else None,
            emitted_sequence=traj,
        )

        payload["transition_allowed"] = verdict.allowed
        payload["transition_verdict_zh"] = verdict.reason_zh
        payload["violated_rules"] = list(verdict.violated_rule_ids)

        if not verdict.allowed:
            context.emit_event(
                "state_transition_failed",
                {
                    "node_id": self.node_id,
                    "from_state": from_st,
                    "to_state": to_st,
                    "reason": verdict.reason_zh,
                },
            )

        return NodeResult(success=True, data=payload)

    def build_node_output(self, result: NodeResult, context: ExecutionContext):
        out = super().build_node_output(result, context)
        if isinstance(result.data, dict):
            ok = bool(result.data.get("transition_allowed"))
            out.trace_events.append(
                {
                    "event_type": "state_transition_validated",
                    "allowed": ok,
                    "node_id": self.node_id,
                }
            )
        return out
