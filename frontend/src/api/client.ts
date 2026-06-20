/*
 * Thin fetch wrappers over the FastAPI REST surface (ARCHITECTURE.md §5).
 * The SSE stream is consumed separately by useRunStream; everything here is
 * request/response JSON. In dev, Vite proxies these paths to the backend
 * (vite.config.ts), so relative URLs work on the same origin.
 */

import type {
  AgentConfig,
  AgentSummary,
  CrewConfig,
  CrewSummary,
  RunRecord,
} from "../types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "Cannot reach the CrewForge backend. Is it running?");
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  health: () => req<{ status: string }>("/health"),

  listAgents: () => req<AgentSummary[]>("/agents"),
  getAgent: (id: string) => req<AgentConfig>(`/agents/${id}`),
  createAgent: (body: AgentConfig) =>
    req<AgentConfig>("/agents", { method: "POST", body: JSON.stringify(body) }),
  updateAgent: (id: string, body: AgentConfig) =>
    req<AgentConfig>(`/agents/${id}`, { method: "PUT", body: JSON.stringify(body) }),

  listCrews: () => req<CrewSummary[]>("/crews"),
  getCrew: (id: string) => req<CrewConfig>(`/crews/${id}`),
  createCrew: (body: CrewConfig) =>
    req<CrewConfig>("/crews", { method: "POST", body: JSON.stringify(body) }),
  updateCrew: (id: string, body: CrewConfig) =>
    req<CrewConfig>(`/crews/${id}`, { method: "PUT", body: JSON.stringify(body) }),

  listRuns: () => req<RunRecord[]>("/runs"),
  getRun: (id: string) => req<RunRecord>(`/runs/${id}`),

  /** Start a run from a text prompt. Returns the new run_id. */
  startRun: (crew_id: string, user_input: string) =>
    req<{ run_id: string }>("/runs", {
      method: "POST",
      body: JSON.stringify({ crew_id, user_input }),
    }),

  /** Start a run with an uploaded file (multipart; text extracted server-side). */
  startRunWithFile: async (crew_id: string, user_input: string, file: File) => {
    const form = new FormData();
    form.append("crew_id", crew_id);
    form.append("user_input", user_input);
    form.append("file", file);
    // Don't set Content-Type — the browser sets the multipart boundary.
    const res = await fetch("/runs/upload", { method: "POST", body: form });
    if (!res.ok) throw new ApiError(res.status, `Upload failed (${res.status}).`);
    return (await res.json()) as { run_id: string };
  },

  cancelRun: (id: string) =>
    req<RunRecord>(`/runs/${id}/cancel`, { method: "POST" }),
};
