# Runtime Boundary Violations

## 扫描规则

- 检查是否存在 `node.execute(other_node_output)` 或等价调用。
- 检查 `workflow_nodes/*_node.py` 内是否直接 `import` 其他 `*_node`。

## 扫描结果

- `node.execute(other_node_output)`：未发现。
- 节点文件直接导入其他节点文件：未发现。

## 说明

- `workflow_nodes/__init__.py` 与 `workflow_nodes/industrial/industrial_registry.py` 中的节点导入属于**节点注册层**，不属于运行期节点间直接通信。
- 当前运行时边界满足：节点之间不通过直接 import/调用传值，调度链路由 `WorkflowRunner + ExecutionContext` 统一承载。
