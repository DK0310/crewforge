/*
 * The Leader is the one place the user reads free text, not JSON — so its
 * output renders as prose in sans, deliberately breaking the Machine-Speaks-
 * Mono rule that governs every worker. The synthesis streams in live, then
 * settles to the final answer.
 */
import type { AgentLane } from "../hooks/useRunStream";
import { AGENT_STATUS } from "../lib/status";
import { StatusPill, cx } from "./ui";
import { IconLeader } from "./icons";

export function LeaderPanel({
  lane,
  finalAnswer,
}: {
  lane: AgentLane;
  finalAnswer: string | null;
}) {
  const meta = AGENT_STATUS[lane.status];
  const prose = finalAnswer ?? lane.tokens;
  const streaming = meta.live && !finalAnswer;

  return (
    <article
      className={cx(
        "rounded-lg border bg-surface transition-shadow duration-200",
        meta.live ? "live-glow border-transparent" : "border-hairline",
      )}
    >
      <header className="flex items-center justify-between gap-3 border-b border-hairline px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <IconLeader width={18} height={18} className="text-signal" />
          <div>
            <h3 className="text-title font-medium text-ink">Leader</h3>
            <span className="font-mono text-[0.7rem] text-muted">system · synthesis</span>
          </div>
        </div>
        <StatusPill meta={meta} />
      </header>

      <div className="px-5 py-5">
        {prose ? (
          <div className="max-w-[70ch] text-body leading-relaxed whitespace-pre-wrap text-ink">
            {prose}
            {streaming && <span className="stream-caret" aria-hidden />}
          </div>
        ) : (
          <p className="text-body text-muted">
            {lane.status === "pending"
              ? "Waiting for the workers to finish…"
              : "Synthesizing the final answer…"}
          </p>
        )}
      </div>
    </article>
  );
}
