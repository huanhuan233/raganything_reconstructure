"""验证器基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseValidator(ABC):
    validator_name = "base"

    @abstractmethod
    def validate(self, data: Any) -> tuple[list[str], list[str]]:
        raise NotImplementedError
