#!/usr/bin/env python3
"""
用 FastAPI TestClient 验证 ``/api/workflows/save|GET|DELETE``（临时目录存储）。

在 ``RAG-Anything`` 根目录执行::

    python backend_api/workflow_store_http_verify.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from workflow_api.main import app  # noqa: E402
from workflow_api import workflow_store  # noqa: E402


def main() -> int:
    payload = {
        "workflow_id": "demo-store-1",
        "name": "Demo",
        "description": "hi",
        "nodes": [
            {
                "id": "a",
                "type": "llm.generate",
                "config": {},
                "position": {"x": 10, "y": 20},
                "label": "L",
            }
        ],
        "edges": [],
        "entry_node_ids": ["a"],
        "input_data": {"seed": True},
    }

    with TemporaryDirectory() as td:
        store_root = Path(td) / "workflows"
        store_root.mkdir(parents=True)

        with patch.object(workflow_store, "_STORAGE_ROOT", store_root):
            client = TestClient(app)

            r1 = client.post("/api/workflows/save", json=payload)
            assert r1.status_code == 200, r1.text
            doc1 = r1.json()
            assert doc1["workflow_id"] == "demo-store-1"
            assert doc1["name"] == "Demo"
            ca = doc1["created_at"]

            r2 = client.post(
                "/api/workflows/save",
                json={**payload, "name": "DemoRenamed"},
            )
            assert r2.status_code == 200, r2.text
            doc2 = r2.json()
            assert doc2["created_at"] == ca
            assert doc2["name"] == "DemoRenamed"

            lst = client.get("/api/workflows")
            assert lst.status_code == 200
            ids = [x["workflow_id"] for x in lst.json()["workflows"]]
            assert "demo-store-1" in ids

            got = client.get("/api/workflows/demo-store-1")
            assert got.status_code == 200
            body = got.json()
            assert body["nodes"][0]["position"] == {"x": 10, "y": 20}

            rm = client.delete("/api/workflows/demo-store-1")
            assert rm.status_code == 204

            assert client.get("/api/workflows/demo-store-1").status_code == 404

    print("workflow_store_http_verify: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
