<template>
  <div class="dify-workflow">
    <!-- 顶栏：工作流名、预览、发布等 -->
    <header class="workflow-header">
      <div class="header-left">
        <span class="workflow-name">{{ appName || '未命名应用' }}</span>
        <span class="workflow-type">{{ (appType || 'CHATFLOW').toUpperCase() }}</span>
      </div>
      <div class="header-center">
        <span class="auto-save">自动保存 {{ saveTime }}，{{ appStatus || '草稿' }}</span>
      </div>
      <div class="header-right">
        <el-button size="small" text>预览</el-button>
        <el-button size="small" text>功能</el-button>
        <el-button size="small" text @click="openAppInfoDialog">编辑信息</el-button>
        <el-button type="primary" size="small" :loading="publishing" @click="publish">发布</el-button>
      </div>
    </header>

    <!-- 从任务管理进入时的轻量提示：请检查节点后发布 -->
    <div v-if="fromTask" class="workflow-task-hint">
      该工作流由任务自动生成，请检查节点后发布
    </div>
    <!-- 兼容：非 fromTask 但 meta 标记为任务生成时仍显示提示 -->
    <div v-else-if="workflowMeta?.source === 'task-auto-generated'" class="workflow-task-hint">
      该工作流由任务自动生成，当前为Mock推荐流，可继续编辑
    </div>

    <div class="workflow-body">
      <!-- 左侧：编排 / API / 日志 / 监测 + 画布工具栏 -->
      <aside class="workflow-sidebar">
        <div class="sidebar-tabs">
          <div class="tab active">编排</div>
          <div class="tab">访问 API</div>
          <div class="tab">日志与标注</div>
          <div class="tab">监测</div>
        </div>
        <div class="canvas-toolbar">
          <button class="tool-btn" title="添加节点" @click="openNodePicker(null, $event)"><el-icon><Plus /></el-icon></button>
          <button class="tool-btn" title="拖动画布"><el-icon><Rank /></el-icon></button>
          <button class="tool-btn" title="重置视图"><el-icon><Refresh /></el-icon></button>
          <button class="tool-btn" title="对齐"><el-icon><Grid /></el-icon></button>
          <button class="tool-btn" title="节点库" @click="openNodePicker(null, $event)"><el-icon><Collection /></el-icon></button>
          <button class="tool-btn" title="更多"><el-icon><MoreFilled /></el-icon></button>
        </div>
      </aside>

      <!-- 中央：点阵画布 + 可拖拽节点 -->
      <main ref="canvasWrapRef" class="workflow-canvas-wrap" @click.self="() => { selectedNodeId = null; nodePickerVisible = false }">
        <div
          class="canvas-dotted"
          ref="canvasRef"
          :style="{ transform: `scale(${zoom})` }"
        >
          <div class="hint-text" v-if="nodes.length === 0">拖动节点到画布，或点击左侧 + 添加节点</div>
          <template v-for="(node, i) in nodes" :key="node.id">
            <!-- 连线：当前节点到下一节点（基于坐标） -->
            <svg v-if="i < nodes.length - 1" class="edge-svg">
              <path :d="edgePathByPos(nodes[i], nodes[i + 1])" fill="none" stroke="#c0c4cc" stroke-width="2" />
            </svg>
            <div
              class="canvas-node"
              :class="{ active: selectedNodeId === node.id }"
              :style="nodePosition(node)"
              @mousedown="startDrag(node.id, $event)"
              @click.stop="selectNode(node.id)"
              @dblclick.stop="handleNodeDblClick(node)"
            >
              <button class="node-handle left" type="button" title="连接" />
              <div class="node-icon">
                <el-icon v-if="node.nodeType === 'start'"><Right /></el-icon>
                <el-icon v-else-if="node.nodeType === 'end'"><CircleCheck /></el-icon>
                <el-icon v-else-if="node.nodeType === 'subAgent'"><Collection /></el-icon>
                <el-icon v-else-if="node.nodeType === 'app'"><Document /></el-icon>
                <el-icon v-else><Cpu /></el-icon>
              </div>
              <div class="node-title">{{ node.label }}</div>
              <div class="node-meta">{{ nodeMeta(node) }}</div>
              <button
                class="node-handle right add"
                type="button"
                title="添加下一个节点"
                @click.stop="openNodePicker(node.id, $event)"
              >
                +
              </button>
              <button
                class="node-delete-btn"
                type="button"
                title="删除"
                @click.stop="removeNode(node.id)"
              >
                <el-icon><Close /></el-icon>
              </button>
            </div>
          </template>
        </div>

        <!-- 节点库（Dify 风格浮层） -->
        <div
          v-if="nodePickerVisible"
          class="node-picker"
          :style="{ left: `${nodePickerPos.x}px`, top: `${nodePickerPos.y}px` }"
          @click.stop
        >
          <div class="node-picker-tabs">
            <button class="np-tab" :class="{ active: nodePickerTab === 'node' }" @click="nodePickerTab = 'node'">节点</button>
            <button class="np-tab" :class="{ active: nodePickerTab === 'tool' }" @click="nodePickerTab = 'tool'">工具</button>
            <button class="np-tab" :class="{ active: nodePickerTab === 'app' }" @click="nodePickerTab = 'app'">APP</button>
            <button class="np-tab" :class="{ active: nodePickerTab === 'subAgent' }" @click="nodePickerTab = 'subAgent'">子智能体</button>
            <button class="np-close" title="关闭" @click="nodePickerVisible = false">×</button>
          </div>
          <div class="node-picker-search">
            <el-input v-model="nodePickerSearch" size="small" placeholder="搜索节点" clearable />
          </div>
          <el-scrollbar class="node-picker-list">
            <template v-for="g in filteredPickerGroups" :key="g.title">
              <div class="np-group-title">{{ g.title }}</div>
              <div
                v-for="item in g.items"
                :key="item.key"
                class="np-item"
                @click="pickNode(item)"
              >
                <div class="np-icon">
                  <span class="np-icon-badge" :class="item.kind">{{ item.badge }}</span>
                </div>
                <div class="np-text">
                  <div class="np-name">{{ item.label }}</div>
                  <div v-if="item.desc" class="np-desc">{{ item.desc }}</div>
                </div>
              </div>
            </template>
          </el-scrollbar>
        </div>
      </main>

      <!-- 右侧：节点/Agent 配置 -->
      <aside class="workflow-config">
        <div class="config-header">
          <span class="config-title">{{ selectedNode ? selectedNode.label : 'Agent' }}</span>
        </div>
        <el-tabs v-model="configTab" class="config-tabs">
          <el-tab-pane label="设置" name="settings">
            <template v-if="selectedNode">
              <!-- 条件分支：Dify 风格 -->
              <template v-if="selectedNode.nodeType === 'branch'">
                <div class="config-block">
                  <div class="block-label">条件分支</div>
                  <p class="block-desc">为 IF / ELSE 配置规则，规则来自「规则配置」已保存列表。</p>
                </div>

                <div class="branch-panel">
                  <div class="branch-section">
                    <div class="branch-title">IF</div>
                    <el-button size="small" type="primary" text @click="openRulePicker('if')">+ 添加条件</el-button>
                    <div v-if="selectedNode.branch?.ifRules?.length" class="branch-rules">
                      <div v-for="r in selectedNode.branch.ifRules" :key="r.ruleId" class="branch-rule-item">
                        <span class="rule-name">{{ r.ruleName }}</span>
                        <el-button link type="danger" size="small" @click="removeBranchRule('if', r.ruleId)">移除</el-button>
                      </div>
                    </div>
                    <el-empty v-else description="未添加条件" :image-size="60" />
                  </div>

                  <div class="branch-divider" />

                  <div class="branch-section">
                    <div class="branch-title">ELSE</div>
                    <p class="block-desc">当 IF 条件不满足时执行的逻辑。</p>
                  </div>
                </div>

                <div class="config-block">
                  <div class="block-label">下一步</div>
                  <p class="block-desc">为不同分支选择下一个节点（前端占位）。</p>
                  <div class="branch-next">
                    <div class="bn-row">
                      <span class="bn-label">IF</span>
                      <el-button size="small" text type="primary" @click="openNodePicker(selectedNode.id, $event)">+ 选择下一个节点</el-button>
                    </div>
                    <div class="bn-row">
                      <span class="bn-label">ELSE</span>
                      <el-button size="small" text type="primary" @click="openNodePicker(selectedNode.id, $event)">+ 选择下一个节点</el-button>
                    </div>
                  </div>
                </div>
              </template>

              <!-- APP 节点：业务软件节点配置 -->
              <template v-else-if="selectedNode.nodeType === 'app'">
                <div class="config-block">
                  <div class="block-label">APP</div>
                  <p class="block-desc">该节点封装了一个前端 APP 页面，可作为工作流中的一步。</p>
                  <div class="block-label" style="margin-top: 12px">页面路径</div>
                  <el-input :model-value="selectedNode.appPath || ''" size="small" readonly />
                  <div style="margin-top: 12px">
                    <el-button size="small" type="primary" @click="openAppPageNewTab(selectedNode.appPath)">打开页面</el-button>
                  </div>
                </div>
                <div v-if="selectedNode.desc" class="config-block">
                  <div class="block-label">说明</div>
                  <p class="block-desc">{{ selectedNode.desc }}</p>
                </div>
                <div v-if="selectedNode.inputs?.length" class="config-block">
                  <div class="block-label">输入</div>
                  <p class="block-desc">{{ selectedNode.inputs.join('、') }}</p>
                </div>
                <div v-if="selectedNode.outputs?.length" class="config-block">
                  <div class="block-label">输出</div>
                  <p class="block-desc">{{ selectedNode.outputs.join('、') }}</p>
                </div>
                <div v-if="selectedNode.configSchema?.length" class="config-block">
                  <div class="block-label">参数</div>
                  <div v-for="sch in selectedNode.configSchema" :key="sch.field" class="config-schema-row">
                    <template v-if="sch.type === 'select' && Array.isArray(sch.options)">
                      <el-select :model-value="(getNodeConfig(selectedNode, sch.field ?? '') as string)" size="small" placeholder="请选择" style="width: 100%" @update:model-value="(v: unknown) => setNodeConfig(selectedNode!.id, sch.field ?? '', v as string)">
                        <el-option v-for="opt in sch.options" :key="opt" :label="opt" :value="opt" />
                      </el-select>
                    </template>
                    <el-input v-else :model-value="(getNodeConfig(selectedNode, sch.field ?? '') as string)" size="small" :placeholder="sch.label" @update:model-value="(v: unknown) => setNodeConfig(selectedNode!.id, sch.field ?? '', v as string)" />
                  </div>
                </div>
                <div class="config-block">
                  <div class="block-label">模拟运行</div>
                  <p class="block-desc">状态：{{ selectedNode.mockRuntime?.status || 'idle' }}</p>
                  <p v-if="selectedNode.mockRuntime?.mockResult" class="mock-result">{{ selectedNode.mockRuntime.mockResult }}</p>
                  <el-button size="small" type="primary" :loading="mockRunningNodeId === selectedNode.id" style="margin-top: 8px" @click="selectedNode && runMockNode(selectedNode)">模拟运行</el-button>
                </div>
              </template>

              <!-- 子智能体节点：引用已发布智能体，可跳转二次编辑 -->
              <template v-else-if="selectedNode.nodeType === 'subAgent'">
                <div class="config-block">
                  <div class="block-label">子智能体</div>
                  <p class="block-desc">该节点引用已发布智能体，点击画布节点或按钮可进入其工作流进行二次修改与发布。</p>
                  <div class="block-label" style="margin-top: 12px">子智能体 ID</div>
                  <el-input :model-value="selectedNode.subAgentAppId || ''" size="small" readonly />
                  <div class="block-label" style="margin-top: 12px">类型</div>
                  <el-input :model-value="formatAppTypeLabel(selectedNode.subAgentAppType)" size="small" readonly />
                  <div style="margin-top: 12px">
                    <el-button size="small" type="primary" @click="openSubAgentEditor(selectedNode.subAgentAppId)">进入子智能体</el-button>
                  </div>
                </div>
              </template>

              <!-- 其它节点：Agent/LLM 等通用配置 -->
              <template v-else>
                <div v-if="selectedNode.desc" class="config-block">
                  <div class="block-label">说明</div>
                  <p class="block-desc">{{ selectedNode.desc }}</p>
                </div>
                <div v-if="selectedNode.inputs?.length" class="config-block">
                  <div class="block-label">输入</div>
                  <p class="block-desc">{{ selectedNode.inputs.join('、') }}</p>
                </div>
                <div v-if="selectedNode.outputs?.length" class="config-block">
                  <div class="block-label">输出</div>
                  <p class="block-desc">{{ selectedNode.outputs.join('、') }}</p>
                </div>
                <div class="config-block">
                  <div class="block-label">AGENT 策略 <el-icon class="help"><QuestionFilled /></el-icon></div>
                  <el-select v-model="selectedNode.modelId" placeholder="选择 Agent 策略 / 模型" style="width: 100%; margin-bottom: 12px" clearable>
                    <el-option v-for="m in modelOptions" :key="m.id" :label="m.name" :value="m.id" />
                  </el-select>
                  <p class="block-desc">请配置 Agent 策略。配置完成后，此节点将自动加载配置，影响多步工具推理机制。</p>
                </div>
                <div class="config-block">
                  <div class="block-label">节点名称</div>
                  <el-input v-model="selectedNode.label" placeholder="如：LLM、工艺推理" size="small" />
                </div>
                <div class="config-block">
                  <div class="block-label">关联知识库</div>
                  <el-select
                    v-model="selectedNode.knowledgeIds"
                    placeholder="可多选"
                    style="width: 100%"
                    multiple
                    collapse-tags
                    size="small"
                  >
                    <el-option v-for="k in knowledgeOptions" :key="k.id" :label="k.name" :value="k.id" />
                  </el-select>
                </div>
                <div v-if="selectedNode.configSchema?.length" class="config-block">
                  <div class="block-label">参数</div>
                  <div v-for="sch in selectedNode.configSchema" :key="sch.field" class="config-schema-row">
                    <template v-if="sch.type === 'select' && Array.isArray(sch.options)">
                      <el-select :model-value="(getNodeConfig(selectedNode, sch.field ?? '') as string)" size="small" placeholder="请选择" style="width: 100%" @update:model-value="(v: unknown) => setNodeConfig(selectedNode!.id, sch.field ?? '', v as string)">
                        <el-option v-for="opt in sch.options" :key="opt" :label="opt" :value="opt" />
                      </el-select>
                    </template>
                    <el-input v-else :model-value="(getNodeConfig(selectedNode, sch.field ?? '') as string)" size="small" :placeholder="sch.label" @update:model-value="(v: unknown) => setNodeConfig(selectedNode!.id, sch.field ?? '', v as string)" />
                  </div>
                </div>
                <div class="config-block">
                  <div class="block-label">模拟运行</div>
                  <p class="block-desc">状态：{{ selectedNode.mockRuntime?.status || 'idle' }}</p>
                  <p v-if="selectedNode.mockRuntime?.mockResult" class="mock-result">{{ selectedNode.mockRuntime.mockResult }}</p>
                  <el-button size="small" type="primary" :loading="mockRunningNodeId === selectedNode.id" style="margin-top: 8px" @click="selectedNode && runMockNode(selectedNode)">模拟运行</el-button>
                </div>
                <div class="config-block">
                  <div class="block-label">输出变量</div>
                  <el-input size="small" placeholder="输出变量名（可选）" disabled />
                </div>
                <div class="config-block">
                  <div class="block-label">下一步</div>
                  <p class="block-desc">添加此工作流程中的下一个节点</p>
                  <el-button size="small" text type="primary" @click="openNodePicker(selectedNode.id, $event)">+ 选择下一个节点</el-button>
                </div>
              </template>
            </template>
            <el-empty v-else description="点击画布中的节点进行配置" :image-size="72" />
          </el-tab-pane>
          <el-tab-pane label="上次运行" name="lastRun">
            <el-empty description="暂无运行记录" :image-size="72" />
          </el-tab-pane>
        </el-tabs>
      </aside>
    </div>

    <!-- 底部：撤销、重做、缩放 -->
    <footer class="workflow-footer">
      <div class="footer-left">
        <el-button size="small" text :icon="RefreshLeft">撤销</el-button>
        <el-button size="small" text :icon="RefreshRight">重做</el-button>
        <span class="footer-label">全局接口</span>
      </div>
      <div class="footer-zoom">
        <button class="zoom-btn" @click="zoom = Math.max(0.5, zoom - 0.1)">−</button>
        <span class="zoom-value">{{ Math.round(zoom * 100) }}%</span>
        <button class="zoom-btn" @click="zoom = Math.min(1.5, zoom + 0.1)">+</button>
      </div>
    </footer>
  </div>

  <!-- 规则选择弹窗（条件分支用） -->
  <el-dialog v-model="rulePickerVisible" title="选择规则" width="720px">
    <div class="rule-picker-toolbar">
      <el-input v-model="rulePickerKeyword" placeholder="搜索规则名称/内容" clearable />
      <el-button @click="fetchRules">刷新</el-button>
    </div>
    <el-table v-loading="rulePickerLoading" :data="filteredRuleList" stripe size="small" height="360">
      <el-table-column prop="name" label="规则名称" min-width="180" />
      <el-table-column prop="status" label="状态" width="90" />
      <el-table-column prop="updateTime" label="更新时间" width="160" />
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="selectRule(row)">选择</el-button>
        </template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="rulePickerVisible = false">关闭</el-button>
    </template>
  </el-dialog>

  <!-- 编辑应用信息 -->
  <el-dialog v-model="appInfoVisible" title="编辑应用信息" width="520px">
    <el-form :model="appInfoForm" label-width="90px">
      <el-form-item label="应用名称" required>
        <el-input v-model="appInfoForm.name" placeholder="应用名称" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="appInfoForm.desc" type="textarea" :rows="2" placeholder="可选" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="appInfoForm.type" style="width: 100%">
          <el-option label="子智能体" value="chatflow" />
          <el-option label="任务流" value="workflow" />
          <el-option label="Agent" value="agent" />
          <el-option label="聊天助手" value="chat" />
          <el-option label="文本生成" value="text" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="appInfoVisible = false">取消</el-button>
      <el-button type="primary" :loading="savingAppInfo" @click="saveAppInfo">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Plus, Rank, Refresh, Grid, Collection, MoreFilled, Right, Cpu, Close, QuestionFilled, RefreshLeft, RefreshRight, Document, CircleCheck } from '@element-plus/icons-vue'
