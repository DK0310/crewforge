# Product

## Register

product

## Users

Technical operators who orchestrate work across multiple AI agents — security analysts, engineers, researchers, and power users running local-first workflows. They run CrewForge on their own machine against a local Ollama model: no cloud, no accounts, data stays put.

Two jobs, two moods:

- **Compose** (deliberate, low-stakes): pick worker agents, name a crew, optionally wire an explicit dependency plan. The user is thinking, not under pressure. The interface should be calm and legible.
- **Run & watch** (live, the moment that matters): trigger a crew and watch a hierarchical run unfold — the Manager plans, workers fan out in parallel "waves," tokens stream live, the Leader synthesizes a final prose answer. This is the product's center of gravity. The user is monitoring something happening *now* and needs to read state at a glance: which wave is active, which agent is thinking, what each produced.

They've used real developer tools and trust earned familiarity over novelty. They are not impressed by decoration; they are impressed by a tool that shows them exactly what is happening and gets out of the way.

## Product Purpose

CrewForge is a local-first multi-agent orchestration platform. It turns a set of YAML-defined agents into a running crew: a built-in Manager that plans, user-chosen Workers that execute in a dependency graph, and a built-in Leader that synthesizes. Runs stream live over SSE; each crew keeps its own persistent memory.

The frontend exists to make orchestration **observable and composable**:

- **Dashboard / app home** — recent runs, crews at a glance, a fast path to start a run. (No marketing landing; the app opens straight into work.)
- **Crew composer** — assemble workers into a crew; a beginner tier (pick + name) by default, an advanced step designer (explicit `depends_on` → execution plan) behind an opt-in. Manager and Leader appear as fixed, non-removable roles.
- **Run view** — the hero. Waves laid out top-to-bottom mirroring execution; per-agent panels with status and live token streams; the Leader's final answer rendered as prose.
- **Run history** — durable past runs, re-openable.
- **Library** — browse and edit the agents and crews (the YAML config, surfaced as UI).

Success: a user composes a crew, runs it, and *understands what happened* — which agents ran when, in what order, what each contributed, and how the final answer was reached — without reading logs.

## Brand Personality

**Refined. Legible. Quietly powerful.** Three words: *considered, transparent, composed.*

The voice is that of a precise instrument, not a hype product and not a sysadmin console. It borrows the spacious, typographic clarity of excellent documentation (Stripe, Notion) and the live, data-honest sensibility of good observability tooling (Vercel) — applied in a dark, focused environment built for watching things run. Editorial restraint over density; whitespace and hierarchy do the work that gray-on-gray clutter does in lesser tools.

Emotional goals: **confidence** (the run is under control and fully visible), **calm** (composing is unhurried and clear), and a small, earned **fascination** when the waves light up and agents stream in parallel. Motion conveys state — an agent waking, a wave completing — never decoration.

## Anti-references

- **Toy / playful AI apps** — no chat bubbles, emoji, pastels, or gumdrop buttons. This is an instrument, not a companion.
- **Generic SaaS landing slop** — no gradient hero, no big centered metric-cards template, no cartoon illustrations, no rounded-purple-everything. The app opens into work, not a pitch.
- **Heavy enterprise console** — no gray-on-gray clutter, dropdown soup, or cramped 1990s admin density. Breathing room is a feature.
- **Cream / warm-minimal editorial** — the beige-paper, parchment, magazine-warm look is the wrong register for a live operational tool and a saturated AI default. Editorial *clarity*, yes; editorial *warmth-as-texture*, no. The surface is a focused dark, not paper.

## Design Principles

1. **The run is the hero.** Every other surface is in service of composing and reviewing runs. When in doubt, spend the design budget on making live execution legible.
2. **Show the structure, honestly.** Waves, dependencies, and per-agent state are the real information. Render the actual execution shape; never fake progress or smooth over what's happening.
3. **Calm to compose, alive to watch.** Two registers in one app: composing is unhurried and quiet; watching is live and responsive. Motion appears only where it reports real state change.
4. **Earned familiarity over novelty.** Standard affordances for standard tasks. The tool should disappear into the task; surprise is reserved for moments, never scattered across pages.
5. **Whitespace and hierarchy, not chrome.** Achieve density through typographic clarity and spacing rhythm, not borders, cards-in-cards, or decoration. Restraint is the house style.

## Accessibility & Inclusion

- **WCAG AA** baseline: body text ≥ 4.5:1 against its background, large/bold text ≥ 3:1. Placeholder and "muted" text held to the same body contrast — no light-gray-for-elegance that fails on the dark surface.
- **Dark-first.** The default theme is a focused dark surface (operators run long, often low-light sessions). A light theme may follow; tokens should not preclude it.
- **State is never color-only.** Agent status (pending / running / done / error) is conveyed by shape, label, or icon in addition to color, for color-blind users.
- **Reduced motion is honored.** Every wave/token/state animation has a `prefers-reduced-motion: reduce` alternative (crossfade or instant). Live token streaming must remain readable without motion.
- **Keyboard reachable.** Composing and navigating runs work from the keyboard; focus states are visible against the dark surface.
