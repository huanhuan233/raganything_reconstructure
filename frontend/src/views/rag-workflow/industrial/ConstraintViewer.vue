<script setup lang="ts">
defineProps<{ constraints: unknown[] }>();
</script>

<template>
  <div class="cv-wrap">
    <ElTable :data="constraints" size="small" height="100%" class="cv-table">
      <ElTableColumn prop="parameter" label="参数" width="140" />
      <ElTableColumn prop="operator" label="操作符" width="90" />
      <ElTableColumn prop="value" label="值" width="100" />
      <ElTableColumn prop="unit" label="单位" width="100" />
    </ElTable>
  </div>
</template>

<style scoped>
.cv-wrap {
  height: 100%;
  min-height: 0;
}

.cv-table {
  width: 100%;
}
</style>
