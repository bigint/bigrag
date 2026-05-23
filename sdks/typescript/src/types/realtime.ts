export interface RealtimeSnapshot<T = unknown> {
  type: "snapshot";
  id: string;
  topic: string;
  payload: T;
  generated_at: string;
}

export interface RealtimeEvent<T = unknown> {
  type: "event";
  id: string;
  topic: string;
  payload: T;
  generated_at: string;
}

export interface RealtimeError {
  type: "error";
  id?: string;
  topic?: string;
  message: string;
  generated_at: string;
}

export interface RealtimeComplete {
  type: "complete";
  id: string;
  topic: string;
  generated_at: string;
}

export interface RealtimeControlMessage {
  type: "subscribed" | "heartbeat" | "pong";
  id?: string;
  topic?: string;
  generated_at?: string;
}

export type RealtimeMessage<T = unknown> =
  | RealtimeSnapshot<T>
  | RealtimeEvent<T>
  | RealtimeError
  | RealtimeComplete
  | RealtimeControlMessage;

export interface ProgressEvent {
  step: string;
  message: string;
  progress: number;
  document_id?: string;
  status?: string;
  detail?: Record<string, unknown>;
}