import * as modelApi from '@/service/api/business/models'
import * as knowledgeApi from '@/service/api/business/knowledge'
import * as toolApi from '@/service/api/business/tools'
import * as ruleApi from '@/service/api/business/rules'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import * as appApi from '@/service/api/business/apps'
import * as integrationApi from '@/service/api/business/integration'

/** 节点扩展：与后端 TaskNodeRegistry / workflowJson 兼容，供配置面板与模拟运行使用 */
interface MockRuntime {
  status?: string
  lastRunTime?: string | null
  mockResult?: string
}
interface ConfigSchemaItem {
  field?: string
  label?: string
  type?: string
  options?: string[]
}

interface WorkflowNode {
  id: string
  label: string
  nodeType: string
  modelId: string
  modelName?: string
  knowledgeIds: string[]
  knowledgeNames?: string[]
  desc: string
  appPath?: string
  subAgentAppId?: string
  subAgentAppType?: string
  x: number
  y: number
  branch?: {
    ifRules: { ruleId: string; ruleName: string }[]
  }
  group?: string
  inputs?: string[]
  outputs?: string[]
  configSchema?: ConfigSchemaItem[]
  mockRuntime?: MockRuntime
  mockResultTemplate?: string
  config?: Record<string, unknown>
}

const canvasRef = ref<HTMLElement | null>(null)
const canvasWrapRef = ref<HTMLElement | null>(null)
// 仅用于模板 ref 绑定，避免 TS 未使用提示
void canvasRef
const saveTime = ref('未保存')
const configTab = ref('settings')
const zoom = ref(1)
const draggingId = ref<string | null>(null)
const dragOffset = ref({ x: 0, y: 0 })

