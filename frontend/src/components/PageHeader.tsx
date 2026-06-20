import type { ReactNode } from "react";

/** Page title block. No all-caps tracked eyebrow (No-Eyebrow Rule); hierarchy
 *  comes from size and weight. An optional kicker is a plain mono breadcrumb. */
export function PageHeader({
  kicker,
  title,
  subtitle,
  actions,
}: {
  kicker?: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="flex flex-col gap-1.5">
        {kicker && <span className="font-mono text-label text-muted">{kicker}</span>}
        <h1 className="text-display font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="max-w-2xl text-body text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}
