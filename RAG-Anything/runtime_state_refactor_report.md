# Runtime State Refactor Report

## 1. 当前 Runtime 问题

- `WorkflowRunner` 之前直接拼接/传递 `NodeResult.data`，数据依赖隐式。
- 节点输出结构依赖自由 dict，缺少统一 `Node Output` 标准。
- 缺少独立的 `NodeState / GraphState / ExecutionState`，生命周期状态分散。
- 内容对象（chunks、entities、retrieval_results 等）没有统一生命周期池，难以追踪来源与去向。

## 2. 新 Runtime State 结构

新增目录：`runtime_kernel/runtime_state/`

- `execution_state.py`: 工作流全局执行状态（phase、started/finished、error、node_states）。
- `graph_state.py`: DAG 依赖状态、ready queue、barrier/parallel 预留结构。
- `node_state.py`: 节点生命周期状态（PENDING/RUNNING/SUCCESS/FAILED/SKIPPED）。
- `content_pool.py`: 统一内容池（parsed_document/chunks/embeddings/...）。
- `variable_pool.py`: 运行参数池（query/top_k/runtime_flags/...）。
- `runtime_registry.py`: 运行时状态注册表（扩展点）。
- `state_types.py`: 状态枚举与内容桶定义。

## 3. Context 生命周期

`ExecutionContext` 已升级为 Runtime 全局状态中心，包含：

- `variable_pool`
- `content_pool`
- `runtime_state`
- `graph_state`
- `node_outputs`
- `trace_events`
- `scheduler_state`
- `execution_metadata`

并保留兼容字段：

- `adapters`
- `shared_data`
- `logs`

执行时：

1. `WorkflowRunner` 初始化 `runtime_state`、`graph_state`。
2. 节点执行后统一写入 `context.set_node_output(...)`。
3. `result.data` 中可识别内容自动同步到 `content_pool`。
4. 事件通过 `context.emit_event(...)` 聚合到 `trace_events`。

## 4. Node 生命周期

`BaseNode` 增加统一执行链：

- `read_from_context`
- `run`（原有处理逻辑）
- `write_to_context`
- `emit_events`
- `execute`（统一编排入口）

`WorkflowRunner` 现在通过 `node.execute(...)` 驱动节点，负责：

- DAG 拓扑调度
- 节点状态更新（NodeState）
- context 注入与生命周期推进
- 基础事件分发

不再负责业务数据拼接策略本身。

## 5. Content 生命周期

已建立统一内容池路径：

`parsed_document -> chunks -> embeddings -> entities/relations -> graph_objects -> retrieval_results -> rerank_results -> generated_content`

说明：

- 节点输出写入 context 后，若命中上述 bucket key，会自动同步到 `content_pool`。
- 后续可将各节点逐步迁移为“仅读写 `content_pool` / `variable_pool`”。

## 6. 后续 TODO

- scheduler（ready queue 消费、并行分支执行、失败恢复策略）。
- parallel runtime（barrier、join、branch 合流策略）。
- event stream（统一事件总线，替代当前内存列表）。
- realtime trace（持久化 trace model 与查询 API 聚合）。
- websocket trace（实时推送层）。
- graph barrier（复杂 DAG 的同步屏障机制）。