const route = useRoute()
const router = useRouter()
const appId = computed(() => (route.query.appId ? String(route.query.appId) : ''))
const taskId = computed(() => (route.query.taskId ? String(route.query.taskId) : ''))
const fromTask = computed(() => route.query.fromTask === '1')
const appName = ref('')
const appType = ref('chatflow')
const appStatus = ref<'草稿' | '已发布' | string>('草稿')
const publishing = ref(false)

/** 工作流元信息（如任务自动生成时的 source / templateKey / taskType） */
const workflowMeta = ref<{ source?: string; templateKey?: string; taskType?: string } | null>(null)
/** 边列表，与 nodes 一起从 workflowJson 解析，为后续画线交互保留 */
const edges = ref<{ source: string; target: string }[]>([])

const appInfoVisible = ref(false)
const savingAppInfo = ref(false)
const appInfoForm = ref({ name: '', desc: '', type: 'chatflow' })

type PickerTab = 'node' | 'tool' | 'app' | 'subAgent'
interface PickerItem {
  key: string
  label: string
  kind: PickerTab
  group: string
  badge: string
  desc?: string
  payload?: { path?: string; appId?: string; appType?: string }
}

const defaultNodes: WorkflowNode[] = [
  { id: '1', label: '开始', nodeType: 'start', modelId: '1', modelName: 'GPT-4', knowledgeIds: [], desc: '', x: 80, y: 180 },
  { id: '2', label: 'LLM', nodeType: 'llm', modelId: '1', modelName: 'deepseek-coder', knowledgeIds: ['1'], desc: '', x: 280, y: 160 },
  { id: '3', label: '工艺推理', nodeType: 'agent', modelId: '4', modelName: 'Qwen-1.8B', knowledgeIds: ['1', '2'], desc: '', x: 480, y: 180 },
  { id: '4', label: '参数推荐', nodeType: 'agent', modelId: '1', modelName: 'GPT-4', knowledgeIds: ['2'], desc: '', x: 680, y: 180 },
]
const nodes = ref<WorkflowNode[]>([...defaultNodes])

