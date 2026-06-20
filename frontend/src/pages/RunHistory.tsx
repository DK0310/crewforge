/*
 * Durable run history (GET /runs, newest first). Each row re-opens into the run
 * view, which renders a finished run from its stored record.
 */
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { PageHeader } from "../components/PageHeader";
import { RunRow } from "../components/RunRow";
import { Button, EmptyState, InlineError, Panel, Spinner } from "../components/ui";
import { IconHistory } from "../components/icons";

export function RunHistory() {
  const runs = useAsync(() => api.listRuns(), []);

  return (
    <div>
      <PageHeader
        title="Run history"
        subtitle="Every run is persisted and survives a restart."
        actions={
          <Button variant="ghost" size="sm" onClick={runs.reload}>
            Refresh
          </Button>
        }
      />

      {runs.loading ? (
        <div className="flex items-center gap-2 py-10 text-label text-muted">
          <Spinner /> loading history…
        </div>
      ) : runs.error ? (
        <InlineError message={runs.error} />
      ) : runs.data && runs.data.length > 0 ? (
        <Panel className="divide-y divide-hairline overflow-hidden">
          {runs.data.map((r) => (
            <RunRow key={r.run_id} run={r} />
          ))}
        </Panel>
      ) : (
        <EmptyState
          icon={<IconHistory width={28} height={28} />}
          title="No runs yet"
          body="When you run a crew, it lands here — re-openable, with its full per-agent output."
          action={
            <Link to="/">
              <Button variant="primary">Start a run</Button>
            </Link>
          }
        />
      )}
    </div>
  );
}
