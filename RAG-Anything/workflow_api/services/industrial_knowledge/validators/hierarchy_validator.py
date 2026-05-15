"""层级结构验证。"""

from __future__ import annotations

from typing import Any

from .base_validator import BaseValidator


class HierarchyValidator(BaseValidator):
    validator_name = "hierarchy_validator"

    def validate(self, data: Any) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        sections = []
        if isinstance(data, dict):
            sections = data.get("sections") if isinstance(data.get("sections"), list) else []
        seen: set[str] = set()
        for one in sections:
            sid = str((one or {}).get("section_id") or "")
            if sid in seen:
                errors.append(f"duplicate_section:{sid}")
            seen.add(sid)
            if "." in sid:
                parent = ".".join(sid.split(".")[:-1])
                if parent and parent not in seen:
                    warnings.append(f"missing_parent:{sid}->{parent}")
        return errors, warnings
