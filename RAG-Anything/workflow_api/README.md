# backend_api — 最小 HTTP 网关

将 `backend_runtime` 工作流编排能力以 REST 暴露，便于前端拖拽画布提交执行。

## 依赖

本项目主包未锁定 Web 栈，请先安装：

```bash
pip install fastapi "uvicorn[standard]"
```

工作目录：**`RAG-Anything` 仓库根目录**（与 `backend_api`、`backend_runtime` 同级）。

## 启动

```bash
cd RAG-Anything
uvicorn backend_api.main:app --host 0.0.0.0 --port 18080 --reload
```

若未将项目根加入默认 `PYTHONPATH`，可先：

```bash
set PYTHONPATH=.
```

（Linux/macOS：`export PYTHONPATH=.`）

## 接口速览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/nodes` | 注册表节点类型列表 |
| POST | `/api/workflows/run` | 提交 DAG 执行 |

OpenAPI：`http://127.0.0.1:18080/docs`

## Mock 请求示例 JSON

见 `backend_api/examples/run_mock_workflow_request.json`。

## 架构说明

见 `backend_api/docs/backend_api_architecture.md`。
