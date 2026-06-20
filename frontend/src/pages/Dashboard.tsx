/*
 * The app home. No marketing landing — it opens straight into work: start a run
 * up top, recent runs and crews below. The run is the hero, so the start panel
 * leads.
 */
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { PageHeader } from "../components/PageHeader";
import { StartRun } from "../components/StartRun";
import { RunRow } from "../components/RunRow";
import { Button, EmptyState, Panel, Spinner } from "../components/ui";
import { IconCompose, IconHistory } from "../components/icons";

export function Dashboard() {
  const crews = useAsync(() => api.listCrews(), []);
  const runs = useAsync(() => api.listRuns(), []);

  const recent = (runs.data ?? []).slice(0, 5);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="Compose a crew, run it, and watch the waves execute live."
        actions={
          <Link to="/compose">
            <Button variant="secondary">
              <IconCompose width={16} height={16} />
              New crew
            </Button>
          </Link>
        }
      />

      {crews.loading ? (
        <div className="flex items-center gap-2 py-10 text-label text-muted">
          <Spinner /> loading crews…
        </div>
      ) : crews.data && crews.data.length > 0 ? (
        <StartRun crews={crews.data} />
      ) : (
        <EmptyState
          icon={<IconCompose width={28} height={28} />}
          title="No crews yet"
          body="A crew is a set of worker agents. Compose one to start running."
          action={
            <Link to="/compose">
              <Button variant="primary">Compose your first crew</Button>
            </Link>
          }
        />
      )}

      <section className="mt-12">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-headline font-semibold text-ink">Recent runs</h2>
          {recent.length > 0 && (
            <Link to="/runs" className="text-label text-muted hover:text-ink">
              View all
            </Link>
          )}
        </div>

        {runs.loading ? (
          <div className="flex items-center gap-2 py-6 text-label text-muted">
            <Spinner /> loading runs…
          </div>
        ) : recent.length > 0 ? (
          <Panel className="divide-y divide-hairline overflow-hidden">
            {recent.map((r) => (
              <RunRow key={r.run_id} run={r} />
            ))}
          </Panel>
        ) : (
          <EmptyState
            icon={<IconHistory width={26} height={26} />}
            title="No runs yet"
            body="Start a run above and it will stream here live, then stay in your history."
          />
        )}
      </section>
    </div>
  );
}
