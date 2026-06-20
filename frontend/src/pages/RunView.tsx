/*
 * The hero. Reading top to bottom mirrors execution: Manager, then each wave
 * (workers side by side, because they run in parallel), then the Leader. The
 * live view is driven entirely by SSE (useRunStream); it holds no orchestration
 * logic. A finished run opened from history renders from its stored RunRecord
 * instead of re-opening the (single-consumer, already-drained) stream.
 */
import { useEffect, useMemo } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { useRunStream } from "../hooks/useRunStream";
import type { AgentLane } from "../hooks/useRunStream";
import { LEADER_ID, MANAGER_ID } from "../types";
import type { RunRecord, RunStatus } from "../types";
import { RUN_STATUS } from "../lib/status";
import { AgentLanePanel } from "../components/AgentLanePanel";
import { LeaderPanel } from "../components/LeaderPanel";
import { PageHeader } from "../components/PageHeader";
import { Button, InlineError, Spinner, StatusPill, cx } from "../components/ui";
import { IconStop } from "../components/icons";

const TERMINAL: RunStatus[] = ["done", "error", "cancelled"];
const isTerminal = (s: RunStatus) => TERMINAL.includes(s);

function emptyLane(id: string, status: AgentLane["status"] = "pending"): AgentLane {
  return { id, status, tokens: "", output: null, error: null };
}

/** Normalized shape both the live stream and a stored record reduce to. */
interface RunVM {
  plan: string[][];
  lanes: Record<string, AgentLane>;
  managerLane: AgentLane;
  leaderLane: AgentLane;
  finalAnswer: string | null;
  status: RunStatus;
  error: string | null;
}

function vmFromRecord(rec: RunRecord): RunVM {
  const lanes: Record<string, AgentLane> = {};
  for (const wave of rec.plan)
    for (const id of wave) {
      const r = rec.results[id];
      lanes[id] = r
        ? { id, status: r.status, tokens: "", output: r.output ?? null, error: r.error ?? null }
        : emptyLane(id, isTerminal(rec.status) ? "done" : "pending");
    }
  const ran = rec.status !== "pending";
  const managerLane = emptyLane(MANAGER_ID, ran ? "done" : "pending");
  const leaderLane = emptyLane(
    LEADER_ID,
    rec.final_answer ? "done" : rec.status === "error" ? "error" : ran ? "done" : "pending",
  );
  return {
    plan: rec.plan,
    lanes,
    managerLane,
    leaderLane,
    finalAnswer: rec.final_answer ?? null,
    status: rec.status,
    error: rec.error ?? null,
  };
}

