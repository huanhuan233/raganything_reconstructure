"""约束验证。"""

from __future__ import annotations

from typing import Any

from .base_validator import BaseValidator


class ConstraintValidator(BaseValidator):
    validator_name = "constraint_validator"

    def validate(self, data: Any) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        rows = data if isinstance(data, list) else []
        for i, one in enumerate(rows, start=1):
            if not isinstance(one, dict):
                continue
            if not one.get("operator"):
                errors.append(f"constraint_{i}:missing_operator")
            if one.get("value") is None:
                errors.append(f"constraint_{i}:invalid_value")
            if not str(one.get("unit") or "").strip():
                warnings.append(f"constraint_{i}:missing_unit")
        return errors, warnings
