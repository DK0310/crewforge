---
name: crewforge-agents
description: Use when defining or validating agent and crew YAML, writing Pydantic config models, enforcing the JSON contract between workers, or reserving the seam for future tools
---

# CrewForge — Agents & Config Skill

This skill holds the **reusable patterns for configuration-as-data**: how agents and crews are described in YAML, how those map to Pydantic models, how a worker's JSON output is validated, and how the tools seam stays open without being built.

> **The concrete schemas live in [BUILD_SPEC.md](../../../BUILD_SPEC.md) / [ARCHITECTURE.md](../../../ARCHITECTURE.md)** — the exact fields of `AgentConfig`, `CrewConfig`, and the example agents/crews checked into `config/`. This skill shows the *techniques and rules*; consult those for the actual field list.

---

## The Golden Rule of Config

**An agent is data. Adding or changing one is editing YAML — never editing engine code.** If a behavior change requires touching `engine/`, it isn't an agent change; it's an engine change, and it must stay domain-agnostic. The engine reads config; it never embeds domain knowledge.

---

## Three kinds of config

| File | Describes | Who edits |
|---|---|---|
| `config/agents/{id}.yaml` | one worker: prompt, model, I/O contract, output schema | agent author (or UI) |
| `config/crews/{id}.yaml` | a crew: which workers, optional explicit plan, role overrides | crew composer (or UI) |
| `config/system_roles/{manager,leader}.yaml` | the built-in role prompts | advanced user |

Workers are the only thing a crew lists. Manager and Leader are injected by the engine for every crew — they are never listed in a crew's `workers`.

---

## Agent YAML — the anatomy

Every agent carries four things the engine relies on:

1. **Identity + prompt** — `id`, `name`, `description` (shown in the UI picker), `system_prompt` (the role/goal/backstory).
2. **Model** — the Ollama tag; falls back to a default if omitted.
3. **I/O contract** — `consumes` / `produces`: named fields it needs upstream and emits downstream. The planner uses these to infer order when the user gives none. Both optional.
4. **Output schema** — the JSON shape this worker must return, validated after generation.
5. **Tools seam** — `tools: []`, always present, empty in v1.

```yaml
id: triage
name: Triage
description: First-pass classification and IOC extraction.
model: llama3.1:8b
system_prompt: >
  You are a triage analyst. Classify the input and extract any indicators
  of compromise. Return ONLY JSON matching the required schema.
consumes: []
produces: [extracted_iocs]
tools: []
output_schema:
  type: object
  required: [summary, extracted_iocs]
  properties:
    summary:        { type: string }
    extracted_iocs: { type: array, items: { type: string } }
```

---

## Pydantic models — validate on load, fail with a clear message

Config is loaded into Pydantic models. Validation happens once, at load, and errors must name the offending file and field — a typo in YAML should never surface as a confusing runtime crash three layers deep.

```python
class AgentConfig(BaseModel):
    id: str
    name: str
    description: str
    model: str | None = None
    system_prompt: str
    consumes: list[str] = []
    produces: list[str] = []
    tools: list[ToolSpec] = []          # reserved; empty in v1
    output_schema: dict                 # JSON Schema the worker must satisfy

# loader
def load_agent(path: Path) -> AgentConfig:
    try:
        return AgentConfig(**yaml.safe_load(path.read_text()))
    except ValidationError as e:
        raise ConfigError(f"Invalid agent config {path.name}: {e}") from e
```

Rules:
- **`id` must match the filename stem.** Check it on load.
- **Cross-check crew references.** When loading a crew, every id in `workers` must resolve to an existing agent file; surface a clear error if not.
- **Validate the plan against the workers.** Every agent in a crew's `execution_plan` must be in its `workers`, and every `depends_on` id too.

---

## The JSON contract between workers

Worker-to-worker communication is **validated JSON**, never prose. This is what makes downstream workers able to rely on upstream output.

- Each worker returns JSON matching its `output_schema`.
- After generation, **parse and validate**. On malformed JSON, **retry the generation once** (LLMs occasionally emit a stray prefix or trailing comma). If it still fails, record an error result for that agent — do not pass unparseable text downstream.
- A downstream worker receives only the fields it `consumes`, pulled from the upstream agent's validated `output`.

```python
def validate_json(raw: str, schema: dict) -> dict:
    data = extract_json(raw)            # tolerate code fences / preamble
    jsonschema.validate(data, schema)   # raises on mismatch
    return data
```

The Leader is the exception: it emits **prose**, not schema-bound JSON, because its audience is the user.

---

## Reserving the tools seam (don't build it in v1)

Tools (external API calls an agent can invoke — e.g. a MITRE ATT&CK lookup, VirusTotal, AbuseIPDB) are out of scope for v1. Keep the door open without faking it:

- Keep `tools: []` in every agent schema.
- Define a minimal `ToolSpec` model (name, description, params) so the field is typed, but don't wire execution.
- In the worker node, leave a clear, commented seam where tool invocation would slot in.
- Don't implement tool-calling, tool routing, or a tool registry yet. When asked to "add tools," that's a new milestone, not a v1 task.

---

## Review Checklist — Config Smells

| ❌ Smell | ✅ Correct | Why |
|---|---|---|
| Agent behavior hard-coded in the engine | Put it in the agent's `system_prompt` | Config-as-data, domain-agnostic engine |
| Manager or Leader listed in a crew's `workers` | They're injected by the engine | Fixed system roles |
| Worker returning prose for another worker | Return JSON matching `output_schema` | Reliable agent-to-agent contract |
| No schema validation on worker output | Validate, repair once, then error | Don't propagate garbage |
| `id` not matching filename | Enforce on load | Predictable lookups |
| Crew referencing a non-existent worker | Validate references on load, clear error | Fail early and legibly |
| `execution_plan` referencing a non-worker | Validate plan ⊆ workers on load | Catch wiring mistakes early |
| Building tool-calling in v1 | Reserve `tools: []` + a commented seam | Scope discipline |
| YAML errors surfacing as deep runtime crashes | Catch at load, name file + field | Debuggability |

---

## Cross-References

- **Golden rules, where config lives** → `crewforge-architecture`
- **How the planner reads `consumes`/`produces`, how workers run** → `crewforge-orchestration`
- **Exact AgentConfig/CrewConfig fields, example files** → [BUILD_SPEC.md](../../../BUILD_SPEC.md) / [ARCHITECTURE.md](../../../ARCHITECTURE.md)
- **CRUD endpoints that read/write these YAML files** → `crewforge-api`
