"""表结构验证。"""

from __future__ import annotations

from typing import Any

from .base_validator import BaseValidator


class TableValidator(BaseValidator):
    validator_name = "table_validator"

    def validate(self, data: Any) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        tables = data if isinstance(data, list) else []
        for i, one in enumerate(tables, start=1):
            if not isinstance(one, dict):
                continue
            headers = one.get("column_headers")
            rows = one.get("rows")
            if not isinstance(headers, list) or not headers:
                errors.append(f"table_{i}:header_missing")
            if not isinstance(rows, list) or not rows:
                warnings.append(f"table_{i}:row_empty")
            merged = one.get("merged_cells")
            if not isinstance(merged, list):
                warnings.append(f"table_{i}:merged_cell_invalid")
        return errors, warnings
