"""
将 ``backend_runtime`` 以 HTTP 形式暴露的最小 FastAPI 层（无库表、无鉴权、无真实模型）。

安装运行依赖::

    pip install fastapi "uvicorn[standard]"
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
