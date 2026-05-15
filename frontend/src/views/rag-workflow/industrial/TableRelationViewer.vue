<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{ tables: unknown[] }>();

function cleanHeaderText(input: unknown): string {
  const raw = String(input ?? '').trim();
  if (!raw) return '-';
  // 去 HTML 标签，并把常见实体转为可读文本
  let s = raw
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/tr>/gi, '\n')
    .replace(/<\/td>/gi, ' | ')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>');
  s = s
    .replace(/\s*\|\s*(\||$)/g, ' | ')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{2,}/g, '\n')
    .trim();
  return s || '-';
}

const tableRows = computed(() =>
  (Array.isArray(props.tables) ? props.tables : []).map(one => {
    const row = (one && typeof one === 'object' ? one : {}) as Record<string, unknown>;
    const headersRaw = row.column_headers;
    const headersText = Array.isArray(headersRaw)
      ? headersRaw.map(cleanHeaderText).filter(Boolean).join(' | ')
      : cleanHeaderText(headersRaw);
    return {
      ...row,
      headersText
    };
  })
);
</script>

<template>
  <div class="trv-wrap">
    <ElTable :data="tableRows" size="small" class="trv-table" height="100%">
      <ElTableColumn prop="table_id" label="Table ID" width="140" />
      <ElTableColumn prop="page" label="Page" width="90" />
      <ElTableColumn label="Headers">
        <template #default="{ row }">
          <span class="trv-headers" :title="String(row.headersText || '-')">{{ String(row.headersText || '-') }}</span>
        </template>
      </ElTableColumn>
    </ElTable>
  </div>
</template>

<style scoped>
.trv-wrap {
  height: 100%;
  min-height: 0;
}

.trv-table {
  width: 100%;
}

.trv-headers {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
