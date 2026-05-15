<script setup lang="ts">
import { computed, ref } from 'vue';

const props = defineProps<{ data: Record<string, unknown> }>();

const DEFAULT_VISIBLE = 10;
const expanded = ref(false);

const steps = computed(() => (Array.isArray(props.data.steps) ? props.data.steps : []));
const hasOverflow = computed(() => steps.value.length > DEFAULT_VISIBLE);
const visibleSteps = computed(() => (expanded.value ? steps.value : steps.value.slice(0, DEFAULT_VISIBLE)));
</script>

<template>
  <div class="pfv-wrap">
    <ElTimeline>
      <ElTimelineItem v-for="(one, idx) in visibleSteps" :key="idx">
        {{ String((one as Record<string, unknown>).name ?? '-') }}
      </ElTimelineItem>
    </ElTimeline>
    <div v-if="hasOverflow" class="pfv-actions">
      <ElButton text size="small" @click="expanded = !expanded">
        {{ expanded ? '收起流程' : `展开全部（${steps.length}）` }}
      </ElButton>
    </div>
  </div>
</template>

<style scoped>
.pfv-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pfv-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