const nodePickerVisible = ref(false)
const nodePickerTab = ref<PickerTab>('node')
const nodePickerSearch = ref('')
const nodePickerSourceId = ref<string | null>(null)
const nodePickerPos = ref({ x: 16, y: 16 })

const nodePickerItems = ref<PickerItem[]>([
  // 节点
  { key: 'start', label: '开始', kind: 'node', group: '基础', badge: 'S', desc: '工作流起始节点' },
  { key: 'end', label: '结束', kind: 'node', group: '基础', badge: 'E', desc: '工作流结束节点' },
  { key: 'llm', label: 'LLM', kind: 'node', group: '基础', badge: 'LL', desc: '大模型对话与推理节点' },
  { key: 'direct', label: '直接回复', kind: 'node', group: '基础', badge: 'R', desc: '不经推理直接输出' },
  { key: 'agent', label: 'Agent', kind: 'node', group: '基础', badge: 'A', desc: '支持工具调用的 Agent 节点' },
  { key: 'understand', label: '问题理解', kind: 'node', group: '问题理解', badge: 'Q' },
  { key: 'classify', label: '问题分类器', kind: 'node', group: '问题理解', badge: 'C' },
  { key: 'branch', label: '条件分支', kind: 'node', group: '逻辑', badge: '⎇' },
  { key: 'human', label: '人工介入', kind: 'node', group: '逻辑', badge: 'H' },
  { key: 'iterate', label: '迭代', kind: 'node', group: '逻辑', badge: '↻' },
  { key: 'loop', label: '循环', kind: 'node', group: '逻辑', badge: '∞' },
  { key: 'template', label: '模板转换', kind: 'node', group: '转换', badge: 'T' },
  { key: 'aggregate', label: '变量聚合器', kind: 'node', group: '转换', badge: 'Σ' },
])

const toolPickerItems = ref<PickerItem[]>([])

// APP：把左侧菜单的三级页面封装成节点（按二级菜单分组）
const appPickerItems = ref<PickerItem[]>([
  // 二级：可制造性分析与优化软件（/business/process-design/review/*）
  { key: 'app-structure', label: '结构合理性分析APP', kind: 'app', group: '可制造性分析与优化软件', badge: 'APP', desc: '/business/process-design/review/structure', payload: { path: '/business/process-design/review/structure' } },
  { key: 'app-feasibility', label: '工艺方案可行性评估和优化APP', kind: 'app', group: '可制造性分析与优化软件', badge: 'APP', desc: '/business/process-design/review/feasibility', payload: { path: '/business/process-design/review/feasibility' } },

  // 二级：特种工艺决策与指令生成软件（/business/process-design/capp/*）
  { key: 'app-special', label: '特种工艺决策与指令生成APP', kind: 'app', group: '特种工艺决策与指令生成软件', badge: 'APP', desc: '/business/process-design/capp/special', payload: { path: '/business/process-design/capp/special' } },
  { key: 'app-laying', label: '复材铺放工艺决策APP', kind: 'app', group: '特种工艺决策与指令生成软件', badge: 'APP', desc: '/business/process-design/capp/laying', payload: { path: '/business/process-design/capp/laying' } },
  { key: 'app-filament', label: '复材铺丝工艺编程APP', kind: 'app', group: '特种工艺决策与指令生成软件', badge: 'APP', desc: '/business/process-design/capp/filament', payload: { path: '/business/process-design/capp/filament' } },
  { key: 'app-conduit', label: '导管成形工艺仿真APP', kind: 'app', group: '特种工艺决策与指令生成软件', badge: 'APP', desc: '/business/process-design/capp/conduit', payload: { path: '/business/process-design/capp/conduit' } },
  { key: 'app-superplastic', label: '超塑成形工艺仿真APP', kind: 'app', group: '特种工艺决策与指令生成软件', badge: 'APP', desc: '/business/process-design/capp/superplastic', payload: { path: '/business/process-design/capp/superplastic' } },

  // 二级：复材成型工艺高精度仿真软件（/business/process-design/cae/*）
  { key: 'app-cae-process', label: '复材制造工艺过程仿真APP', kind: 'app', group: '复材成型工艺高精度仿真软件', badge: 'APP', desc: '/business/process-design/cae/process', payload: { path: '/business/process-design/cae/process' } },
  { key: 'app-cae-solver', label: '渗流求解器与多物理耦合器APP', kind: 'app', group: '复材成型工艺高精度仿真软件', badge: 'APP', desc: '/business/process-design/cae/solver', payload: { path: '/business/process-design/cae/solver' } },
])
const subAgentPickerItems = ref<PickerItem[]>([])

