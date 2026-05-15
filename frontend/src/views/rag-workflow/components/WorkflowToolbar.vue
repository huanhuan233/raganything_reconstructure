<script setup lang="ts">
import { Icon } from '@iconify/vue';

defineProps<{
  interactionMode: 'pan' | 'select';
}>();

const emit = defineEmits<{
  'open-picker': [anchor: HTMLElement | null];
  'set-mode': [mode: 'pan' | 'select'];
  'fit-view': [];
  'reset-view': [];
  hotkeys: [];
}>();
</script>

<template>
  <div class="rag-wf-float-toolbar" @click.stop>
    <ElTooltip content="添加节点" placement="right">
      <button type="button" class="rag-wf-float-tool-btn" @click="(e: MouseEvent) => emit('open-picker', e.currentTarget as HTMLElement)">
        <Icon icon="mdi:plus" class="rag-wf-float-tool-ico" />
      </button>
    </ElTooltip>
    <ElTooltip content="选择 · 框选" placement="right">
      <button
        type="button"
        class="rag-wf-float-tool-btn"
        :class="{ 'is-active': interactionMode === 'select' }"
        @click="emit('set-mode', 'select')"
      >
        <Icon icon="mdi:cursor-pointer" class="rag-wf-float-tool-ico" />
      </button>
    </ElTooltip>
    <ElTooltip content="拖拽画布" placement="right">
      <button
        type="button"
        class="rag-wf-float-tool-btn"
        :class="{ 'is-active': interactionMode === 'pan' }"
        @click="emit('set-mode', 'pan')"
      >
        <Icon icon="mdi:hand-back-left-outline" class="rag-wf-float-tool-ico" />
      </button>
    </ElTooltip>
    <ElTooltip content="适配视图" placement="right">
      <button type="button" class="rag-wf-float-tool-btn" @click="emit('fit-view')">
        <Icon icon="mdi:fit-to-screen-outline" class="rag-wf-float-tool-ico" />
      </button>
    </ElTooltip>
    <ElDropdown trigger="click" @command="(c: string) => (c === 'keys' ? emit('hotkeys') : null)">
      <button type="button" class="rag-wf-float-tool-btn">
        <Icon icon="mdi:dots-horizontal" class="rag-wf-float-tool-ico" />
      </button>
      <template #dropdown>
        <ElDropdownMenu>
          <ElDropdownItem command="keys">快捷键说明</ElDropdownItem>
        </ElDropdownMenu>
      </template>
    </ElDropdown>
  </div>
</template>
