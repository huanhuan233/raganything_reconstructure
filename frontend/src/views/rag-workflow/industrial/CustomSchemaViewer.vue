<script setup lang="ts">
defineProps<{ data: Record<string, unknown> }>();
</script>

<template>
  <ElScrollbar height="100%">
    <pre class="csv-json">{{ JSON.stringify(data, null, 2) }}</pre>
  </ElScrollbar>
</template>

<style scoped>
.csv-json {
  margin: 0;
}
</style>