async function refreshToolPickerItems() {
  try {
    const res = await toolApi.listTools({ status: '已启用' })
    const list = res.data ?? []
    toolPickerItems.value = list.map(t => {
      const group = t.type === 'mcp' ? 'MCP' : t.type === 'api' ? 'API 工具' : '自定义'
      const badge = t.type === 'mcp' ? 'MCP' : t.type === 'api' ? 'API' : 'C'
      return {
        key: `tool-${t.id}`,
        label: t.name,
        kind: 'tool',
        group,
        badge,
        desc: t.desc || t.endpoint,
      }
    })
  } catch {
    toolPickerItems.value = []
  }
}

async function refreshSubAgentPickerItems() {
  try {
    const res = await appApi.listApps({ status: '已发布' })
    const list = (res.data ?? []).filter(a => a.id !== appId.value)
    subAgentPickerItems.value = list.map(a => ({
      key: `sub-agent-${a.id}`,
      label: a.name,
      kind: 'subAgent',
      group: '已发布智能体',
      badge: 'SA',
      desc: `${a.type || 'app'}${a.updateTime ? ` · ${a.updateTime}` : ''}`,
      payload: { appId: a.id, appType: a.type },
    }))
  } catch {
    subAgentPickerItems.value = []
  }
}

const modelOptions = ref<{ id: string; name: string }[]>([])
const knowledgeOptions = ref<{ id: string; name: string }[]>([])

/**
 * 将后端/模板中的节点格式统一为页面使用的 WorkflowNode。
 * 兼容：label/title、nodeType/type、position.{x,y}/x,y、group、appPath、inputs、outputs、configSchema、mockRuntime、config 等。
 */
function normalizeWorkflowNode(raw: Record<string, unknown>, index: number): WorkflowNode {
  const id = (raw.id != null ? String(raw.id) : undefined) || `node-${index}`
  const label = (raw.label ?? raw.title) != null ? String(raw.label ?? raw.title) : '未命名'
  const nodeType = (raw.nodeType ?? raw.type) != null ? String(raw.nodeType ?? raw.type) : 'agent'
  const pos = raw.position as { x?: number; y?: number } | undefined
  const x = pos?.x ?? (raw.x != null ? Number(raw.x) : undefined) ?? 80 + index * 200
  const y = pos?.y ?? (raw.y != null ? Number(raw.y) : undefined) ?? 160
  const config = (raw.config as Record<string, unknown>) || {}
  const node: WorkflowNode = {
    id,
    label,
    nodeType,
    modelId: (raw.modelId as string) ?? '',
    modelName: raw.modelName as string | undefined,
    knowledgeIds: Array.isArray(raw.knowledgeIds) ? raw.knowledgeIds.map(String) : [],
    knowledgeNames: Array.isArray(raw.knowledgeNames) ? raw.knowledgeNames.map(String) : undefined,
    desc: (raw.desc as string) ?? (raw.description as string) ?? '',
    appPath: (raw.appPath as string) ?? (config.appPath as string) ?? undefined,
    subAgentAppId: (raw.subAgentAppId as string) ?? (config.subAgentAppId as string) ?? undefined,
    subAgentAppType: (raw.subAgentAppType as string) ?? (config.subAgentAppType as string) ?? undefined,
    x,
    y,
    branch: raw.branch as WorkflowNode['branch'],
  }
  if (raw.group != null) node.group = String(raw.group)
  if (Array.isArray(raw.inputs)) node.inputs = raw.inputs.map(String)
  if (Array.isArray(raw.outputs)) node.outputs = raw.outputs.map(String)
  if (Array.isArray(raw.configSchema)) node.configSchema = raw.configSchema as ConfigSchemaItem[]
  if (raw.mockRuntime != null && typeof raw.mockRuntime === 'object') {
    const mr = raw.mockRuntime as Record<string, unknown>
    node.mockRuntime = {
      status: mr.status != null ? String(mr.status) : undefined,
      lastRunTime: mr.lastRunTime != null ? String(mr.lastRunTime) : null,
      mockResult: mr.mockResult != null ? String(mr.mockResult) : undefined,
    }
  } else {
    node.mockRuntime = { status: 'idle', lastRunTime: null, mockResult: '' }
  }
  if (raw.mockResultTemplate != null) node.mockResultTemplate = String(raw.mockResultTemplate)
  if (Object.keys(config).length > 0) node.config = config
  return node
}

