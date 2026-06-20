/*
 * The run view is driven entirely by SSE events (crewforge-frontend principle 1).
 * This hook opens the EventSource, reduces the RunEvent union into run state,
 * and hands that state to the view. It holds no orchestration logic.
 *
 * Connecting to GET /runs/{id}/stream is what *launches* the graph on the
 * backend (lazy, single-consumer), so this hook is for live runs only; to
 * inspect a finished run, read the RunRecord via api.getRun instead.
 *
 * Tokens arrive rapidly. We buffer incoming events in a ref and flush them to
 * the reducer once per animation frame, so a burst of tokens is one render, not
 * hundreds.
 */

import { useEffect, useReducer, useRef } from "react";
import type { AgentStatus, RunEvent } from "../types";

export interface AgentLane {
  id: string;
  status: AgentStatus;
  tokens: string;
  output: Record<string, unknown> | null;
  error: string | null;
}

export type StreamPhase = "connecting" | "streaming" | "done" | "error";

export interface RunState {
  phase: StreamPhase;
  plan: string[][];
  /** Every lane the run touches, keyed by agent_id (incl. manager/leader sentinels). */
  lanes: Record<string, AgentLane>;
  finalAnswer: string | null;
  error: string | null;
}

const initialState: RunState = {
  phase: "connecting",
  plan: [],
  lanes: {},
  finalAnswer: null,
  error: null,
};

function lane(state: RunState, id: string): AgentLane {
  return (
    state.lanes[id] ?? { id, status: "pending", tokens: "", output: null, error: null }
  );
}

function applyOne(state: RunState, ev: RunEvent): RunState {
  switch (ev.type) {
    case "plan": {
      const lanes: Record<string, AgentLane> = { ...state.lanes };
      for (const wave of ev.waves)
        for (const id of wave)
          lanes[id] ??= { id, status: "pending", tokens: "", output: null, error: null };
      return { ...state, phase: "streaming", plan: ev.waves, lanes };
    }
    case "agent_status":
      return {
        ...state,
        lanes: { ...state.lanes, [ev.agent_id]: { ...lane(state, ev.agent_id), status: ev.status } },
      };
    case "token": {
      const l = lane(state, ev.agent_id);
      return {
        ...state,
        lanes: { ...state.lanes, [ev.agent_id]: { ...l, tokens: l.tokens + ev.text } },
      };
    }
    case "agent_result":
      return {
        ...state,
        lanes: {
          ...state.lanes,
          [ev.agent_id]: { ...lane(state, ev.agent_id), output: ev.output, status: "done" },
        },
      };
    case "final":
      return { ...state, finalAnswer: ev.answer };
    case "error": {
      if (ev.agent_id) {
        return {
          ...state,
          lanes: {
            ...state.lanes,
            [ev.agent_id]: { ...lane(state, ev.agent_id), status: "error", error: ev.message },
          },
        };
      }
      return { ...state, error: ev.message };
    }
    case "done":
      return { ...state, phase: state.error ? "error" : "done" };
    default: {
      // Exhaustiveness guard: a new backend event type lands here as a type error.
      const _exhaustive: never = ev;
      return _exhaustive;
    }
  }
}

type Action = { kind: "batch"; events: RunEvent[] } | { kind: "fail"; message: string };

function reducer(state: RunState, action: Action): RunState {
  if (action.kind === "fail") {
    if (state.phase === "done") return state; // already finished cleanly
    return { ...state, phase: "error", error: state.error ?? action.message };
  }
  return action.events.reduce(applyOne, state);
}

export function useRunStream(runId: string | null): RunState {
  const [state, dispatch] = useReducer(reducer, initialState);
  const buffer = useRef<RunEvent[]>([]);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    if (!runId) return;

    const flush = () => {
      frame.current = null;
      if (buffer.current.length === 0) return;
      const events = buffer.current;
      buffer.current = [];
      dispatch({ kind: "batch", events });
    };
    const schedule = () => {
      if (frame.current === null) frame.current = requestAnimationFrame(flush);
    };

    const es = new EventSource(`/runs/${runId}/stream`);
    es.onmessage = (e) => {
      try {
        buffer.current.push(JSON.parse(e.data) as RunEvent);
        schedule();
      } catch {
        /* keep-alive comments and malformed lines are ignored */
      }
    };
    es.addEventListener("error", () => {
      // EventSource fires `error` on normal close too; flush what we have, then
      // only mark failed if the run never reached a terminal state.
      flush();
      es.close();
      dispatch({ kind: "fail", message: "Stream disconnected." });
    });

    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      es.close();
    };
  }, [runId]);

  return state;
}
