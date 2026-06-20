/*
 * The signature component: one agent's lane in a run. Header (role icon, name,
 * status pill), a live monospace token stream (the machine speaking — auto-
 * scrolls while running, with a blinking caret), and, once done, the validated
 * JSON output. The active lane earns the amber live-glow; resting lanes are flat.
 */
import { memo, useEffect, useRef } from "react";
import type { ComponentType, SVGProps } from "react";
import type { AgentLane } from "../hooks/useRunStream";
import { AGENT_STATUS } from "../lib/status";
import { StatusPill, cx } from "./ui";
import { IconLeader, IconManager } from "./icons";

export type LaneRole = "manager" | "worker" | "leader";

const ROLE_ICON: Partial<Record<LaneRole, ComponentType<SVGProps<SVGSVGElement>>>> = {
  manager: IconManager,
  leader: IconLeader,
};

function useAutoScroll(dep: unknown) {
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Only stick to the bottom if the user hasn't scrolled up to read.
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    if (nearBottom) el.scrollTop = el.scrollHeight;
  }, [dep]);
  return ref;
}

function AgentLanePanelImpl({
  lane,
  name,
  role,
  task,
}: {
  lane: AgentLane;
  name: string;
  role: LaneRole;
  task?: string;
}) {
  const meta = AGENT_STATUS[lane.status];
  const RoleIcon = ROLE_ICON[role];
  const streamRef = useAutoScroll(lane.tokens);
  const hasOutput = lane.output && Object.keys(lane.output).length > 0;

  return (
    <article
      className={cx(
        "flex flex-col rounded-lg border bg-surface transition-shadow duration-200",
        meta.live ? "live-glow border-transparent" : "border-hairline",
      )}
    >
      <header className="flex items-center justify-between gap-3 border-b border-hairline px-4 py-3">
        <div className="flex min-w-0 items-center gap-2.5">
          {RoleIcon ? (
            <RoleIcon width={18} height={18} className="shrink-0 text-muted" />
          ) : (
            <span className="grid size-5 shrink-0 place-items-center rounded bg-surface-2 font-mono text-[0.7rem] text-muted">
              {name.charAt(0).toUpperCase()}
            </span>
          )}
          <div className="min-w-0">
            <h3 className="truncate text-title font-medium text-ink">{name}</h3>
            {role !== "worker" && (
              <span className="font-mono text-[0.7rem] text-muted">system · {role}</span>
            )}
          </div>
        </div>
        <StatusPill meta={meta} />
      </header>

      {task && (
        <p className="border-b border-hairline px-4 py-2.5 text-label leading-relaxed text-muted">
          {task}
        </p>
      )}

      <div className="flex flex-1 flex-col gap-3 p-4">
        {lane.tokens ? (
          <pre
            ref={streamRef}
            className="max-h-72 overflow-auto whitespace-pre-wrap break-words font-mono text-data leading-relaxed text-ink/90"
          >
            {lane.tokens}
            {meta.live && <span className="stream-caret" aria-hidden />}
          </pre>
        ) : (
          <p className="font-mono text-data text-muted">
            {meta.live ? "thinking…" : lane.status === "pending" ? "awaiting upstream…" : "—"}
          </p>
        )}

        {lane.error && (
          <p className="rounded-md border border-error/40 bg-error/10 px-3 py-2 font-mono text-data text-ink">
            {lane.error}
          </p>
        )}

        {hasOutput && (
          <details className="group rounded-md border border-hairline bg-bg" open={role === "worker"}>
            <summary className="flex cursor-pointer items-center gap-2 px-3 py-2 text-label text-muted select-none hover:text-ink">
              <span className="font-mono text-done">{"{ }"}</span>
              validated output
            </summary>
            <pre className="overflow-auto border-t border-hairline px-3 py-2 font-mono text-data leading-relaxed text-ink/90">
              {JSON.stringify(lane.output, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </article>
  );
}

// Memoized: a lane only re-renders when its own props change, so a token batch
// touching one lane doesn't re-render the others.
export const AgentLanePanel = memo(AgentLanePanelImpl);
