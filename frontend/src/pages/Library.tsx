/*
 * The library surfaces the YAML config as UI. Agents are browsable (they're
 * authored as prompts + schema; the composer owns crew authoring). Crews can be
 * opened into the composer to edit, or created fresh. Config is data — this is
 * just a readable window onto config/.
 */
import { useState } from "react";
import type { KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import type { AgentConfig } from "../types";
import { PageHeader } from "../components/PageHeader";
import { Button, EmptyState, InlineError, Panel, Spinner, cx } from "../components/ui";
import { IconChevron, IconCompose, IconLibrary } from "../components/icons";

type Tab = "agents" | "crews";

const TAB_ITEMS: { id: Tab; label: string }[] = [
  { id: "agents", label: "Agents" },
  { id: "crews", label: "Crews" },
];

function Tabs({ tab, onChange }: { tab: Tab; onChange: (t: Tab) => void }) {
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const i = TAB_ITEMS.findIndex((t) => t.id === tab);
    const next = e.key === "ArrowRight" ? (i + 1) % TAB_ITEMS.length : (i - 1 + TAB_ITEMS.length) % TAB_ITEMS.length;
    onChange(TAB_ITEMS[next].id);
  };
  return (
    <div className="mb-6 flex gap-1 border-b border-hairline" role="tablist" onKeyDown={onKeyDown}>
      {TAB_ITEMS.map((it) => {
        const selected = tab === it.id;
        return (
          <button
            key={it.id}
            id={`tab-${it.id}`}
            role="tab"
            aria-selected={selected}
            aria-controls={`panel-${it.id}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(it.id)}
            className={cx(
              "relative -mb-px px-4 py-2.5 text-body transition-colors duration-150",
              selected
                ? "text-ink after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-signal"
                : "text-muted hover:text-ink",
            )}
          >
            {it.label}
          </button>
        );
      })}
    </div>
  );
}

function FieldChips({ label, values }: { label: string; values: string[] }) {
  if (!values.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-label text-muted">{label}</span>
      {values.map((v) => (
        <span
          key={v}
          className="rounded-full border border-hairline bg-surface-2 px-2 py-0.5 font-mono text-label text-ink"
        >
          {v}
        </span>
      ))}
    </div>
  );
}

function AgentDetail({ id }: { id: string }) {
  const agent = useAsync<AgentConfig>(() => api.getAgent(id), [id]);
  if (agent.loading)
    return (
      <div className="flex items-center gap-2 px-4 py-4 text-label text-muted">
        <Spinner /> loading…
      </div>
    );
  if (agent.error) return <div className="px-4 py-4"><InlineError message={agent.error} /></div>;
  const a = agent.data!;
  return (
    <div className="flex flex-col gap-4 border-t border-hairline bg-bg px-4 py-4">
      <div className="flex flex-col gap-2">
        <span className="text-label text-muted">system prompt</span>
        <p className="max-w-[72ch] text-body leading-relaxed whitespace-pre-wrap text-ink/90">
          {a.system_prompt}
        </p>
      </div>
      <FieldChips label="consumes" values={a.consumes} />
      <FieldChips label="produces" values={a.produces} />
      <div className="flex flex-wrap gap-4 text-label text-muted">
        <span>
          model <span className="font-mono text-ink">{a.model ?? "default"}</span>
        </span>
        <span>
          tools{" "}
          <span className="font-mono text-ink">
            {a.tools.length ? a.tools.map((t) => t.name).join(", ") : "none (reserved)"}
          </span>
        </span>
      </div>
      <details className="rounded-md border border-hairline">
        <summary className="cursor-pointer px-3 py-2 text-label text-muted hover:text-ink select-none">
          output schema
        </summary>
        <pre className="overflow-auto border-t border-hairline px-3 py-2 font-mono text-data leading-relaxed text-ink/90">
          {JSON.stringify(a.output_schema, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function AgentsTab() {
  const agents = useAsync(() => api.listAgents(), []);
  const [open, setOpen] = useState<string | null>(null);

  if (agents.loading)
    return (
      <div className="flex items-center gap-2 py-10 text-label text-muted">
        <Spinner /> loading agents…
      </div>
    );
  if (agents.error) return <InlineError message={agents.error} />;
  if (!agents.data?.length)
    return (
      <EmptyState
        icon={<IconLibrary width={28} height={28} />}
        title="No agents"
        body="Add agent YAML files under config/agents and they'll appear here."
      />
    );

  return (
    <Panel className="divide-y divide-hairline overflow-hidden">
      {agents.data.map((a) => {
        const isOpen = open === a.id;
        return (
          <div key={a.id}>
            <button
              onClick={() => setOpen(isOpen ? null : a.id)}
              aria-expanded={isOpen}
              className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2/60"
            >
              <IconChevron
                width={16}
                height={16}
                className={cx(
                  "shrink-0 text-muted transition-transform duration-150",
                  isOpen && "rotate-90",
                )}
              />
              <div className="min-w-0 flex-1">
                <p className="text-body text-ink">{a.name}</p>
                <p className="truncate text-label text-muted">{a.description}</p>
              </div>
              <span className="font-mono text-label text-muted">{a.id}</span>
            </button>
            {isOpen && <AgentDetail id={a.id} />}
          </div>
        );
      })}
    </Panel>
  );
}

function CrewsTab() {
  const crews = useAsync(() => api.listCrews(), []);

  if (crews.loading)
    return (
      <div className="flex items-center gap-2 py-10 text-label text-muted">
        <Spinner /> loading crews…
      </div>
    );
  if (crews.error) return <InlineError message={crews.error} />;
  if (!crews.data?.length)
    return (
      <EmptyState
        icon={<IconCompose width={28} height={28} />}
        title="No crews yet"
        body="Compose a crew to get started."
        action={
          <Link to="/compose">
            <Button variant="primary">Compose a crew</Button>
          </Link>
        }
      />
    );

  return (
    <Panel className="divide-y divide-hairline overflow-hidden">
      {crews.data.map((c) => (
        <div key={c.id} className="flex items-center gap-4 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="text-body text-ink">{c.name}</p>
            <p className="truncate text-label text-muted">
              {c.description || `${c.workers.length} workers`}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <FieldChips label="" values={c.workers} />
            <Link to={`/compose/${c.id}`}>
              <Button variant="ghost" size="sm">
                Edit
              </Button>
            </Link>
          </div>
        </div>
      ))}
    </Panel>
  );
}

export function Library() {
  const [tab, setTab] = useState<Tab>("agents");
  return (
    <div>
      <PageHeader
        title="Library"
        subtitle="Your agents and crews, surfaced from config."
        actions={
          <Link to="/compose">
            <Button variant="secondary">
              <IconCompose width={16} height={16} />
              New crew
            </Button>
          </Link>
        }
      />
      <Tabs tab={tab} onChange={setTab} />
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "agents" ? <AgentsTab /> : <CrewsTab />}
      </div>
    </div>
  );
}
