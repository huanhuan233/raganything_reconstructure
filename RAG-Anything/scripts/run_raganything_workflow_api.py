#!/usr/bin/env python3
"""
通过命令行参数构造工作流 JSON，并 POST 到 ``POST /api/workflows/run``。

默认 DAG：``raganything.insert`` → ``rag.query``（``engine=raganything``）。

用法（在任意目录，需已启动 uvicorn）::

    cd RAG-Anything
    python scripts/run_raganything_workflow_api.py "D:/path/to/file.pdf"
    python scripts/run_raganything_workflow_api.py "D:/path/to/file.pdf" --parse-method ocr --query "第一章讲什么？"

说明：
- ``--parse-method`` 对应 MinerU 的 ``-m``，仅 ``auto`` / ``txt`` / ``ocr``；用哪种**解析器**由服务端 ``.env`` 的 ``PARSER`` 决定。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _build_payload(
    *,
    workflow_id: str,
    pdf: str,
    parse_method: str,
    query: str,
    query_mode: str,
    ins_id: str,
    q_id: str,
) -> dict:
    pdf_resolved = str(Path(pdf).expanduser().resolve())
    return {
        "workflow_id": workflow_id,
        "nodes": [
            {
                "id": ins_id,
                "type": "raganything.insert",
                "config": {
                    "source_path": pdf_resolved,
                    "parse_method": parse_method,
                },
            },
            {
                "id": q_id,
                "type": "rag.query",
                "config": {
                    "query": query,
                    "engine": "raganything",
                    "mode": query_mode,
                },
            },
        ],
        "edges": [[ins_id, q_id]],
        "entry_node_ids": [ins_id],
        "input_data": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="命令行提交 raganything.insert → rag.query 到 /api/workflows/run",
    )
    parser.add_argument(
        "pdf",
        help="本地 PDF 路径（写入 insert 节点的 source_path）",
    )
    parser.add_argument(
        "--parse-method",
        choices=("auto", "txt", "ocr"),
        default="auto",
        help="MinerU --method，默认 auto",
    )
    parser.add_argument(
        "--query",
        default="简述文档主要内容。",
        help="rag.query 的查询文本",
    )
    parser.add_argument(
        "--mode",
        default="hybrid",
        dest="query_mode",
        help="rag.query 的 mode（如 hybrid、mix、naive）",
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:18080",
        help="API 根地址，不含尾斜杠",
    )
    parser.add_argument(
        "--workflow-id",
        default="cli-raganything",
        dest="workflow_id",
        help="workflow_id 字段",
    )
    parser.add_argument(
        "--ins-id",
        default="ins",
        dest="ins_id",
        help="入库节点 id",
    )
    parser.add_argument(
        "--q-id",
        default="q",
        dest="q_id",
        help="查询节点 id",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印 JSON，不发送请求",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser()
    if not pdf_path.is_file():
        print(f"文件不存在: {pdf_path}", file=sys.stderr)
        return 2

    payload = _build_payload(
        workflow_id=args.workflow_id,
        pdf=str(pdf_path),
        parse_method=args.parse_method,
        query=args.query,
        query_mode=args.query_mode,
        ins_id=args.ins_id,
        q_id=args.q_id,
    )

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    url = args.url.rstrip("/") + "/api/workflows/run"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"请求失败: {e}", file=sys.stderr)
        return 1

    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        print(raw)
        return 0

    print(json.dumps(out, ensure_ascii=False, indent=2))
    if not out.get("success"):
        return 1
    qres = (out.get("node_results") or {}).get(args.q_id) or {}
    data = qres.get("data") or {}
    ans = data.get("answer")
    if ans:
        print("\n--- answer ---\n", ans, sep="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
