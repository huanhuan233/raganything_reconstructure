# Backend API 架构说明

## 1. 与 `backend_runtime` 的关系

| 层级 | 职责 |
|------|------|
| `backend_runtime` | DAG 拓扑、节点注册、`WorkflowRunner`、`ExecutionContext`、业务节点实现 |
| `backend_api` | **薄 HTTP 网关**：校验 JSON、调用 `runtime_service`、序列化返回值；**不写**编排算法 |

调用链：`前端 / curl` → FastAPI Router → `runtime_service.run_workflow` → `WorkflowRunner.run` → 各 `BaseNode.run`。

当前 `run_workflow` 内 **`ExecutionContext.adapters` 恒为空 `{}`**：仅便于占位节点链路（如 `multimodal.process`、`llm.generate`）冒烟；接入真实 LightRAG / RAGAnything 时需在本层增加适配器工厂与依赖注入策略（仍可不接数据库与用户系统）。

## 2. 未来前端如何调用

1. **拉节点面板**：`GET /api/nodes` → 返回 `nodes`（节点元数据 + `config_fields`）及兼容字段 `node_types`。
2. **保存画布到磁盘（可选）**：`POST /api/workflows/save`，请求体包含 `workflow_id`、`name`、`description`、`nodes`、`edges`、`entry_node_ids`、`input_data`；服务端写入 `backend_api/storage/workflows/{workflow_id}.json`（无数据库）。已存在同名 id 则覆盖并更新 `updated_at`，保留原有 `created_at`。
3. **列出 / 读取 / 删除已保存工作流**：`GET /api/workflows`（摘要列表）、`GET /api/workflows/{workflow_id}`（完整 JSON）、`DELETE /api/workflows/{workflow_id}`（204）。
4. **执行**：`POST /api/workflows/run`，请求体与运行契约一致（见 §4）；**响应 JSON 结构与历史版本一致**。**额外行为**：每次调用结束前会在 `backend_api/storage/runs/{run_id}.json` **同步**落盘一条运行记录（Runner 失败写入 `WorkflowRunResponse.error`；构建 DAG 等环节抛出的异常也会写入记录；落盘失败静默忽略，不改变 HTTP 返回值）。
5. **运行记录**：`GET /api/workflows/runs`（摘要列表，支持 query `workflow_id` 可选筛选）、`GET /api/workflows/runs/{run_id}`（完整快照）、`DELETE /api/workflows/runs/{run_id}`（204）。
6. **存活检测**：部署侧对 `GET /api/health` 做 LB 探针。

路由注册顺序保证 **`/workflows/runs`** 系列位于 **`/workflows/{workflow_id}`**（画布读写）之前，避免将字面量 `runs` 误解为 workflow_id。

Base URL 建议由网关统一（如 `/rag-backend`）；本服务默认为根路径挂载 `/api/...`。

## 3. 节点注册表与节点面板

- `GET /api/nodes` 返回 **`NodeRegistry.list_nodes()`** 序列化后的元数据列表（按 `node_type` 排序），并附带 **`node_types`** 字符串数组以兼容旧客户端。
- `backend_runtime.nodes` 包被 import 时会 **register_builtin_nodes()**；后端若注册了自定义节点，需与应用进程同生命周期执行注册后，面板才能看到新 `node_type`。

前端可按 `node_type` 映射到：

- 展示名称、图标；
- **config 表单 schema**（首版可由前端写死常量表或以 OpenAPI `/openapi.json` + 自建描述扩展）。

## 4. Workflow JSON 如何提交

路径：`POST /api/workflows/run`  
Content-Type：`application/json`

必填语义字段：

| 字段 | 含义 |
|------|------|
| `workflow_id` | 业务侧工作流 id（与运行追踪相关） |
| `nodes` | 每项含 `id`（节点实例 id）、`type`（注册表类型）、`config`（对象） |
| `edges` | `[["from_id","to_id"], ...]` |
| `entry_node_ids` | 可选；推荐显式填入入度为 0 的起点 |
| `input_data` | 传给入口节点的初始数据，通常为 `{}` |

OpenAPI 中带有 `WorkflowRunRequest` 的结构说明；亦可参考 **`backend_api/examples/run_mock_workflow_request.json`**。

**说明**：`workflow_name` **不在**请求体中；运行记录中的 `workflow_name` 在落盘时优先从已保存画布 `storage/workflows/{workflow_id}.json` 的 `name` 字段推断，若无则存空字符串。

## 5. 运行记录（runs）

| 路径 | 说明 |
|------|------|
| 落盘触发 | 每次 `POST /api/workflows/run` 返回前写入 `backend_api/storage/runs/{run_id}.json` |
| 文件内容 | `run_id`、`workflow_id`、`workflow_name`、`success`、`started_at`、`finished_at`、`duration_ms`、`error`、`failed_node_id`、`node_results`、`logs`、`request_snapshot` |
| `GET /api/workflows/runs` | 摘要列表；`?workflow_id=` 可选，仅列出该工作流的记录 |
| `GET /api/workflows/runs/{run_id}` | 读取单条完整 JSON |
| `DELETE /api/workflows/runs/{run_id}` | 删除记录文件（204） |
| `run_id` 校验 | 16 位小写十六进制（与 `WorkflowRunResponse.run_id` 一致） |

校验脚本：`python backend_api/run_store_http_verify.py`（临时目录 + TestClient）。

## 6. 工作流画布存储说明

| 路径 | 说明 |
|------|------|
| `POST /api/workflows/save` | 写入或覆盖 `{workflow_id}.json` |
| `GET /api/workflows` | 扫描存储目录，返回摘要（含 `workflow_id`、`name`、`updated_at` 等） |
| `workflow_id` 校验 | 1–128 位，仅限字母、数字、`.`、`_`、`-`，防止路径穿越 |

画布节点在保存时可附带 UI 字段（如 `position`、`label`）；**执行运行**时仍可只发送 `WorkflowRunRequest` 所需字段。

## 7. 当前限制

- **无数据库、无会话、无鉴权**，无 SSE/WebSocket；工作流与运行记录均为 **本地 JSON 文件**。
- **不接真实模型**；`rag.query`、`lightrag.insert` 等在 `adapters` 为空时会按节点逻辑报错或跳过。
- 除占位 DAG 外，可接通 **LightRAG / RAGAnything** 适配器与真实引擎；枚举节点、画布 CRUD、运行记录 API 独立于 Runner 内部算法。
- FastAPI / Uvicorn **未写入**本项目 `pyproject.toml` 主依赖集；使用前请：`pip install fastapi "uvicorn[standard]"`。

---

*迭代时请以代码与 `/openapi.json` 为准。*
