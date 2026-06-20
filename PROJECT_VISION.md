# Project Vision

## What this is

A **local-first, multi-agent orchestration platform** with a web UI. Users build "crews" of AI agents that collaborate to solve a problem, then watch the agents work in real time as the answer streams in.

It is a spiritual successor to an earlier SOC-automation project (a fixed sequential pipeline built on CrewAI + Ollama that processed Wazuh alerts). This project generalizes that idea: instead of one hard-coded pipeline, the user composes their own crews through a UI, and the orchestration is hierarchical rather than a flat sequence.

The product is **domain-agnostic** at its core — the orchestration engine knows nothing about cybersecurity. Security (threat intel, triage, forensics) is just the first set of agents we ship as examples. The same engine could run a research crew, a writing crew, or anything else.

## Who it's for

The developer building it (a CS student strong in Python and AI tooling) is the primary user, but the UI is designed so that a non-technical person can compose and run a crew without understanding dependency graphs or prompt engineering. Technical users get an "advanced" path to design execution order explicitly.

## The core mental model

A **crew** is a team of AI agents. Every crew has three kinds of members:

1. **Manager** — a built-in role, always present, cannot be removed. It reads the user's input (and the crew's memory of past runs), understands the problem, and breaks it into specific tasks for the workers. When the user has not specified an execution order, the Manager also decides which workers depend on which.

2. **Workers** — the agents the user picks for the crew. Each worker does one job (e.g. "Triage", "Threat Intel", "Forensics"). Workers can depend on each other's output; independent workers run in parallel. Each worker returns **structured JSON** so downstream workers can read its output reliably.

3. **Leader** — a built-in role, always present, cannot be removed. It collects every worker's output, synthesizes a single coherent answer, and returns it to the user as **free-form text**. After the run, the Leader's conclusion is summarized and written into the crew's memory.

So the flow of any run is: **Manager dispatches → Workers execute (in a dependency graph, parallel where possible) → Leader synthesizes → result streams to the user → memory is updated.**

## What makes it distinct

- **Hierarchical, not flat.** A dedicated Manager plans and a dedicated Leader synthesizes. Workers are the interchangeable middle.
- **Two ways to set execution order.** Beginners let the Manager decide. Advanced users design the steps themselves; their plan always wins over the Manager's.
- **Per-crew memory that persists across runs.** Each crew remembers its own past runs (via a vector store) and the Manager pulls relevant past context into new runs. Crews do not share memory with each other.
- **Local-first.** All inference and embeddings run on a local Ollama instance. No cloud LLM dependency. This matters for the security use case (sensitive data never leaves the machine) and for cost.
- **Watch it think.** The UI streams tokens live and shows which agents are running in which wave, so the orchestration is legible, not a black box.

## Design principles

- **The engine is generic; agents carry the domain knowledge.** Keep orchestration logic free of any security-specific assumptions. Domain behavior lives in agent definitions (prompts, tools), not in the engine.
- **Configuration is data, not code.** Agents and crews are defined in YAML files that humans can read and edit, and that the UI can generate. Adding an agent should never require touching the engine.
- **Don't burden the user with plumbing.** Composing a crew is choosing agents and naming the crew. Dependency wiring is optional and hidden behind an advanced mode.
- **Structured between agents, human between system and user.** Agent-to-agent communication is JSON (machine-reliable). The final answer to the user is prose (human-friendly).
- **Build for the next feature without building it now.** Tools (external API calls an agent can invoke, e.g. a MITRE ATT&CK mapping lookup) are out of scope for v1, but every schema and interface must leave a clean seam to add them later.

## Out of scope for v1

- Tool execution by agents (schema reserved, not implemented).
- Human-in-the-loop interruption mid-run (SSE one-way streaming is sufficient; revisit with WebSocket later if needed).
- Background job queue (runs are synchronous + streamed).
- Multi-user accounts, auth, cloud deployment.
- Cloud LLM providers (Ollama only for now).

## Lineage / context

The earlier project ("soar-crew") was a CrewAI-based sequential SOC pipeline: triage → false-positive review → threat-intel enrichment → forensic investigation → incident-response planning → SOC-leader synthesis, fed by Wazuh alerts, enriched via VirusTotal and AbuseIPDB, with a Chroma knowledge base. This project deliberately moves **off CrewAI** (to remove framework lock-in and gain control) and **onto LangGraph** for orchestration, while keeping the local Ollama + Chroma foundation the developer already knows.