export function RunView() {
  const { runId = "" } = useParams();
  const record = useAsync(() => api.getRun(runId), [runId]);

  // Only stream a run that hasn't finished; a historical run renders statically.
  const streamId =
    record.data && !isTerminal(record.data.status) ? runId : null;
  const run = useRunStream(streamId);
  const agents = useAsync(() => api.listAgents(), []);

  const streamTerminal = run.phase === "done" || run.phase === "error";
  useEffect(() => {
    if (streamTerminal) record.reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streamTerminal]);

  const nameFor = useMemo(() => {
    const map = new Map((agents.data ?? []).map((a) => [a.id, a.name]));
    return (id: string) =>
      id === MANAGER_ID ? "Manager" : id === LEADER_ID ? "Leader" : map.get(id) ?? id;
  }, [agents.data]);

  if (record.loading && !record.data) {
    return (
      <div className="flex items-center gap-2 py-20 text-label text-muted">
        <Spinner /> loading run…
      </div>
    );
  }
  if (record.error && !record.data) {
    return (
      <div className="py-10">
        <PageHeader kicker={`run · ${runId.slice(0, 8)}`} title="Run not found" />
        <InlineError message={record.error} />
      </div>
    );
  }

  // Build the view model from whichever source is authoritative.
  const usingLive = streamId !== null;
  let vm: RunVM;
  if (usingLive) {
    const plan = run.plan.length ? run.plan : (record.data?.plan ?? []);
    vm = {
      plan,
      lanes: run.lanes,
      managerLane: run.lanes[MANAGER_ID] ?? emptyLane(MANAGER_ID),
      leaderLane: run.lanes[LEADER_ID] ?? emptyLane(LEADER_ID),
      finalAnswer: run.finalAnswer,
      status: streamTerminal ? (record.data?.status ?? "done") : "running",
      error: run.error,
    };
  } else {
    vm = vmFromRecord(record.data!);
  }

  const live = vm.status === "running" || vm.status === "pending";
  const crewId = record.data?.crew_id;
  const connecting = usingLive && run.phase === "connecting";

  const onCancel = async () => {
    try {
      await api.cancelRun(runId);
    } catch {
      /* the stream's terminal event reconciles the UI */
    }
  };

  return (
    <div>
      <PageHeader
        kicker={`run · ${runId.slice(0, 8)}`}
        title={crewId ?? "Run"}
        subtitle="Manager plans, workers run in waves, the Leader synthesizes."
        actions={
          <div className="flex items-center gap-3">
            <StatusPill meta={RUN_STATUS[vm.status]} />
            {live && (
              <Button variant="danger" size="sm" onClick={onCancel}>
                <IconStop width={15} height={15} />
                Cancel
              </Button>
            )}
          </div>
        }
      />

      {vm.error && (
        <div className="mb-6">
          <InlineError message={vm.error} />
        </div>
      )}

      {connecting && (
        <div className="mb-6 flex items-center gap-2 text-label text-muted">
          <Spinner /> connecting to the run stream…
        </div>
      )}

      {/* Manager */}
      <StageRail label="Manager · planning" live={vm.managerLane.status === "running"} />
      <AgentLanePanel lane={vm.managerLane} name="Manager" role="manager" />

      {/* Waves */}
      {vm.plan.map((wave, i) => {
        const waveLive = wave.some((id) => vm.lanes[id]?.status === "running");
        const waveDone = wave.every((id) => {
          const s = vm.lanes[id]?.status;
          return s === "done" || s === "error";
        });
        return (
          <div key={`wave-${i}`}>
            <Connector live={vm.managerLane.status === "done" || waveLive} />
            <StageRail
              label={`Wave ${i + 1}${wave.length > 1 ? " · runs in parallel" : ""}`}
              live={waveLive}
            />
            <div className={cx("grid gap-4", wave.length > 1 ? "md:grid-cols-2" : "grid-cols-1")}>
              {wave.map((id) => (
                <AgentLanePanel
                  key={id}
                  lane={vm.lanes[id] ?? emptyLane(id)}
                  name={nameFor(id)}
                  role="worker"
                />
              ))}
            </div>
            <span className="sr-only">{waveDone ? "wave complete" : ""}</span>
          </div>
        );
      })}

      {/* Leader */}
      <Connector live={vm.leaderLane.status === "running" || vm.leaderLane.status === "done"} />
      <StageRail label="Leader · synthesis" live={vm.leaderLane.status === "running"} />
      <LeaderPanel lane={vm.leaderLane} finalAnswer={vm.finalAnswer} />
    </div>
  );
}

function StageRail({ label, live }: { label: string; live: boolean }) {
  return (
    <div className="mb-3 flex items-center gap-3">
      <span className={cx("size-1.5 rounded-full", live ? "bg-signal" : "bg-hairline")} />
      <h2 className={cx("text-label font-medium", live ? "text-signal" : "text-muted")}>{label}</h2>
      <span className="h-px flex-1 bg-hairline" />
    </div>
  );
}

function Connector({ live }: { live: boolean }) {
  return (
    <div className="flex justify-start pl-[2px]" aria-hidden>
      <span className={cx("my-1 h-6 w-px", live ? "bg-signal" : "bg-hairline")} />
    </div>
  );
}
