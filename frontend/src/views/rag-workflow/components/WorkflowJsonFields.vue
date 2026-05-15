<script setup lang="ts">
const workflowPreview = defineModel<string>('workflowPreview', { required: true });
const inputDataJson = defineModel<string>('inputDataJson', { required: true });
</script>

<template>
  <div class="rag-wf-json-fields">
    <div class="rag-wf-field">
      <div class="rag-wf-field-label">提交载荷预览（workflow_id / nodes / edges / entry / input）</div>
      <ElScrollbar max-height="160px">
        <pre class="rag-wf-json-pre">{{ workflowPreview }}</pre>
      </ElScrollbar>
    </div>
    <div class="rag-wf-field">
      <div class="rag-wf-field-label">入口 input_data（JSON）</div>
      <ElInput v-model="inputDataJson" type="textarea" :autosize="{ minRows: 5, maxRows: 12 }" class="rag-wf-input-mono" spellcheck="false" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.rag-wf-json-fields {
  min-height: 0;
}

.rag-wf-field-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
  line-height: 1.4;
}

.rag-wf-json-pre {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
}
</style>
