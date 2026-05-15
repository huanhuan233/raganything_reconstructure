<script setup lang="ts">
import type { RagRunHistoryDetail, RagRunHistorySummary } from '@/types/ragWorkflow';

withDefaults(
  defineProps<{
    runHistoryList: RagRunHistorySummary[];
    runHistoryLoading: boolean;
    runDetailLoading: boolean;
    runDetailFull: RagRunHistoryDetail | null;
    prettyJson: (v: unknown) => string;
    mode?: 'collapse' | 'dock';
  }>(),
  { mode: 'collapse' }
);

const filterRunsByCurrentWorkflow = defineModel<boolean>('filterRunsByCurrentWorkflow', { default: true });
const runDetailVisible = defineModel<boolean>('runDetailVisible', { default: false });

const emit = defineEmits<{
  'refresh-list': [];
  'open-detail': [row: RagRunHistorySummary];
  'delete-record': [runId: string];
}>();
</script>

<template>
  <template v-if="mode === 'collapse'">
    <ElCollapseItem title="运行记录" name="history">
      <div class="rag-wf-history-toolbar">
        <ElButton size="small" :loading="runHistoryLoading" @click="emit('refresh-list')">刷新列表</ElButton>
        <ElCheckbox v-model="filterRunsByCurrentWorkflow" size="small" @change="emit('refresh-list')">
          仅当前 workflow_id
        </ElCheckbox>
      </div>
      <ElTable
        v-loading="runHistoryLoading"
        :data="runHistoryList"
        stripe
        size="small"
        max-height="220"
        class="rag-wf-history-table"
        @row-dblclick="(row: RagRunHistorySummary) => emit('open-detail', row)"
      >
        <ElTableColumn prop="run_id" label="run_id" min-width="136" show-overflow-tooltip />
        <ElTableColumn prop="workflow_id" label="workflow_id" min-width="120" show-overflow-tooltip />
        <ElTableColumn label="success" width="88">
          <template #default="{ row }">
            <ElTag :type="row.success ? 'success' : 'danger'" size="small">{{ row.success ? 'ok' : 'fail' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="duration_ms" label="duration_ms" width="104" />
        <ElTableColumn prop="started_at" label="started_at" min-width="172" show-overflow-tooltip />
        <ElTableColumn prop="failed_node_id" label="failed_node" width="108" show-overflow-tooltip />
        <ElTableColumn label="操作" width="148" fixed="right">
          <template #default="{ row }">
            <ElButton size="small" type="primary" link @click="emit('open-detail', row)">详情</ElButton>
            <ElButton size="small" type="danger" link @click="emit('delete-record', row.run_id)">删除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
      <div class="rag-wf-history-hint">双击行查看详情。</div>
    </ElCollapseItem>
  </template>

  <div v-else class="rag-wf-history-dock-body">
    <div class="rag-wf-history-toolbar">
      <ElButton size="small" :loading="runHistoryLoading" @click="emit('refresh-list')">刷新列表</ElButton>
      <ElCheckbox v-model="filterRunsByCurrentWorkflow" size="small" @change="emit('refresh-list')">
        仅当前 workflow_id
      </ElCheckbox>
    </div>
    <ElTable
      v-loading="runHistoryLoading"
      :data="runHistoryList"
      stripe
      size="small"
      max-height="360"
      class="rag-wf-history-table"
      @row-dblclick="(row: RagRunHistorySummary) => emit('open-detail', row)"
    >
      <ElTableColumn prop="run_id" label="run_id" min-width="136" show-overflow-tooltip />
      <ElTableColumn prop="workflow_id" label="workflow_id" min-width="120" show-overflow-tooltip />
      <ElTableColumn label="success" width="88">
        <template #default="{ row }">
          <ElTag :type="row.success ? 'success' : 'danger'" size="small">{{ row.success ? 'ok' : 'fail' }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="duration_ms" label="duration_ms" width="104" />
      <ElTableColumn prop="started_at" label="started_at" min-width="172" show-overflow-tooltip />
      <ElTableColumn prop="failed_node_id" label="failed_node" width="108" show-overflow-tooltip />
      <ElTableColumn label="操作" width="148" fixed="right">
        <template #default="{ row }">
          <ElButton size="small" type="primary" link @click="emit('open-detail', row)">详情</ElButton>
          <ElButton size="small" type="danger" link @click="emit('delete-record', row.run_id)">删除</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>
    <div class="rag-wf-history-hint">双击行查看详情。</div>
  </div>

  <ElDialog v-model="runDetailVisible" title="运行详情" width="720px" destroy-on-close append-to-body>
    <ElSkeleton v-if="runDetailLoading" :rows="6" animated />
    <template v-else-if="runDetailFull">
      <div class="rag-wf-detail-meta">
        <span><strong>run_id</strong> {{ runDetailFull.run_id }}</span>
        <span><strong>workflow</strong> {{ runDetailFull.workflow_id }}</span>
        <ElTag :type="runDetailFull.success ? 'success' : 'danger'" size="small">
          {{ runDetailFull.success ? 'success' : 'failed' }}
        </ElTag>
      </div>
      <div v-if="runDetailFull.error" class="rag-wf-detail-err">
        <div class="rag-wf-field-label">error</div>
        <pre class="rag-wf-json-pre">{{ runDetailFull.error }}</pre>
      </div>
      <div class="rag-wf-detail-block">
        <div class="rag-wf-field-label">node_results</div>
        <ElScrollbar max-height="200px">
          <pre class="rag-wf-json-pre">{{ prettyJson(runDetailFull.node_results) }}</pre>
        </ElScrollbar>
      </div>
      <div class="rag-wf-detail-block">
        <div class="rag-wf-field-label">logs</div>
        <ElScrollbar max-height="160px">
          <pre class="rag-wf-json-pre">{{ prettyJson(runDetailFull.logs) }}</pre>
        </ElScrollbar>
      </div>
      <div class="rag-wf-detail-block">
        <div class="rag-wf-field-label">request_snapshot</div>
        <ElScrollbar max-height="200px">
          <pre class="rag-wf-json-pre">{{ prettyJson(runDetailFull.request_snapshot) }}</pre>
        </ElScrollbar>
      </div>
    </template>
    <template #footer>
      <ElButton v-if="runDetailFull" type="danger" plain @click="emit('delete-record', runDetailFull.run_id)">
        删除此记录
      </ElButton>
      <ElButton @click="runDetailVisible = false">关闭</ElButton>
    </template>
  </ElDialog>
</template>
