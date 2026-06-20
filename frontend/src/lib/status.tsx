/*
 * Single source for how a status looks. Per the Status-Is-Not-Only-Color Rule,
 * every state carries an icon and a label in addition to color, so the run view
 * is legible without relying on green-vs-red.
 */
import type { ComponentType, SVGProps } from "react";
import type { AgentStatus, RunStatus } from "../types";
import { IconAlert, IconCheck, IconDot, IconPulse, IconStop } from "../components/icons";

export interface StatusMeta {
  label: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
  /** Tailwind text-color class for the icon/accent. */
  color: string;
  /** True while work is actively happening (drives the live amber treatment). */
  live: boolean;
}

export const AGENT_STATUS: Record<AgentStatus, StatusMeta> = {
  pending: { label: "Pending", Icon: IconDot, color: "text-muted", live: false },
  running: { label: "Running", Icon: IconPulse, color: "text-signal", live: true },
  done: { label: "Done", Icon: IconCheck, color: "text-done", live: false },
  error: { label: "Error", Icon: IconAlert, color: "text-error", live: false },
};

export const RUN_STATUS: Record<RunStatus, StatusMeta> = {
  pending: { label: "Queued", Icon: IconDot, color: "text-muted", live: false },
  running: { label: "Running", Icon: IconPulse, color: "text-signal", live: true },
  done: { label: "Done", Icon: IconCheck, color: "text-done", live: false },
  error: { label: "Error", Icon: IconAlert, color: "text-error", live: false },
  cancelled: { label: "Cancelled", Icon: IconStop, color: "text-muted", live: false },
};
