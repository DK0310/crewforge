/*
 * The shared component vocabulary. One button shape, one pill, one field,
 * reused everywhere — consistency over surprise (product register). Depth is
 * tonal (surface lightness steps), not shadow; amber is reserved for primary.
 */
import { cloneElement, isValidElement, useId } from "react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactElement,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import type { StatusMeta } from "../lib/status";

function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

// --- Button ----------------------------------------------------------------

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-md text-label font-medium " +
  "transition-[background-color,border-color,color,transform] duration-150 ease-out " +
  "focus-visible:outline-2 disabled:opacity-45 disabled:pointer-events-none select-none";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-signal text-signal-ink hover:brightness-110 active:brightness-95 active:translate-y-px font-semibold",
  secondary:
    "bg-surface-2 text-ink border border-hairline hover:border-muted/60 active:translate-y-px",
  ghost: "text-muted hover:text-ink hover:bg-surface-2 active:translate-y-px",
  danger:
    "bg-transparent text-error border border-error/40 hover:bg-error/10 active:translate-y-px",
};

export function Button({
  variant = "secondary",
  size = "md",
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md";
}) {
  const sizing = size === "sm" ? "h-9 px-3" : "h-10 px-4";
  return (
    <button className={cx(BUTTON_BASE, BUTTON_VARIANTS[variant], sizing, className)} {...props}>
      {children}
    </button>
  );
}

// --- Status pill -----------------------------------------------------------

export function StatusPill({ meta, className }: { meta: StatusMeta; className?: string }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-label font-medium",
        meta.live
          ? "border-signal/40 bg-signal-dim text-signal"
          : "border-hairline bg-surface-2 " + meta.color,
        className,
      )}
    >
      <meta.Icon width={14} height={14} className={meta.live ? "animate-pulse" : undefined} />
      {meta.label}
    </span>
  );
}

// --- Panel -----------------------------------------------------------------

export function Panel({
  className,
  children,
  as: Tag = "div",
}: {
  className?: string;
  children: ReactNode;
  as?: "div" | "section" | "article";
}) {
  return (
    <Tag className={cx("rounded-lg border border-hairline bg-surface", className)}>{children}</Tag>
  );
}

// --- Form fields -----------------------------------------------------------

export function Field({
  label,
  hint,
  htmlFor,
  children,
}: {
  label: string;
  hint?: string;
  htmlFor?: string;
  children: ReactNode;
}) {
  // Auto-associate the label with its control (and the hint via aria-describedby)
  // by injecting an id into the single child element — no call-site wiring needed.
  const autoId = useId();
  const id = htmlFor ?? autoId;
  const hintId = hint ? `${id}-hint` : undefined;

  let control = children;
  if (isValidElement(children)) {
    const child = children as ReactElement<{ id?: string; "aria-describedby"?: string }>;
    control = cloneElement(child, {
      id: child.props.id ?? id,
      "aria-describedby": [child.props["aria-describedby"], hintId].filter(Boolean).join(" ") || undefined,
    });
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-label font-medium text-ink">
        {label}
      </label>
      {hint && (
        <p id={hintId} className="text-label text-muted">
          {hint}
        </p>
      )}
      {control}
    </div>
  );
}

const INPUT_BASE =
  "w-full rounded-md border border-hairline bg-bg text-body text-ink placeholder:text-muted " +
  "px-3 py-2 transition-colors duration-150 focus:border-signal/60 focus-visible:outline-none";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(INPUT_BASE, props.className)} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx(INPUT_BASE, "resize-y leading-relaxed", props.className)} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={cx(INPUT_BASE, "appearance-none cursor-pointer pr-9", props.className)}
    />
  );
}

// --- States ----------------------------------------------------------------

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cx(
        "inline-block size-4 animate-spin rounded-full border-2 border-hairline border-t-signal",
        className,
      )}
    />
  );
}

export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon?: ReactNode;
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-hairline px-6 py-14 text-center">
      {icon && <div className="text-muted">{icon}</div>}
      <h3 className="text-title font-semibold text-ink">{title}</h3>
      {body && <p className="max-w-sm text-body text-muted">{body}</p>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

export function InlineError({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-error/40 bg-error/10 px-3 py-2 text-label text-ink">
      <span className="mt-0.5 size-1.5 shrink-0 rounded-full bg-error" aria-hidden />
      <span>{message}</span>
    </div>
  );
}

export { cx };
