/*
 * Crew composer. Beginner-first: name the crew, pick workers — done. The
 * Manager decides order at run time. The advanced step designer (explicit
 * depends_on → execution_plan) is opt-in behind a toggle, so it never confronts
 * a beginner. Manager and Leader are shown as fixed, non-removable roles and are
 * never in the worker picker (non-negotiable design rule 1).
 */
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import type { AgentSummary, CrewConfig, DependencySpec } from "../types";
import { PageHeader } from "../components/PageHeader";
import {
  Button,
  Field,
  InlineError,
  Spinner,
  TextInput,
  Textarea,
  cx,
} from "../components/ui";
import { IconCheck, IconLeader, IconManager } from "../components/icons";

const slugify = (s: string) =>
  s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");

function FixedRole({
  icon,
  name,
  blurb,
}: {
  icon: ReactNode;
  name: string;
  blurb: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-hairline bg-surface-2 px-3 py-2.5">
      <span className="text-muted">{icon}</span>
      <div className="min-w-0">
        <p className="text-label font-medium text-ink">
          {name} <span className="font-normal text-muted">· built-in</span>
        </p>
        <p className="truncate text-label text-muted">{blurb}</p>
      </div>
    </div>
  );
}

function WorkerCard({
  agent,
  selected,
  onToggle,
}: {
  agent: AgentSummary;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={selected}
      className={cx(
        "flex items-start gap-3 rounded-lg border p-4 text-left transition-colors duration-150",
        selected
          ? "border-signal/50 bg-signal-dim"
          : "border-hairline bg-surface hover:border-muted/50",
      )}
    >
      <span
        className={cx(
          "mt-0.5 grid size-5 shrink-0 place-items-center rounded border",
          selected ? "border-signal bg-signal text-signal-ink" : "border-hairline text-transparent",
        )}
      >
        <IconCheck width={14} height={14} />
      </span>
      <span className="min-w-0">
        <span className="block text-title font-medium text-ink">{agent.name}</span>
        <span className="mt-0.5 block text-label leading-relaxed text-muted">
          {agent.description}
        </span>
      </span>
    </button>
  );
}

