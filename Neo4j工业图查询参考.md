# Neo4j 工业图查询参考（ceshi07）→工作流e6dd07e874574746

本文档汇总工作流 `industrial.graph.persist` 落库后的常用 Cypher，便于在 **Neo4j Browser** 中按 `namespace` 隔离查看数据，并突出工序/执行相关语义。

## 数据模型速览

| 项目 | 说明 |
|------|------|
| 节点标签 | `IndustrialNode` + 子标签：`Document`、`Section`、`ProcessStep`、`Constraint`、`Table` 等 |
| 分区字段 | 节点属性 **`namespace`**（如 `ceshi07`，与工作流 persist 配置一致） |
| 节点主键 | `(namespace, id)`，约束名 `industrial_node_ns_id_unique` |
| 常见关系 | `CONTAINS`、`CONSTRAINT_OF`、`BEFORE`、`NEXT_STEP`、`REFERENCES` |
| 关系属性 | 边上通常也有 **`r.namespace = 'ceshi07'`** |

> **注意：** Neo4j 左侧 Database information 显示的是**整库**统计；点击标签会生成**不带** `namespace` 的默认查询。要只看 `ceshi07`，请在编辑器中始终加上 `namespace: 'ceshi07'`。

---

## 1. 按 namespace 查看整图

### 1.1 子图可视化（推荐）

```cypher
MATCH (n:IndustrialNode {namespace: 'ceshi07'})
OPTIONAL MATCH (n)-[r]-(m:IndustrialNode {namespace: 'ceshi07'})
RETURN n, r, m
```

节点过多时先限量（Browser 默认展示上限约 1000）：

```cypher
MATCH (n:IndustrialNode {namespace: 'ceshi07'})
WITH n LIMIT 200
OPTIONAL MATCH (n)-[r]-(m:IndustrialNode {namespace: 'ceshi07'})
RETURN n, r, m
```

### 1.2 仅有向边

```cypher
MATCH (a:IndustrialNode {namespace: 'ceshi07'})-[r]->(b:IndustrialNode {namespace: 'ceshi07'})
WHERE r.namespace = 'ceshi07'
RETURN a, r, b
LIMIT 1000
```

### 1.3 从文档根展开（星型，1～2 跳）

默认文档 id 多为 `document:industrial`（若工作流改过 `document_id` 请替换）：

```cypher
MATCH (d:IndustrialNode {namespace: 'ceshi07', id: 'document:industrial'})
MATCH p = (d)-[*1..2]-(n:IndustrialNode {namespace: 'ceshi07'})
RETURN p
LIMIT 500
```

### 1.4 统计本 namespace 规模

```cypher
MATCH (n:IndustrialNode {namespace: 'ceshi07'})
RETURN count(n) AS nodes;
```

```cypher
MATCH (:IndustrialNode {namespace: 'ceshi07'})-[r]->(:IndustrialNode {namespace: 'ceshi07'})
WHERE r.namespace = 'ceshi07'
RETURN count(r) AS rels;
```

### 1.5 查看库内有哪些 namespace

```cypher
MATCH (n:IndustrialNode)
RETURN n.namespace AS namespace, count(*) AS cnt
ORDER BY cnt DESC;
```

---

## 2. ProcessStep（工序节点）

### 2.1 全部 ProcessStep（ceshi07）

```cypher
MATCH (n:IndustrialNode:ProcessStep {namespace: 'ceshi07'})
RETURN n
```

### 2.2 表格列表

```cypher
MATCH (n:IndustrialNode:ProcessStep {namespace: 'ceshi07'})
RETURN n.id AS id, n.name AS name, n.block_id AS block_id, n.title AS title
ORDER BY n.id
```

### 2.3 计数

```cypher
MATCH (n:IndustrialNode:ProcessStep {namespace: 'ceshi07'})
RETURN count(n) AS process_step_count
```

### 2.4 ProcessStep 与邻接关系

```cypher
MATCH (n:IndustrialNode:ProcessStep {namespace: 'ceshi07'})
OPTIONAL MATCH (n)-[r]-(m:IndustrialNode {namespace: 'ceshi07'})
RETURN n, r, m
```

### 2.5 按子类型查（示例）

将 `ProcessStep` 换成 `Section`、`Constraint`、`Table` 等即可：

```cypher
MATCH (n:IndustrialNode:Constraint {namespace: 'ceshi07'})
OPTIONAL MATCH (n)-[r]-(m:IndustrialNode {namespace: 'ceshi07'})
RETURN n, r, m
LIMIT 300
```

---

## 3. 突出「执行 / 工艺」语义（Neo4j 内）

工业图在 Neo4j 中**最能体现执行序**的是工序链关系；ISR 层（`semantic_plan`、`ontology_objects`）若未配置 `ontology_graph_runtime` 适配器，可能**只在 run JSON** 中，见第 4 节。

### 3.1 工序先后顺序（BEFORE / NEXT_STEP）

```cypher
MATCH (a:IndustrialNode:ProcessStep {namespace: 'ceshi07'})-[r:BEFORE|NEXT_STEP]->(b:IndustrialNode:ProcessStep {namespace: 'ceshi07'})
RETURN a, r, b
```

表格：

