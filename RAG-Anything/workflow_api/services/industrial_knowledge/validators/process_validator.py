"""流程验证。"""

from __future__ import annotations

from typing import Any

from .base_validator import BaseValidator


class ProcessValidator(BaseValidator):
    validator_name = "process_validator"

    def validate(self, data: Any) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        steps = data if isinstance(data, list) else []
        if not steps:
            errors.append("process:missing_steps")
            return errors, warnings
        ids = {str((x or {}).get("step_id") or "") for x in steps if isinstance(x, dict)}
        for one in steps:
            if not isinstance(one, dict):
                continue
            nxt = str(one.get("next_step") or "")
            if nxt and nxt not in ids:
                errors.append(f"invalid_next_step:{one.get('step_id')}->{nxt}")
        return errors, warnings
