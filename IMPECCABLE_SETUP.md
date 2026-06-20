# Impeccable Setup

CrewForge uses **[Impeccable](https://github.com/pbakaus/impeccable)** as its frontend design authority. It replaces Anthropic's `frontend-design` skill (which it is built on and supersedes). The coding agent does not design UI ad hoc — all look-and-feel goes through Impeccable's commands and its `PRODUCT.md` / `DESIGN.md` context.

This file is the **one-time, run-on-your-machine** setup. The commands below are not run by the in-repo agent for you; run them yourself in the project root.

## Requirements

- Node.js (for `npx` and Impeccable's scripts/detectors).
- Claude Code (this repo's harness). Impeccable also supports Cursor, Codex, Gemini CLI, etc.

## 1. Install into the project

From the repository root:

```bash
npx impeccable install
```

It detects your harness folders (e.g. `.claude`), lets you confirm or customize providers, and asks project-vs-global — choose **project** so the install lives in this repo. To skip the prompts:

```bash
npx impeccable install --providers=claude --scope=project
```

This installs Impeccable under `.agents/skills/impeccable/` and wires the provider-native hooks for Claude Code. **Reload Claude Code afterward** so it picks up the new skill and `/impeccable` command.

## 2. Initialize design context

Inside Claude Code, run:

```
/impeccable init
```

`init` asks whether the surface is **brand** (marketing/landing — design *is* the product) or **product** (app UI/dashboard/tool — design *serves* the product). **CrewForge is a `product` surface** — it's an app UI: a crew composer and a live run dashboard. Pick `product`.

`init` writes:
- **`PRODUCT.md`** — audience, product lane, voice, anti-references.
- **`DESIGN.md`** — colors, type, components, the design system every later command reads.

Commit both. They are the durable design context for the project.

## 3. Use it while building UI

The frontend workflow (also documented in the `crewforge-frontend` skill):

| Step | Command | When |
|---|---|---|
| Plan | `/impeccable shape` | Before writing any UI — plan UX/IA first. |
| Build | `/impeccable craft` | The full shape-then-build flow with visual iteration. |
| Review | `/impeccable critique` | UX review: hierarchy, clarity, resonance. |
| Review | `/impeccable audit` | Technical checks: a11y, performance, responsive. |
| Ship | `/impeccable polish` | Final pass + design-system alignment before shipping. |

Targeted commands as needed: `bolder`, `quieter`, `distill`, `animate`, `colorize`, `typeset`, `layout`, `harden`, `onboard`, `clarify`, `adapt`, `optimize`, `live`. Full list: `/impeccable` or the project README.

## 4. Keep it updated

```bash
npx impeccable update
```

## How this maps to the rest of the repo

- **`crewforge-frontend` skill** — owns the *data flow* (SSE client, wave/agent run view, crew composer). For *appearance*, it defers to Impeccable.
- **`BUILD_SPEC.md` / `ARCHITECTURE.md`** — the frontend file tree and components. Their *structure* is specified there; their *visual language* conforms to Impeccable.
- **`CLAUDE.md`** — instructs the agent to route all UI styling through Impeccable, never invent its own.

## Note on what lives where

Impeccable installs to **`.agents/skills/impeccable/`**, not `.claude/skills/`. That is intentional — it ships scripts (context detection, palette seeding, 44 deterministic detector rules, live browser mode) that need to live as a real package, not a markdown-only skill. Leave it where the installer puts it.
