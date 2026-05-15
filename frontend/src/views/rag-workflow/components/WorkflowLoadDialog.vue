<script setup lang="ts">
import type { RagWorkflowSummary } from '@/types/ragWorkflow';

defineProps<{
  savedWorkflowList: RagWorkflowSummary[];
  loadListLoading: boolean;
}>();

const visible = defineModel<boolean>('visible', { default: false });

const emit = defineEmits<{
  refresh: [];
  load: [workflowId: string];
}>();
</script>

<template>
  <ElDialog v-model="visible" title="加载工作流" width="600px" destroy-on-close append-to-body>
    <div class="rag-wf-load-toolbar">
      <ElButton size="small" :loading="loadListLoading" @click="emit('refresh')">刷新列表</ElButton>
    </div>
    <ElTable v-loading="loadListLoading" :data="savedWorkflowList" stripe max-height="380" style="width: 100%">
      <ElTableColumn prop="workflow_id" label="workflow_id" min-width="130" show-overflow-tooltip />
      <ElTableColumn prop="name" label="名称" min-width="110" show-overflow-tooltip />
      <ElTableColumn prop="updated_at" label="更新时间" width="172" />
      <ElTableColumn label="操作" width="92" fixed="right">
        <template #default="{ row }">
          <ElButton size="small" type="primary" link @click="emit('load', row.workflow_id)">加载</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>
  </ElDialog>
</template>
