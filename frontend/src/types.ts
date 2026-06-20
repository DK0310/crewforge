/*
 * TypeScript mirror of the backend Pydantic models. The SSE event union is the
 * load-bearing contract — it must stay in lockstep with
 * backend/app/models/run.py (the RunEvent discriminated union). When the
 * backend adds an event type, add it here and the reducer's switch goes
 * non-exhaustive, which is the point.
 */

export type AgentStatus = "pending" | "running" | "done" | "error";
export type RunStatus = "pending" | "running" | "done" | "error" | "cancelled";

// --- Config: agents & crews (config/*.yaml surfaced as JSON) ---------------

export interface ToolSpec {
  name: string;
  description?: string;
}

export interface AgentSummary {
  id: string;
  name: string;
  description: string;
}

export interface AgentConfig {
  id: string;
  name: string;
  description: string;
  model?: string | null;
  system_prompt: string;
  consumes: string[];
  produces: string[];
  tools: ToolSpec[];
  output_schema: Record<string, unknown>;
}

export interface DependencySpec {
  agent: string;
  depends_on: string[];
}

export interface CrewSummary {
  id: string;
  name: string;
  description?: string | null;
  workers: string[];
}

export interface CrewConfig {
  id: string;
  name: string;
  description?: string | null;
  workers: string[];
  execution_plan?: DependencySpec[] | null;
  manager_prompt_override?: string | null;
  leader_prompt_override?: string | null;
}

// --- Run records (GET /runs, GET /runs/{id}) -------------------------------

export interface AgentResult {
  agent_id: string;
  status: AgentStatus;
  output?: Record<string, unknown> | null;
  error?: string | null;
  started_at?: number | null;
  finished_at?: number | null;
}

export interface RunRecord {
  run_id: string;
  crew_id: string;
  status: RunStatus;
  plan: string[][];
  results: Record<string, AgentResult>;
  final_answer?: string | null;
  error?: string | null;
}

// --- SSE event union (mirror of models/run.py:41-90) -----------------------

export type RunEvent =
  | { type: "plan"; waves: string[][] }
  | { type: "agent_status"; agent_id: string; status: AgentStatus }
  | { type: "token"; agent_id: string; text: string }
  | { type: "agent_result"; agent_id: string; output: Record<string, unknown> }
  | { type: "final"; answer: string }
  | { type: "error"; agent_id?: string | null; message: string }
  | { type: "done" };

// The reserved sentinels the engine uses for the built-in roles.
export const MANAGER_ID = "__manager__";
export const LEADER_ID = "__leader__";