```cypher
MATCH (a:IndustrialNode:ProcessStep {namespace: 'ceshi07'})-[r:BEFORE|NEXT_STEP]->(b:IndustrialNode:ProcessStep {namespace: 'ceshi07'})
RETURN a.id AS from_step, type(r) AS rel, b.id AS to_step, a.name AS from_name, b.name AS to_name
ORDER BY from_step
```

### 3.2 从「无前驱」工序向后展开路径

```cypher
MATCH (start:IndustrialNode:ProcessStep {namespace: 'ceshi07'})
WHERE NOT ()-[:NEXT_STEP|BEFORE]->(start)
MATCH p = (start)-[:NEXT_STEP|BEFORE*0..15]->(n:IndustrialNode:ProcessStep {namespace: 'ceshi07'})
RETURN p
LIMIT 50
```

### 3.3 文档包含的工序

```cypher
MATCH (d:IndustrialNode:Document {namespace: 'ceshi07'})-[:CONTAINS]->(p:IndustrialNode:ProcessStep {namespace: 'ceshi07'})
RETURN d, p
```

### 3.4 约束节点（规范侧）

```cypher
MATCH (c:IndustrialNode:Constraint {namespace: 'ceshi07'})-[:CONSTRAINT_OF]->(t)
WHERE t.namespace = 'ceshi07'
RETURN c, t
```

### 3.5 探测 ISR 本体是否已写入 Neo4j

**若下面两条均为 0，在 run `e6dd07e874574746` 场景下属于预期**（见下文「ISR 为何查不到」），不是 Cypher 写错。

```cypher
MATCH (n)
WHERE n.namespace = 'ceshi07'
  AND any(l IN labels(n) WHERE l IN ['Part', 'Process', 'Operation', 'Equipment', 'State'])
RETURN labels(n) AS lbl, count(*) AS c
```

```cypher
MATCH ()-[r:DEPENDS_ON]->()
WHERE r.namespace = 'ceshi07'
RETURN count(r) AS depends_on_edges
```

#### ISR 为何在 Neo4j 里查不到（run `e6dd07e874574746`）

| 现象 | 原因 |
|------|------|
| `Part` / `Process` 标签为 0 | `ontology.graph.persist` **skipped**：`no adapter ontology_graph_runtime / industrial_semantic_graph`，未写入 Neo4j |
| `DEPENDS_ON` 为 0 | `semantic.relation.persist` **skipped**：`no adapter` |
| 工业图里大量 `Constraint` | 来自 **`industrial.constraint_extract` → `industrial.graph_build`**，标签是 `IndustrialNode:Constraint`，**不是** ISR 的 `ConstraintObject` |
| 执行序在 Neo4j 里 | 用 **`ProcessStep` + `BEFORE` / `NEXT_STEP`**，不要用 `DEPENDS_ON` |

run JSON 中仍有 ISR 内存结果：`node_results.isr_semantic_plan.data.semantic_plan`（本次仅 1 个占位 `Part`，`semantic_dependencies` 为空）。持久化适配器实现前，请在 **工作流运行结果** 里看 ISR，不要只在 Neo4j 用 Part/Process 查询。

---

## 4. 执行语义 IR（工作流 run 结果，非 Cypher）

以下字段在节点输出 / run JSON 中，对应 **OntologyObject + SemanticExecutionPlan + 运行时过滤**：

| 字段 | 来源节点 | 含义 |
|------|----------|------|
| `ontology_objects` | `ontology.object.define` | 运行时本体对象（Part / Process 等） |
| `semantic_plan` | `semantic.runtime.plan` | `execution_order`、`semantic_dependencies`、`constraint_chain_refs` |
| `constraints` | `constraint.extract` | 可机读约束对象 |
| `industrial_filtered` | `constraint.runtime.filter` | `valid_objects` / `rejected_objects` |
| `constraint_explanations` | `constraint.runtime.filter` | 约束触发与解释 |

在运行结果中搜索 **`semantic_plan`**、**`execution_order`** 即可。

---

## 5. GRAPH_SUMMARY 指标说明（工业图 build）

| 指标 | 常见值 | 含义 |
|------|--------|------|
| `component_count = 1` | 整图一个连通分量 | 多数节点经 `Document` 的 `CONTAINS` / `REFERENCES` 连在一起 |
| `isolated_entity_count = 0` | 无孤立点 | 建图时每个节点至少有一条边 |

这不等于「语义上全是精细工艺网」，而是 **建图规则（Document 枢纽）** 导致的统计现象。

---

## 6. 与 Milvus 向量的关系

向量集合名在工作流里常与 namespace 同名（如 **`ceshi07`**），在 Milvus 中按 collection 过滤；与 Neo4j 的 `namespace` 属性对应同一「分区」命名，但是不同存储。

---

## 7. 参考配置位置

- 工作流 namespace：`RAG-Anything/workflow_storage/workflows/default-industrial-ontology-object-library.json` → `industrial.graph.persist.config.namespace`
- 写入实现：`RAG-Anything/workflow_nodes/industrial/industrial_neo4j_writer.py`

---

*文档生成自工作流实践与 run `e6dd07e874574746`（namespace: ceshi07）。替换 namespace 或 `document_id` 时请同步修改查询中的字面量。*
