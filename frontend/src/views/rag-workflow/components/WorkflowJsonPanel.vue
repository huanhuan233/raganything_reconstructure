<script setup lang="ts">
import WorkflowJsonFields from './WorkflowJsonFields.vue';

const workflowPreview = defineModel<string>('workflowPreview', { required: true });
const inputDataJson = defineModel<string>('inputDataJson', { required: true });
</script>

<template>
  <ElCollapseItem title="Workflow JSON（实时）" name="json">
    <WorkflowJsonFields v-model:workflow-preview="workflowPreview" v-model:input-data-json="inputDataJson" />
  </ElCollapseItem>
</template>
