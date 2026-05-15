import { fetchRagRuntimeTrace, fetchRagRuntimeTraceNodeDetail, getRagRuntimeTraceStreamUrl } from '@/service/api';
import type {
  RuntimeTraceEvent,
  RuntimeTraceNodeDetail,
  RuntimeTraceSnapshot
} from './RuntimeTraceTypes';

type EventHandler = (event: RuntimeTraceEvent) => void;
type SnapshotHandler = (snapshot: RuntimeTraceSnapshot) => void;
type ErrorHandler = (err: unknown) => void;

export class RuntimeTraceService {
  private es: EventSource | null = null;

  close() {
    if (this.es) {
      this.es.close();
      this.es = null;
    }
  }

  // eslint-disable-next-line class-methods-use-this
  async getSnapshot(runId: string): Promise<RuntimeTraceSnapshot> {
    return fetchRagRuntimeTrace(runId);
  }

  // eslint-disable-next-line class-methods-use-this
  async getNodeDetail(runId: string, nodeId: string): Promise<RuntimeTraceNodeDetail> {
    return fetchRagRuntimeTraceNodeDetail(runId, nodeId);
  }

  subscribeSSE(
    runId: string,
    handlers: {
      onEvent: EventHandler;
      onSnapshot?: SnapshotHandler;
      onError?: ErrorHandler;
    }
  ) {
    this.close();
    const url = getRagRuntimeTraceStreamUrl(runId);
    const es = new EventSource(url);
    this.es = es;

    es.addEventListener('trace', evt => {
      try {
        const data = JSON.parse((evt as MessageEvent).data) as RuntimeTraceEvent;
        handlers.onEvent(data);
      } catch (err) {
        handlers.onError?.(err);
      }
    });

    es.addEventListener('snapshot', evt => {
      try {
        const data = JSON.parse((evt as MessageEvent).data) as RuntimeTraceEvent;
        const snap = ((data.payload || {}) as unknown) as RuntimeTraceSnapshot;
        handlers.onSnapshot?.(snap);
      } catch (err) {
        handlers.onError?.(err);
      }
    });

    es.onerror = err => {
      handlers.onError?.(err);
    };
  }
}

