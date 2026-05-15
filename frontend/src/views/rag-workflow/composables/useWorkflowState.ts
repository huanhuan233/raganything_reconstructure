import type { Edge, Node } from '@vue-flow/core';
import { ref, shallowRef, watch, type Ref } from 'vue';
import type { VueFlowStore } from '@vue-flow/core';
import { stringifyPretty } from '../utils/jsonHelper';
import { flowToRunPayload } from '../utils/workflowTransform';

export const INITIAL_INPUT_JSON = '{\n  "seed": true\n}\n';

export function useWorkflowState() {
  const flowNodes = ref<Node[]>([]);
  const flowEdges = ref<Edge[]>([]);
  const selectedNodeId = ref<string | null>(null);

  const workflowId = ref('ui-dag');
  const workflowDisplayName = ref('');
  const workflowDescription = ref('');
  const workflowInputJson = ref(INITIAL_INPUT_JSON);

  const vfStore = shallowRef<VueFlowStore | null>(null);
  const zoomPercent = ref(100);

  const workflowPreview = ref('');

  function updateWorkflowPreview() {
    workflowPreview.value = stringifyPretty(
      flowToRunPayload(
        flowNodes.value,
        flowEdges.value,
        workflowId.value.trim(),
        workflowInputJson.value
      )
    );
  }

  watch(
    () =>
      [workflowId.value, workflowInputJson.value, flowNodes.value, flowEdges.value] as const,
    () => updateWorkflowPreview(),
    { deep: true }
  );

  function onStructureChange() {
    updateWorkflowPreview();
  }

  return {
    flowNodes,
    flowEdges,
    selectedNodeId,
    workflowId,
    workflowDisplayName,
    workflowDescription,
    workflowInputJson,
    vfStore,
    zoomPercent,
    workflowPreview,
    updateWorkflowPreview,
    onStructureChange
  };
}

export type WorkflowStateRefs = ReturnType<typeof useWorkflowState>;
