import { Link } from "react-router-dom";
import type { RunRecord } from "../types";
import { RUN_STATUS } from "../lib/status";
import { StatusPill } from "./ui";
import { IconArrowRight } from "./icons";

/** One run in a list — links into the run view. Used on the dashboard and in history. */
export function RunRow({ run }: { run: RunRecord }) {
  const workers = Object.keys(run.results).length;
  return (
    <Link
      to={`/run/${run.run_id}`}
      className="group flex items-center gap-4 px-4 py-3 transition-colors duration-150 hover:bg-surface-2/60"
    >
      <StatusPill meta={RUN_STATUS[run.status]} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-body text-ink">{run.crew_id}</p>
        <p className="font-mono text-label text-muted">
          {run.run_id.slice(0, 12)} · {workers} worker{workers === 1 ? "" : "s"}
        </p>
      </div>
      <IconArrowRight
        width={18}
        height={18}
        className="shrink-0 text-muted transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-ink"
      />
    </Link>
  );
}
