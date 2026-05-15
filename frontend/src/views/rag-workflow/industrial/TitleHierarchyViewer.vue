<script setup lang="ts">
defineProps<{ data: Record<string, unknown> }>();
</script>

<template>
  <ElDescriptions :column="1" border size="small">
    <ElDescriptionsItem label="Section 数">
      {{ Array.isArray(data.sections) ? data.sections.length : 0 }}
    </ElDescriptionsItem>
  </ElDescriptions>
</template>
