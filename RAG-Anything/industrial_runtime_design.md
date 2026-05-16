# Industrial Semantic Runtime（ISR）设计文档

本文档定义在 **不重起第四套顶层节点体系** 的前提下，已将 **Industrial Ontology Runtime** 能力并入现有 `workflow_nodes/industrial/` 与 `runtime_kernel/runtime_state/`，并形成 **最小可运行闭环**：`OntologyObject` → `ConstraintObject` → `RuntimeConstraintEngine.filter` → `SemanticExecutionPlan`。

---

## 1. 新 Industrial Runtime 架构

### 分层

| 层级 | 模块 | 职责 |
|------|------|------|
| **内核** | `runtime_kernel/runtime_state/*.py`、`runtime_kernel/execution_context/execution_context.py` | `OntologyState` / `ConstraintState` / `SemanticRuntimeState` / `IndustrialRuntimeMeta`、`RuntimeConstraintEngine`、`ExecutionContext.semantic_plan` |
| **工业语义域** | `workflow_nodes/industrial/{ontology,constraint,semantic,state,runtime}/` | ISR 专属节点与子域占位 |
| **模型** | `workflow_nodes/industrial/models/*.py` | 全 Pydantic：对象与 IR |
| **图持久化（扩展）** | `workflow_nodes/graph/*_persist_node.py` | 与 LightRAG `graph.persist` 并列的 **本体/语义/约束** Neo4j 写入（适配器可选） |
| **内容池** | `CONTENT_BUCKETS` 扩展 | `ontology_objects`、`constraints`、`industrial_candidates`、`industrial_filtered` |

### 原则

- **Runtime-first**：不引入 OWL/SPARQL/RDF；规则与合法性在 **运行时** 由 `RuntimeConstraintEngine` + 状态校验表达。
- **单 Runtime Kernel**：不新建第二套 `Runtime`；仅扩展 `ExecutionContext` 与 `runtime_state`。
- **子域归入 industrial**：ontology / constraint / semantic / state **不是**并行第四套编排树，而是 `industrial` 下的语义包。

---

## 2. 子域设计（workflow_nodes/industrial/）

| 子目录 | 节点 / 产物 | 说明 |
|--------|-------------|------|
| `ontology/` | `ontology.object.define` | 注册 `OntologyObject` → `content_pool["ontology_objects"]` + `context.ontology_state` |
| `constraint/` | `constraint.extract`、`constraint.runtime.filter` | 启发式抽取 `ConstraintObject`；可解释过滤 |
| `state/` | `state.transition.validate` | 黑名单边 + `required_order` + 轨迹校验 |
| `semantic/` | `semantic.runtime.plan` | 产出 `SemanticExecutionPlan` → `context.semantic_plan` |
| `runtime/` | （占位） | 复杂编排仍可走现有 `WorkflowRunner` |
| `models/` | Pydantic 全集 | ISR 数据结构单一来源 |
| `schemas/` | 占位 | OpenAPI / JSON Schema 扩展位 |

**与遗留工业节点**：`industrial.constraint_extract`（适配器-heavy）仍在；新标准路径为 **`constraint.extract`**（Pydantic + ContentPool ISR）。

---

## 3. RuntimeConstraint 设计

**文件**：`runtime_kernel/runtime_state/runtime_constraint.py`

**类**：`RuntimeConstraintEngine`

| 方法 | 语义 |
|------|------|
| `evaluate` | 单条规范化规则 dict × 单候选 `OntologyObject` dump |
| `filter` | 批量过滤 → `(valid_objects, rejected_objects, explanations)` |
| `explain` | 将 explanations 聚合为可读中文摘要 |
| `validate_transition` | `forbidden_edges` + `required_order` + `emitted_sequence` |

**与 SemTK**：`constraint_engine_bridge.py` 将 `ConstraintObject` lowering 为 engine 识别的 `kind`（如 `numeric_threshold`、`forbid_pair`、`must_not_rule`）。

---

## 4. SemanticExecutionPlan 设计

**文件**：`workflow_nodes/industrial/models/semantic_execution_plan.py`

| 字段 | 含义 |
|------|------|
| `ontology_object_ids` | 本轮参与语义推理的对象 id |
| `semantic_dependencies` | `SemanticDependency(subject, predicate, obj)` |
| `constraint_chain_refs` | 约束 id 列表 |
| `execution_order` | 建议工艺/动作线性序（脚手架：当前为 **Process** 按 id 字典序链式 `DEPENDS_ON`） |
| `runtime_legality_notes` | 由约束 NL / 关键字生成的 **待闭环** 说明 |
| `workflow_node_order` | 可选：若将来在 `execution_metadata["dag_topo_order"]` 注入 DAG 拓扑 |

