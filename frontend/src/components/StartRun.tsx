/*
 * The fast path to a run: pick a crew, write a prompt, optionally attach a file,
 * go. On submit it starts the run and navigates to the live run view. This is
 * the dashboard's center of gravity — composing is calm, but starting is one move.
 */
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { CrewSummary } from "../types";
import { Button, Field, InlineError, Select, Textarea, cx } from "./ui";
import { IconPlay, IconUpload, IconX } from "./icons";

export function StartRun({
  crews,
  defaultCrewId,
}: {
  crews: CrewSummary[];
  defaultCrewId?: string;
}) {
  const navigate = useNavigate();
  const fileInput = useRef<HTMLInputElement>(null);
  const [crewId, setCrewId] = useState(defaultCrewId ?? crews[0]?.id ?? "");
  const [prompt, setPrompt] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canRun = crewId && prompt.trim().length > 0 && !submitting;

  const submit = async () => {
    if (!canRun) return;
    setSubmitting(true);
    setError(null);
    try {
      const { run_id } = file
        ? await api.startRunWithFile(crewId, prompt.trim(), file)
        : await api.startRun(crewId, prompt.trim());
      navigate(`/run/${run_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start the run.");
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 rounded-lg border border-hairline bg-surface p-6">
      <div className="grid gap-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
        <Field label="Crew" hint="The Manager and Leader are built in — you compose the workers.">
          <Select value={crewId} onChange={(e) => setCrewId(e.target.value)} disabled={!crews.length}>
            {crews.length === 0 && <option value="">No crews yet</option>}
            {crews.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} · {c.workers.length} worker{c.workers.length === 1 ? "" : "s"}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <Field label="Prompt" hint="What should the crew investigate or produce?">
        <Textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
          }}
          rows={4}
          placeholder="e.g. Investigate failed SSH logins from 203.0.113.7 on web-01."
        />
      </Field>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <input
            ref={fileInput}
            type="file"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          {file ? (
            <span className="inline-flex items-center gap-2 rounded-md border border-hairline bg-surface-2 px-3 py-1.5 text-label text-ink">
              <span className="font-mono text-muted">file</span>
              <span className="max-w-50 truncate">{file.name}</span>
              <button
                onClick={() => {
                  setFile(null);
                  if (fileInput.current) fileInput.current.value = "";
                }}
                className="-mr-1.5 grid size-7 place-items-center rounded text-muted hover:bg-bg hover:text-ink"
                aria-label="Remove file"
              >
                <IconX width={15} height={15} />
              </button>
            </span>
          ) : (
            <Button variant="ghost" size="sm" onClick={() => fileInput.current?.click()}>
              <IconUpload width={16} height={16} />
              Attach file
            </Button>
          )}
          <span className="text-label text-muted">optional source material</span>
        </div>

        <Button variant="primary" onClick={submit} disabled={!canRun} className={cx(!canRun && "")}>
          <IconPlay width={16} height={16} />
          {submitting ? "Starting…" : "Run crew"}
        </Button>
      </div>

      {error && <InlineError message={error} />}
    </div>
  );
}
