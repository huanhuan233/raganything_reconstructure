<script setup lang="ts">
const props = defineProps<{
  modelValue: string[];
}>();
const emit = defineEmits<{
  'update:modelValue': [v: string[]];
}>();

const options = [
  'title_hierarchy',
  'process_flow',
  'table_structure',
  'form_structure',
  'custom_schema'
];

function onUpdate(v: string[] | undefined) {
  emit('update:modelValue', Array.isArray(v) ? v : []);
}
</script>

<template>
  <ElSelect
    :model-value="props.modelValue"
    multiple
    filterable
    collapse-tags
    collapse-tags-tooltip
    placeholder="选择结构解析器"
    class="ik-full"
    @update:model-value="onUpdate"
  >
    <ElOption v-for="one in options" :key="one" :label="one" :value="one" />
  </ElSelect>
</template>

<style scoped>
.ik-full {
  width: 100%;
}
</style>
