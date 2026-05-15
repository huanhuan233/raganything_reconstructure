<script setup lang="ts">
defineProps<{ validation: Record<string, unknown> }>();
</script>

<template>
  <ElRow :gutter="8">
    <ElCol :span="12">
      <ElCard>
        <template #header>Errors</template>
        <div v-for="(e, idx) in (Array.isArray(validation.errors) ? validation.errors : [])" :key="idx">{{ e }}</div>
      </ElCard>
    </ElCol>
    <ElCol :span="12">
      <ElCard>
        <template #header>Warnings</template>
        <div v-for="(w, idx) in (Array.isArray(validation.warnings) ? validation.warnings : [])" :key="idx">{{ w }}</div>
      </ElCard>
    </ElCol>
  </ElRow>
</template>
