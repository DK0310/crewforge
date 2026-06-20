/*
 * The app shell: a quiet fixed sidebar on desktop that collapses to a slide-in
 * drawer (with a top bar) under md. The app opens straight into work — no
 * marketing landing. Standard nav affordance; the tool disappears into the task.
 */
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";
import type { ComponentType, SVGProps } from "react";
import { IconCompose, IconHistory, IconHome, IconLibrary } from "./icons";
import { cx } from "./ui";

interface NavItem {
  to: string;
  label: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
  end?: boolean;
}

const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", Icon: IconHome, end: true },
  { to: "/compose", label: "Compose", Icon: IconCompose },
  { to: "/runs", label: "History", Icon: IconHistory },
  { to: "/library", label: "Library", Icon: IconLibrary },
];

function Wordmark() {
  return (
    <div className="flex items-center gap-2.5 px-3 py-1">
      <img src="/forge.svg" alt="" width={26} height={26} className="rounded-md" />
      <span className="text-title font-semibold tracking-tight text-ink">CrewForge</span>
    </div>
  );
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5">
      {NAV.map(({ to, label, Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cx(
              "group flex items-center gap-3 rounded-md px-3 py-2 text-body transition-colors duration-150",
              isActive ? "bg-surface-2 text-ink" : "text-muted hover:bg-surface-2/60 hover:text-ink",
            )
          }
        >
          {({ isActive }) => (
            <>
              <Icon
                width={18}
                height={18}
                className={isActive ? "text-signal" : "text-muted group-hover:text-ink"}
              />
              {label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function MenuIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden {...props}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}

export function AppShell() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  // Close the mobile drawer on route change.
  useEffect(() => setOpen(false), [location.pathname]);

  const sidebarBody = (
    <div className="flex h-full flex-col gap-6 px-3 py-5">
      <Wordmark />
      <NavItems onNavigate={() => setOpen(false)} />
      <div className="mt-auto px-3">
        <p className="text-label leading-relaxed text-muted">
          Local-first multi-agent orchestration. Runs stream live; nothing leaves your machine.
        </p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-bg text-ink">
      {/* Desktop rail */}
      <aside className="fixed inset-y-0 left-0 z-(--z-sticky) hidden w-60 border-r border-hairline bg-surface/40 md:block">
        {sidebarBody}
      </aside>

      {/* Mobile top bar */}
      <header className="fixed inset-x-0 top-0 z-(--z-sticky) flex items-center justify-between border-b border-hairline bg-surface/80 px-2 py-2 backdrop-blur-sm md:hidden">
        <Wordmark />
        <button
          onClick={() => setOpen(true)}
          aria-label="Open navigation"
          aria-expanded={open}
          className="grid size-11 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-ink"
        >
          <MenuIcon />
        </button>
      </header>

      {/* Mobile drawer */}
      {open && (
        <button
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-(--z-modal-backdrop) bg-bg/70 md:hidden"
        />
      )}
      <aside
        className={cx(
          "fixed inset-y-0 left-0 z-(--z-modal) w-64 border-r border-hairline bg-surface transition-transform duration-200 ease-out md:hidden",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        aria-hidden={!open}
      >
        {sidebarBody}
      </aside>

      <main className="md:pl-60">
        <div className="mx-auto min-h-screen w-full max-w-5xl px-5 pt-20 pb-10 sm:px-8 md:pt-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
