/** An SSE event emitted during document processing. */
export interface ProgressEvent {
  step: string;
  message: string;
  progress: number;
  status?: string;
  detail?: Record<string, unknown>;
}