export function Composer() {
  const { crewId } = useParams();
  const editing = Boolean(crewId);
  const navigate = useNavigate();

  const agents = useAsync(() => api.listAgents(), []);
  const existing = useAsync(
    () => (crewId ? api.getCrew(crewId) : Promise.resolve(null)),
    [crewId],
  );

  const [name, setName] = useState("");
  const [id, setId] = useState("");
  const [idEdited, setIdEdited] = useState(false);
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [advanced, setAdvanced] = useState(false);
  const [deps, setDeps] = useState<Record<string, string[]>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  // Hydrate the form once when editing an existing crew.
  if (editing && existing.data && !hydrated) {
    const c = existing.data;
    setName(c.name);
    setId(c.id);
    setIdEdited(true);
    setDescription(c.description ?? "");
    setSelected(c.workers);
    if (c.execution_plan && c.execution_plan.length) {
      setAdvanced(true);
      setDeps(Object.fromEntries(c.execution_plan.map((d) => [d.agent, d.depends_on])));
    }
    setHydrated(true);
  }

  const toggleWorker = (wid: string) => {
    setSelected((prev) =>
      prev.includes(wid) ? prev.filter((x) => x !== wid) : [...prev, wid],
    );
    setDeps((prev) => {
      const next = { ...prev };
      delete next[wid];
      for (const k of Object.keys(next)) next[k] = next[k].filter((d) => d !== wid);
      return next;
    });
  };

  const toggleDep = (worker: string, dep: string) => {
    setDeps((prev) => {
      const cur = prev[worker] ?? [];
      return {
        ...prev,
        [worker]: cur.includes(dep) ? cur.filter((d) => d !== dep) : [...cur, dep],
      };
    });
  };

  const effectiveId = idEdited ? id : slugify(name);
  const canSave = effectiveId && name.trim() && selected.length > 0 && !saving;

  const executionPlan = useMemo<DependencySpec[] | null>(() => {
    if (!advanced) return null;
    return selected.map((w) => ({ agent: w, depends_on: (deps[w] ?? []).filter((d) => selected.includes(d)) }));
  }, [advanced, selected, deps]);

  const save = async () => {
    if (!canSave) return;
    setSaving(true);
    setError(null);
    const body: CrewConfig = {
      id: effectiveId,
      name: name.trim(),
      description: description.trim() || null,
      workers: selected,
      execution_plan: executionPlan,
      manager_prompt_override: null,
      leader_prompt_override: null,
    };
    try {
      if (editing) await api.updateCrew(effectiveId, body);
      else await api.createCrew(body);
      navigate("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save the crew.");
      setSaving(false);
    }
  };

  if (agents.loading) {
    return (
      <div className="flex items-center gap-2 py-20 text-label text-muted">
        <Spinner /> loading agents…
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        kicker={editing ? `editing · ${crewId}` : "new crew"}
        title={editing ? "Edit crew" : "Compose a crew"}
        subtitle="Pick the workers. The Manager and Leader are built in to every crew."
      />

      <div className="flex flex-col gap-8">
        {/* Identity */}
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Crew name">
            <TextInput
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="SOC Analysis Crew"
            />
          </Field>
          <Field label="Crew ID" hint="Lowercase identifier; becomes the config filename.">
            <TextInput
              value={effectiveId}
              onChange={(e) => {
                setIdEdited(true);
                setId(slugify(e.target.value));
              }}
              disabled={editing}
              className="font-mono"
              placeholder="soc_crew"
            />
          </Field>
        </div>
        <Field label="Description" hint="Optional — shown in the crew picker.">
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="Investigates a security alert end to end."
          />
        </Field>

        {/* Fixed roles */}
        <div>
          <h2 className="mb-3 text-headline font-semibold text-ink">Built-in roles</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <FixedRole
              icon={<IconManager width={18} height={18} />}
              name="Manager"
              blurb="Plans the run and writes each worker's task."
            />
            <FixedRole
              icon={<IconLeader width={18} height={18} />}
              name="Leader"
              blurb="Synthesizes the workers' output into the final answer."
            />
          </div>
        </div>

        {/* Workers */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-headline font-semibold text-ink">Workers</h2>
            <span className="text-label text-muted">
              {selected.length} selected
            </span>
          </div>
          {agents.data && agents.data.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {agents.data.map((a) => (
                <WorkerCard
                  key={a.id}
                  agent={a}
                  selected={selected.includes(a.id)}
                  onToggle={() => toggleWorker(a.id)}
                />
              ))}
            </div>
          ) : (
            <p className="text-body text-muted">No agents found in config/agents.</p>
          )}
        </div>

        {/* Advanced step designer */}
        <div className="rounded-lg border border-hairline bg-surface p-5">
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={advanced}
              onChange={(e) => setAdvanced(e.target.checked)}
              className="mt-1 size-4 accent-[var(--color-signal)]"
            />
            <span>
              <span className="block text-title font-medium text-ink">
                Design the execution steps
              </span>
              <span className="mt-0.5 block text-label leading-relaxed text-muted">
                Advanced. Wire which workers depend on which — this becomes the crew's
                execution plan and wins over the Manager's ordering. Leave off and the
                Manager decides order at run time.
              </span>
            </span>
          </label>

          {advanced && (
            <div className="mt-5 flex flex-col gap-3 border-t border-hairline pt-5">
              {selected.length === 0 ? (
                <p className="text-label text-muted">Select workers above to wire their order.</p>
              ) : (
                selected.map((w) => {
                  const others = selected.filter((o) => o !== w);
                  const agentName = agents.data?.find((a) => a.id === w)?.name ?? w;
                  return (
                    <div key={w} className="flex flex-wrap items-center gap-3">
                      <span className="w-40 shrink-0 truncate text-body text-ink">{agentName}</span>
                      {others.length === 0 ? (
                        <span className="text-label text-muted">runs first</span>
                      ) : (
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-label text-muted">depends on</span>
                          {others.map((o) => {
                            const on = (deps[w] ?? []).includes(o);
                            return (
                              <button
                                key={o}
                                type="button"
                                onClick={() => toggleDep(w, o)}
                                className={cx(
                                  "rounded-full border px-2.5 py-0.5 font-mono text-label transition-colors",
                                  on
                                    ? "border-signal/50 bg-signal-dim text-signal"
                                    : "border-hairline text-muted hover:text-ink",
                                )}
                              >
                                {o}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>

        {error && <InlineError message={error} />}

        <div className="flex items-center justify-end gap-3 border-t border-hairline pt-5">
          <Button variant="ghost" onClick={() => navigate(-1)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={save} disabled={!canSave}>
            {saving ? "Saving…" : editing ? "Save changes" : "Create crew"}
          </Button>
        </div>
      </div>
    </div>
  );
}
