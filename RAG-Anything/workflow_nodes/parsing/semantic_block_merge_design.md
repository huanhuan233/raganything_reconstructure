# Semantic Block Merge 设计说明

## 1. 当前问题分析

### layout fragmentation

MinerU / `content.route` 产出大量碎片 layout block（paragraph、subtitle、caption、list item 等）。每条 block 在文档顺序上相邻，但语义上属于同一节或同一段落。

### chunk explosion

`chunk.split` 原实现对 **每条 routed block 独立** 调用 LightRAG `chunking_func`。当单块文本短于 `chunk_token_size` 时，仍产生 **1 block → 1 chunk**。典型现象：`492 routed blocks → 492 chunks`。

### entity explosion

`entity_relation.extract` 按 chunk 调用 LLM。碎片 chunk 导致：

- 每个小 paragraph 都触发抽取
- 实体 / 关系数量膨胀
- 图谱噪声与语义碎片化

**注意**：调大 `chunk_token_size` **不能**解决上述问题，因为瓶颈在「未跨 block 合并」，而非单块内 token 切分。

---

## 2. Semantic Merge Strategy

节点：`semantic.block.merge`（`workflow_nodes/parsing/semantic_block_merge_node.py`）  
引擎：`semantic_merge_engine.py`

### 输入

- `payload.routes`（来自 `content.route`）

### 合并规则（按全局路由顺序展平）

1. **同类型段落流**：`text`、`list`、`reference`、`caption`、`code`、`algorithm` 在相邻序号、同 pipeline、同页（可配置）且未超 token 上限时合并为 `paragraph_run` / `list_block`。
2. **标题绑定**：`title` / `subtitle` 开启 `section`，后续段落并入同一 semantic block，`section_title` 保留标题文本。
3. **页面连续性**：`require_same_page=true` 时仅合并 `page_idx` 相同的相邻块。
4. **Token 上限**：`semantic_merge_token_limit`（默认 2048，估算 `len(text)//2`），防止无限拼接。
5. **多模态边界**：`table` / `image` / `equation` 等 **原子块**，不与普通段落合并（`table_block` / `figure_block` / `equation_block`）。
6. **工业语义边界**：工序名、约束用语（应/不得/≤）、阶段/状态标题等触发 **切断**，单独 `industrial_segment`。

### 输出

- `semantic_blocks[]`：`SemanticMergedBlock.to_dict()`
- `semantic_merge_summary`：输入条数、输出块数、合并组数等

---

## 3. Industrial Boundary Protection

正则与启发式检测（见 `semantic_merge_engine._detect_industrial_boundary`）：

- 工序 / 步骤 / 阶段 / 状态标题
- 约束语句（应满足、不得、必须、≤、≥ 等）
- 常见工序名单行（粗加工、热处理、铆接等）

**不跨**上述边界合并，避免「粗加工 … 热处理」被拼成一块。

工业结构识别（`industrial.*`）仍使用 `content_list` / `routes` 原始 layout；合并在 **图谱 chunk 路径** 上生效，不改变 MinerU 解析结果。

---

## 4. SemanticMergedBlock 设计

路径：`workflow_nodes/parsing/models/semantic_merged_block.py`

| 字段 | 说明 |
|------|------|
| `semantic_block_id` | 稳定 ID（pipeline + source block_ids + 文本摘要 hash） |
| `source_blocks` | 溯源 layout dict 列表 |
| `merged_text` | 合并正文（段落间 `\n\n`） |
| `semantic_type` | `section` / `paragraph_run` / `list_block` / `table_block` / … |
| `page_range` | 涉及页码列表 |
| `token_estimate` | 粗估 token（Runtime 内估算，不依赖 LightRAG） |
| `section_title` | 节标题（若有） |
| `layout_types` | 源 layout type 列表 |
| `pipeline` / `route_pipeline` | 来源 pipeline |

---

## 5. chunk.split 集成方案

配置：`prefer_semantic_blocks`（默认 `true`）

优先级：

1. `payload.semantic_blocks` 或 `ContentPool.semantic_blocks`
2. fallback：`routes` / `content_list`（原逻辑）

每个 semantic block → 一条 `chunk.split` 输入项；`merged_text` 过长时仍由 **既有** `chunking_func` 按 `chunk_token_size` 二次切分。

日志：`chunk.split 使用 semantic_blocks（N 条）`

---

## 6. Content Lifecycle

```text
document.parse
  → content.filter
  → multimodal.process
  → content.route          # routed_blocks
  → semantic.block.merge   # semantic_blocks  → ContentPool
  → industrial.* (可选，仍读 routes/content_list)
  → chunk.split            # chunks（优先 semantic_blocks）
  → embedding.index
  → entity_relation.extract
  → …
```

`CONTENT_BUCKETS` 已增加 `semantic_blocks`。`CONTENT_LIFECYCLE_REGISTRY` 登记 producer=`semantic.block.merge`，consumer=`chunk.split`。

---

## 7. 后续 TODO

- hierarchical chunking：按 `title_hierarchy` 二次分层合并策略
- semantic section graph：semantic block 与 Section 节点显式对齐
- dynamic chunk strategy：按 pipeline / 文档类型自适应 `semantic_merge_token_limit`
- adaptive merge policy：基于 LLM 或规则的弱监督合并（当前为纯规则）
- chunk_refs：semantic block 多 source_block_ids 与工业实体对齐增强

---

## 8. 禁止事项（当前阶段）

- 不修改 `third_party/raganything`
- 不修改 MinerU
- 不修改 LightRAG `chunking_func` 内部实现

仅在 **Workflow Runtime Layer** 完成 layout-driven → semantic-driven chunking 升级。
