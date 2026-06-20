"""The planner — a pure function turning dependencies into execution waves.

No I/O, no LLM, no clock: same inputs -> same waves, so it is trivially
unit-testable. Precedence (highest wins):

  1. explicit execution_plan  (user, advanced mode) — wins
  2. consumes/produces inference (from agent I/O contracts)
  3. a single all-parallel wave (fallback)

Cycles raise `PlanError` naming the agents involved — never loop forever.

(The Manager-decided ordering slot from the design sits *between* 1 and 2
conceptually; in v1 the graph topology is fixed at build time from config, so the
Manager writes task descriptions but does not reshape waves. See ARCHITECTURE.md
"Design decisions".)
"""

from __future__ import annotations

from backend.app.models import AgentConfig, DependencySpec


class PlanError(Exception):
    """Raised on an unsatisfiable plan (e.g. a dependency cycle)."""


def dependency_map(
    workers: list[str],
    explicit_plan: list[DependencySpec] | None,
    agents: dict[str, AgentConfig],
) -> dict[str, set[str]]:
    """Return `{worker: set(of worker ids it depends on)}`.

    Explicit plan wins; otherwise dependencies are inferred from consumes/produces;
    otherwise every worker is independent.
    """
    wset = set(workers)

    if explicit_plan:
        deps: dict[str, set[str]] = {w: set() for w in workers}
        for spec in explicit_plan:
            if spec.agent not in wset:
                raise PlanError(f"execution_plan references unknown worker '{spec.agent}'")
            for dep in spec.depends_on:
                if dep not in wset:
                    raise PlanError(
                        f"worker '{spec.agent}' depends_on unknown worker '{dep}'"
                    )
            deps[spec.agent] = set(spec.depends_on)
        return deps

    # consumes/produces inference: a worker depends on whoever produces a field
    # it consumes.
    producers: dict[str, set[str]] = {}
    for w in workers:
        for field in agents[w].produces:
            producers.setdefault(field, set()).add(w)

    deps = {w: set() for w in workers}
    for w in workers:
        for field in agents[w].consumes:
            for producer in producers.get(field, ()):
                if producer != w:
                    deps[w].add(producer)
    return deps


def resolve(
    workers: list[str],
    explicit_plan: list[DependencySpec] | None,
    agents: dict[str, AgentConfig],
) -> list[list[str]]:
    """Return execution waves: a list of waves, each a list of worker ids that
    run in parallel. Later waves wait for all earlier ones.
    """
    deps = dependency_map(workers, explicit_plan, agents)
    return _waves(workers, deps)


def _waves(workers: list[str], deps: dict[str, set[str]]) -> list[list[str]]:
    """Kahn-style layered topological sort. Input order is preserved within a
    wave for stable, legible output.
    """
    remaining = set(workers)
    resolved: set[str] = set()
    waves: list[list[str]] = []

    while remaining:
        layer = [w for w in workers if w in remaining and deps[w] <= resolved]
        if not layer:
            cycle = ", ".join(sorted(remaining))
            raise PlanError(f"Dependency cycle among workers: {cycle}")
        waves.append(layer)
        resolved |= set(layer)
        remaining -= set(layer)

    return waves