**写入**：节点 `semantic.runtime.plan` 将 `plan.model_dump()` 赋给 `ExecutionContext.semantic_plan`，并更新 `SemanticRuntimeState`。

---

## 5. Neo4j Ontology Schema（Runtime-first）

**节点标签（示例）**：`(:Part)`, `(:Process)`, `(:Constraint)`, `(:State)`, `(:Operation)`

**关系类型（示例）**：`USES`、`CONSTRAINED_BY`、`REQUIRES`、`TRANSITIONS_TO`、`FORBIDS`、`DEPENDS_ON`

**落地方式**：适配器 **`ontology_graph_runtime`** 或回退 **`industrial_semantic_graph`**，约定方法（任选实现）：

- `persist_ontology_objects(bundle)` — `ontology.graph.persist`
- `persist_semantic_relations(bundle)` — `semantic.relation.persist`
- `persist_constraint_relations(bundle)` — `constraint.relation.persist`

无适配器时节点 **仍以 success 返回**，并带 `*_skipped*` 字段（符合「foundation」阶段的 dry-run）。

---

## 6. ExecutionContext 集成

**新增字段**（`runtime_kernel/execution_context/execution_context.py`）：

| 字段 | 类型 |
|------|------|
| `ontology_state` | `OntologyState` |
| `constraint_state` | `ConstraintState` |
| `semantic_runtime_state` | `SemanticRuntimeState` |
| `industrial_runtime_meta` | `IndustrialRuntimeState`（聚合元信息） |
| `runtime_constraints` | `list[Any]` |
| `semantic_plan` | `dict \| None`（`SemanticExecutionPlan.model_dump()`） |

---

## 7. Content Lifecycle 集成

`CONTENT_BUCKETS` 已扩展；`CONTENT_LIFECYCLE_REGISTRY` 增加：

```
chunks → constraint.extract → constraints
ontology.object.define → ontology_objects
ontology_objects + constraints → constraint.runtime.filter → industrial_filtered
→ semantic.runtime.plan → semantic_plan（ExecutionContext）
```

---

## 8. Runtime Event 集成

| 事件类型 | 触发点 |
|-----------|--------|
| `ontology_object_defined` | `ontology.object.define` |
| `constraint_materialized` | `constraint.extract` |
| `constraint_triggered` / `constraint_rejected` / `constraint_filter_completed` | `constraint.runtime.filter` |
| `semantic_plan_generated` | `semantic.runtime.plan` |
| `state_transition_failed` | `state.transition.validate` 未通过 |

（另：`ExecutionContext.trace_events` 与 `NodeOutput.trace_events` 链路不变。）

---

## 9. 最小实现代码（闭环）

| node_type | 文件 |
|-----------|------|
| `ontology.object.define` | `workflow_nodes/industrial/ontology/object_define_node.py` |
| `constraint.extract` | `workflow_nodes/industrial/constraint/extract_node.py` |
| `constraint.runtime.filter` | `workflow_nodes/industrial/constraint/runtime_filter_node.py` |
| `semantic.runtime.plan` | `workflow_nodes/industrial/semantic/runtime_plan_node.py` |
| （可选验证） | `workflow_nodes/industrial/state/transition_validate_node.py` |
| （可选落库） | `workflow_nodes/graph/ontology_graph_persist_node.py` 等 |

**注册**：`workflow_nodes/industrial/industrial_registry.py` + `workflow_nodes/__init__.py`。

### NodeMetadata 扩展

dataclass `NodeMetadata` 与 API 模型 `NodeMetadataModel` 已增加：`semantic_inputs` / `semantic_outputs` / `constraint_dependencies` / `runtime_state_dependencies` / `ontology_types`。

---

## 10. 禁止项确认

本阶段 **未修改**：前端、`scheduler`、`websocket`、`third_party`；**未引入** RDF/OWL/SPARQL。

---

## 后续可演进方向

1. **`execution_metadata["dag_topo_order"]`**：在不含 scheduler 侵入的前提下，可由运行器单行注入拓扑（当前 plan 默认为 false）。
2. **规则 DSL**：将 `ConstraintObject` → Rete/DMN 风格层。
3. **Neo4j 适配器**：在 `ontology_graph_runtime` 中实现 MERGE/Cypher。
4. **Hybrid retrieval**：ISR 输出的 `semantic_plan` 作为向量检索的 **结构化前缀过滤**。
