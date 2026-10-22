export type RunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface TweetArtifact {
  id: string;
  run_id: string;
  artifact_type: string;
  title: string | null;
  content_json: Record<string, unknown>;
  created_at: string;
}

export interface TweetRevision {
  id: string;
  project_id: string;
  run_id: string | null;
  content: string;
  platform: string | null;
  tone: string | null;
  score: number | null;
  risk_level: string;
  version: number;
  is_final: boolean;
  source: string;
  created_at: string;
}

export interface Run {
  id: string;
  project_id: string;
  status: RunStatus;
  current_node: string | null;
  error_message: string | null;
  llm_calls: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface RunDetail extends Run {
  artifacts: TweetArtifact[];
  revisions: TweetRevision[];
}

export type RunEventType =
  | "run.started"
  | "node.completed"
  | "node.progress"
  | "run.completed"
  | "run.cancelled"
  | "run.failed"
  | "stream.end"
  | "stream.timeout";

export interface RunEvent {
  id?: string;
  eventType: RunEventType;
  nodeId: string | null;
  message: string | null;
  payload: Record<string, unknown>;
  createdAt?: string | null;
}
