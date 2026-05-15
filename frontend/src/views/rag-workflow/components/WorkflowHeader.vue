<script setup lang="ts">
import { reactive, watch } from 'vue';

const workflowId = defineModel<string>('workflowId', { required: true });
const workflowName = defineModel<string>('workflowName', { required: true });
const description = defineModel<string>('description', { required: true });

defineProps<{
  saveLoading: boolean;
  loadListLoading: boolean;
  runLoading: boolean;
  /** 第二行灰色状态，如草稿时间 */
  statusLine: string;
}>();

const emit = defineEmits<{
  save: [];
  'new-workflow': [];
  'open-load': [];
  'delete-workflow': [];
  'refresh-palette': [];
  'clear-canvas': [];
  run: [];
}>();

const metaDlg = reactive({
  open: false,
  workflowId: '',
  workflowName: '',
  description: ''
});

watch(
  () => metaDlg.open,
  v => {
    if (!v) return;
    metaDlg.workflowId = workflowId.value;
    metaDlg.workflowName = workflowName.value;
    metaDlg.description = description.value;
  }
);

function applyMetaDlg() {
  workflowId.value = metaDlg.workflowId.trim();
  workflowName.value = metaDlg.workflowName.trim();
  description.value = metaDlg.description.trim();
  metaDlg.open = false;
}

function onMoreCommand(cmd: string) {
  switch (cmd) {
    case 'refresh-palette':
      emit('refresh-palette');
      break;
    case 'delete-workflow':
      emit('delete-workflow');
      break;
    case 'clear-canvas':
      emit('clear-canvas');
      break;
    default:
      break;
  }
}
</script>

<template>
  <header class="rag-wf-header rag-wf-header--dify">
    <div class="rag-wf-header-left">
      <span class="rag-wf-title">多模态RAG工作流</span>
      <ElTooltip v-if="workflowId.trim()" :content="'workflow_id: ' + workflowId" placement="bottom">
        <span class="rag-wf-id-tag">{{ workflowId }}</span>
      </ElTooltip>
      <ElTag v-else type="info" size="small" effect="plain" class="rag-wf-id-placeholder">未设 workflow_id</ElTag>

      <div class="rag-wf-meta-line">
        <span class="rag-wf-status-line">{{ statusLine }}</span>
        <ElButton type="primary" link size="small" class="rag-wf-meta-edit-btn" @click="metaDlg.open = true">
          <span class="rag-wf-meta-edit-inner">编辑</span>
        </ElButton>
      </div>
    </div>

    <div class="rag-wf-header-right">
      <div class="rag-wf-actions">
        <ElButton size="small" type="info" plain @click="emit('new-workflow')">新建工作流</ElButton>
        <ElButton type="primary" size="small" :loading="runLoading" @click="emit('run')">测试运行</ElButton>
        <ElButton size="small" type="success" plain :loading="saveLoading" @click="emit('save')">保存</ElButton>
        <ElButton size="small" type="primary" plain :loading="loadListLoading" @click="emit('open-load')">加载</ElButton>

        <ElDropdown trigger="click" @command="onMoreCommand">
          <ElButton size="small" circle class="rag-wf-more-btn">
            <span class="rag-wf-more-dots">···</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <ElDropdownItem command="refresh-palette">
                <span>刷新节点类型</span>
              </ElDropdownItem>
              <ElDropdownItem divided command="delete-workflow">
                <span class="rag-wf-drop-danger">删除工作流文件</span>
              </ElDropdownItem>
              <ElDropdownItem command="clear-canvas">
                <span class="rag-wf-drop-danger">清空画布</span>
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </div>
    </div>
  </header>

  <ElDialog v-model="metaDlg.open" title="编辑工作流信息" width="440px" destroy-on-close append-to-body>
    <div class="rag-wf-meta-dlg-fields">
      <div class="rag-wf-field">
        <div class="rag-wf-field-label">workflow_id（保存文件名）</div>
        <ElInput v-model="metaDlg.workflowId" maxlength="160" placeholder="ui-dag" clearable />
      </div>
      <div class="rag-wf-field">
        <div class="rag-wf-field-label">工作流名称</div>
        <ElInput v-model="metaDlg.workflowName" maxlength="200" placeholder="名称" clearable />
      </div>
      <div class="rag-wf-field">
        <div class="rag-wf-field-label">描述</div>
        <ElInput v-model="metaDlg.description" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" placeholder="可选" />
      </div>
    </div>
    <template #footer>
      <ElButton @click="metaDlg.open = false">取消</ElButton>
      <ElButton type="primary" @click="applyMetaDlg">保存</ElButton>
    </template>
  </ElDialog>
</template>