async function loadAppAndWorkflow() {
  workflowMeta.value = null
  edges.value = []
  if (!appId.value) {
    appName.value = '未命名应用'
    appType.value = 'chatflow'
    appStatus.value = '草稿'
    nodes.value = [...defaultNodes]
    return
  }
  try {
    const res = await appApi.getApp(appId.value)
    const app = res.data
    appName.value = app.name
    appType.value = app.type || 'chatflow'
    appStatus.value = app.status || '草稿'
    const wf = app.workflowJson || ''
    if (wf) {
      try {
        const parsed = JSON.parse(wf) as Record<string, unknown>
        // 兼容 { meta, nodes, edges } 与 仅 { nodes } 或 直接 nodes 数组
        if (parsed && typeof parsed === 'object') {
          if (parsed.meta && typeof parsed.meta === 'object') {
            const m = parsed.meta as Record<string, unknown>
            workflowMeta.value = {
              source: m.source as string | undefined,
              templateKey: m.templateKey as string | undefined,
              taskType: m.taskType as string | undefined,
            }
          }
          if (Array.isArray(parsed.edges)) {
            edges.value = parsed.edges
              .filter((e: unknown) => e && typeof e === 'object' && 'source' in e && 'target' in e)
              .map((e: Record<string, unknown>) => ({ source: String(e.source), target: String(e.target) }))
          }
          const rawNodes = Array.isArray(parsed.nodes) ? parsed.nodes : null
          if (rawNodes && rawNodes.length > 0) {
            nodes.value = rawNodes.map((n: unknown, i: number) =>
              normalizeWorkflowNode((n && typeof n === 'object' ? n : {}) as Record<string, unknown>, i),
            )
          } else if (rawNodes && rawNodes.length === 0) {
            nodes.value = []
          }
        } else if (Array.isArray(parsed)) {
          const rawNodes = parsed as unknown[]
          if (rawNodes.length > 0) {
            nodes.value = rawNodes.map((n: unknown, i: number) =>
              normalizeWorkflowNode((n && typeof n === 'object' ? n : {}) as Record<string, unknown>, i),
            )
          }
        }
      } catch {
        // 解析失败时保留当前节点，不报错
      }
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载应用失败')
  }
}

function nowTimeHHmmss() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

let saveTimer: number | null = null
async function saveWorkflowNow() {
  if (!appId.value) return
  try {
    const payload: { meta?: typeof workflowMeta.value; nodes: WorkflowNode[]; edges?: { source: string; target: string }[] } = {
      nodes: nodes.value,
    }
    if (workflowMeta.value) payload.meta = workflowMeta.value
    if (edges.value.length > 0) payload.edges = edges.value
    const workflowJson = JSON.stringify(payload)
    await appApi.saveWorkflow(appId.value, { workflowJson })
    saveTime.value = nowTimeHHmmss()
  } catch {
    // ignore
  }
}

function scheduleSaveWorkflow() {
  if (!appId.value) return
  if (saveTimer) window.clearTimeout(saveTimer)
  saveTimer = window.setTimeout(() => {
    saveWorkflowNow()
  }, 600)
}

function openAppInfoDialog() {
  appInfoForm.value = { name: appName.value || '', desc: '', type: appType.value || 'chatflow' }
  appInfoVisible.value = true
}

async function saveAppInfo() {
  if (!appId.value) {
    ElMessage.warning('请先从工作台创建应用后再编辑信息')
    return
  }
  if (!appInfoForm.value.name.trim()) {
    ElMessage.warning('请填写应用名称')
    return
  }
  savingAppInfo.value = true
  try {
    const res = await appApi.updateApp(appId.value, {
      name: appInfoForm.value.name,
      desc: appInfoForm.value.desc,
      type: appInfoForm.value.type,
    })
    appName.value = res.data.name
    appType.value = res.data.type
    appInfoVisible.value = false
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    savingAppInfo.value = false
  }
}

async function publish() {
  if (!appId.value) {
    ElMessage.warning('请先创建应用后再发布')
    return
  }
  publishing.value = true
  try {
    await saveWorkflowNow()
    const res = await appApi.publishApp(appId.value)
    appStatus.value = res.data.status
    if (taskId.value) {
      try {
        await integrationApi.updateIntegrationTask(taskId.value, { status: '排队中' })
      } catch {
        // 任务状态更新失败不影响发布结果
      }
    }
    ElMessage.success('已发布')
    if (taskId.value || fromTask.value) {
      await router.replace({ path: '/business/process-design/task-manage' })
    } else {
      await router.replace({ path: '/business/agent-config/workbench' })
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '发布失败')
  } finally {
    publishing.value = false
  }
}

onMounted(async () => {
  try {
    const [modelRes, knowledgeRes] = await Promise.all([
      modelApi.listModels(),
      knowledgeApi.listKnowledge(),
    ])
    modelOptions.value = (modelRes.data ?? []).map(m => ({ id: m.id, name: m.name }))
    knowledgeOptions.value = (knowledgeRes.data ?? []).map(k => ({ id: k.id, name: k.name }))
  } catch {
    modelOptions.value = [
      { id: '1', name: 'GPT-4' },
      { id: '4', name: 'Qwen-1.8B-工艺助手' },
    ]
    knowledgeOptions.value = [
      { id: '1', name: '车削工艺规范' },
      { id: '2', name: '铣削参数库' },
    ]
  }
  await loadAppAndWorkflow()
})

watch(appId, () => {
  loadAppAndWorkflow()
})

watch([nodePickerVisible, nodePickerTab], ([visible, tab]) => {
  if (visible && tab === 'tool') refreshToolPickerItems()
  if (visible && tab === 'subAgent') refreshSubAgentPickerItems()
})

const selectedNodeId = ref<string | null>(nodes.value[0]?.id ?? null)
const selectedNode = computed(() => {
  if (!selectedNodeId.value) return null
  const n = nodes.value.find(x => x.id === selectedNodeId.value)
  if (n) {
    n.modelName = modelOptions.value.find(m => m.id === n.modelId)?.name
    n.knowledgeNames = n.knowledgeIds.map(id => knowledgeOptions.value.find(k => k.id === id)?.name).filter(Boolean) as string[]
  }
  return n ?? null
})

function nodePosition(node: WorkflowNode) {
  return { left: `${node.x}px`, top: `${node.y}px` }
}

function edgePathByPos(a: WorkflowNode, b: WorkflowNode) {
  const half = 80
  const x1 = a.x + half
  const y1 = a.y
  const x2 = b.x - half
  const y2 = b.y
  const cx = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}`
}

function selectNode(id: string) {
  selectedNodeId.value = id
}

function handleNodeDblClick(node: WorkflowNode) {
  if (node.nodeType === 'subAgent' && node.subAgentAppId) {
    openSubAgentEditor(node.subAgentAppId)
  }
}

function removeNode(id: string) {
  const idx = nodes.value.findIndex(n => n.id === id)
  if (idx < 0) return
  nodes.value.splice(idx, 1)
  if (selectedNodeId.value === id) selectedNodeId.value = null
  scheduleSaveWorkflow()
}

function openNodePicker(sourceId: string | null, e?: MouseEvent) {
  nodePickerSourceId.value = sourceId
  nodePickerTab.value = 'node'
  nodePickerSearch.value = ''

  const wrap = canvasWrapRef.value
  if (wrap) {
    const panelW = 320
    const panelH = 420
    const margin = 12
    const rect = wrap.getBoundingClientRect()

    // 转换为“滚动内容坐标系”，保证滚动时定位准确
    let x = wrap.scrollLeft + wrap.clientWidth - panelW - margin
    let y = wrap.scrollTop + margin
    if (e) {
      x = e.clientX - rect.left + wrap.scrollLeft
      y = e.clientY - rect.top + wrap.scrollTop
    }

    const minX = wrap.scrollLeft + margin
    const maxX = wrap.scrollLeft + wrap.clientWidth - panelW - margin
    const minY = wrap.scrollTop + margin
    const maxY = wrap.scrollTop + wrap.clientHeight - panelH - margin

    nodePickerPos.value = {
      x: Math.max(minX, Math.min(x, maxX)),
      y: Math.max(minY, Math.min(y, maxY)),
    }
  }

  nodePickerVisible.value = true
}

const filteredPickerGroups = computed(() => {
  const tab = nodePickerTab.value
  const kw = nodePickerSearch.value.trim().toLowerCase()
  let list: PickerItem[] = []
  if (tab === 'node') list = nodePickerItems.value
  if (tab === 'tool') list = toolPickerItems.value
  if (tab === 'app') list = appPickerItems.value
  if (tab === 'subAgent') list = subAgentPickerItems.value
  if (kw) list = list.filter(i => i.label.toLowerCase().includes(kw) || (i.desc && i.desc.toLowerCase().includes(kw)))
  const groups = new Map<string, PickerItem[]>()
  for (const it of list) {
    const key = it.group || '其他'
    groups.set(key, [...(groups.get(key) ?? []), it])
  }
  return Array.from(groups.entries()).map(([title, items]) => ({ title, items }))
})

function pickNode(item: PickerItem) {
  const insertAfterId = nodePickerSourceId.value ?? selectedNodeId.value
  const sourceIdx = insertAfterId ? nodes.value.findIndex(n => n.id === insertAfterId) : nodes.value.length - 1
  const afterIdx = sourceIdx >= 0 ? sourceIdx : nodes.value.length - 1
  const sourceNode = nodes.value[afterIdx]

  const id = String(Date.now())
  const baseX = sourceNode ? sourceNode.x : 80
  const baseY = sourceNode ? sourceNode.y : 180
  const newNode: WorkflowNode = {
    id,
    label: item.label,
    nodeType: item.kind === 'node' ? item.key : item.kind === 'tool' ? 'tool' : item.kind === 'app' ? 'app' : 'subAgent',
    modelId: '',
    knowledgeIds: [],
    desc: '',
    x: baseX + 200,
    y: baseY,
  }
  if (newNode.nodeType === 'app') {
    newNode.appPath = item.payload?.path || ''
  }
  if (newNode.nodeType === 'subAgent') {
    newNode.subAgentAppId = item.payload?.appId || ''
    newNode.subAgentAppType = item.payload?.appType || ''
    newNode.desc = '已发布子智能体'
  }
  if (newNode.nodeType === 'branch') {
    newNode.branch = { ifRules: [] }
  }

  nodes.value.splice(afterIdx + 1, 0, newNode)
  // 简单避让：把后续节点整体右移
  for (let i = afterIdx + 2; i < nodes.value.length; i++) {
    nodes.value[i].x += 200
  }

  selectedNodeId.value = id
  nodePickerVisible.value = false
  scheduleSaveWorkflow()
}

function nodeMeta(n: WorkflowNode) {
  if (n.nodeType === 'app') return n.appPath || n.group || 'APP'
  if (n.nodeType === 'subAgent') return formatAppTypeLabel(n.subAgentAppType)
  if (n.nodeType === 'start') return '起始'
  if (n.nodeType === 'end') return '结束'
  return n.modelName || '未配置'
}

function formatAppTypeLabel(type?: string) {
  const map: Record<string, string> = {
    workflow: '任务流',
    chatflow: '子智能体',
    agent: 'Agent',
    chat: '聊天助手',
    text: '文本生成',
  }
  if (!type) return '子智能体'
  return map[type] || type
}

function openSubAgentEditor(subAppId?: string) {
  if (!subAppId) return
  router.push(`/business/agent-config/workflow?appId=${subAppId}`)
}

const mockRunningNodeId = ref<string | null>(null)

function getNodeConfig(node: WorkflowNode, field: string): unknown {
  if (!node.config || typeof node.config !== 'object') return undefined
  return (node.config as Record<string, unknown>)[field]
}

function setNodeConfig(nodeId: string, field: string, value: unknown) {
  const node = nodes.value.find(n => n.id === nodeId)
  if (!node) return
  if (!node.config) node.config = {}
  ;(node.config as Record<string, unknown>)[field] = value
  scheduleSaveWorkflow()
}

function runMockNode(node: WorkflowNode) {
  if (!node.mockRuntime) node.mockRuntime = { status: 'idle', lastRunTime: null, mockResult: '' }
  node.mockRuntime.status = 'running'
  mockRunningNodeId.value = node.id
  const delay = 500 + Math.random() * 700
  setTimeout(() => {
    node.mockRuntime!.status = 'success'
    node.mockRuntime!.mockResult = node.mockResultTemplate || `节点【${node.label}】模拟运行完成，已输出示例结果。`
    node.mockRuntime!.lastRunTime = new Date().toLocaleString()
    mockRunningNodeId.value = null
    scheduleSaveWorkflow()
  }, delay)
}

function openAppPageNewTab(path?: string) {
  if (!path) return
  const href = router.resolve(path).href
  window.open(href, '_blank')
}

// 条件分支：规则选择
const rulePickerVisible = ref(false)
const rulePickerLoading = ref(false)
const rulePickerKeyword = ref('')
const rulePickerTarget = ref<'if'>('if')
const ruleList = ref<ruleApi.RuleItem[]>([])

async function fetchRules() {
  rulePickerLoading.value = true
  try {
    const res = await ruleApi.listRules()
    ruleList.value = res.data ?? []
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载规则失败')
  } finally {
    rulePickerLoading.value = false
  }
}

const filteredRuleList = computed(() => {
  const kw = rulePickerKeyword.value.trim().toLowerCase()
  if (!kw) return ruleList.value
  return ruleList.value.filter(r =>
    r.name.toLowerCase().includes(kw)
    || r.naturalLanguage.toLowerCase().includes(kw)
    || r.logicOutput.toLowerCase().includes(kw),
  )
})

function openRulePicker(target: 'if') {
  rulePickerTarget.value = target
  rulePickerKeyword.value = ''
  rulePickerVisible.value = true
  if (ruleList.value.length === 0) fetchRules()
}

function selectRule(rule: ruleApi.RuleItem) {
  const n = selectedNode.value
  if (!n || n.nodeType !== 'branch') return
  if (!n.branch) n.branch = { ifRules: [] }
  const list = n.branch.ifRules
  if (list.some(x => x.ruleId === rule.id)) {
    ElMessage.info('该规则已添加')
    return
  }
  list.push({ ruleId: rule.id, ruleName: rule.name })
  rulePickerVisible.value = false
  ElMessage.success('已添加条件')
  scheduleSaveWorkflow()
}

function removeBranchRule(_target: 'if', ruleId: string) {
  const n = selectedNode.value
  if (!n || n.nodeType !== 'branch' || !n.branch) return
  n.branch.ifRules = n.branch.ifRules.filter(x => x.ruleId !== ruleId)
  scheduleSaveWorkflow()
}

function startDrag(id: string, e: MouseEvent) {
  const node = nodes.value.find(n => n.id === id)
  if (!node) return
  draggingId.value = id
  const wrap = canvasWrapRef.value
  const getPoint = (ev: MouseEvent) => {
    if (!wrap) return { x: ev.clientX / zoom.value, y: ev.clientY / zoom.value }
    const rect = wrap.getBoundingClientRect()
    const x = (ev.clientX - rect.left + wrap.scrollLeft) / zoom.value
    const y = (ev.clientY - rect.top + wrap.scrollTop) / zoom.value
    return { x, y }
  }
  const p0 = getPoint(e)
  dragOffset.value = { x: p0.x - node.x, y: p0.y - node.y }
  const onMove = (ev: MouseEvent) => {
    if (draggingId.value !== id) return
    const p = getPoint(ev)
    node.x = Math.max(0, p.x - dragOffset.value.x)
    node.y = Math.max(0, p.y - dragOffset.value.y)
  }
  const onUp = () => {
    draggingId.value = null
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    scheduleSaveWorkflow()
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}
</script>

<style scoped>
.dify-workflow {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  height: 100%;
  background: #f9fafb;
}
.workflow-header {
  height: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.workflow-name {
  font-weight: 600;
  color: #111827;
}
.workflow-type {
  font-size: 12px;
  color: #6b7280;
  background: #f3f4f6;
  padding: 2px 8px;
  border-radius: 4px;
}
.header-center .auto-save {
  font-size: 12px;
  color: #6b7280;
}
.workflow-task-hint {
  flex-shrink: 0;
  padding: 8px 16px;
  font-size: 12px;
  color: #0d9488;
  background: #ccfbf1;
  border-bottom: 1px solid #99f6e4;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.workflow-body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.workflow-sidebar {
  width: 56px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
  gap: 8px;
}
.sidebar-tabs {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sidebar-tabs .tab {
  padding: 8px 12px;
  font-size: 12px;
  color: #6b7280;
  cursor: pointer;
  border-radius: 4px;
}
.sidebar-tabs .tab.active {
  background: #eff6ff;
  color: #2563eb;
  font-weight: 500;
}
.canvas-toolbar {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 12px;
}
.tool-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: #6b7280;
  border-radius: 6px;
  cursor: pointer;
}
.tool-btn:hover {
  background: #f3f4f6;
  color: #111827;
}
.workflow-canvas-wrap {
  flex: 1;
  overflow: auto;
  position: relative;
  background: #f3f4f6;
}
.canvas-dotted {
  position: relative;
  min-width: 100%;
  min-height: 100%;
  background-image: radial-gradient(circle, #d1d5db 1px, transparent 1px);
  background-size: 12px 12px;
  transform-origin: 0 0;
}
.hint-text {
  position: absolute;
  left: 50%;
  top: 40%;
  transform: translate(-50%, -50%);
  color: #9ca3af;
  font-size: 13px;
}
.edge-svg {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: visible;
}
.canvas-node {
  position: absolute;
  width: 160px;
  padding: 12px;
  background: #fff;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transform: translate(-50%, -50%);
  transition: border-color 0.2s, box-shadow 0.2s;
  user-select: none;
}
.canvas-node:hover,
.canvas-node.active {
  border-color: #2563eb;
  box-shadow: 0 2px 12px rgba(37, 99, 235, 0.2);
}
.node-handle {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid #9ca3af;
  top: 50%;
  transform: translateY(-50%);
  padding: 0;
  line-height: 1;
  font-size: 10px;
  color: #6b7280;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.node-handle.left {
  left: -5px;
}
.node-handle.right {
  right: -5px;
}
.node-handle.add {
  width: 18px;
  height: 18px;
  border-color: #2563eb;
  color: #2563eb;
  background: #fff;
}
.node-handle.add:hover {
  background: #eff6ff;
}
.node-delete-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  opacity: 0;
  transition: opacity 0.2s, color 0.2s, background 0.2s;
}
.canvas-node:hover .node-delete-btn,
.canvas-node.active .node-delete-btn {
  opacity: 1;
}
.node-delete-btn:hover {
  color: #ef4444;
  background: #fef2f2;
}
.node-icon {
  margin-bottom: 6px;
  color: #6b7280;
  font-size: 16px;
}
.node-title {
  font-weight: 600;
  color: #111827;
  margin-bottom: 2px;
}
.node-meta {
  font-size: 11px;
  color: #6b7280;
}
.workflow-config {
  width: 320px;
  flex-shrink: 0;
  flex: 0 0 320px;
  background: #fff;
  border-left: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* 节点库浮层（模仿 Dify 右侧节点列表） */
.node-picker {
  position: absolute;
  width: 320px;
  max-height: min(420px, calc(100vh - 120px));
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
  z-index: 20;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.node-picker-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 10px 6px;
  border-bottom: 1px solid #eef2f7;
}
.np-tab {
  border: none;
  background: transparent;
  padding: 6px 10px;
  font-size: 13px;
  color: #6b7280;
  border-radius: 8px;
  cursor: pointer;
}
.np-tab.active {
  background: #eff6ff;
  color: #2563eb;
  font-weight: 600;
}
.np-close {
  margin-left: auto;
  border: none;
  background: transparent;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  cursor: pointer;
  color: #9ca3af;
  font-size: 18px;
  line-height: 1;
}
.np-close:hover {
  background: #f3f4f6;
  color: #374151;
}
.node-picker-search {
  padding: 10px;
  border-bottom: 1px solid #f3f4f6;
}
.node-picker-list {
  padding: 8px 10px 10px;
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.node-picker-list :deep(.el-scrollbar__wrap) {
  overflow-x: hidden;
}
.np-group-title {
  margin: 10px 0 6px;
  font-size: 12px;
  color: #9ca3af;
}
.np-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 10px;
  border-radius: 10px;
  cursor: pointer;
}
.np-item:hover {
  background: #f8fafc;
}
.np-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.np-icon-badge {
  font-size: 12px;
  color: #111827;
  font-weight: 700;
}
.np-icon-badge.tool {
  color: #2563eb;
}
.np-text {
  min-width: 0;
}
.np-name {
  font-size: 13px;
  color: #111827;
  font-weight: 600;
  line-height: 1.2;
}
.np-desc {
  margin-top: 2px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.2;
}

.branch-panel {
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 12px;
  background: #fafafa;
  margin-bottom: 14px;
}
.branch-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.branch-title {
  font-weight: 700;
  color: #111827;
}
.branch-divider {
  height: 1px;
  background: #eef2f7;
  margin: 12px 0;
}
.branch-rules {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.branch-rule-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 10px;
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 10px;
}
.rule-name {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.branch-next {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bn-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.bn-label {
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
}
.rule-picker-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.config-header {
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
}
.config-title {
  font-weight: 600;
  color: #111827;
}
.config-tabs {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
}
.config-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow: auto;
}
.config-tabs :deep(.el-tab-pane) {
  height: 100%;
}
.config-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}
.config-block {
  margin-bottom: 16px;
}
.block-label {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.block-label .help {
  color: #9ca3af;
  font-size: 14px;
}
.block-desc {
  font-size: 12px;
  color: #6b7280;
  margin: 0;
}
.mock-result {
  font-size: 12px;
  color: #059669;
  background: #ecfdf5;
  padding: 8px;
  border-radius: 4px;
  margin-top: 8px;
}
.config-schema-row {
  margin-bottom: 8px;
  line-height: 1.5;
}
.workflow-footer {
  height: 40px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: #fff;
  border-top: 1px solid #e5e7eb;
  font-size: 12px;
  color: #6b7280;
}
.footer-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.footer-label {
  margin-left: 8px;
}
.footer-zoom {
  display: flex;
  align-items: center;
  gap: 4px;
}
.zoom-btn {
  width: 24px;
  height: 24px;
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  color: #374151;
}
.zoom-btn:hover {
  background: #f3f4f6;
}
.zoom-value {
  min-width: 44px;
  text-align: center;
}
</style>
