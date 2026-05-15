#!/usr/bin/env python3
"""
用 FastAPI TestClient 验证 ``/api/workflows/runs`` 与落盘：
1) ``run_store`` 写入后 list/get/delete
2) ``POST /api/workflows/run`` 后自动生成运行记录并可查询

在项目根 ``RAG-Anything`` 下执行::

    python backend_api/run_store_http_verify.py
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
from workflow_api import run_store  # noqa: E402


def main() -> int:
    fake_run_id = "a1b2c3d4e5f60718"
    record = {
        "run_id": fake_run_id,
        "workflow_id": "wf-verify",
        "workflow_name": "Verify",
        "success": False,
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:01Z",
        "duration_ms": 42,
        "error": None,
        "failed_node_id": "n1",
        "node_results": {},
        "logs": ["ping"],
        "request_snapshot": {"workflow_id": "wf-verify"},
    }

    minimal_run_body = {
        "workflow_id": "run-integration",
        "nodes": [
            {"id": "a", "type": "multimodal.process", "config": {}},
            {
                "id": "b",
                "type": "llm.generate",
                "config": {"query": "x", "mock_answer": "y"},
            },
        ],
        "edges": [["a", "b"]],
        "entry_node_ids": ["a"],
        "input_data": {},
    }

    with TemporaryDirectory() as td:
        runs_root = Path(td) / "runs"
        runs_root.mkdir(parents=True)
        with patch.object(run_store, "_STORAGE_ROOT", runs_root):
            run_store.save_run_record(record.copy())

            c = TestClient(app)
            lst = c.get("/api/workflows/runs").json()
            assert any(r["run_id"] == fake_run_id for r in lst["runs"])

            filt = c.get("/api/workflows/runs", params={"workflow_id": "wf-verify"}).json()
            assert len(filt["runs"]) >= 1
            assert all(r["workflow_id"] == "wf-verify" for r in filt["runs"])

            got = c.get(f"/api/workflows/runs/{fake_run_id}").json()
            assert got["run_id"] == fake_run_id
            assert got["failed_node_id"] == "n1"

            rm = c.delete(f"/api/workflows/runs/{fake_run_id}")
            assert rm.status_code == 204
            assert c.get(f"/api/workflows/runs/{fake_run_id}").status_code == 404

            rrun = c.post("/api/workflows/run", json=minimal_run_body)
            assert rrun.status_code == 200, rrun.text
            jr = rrun.json()
            rid = jr["run_id"]
            assert len(rid) == 16
            g2 = c.get(f"/api/workflows/runs/{rid}")
            assert g2.status_code == 200
            body = g2.json()
            assert body["workflow_id"] == "run-integration"
            assert "request_snapshot" in body
            assert c.delete(f"/api/workflows/runs/{rid}").status_code == 204

    print("run_store_http_verify: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
