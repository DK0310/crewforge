<!-- SEED: re-run /impeccable document once there's code to capture the actual tokens and components. -->
---
name: CrewForge
description: A local-first multi-agent orchestration instrument — compose crews, watch waves run live.
---

# Design System: CrewForge

## 1. Overview

**Creative North Star: "The Mission Control Reading Room"**

CrewForge is an instrument, not a product pitch. The North Star holds two ideas in tension and refuses to drop either: the *reading room* (refined, editorial, spacious, calm — the place you compose and review) and *mission control* (a dark, focused environment where you watch something happen live, status legible at a glance). The surface is a quiet near-black; the editorial clarity of excellent documentation (Stripe, Notion) governs the type and spacing; the live, data-honest sensibility of good observability tooling (Vercel) governs the run view. Warmth is carried by a single amber signal and by typography — never by the surface.

The system is **Restrained by default**: a near-black surface, a cooler-neutral panel layer, generous whitespace, and exactly one accent — warm amber — held in reserve for the things that are *live or chosen*. Amber is the color of an active wave, a running agent, the primary action, the current selection. Its rarity is the entire point: when the waves light up, the eye goes straight to what's happening. Everything else is neutral, and the neutrals do the structural work that gray-on-gray clutter does in lesser tools.

This system explicitly rejects: **toy/playful AI** (chat bubbles, emoji, pastels, gumdrop buttons), **generic SaaS landing slop** (gradient hero, centered metric-card template, cartoon illustration, rounded-purple-everything), **heavy enterprise console** (gray-on-gray, dropdown soup, cramped admin density), and **cream/warm-minimal editorial** (the beige-paper, parchment look — wrong register for a live operational tool and a saturated AI default). Editorial *clarity*, yes; editorial *warmth-as-surface-texture*, never.

**Key Characteristics:**
- Dark-first near-black surface; the run view is the hero, everything else serves it.
- One amber signal, reserved for live/active/selected state and primary action (≤10% of any screen).
- Editorial spacing and hierarchy over chrome — whitespace, not borders and nested cards.
- Single well-tuned sans for UI; monospace for the data (token streams, agent IDs, JSON).
- Motion reports real state (an agent waking, a wave completing); it is never decoration.
- WCAG AA, state never color-only, reduced-motion honored.

## 2. Colors

A focused near-black surface with cool-neutral panels, one warm-amber signal, and semantic status hues that stay quiet until they matter. `[Exact OKLCH values to be resolved during implementation — seed anchor: amber primary at oklch(0.842 0.165 91.3).]`

### Primary
- **Live Amber** (`[oklch ~0.84 0.165 91° — to be resolved]`): The signal color. Reserved for *live or chosen* state — an active wave, a running agent's pulse, the primary action button, the current selection, focus accents. Never decorative. Carries white/near-white text when used as a filled button (Helmholtz-Kohlrausch: saturated mid-luminance fills take light text). On the dark surface, amber may also appear as a glow/outline rather than a fill. The One Voice Rule governs its budget.

### Neutral
- **Near-Black Surface** (`[oklch ~0.16 0 0 — to be resolved; chroma 0, no hue tint]`): The app background. A true focused dark, not a tinted warm-black — the warmth lives in amber, not here.
- **Panel** (`[oklch ~0.20–0.22, cool-neutral — to be resolved]`): A second neutral layer for the sidebar, toolbars, agent panels, and cards. Slightly lifted from the surface; cooler, not warmer.
- **Ink** (`[oklch ~0.96 — to be resolved]`): Primary body and heading text. Must hit ≥4.5:1 on the surface (target ≥7:1 for prose).
- **Muted Ink** (`[oklch ~0.72 — to be resolved]`): Secondary text, labels, metadata. Held to ≥4.5:1 — no light-gray-for-elegance that fails on dark. Placeholder text gets the same treatment, not a fainter one.
- **Hairline** (`[oklch ~0.28 — to be resolved]`): 1px dividers and borders only. Structure comes from spacing first, hairlines second.

### Tertiary (status — `[to be resolved during implementation]`)
- **Done Green** (`[oklch ~0.70 ~0.15 150° — to be resolved]`): A completed agent/wave. Quiet, not celebratory.
- **Error Red** (`[oklch ~0.62 ~0.20 25° — to be resolved]`): A failed agent or run.
- **Pending Neutral** (uses Muted Ink): Not-yet-started state reads as muted, not colored.

### Named Rules
**The One Voice Rule.** Amber appears on ≤10% of any given screen. It marks what is live, primary, or selected — nothing else. The moment amber becomes decoration, the run view loses its ability to say "look here."

**The Warmth-Lives-in-the-Signal Rule.** The surface is chroma-0 near-black. Warmth is forbidden in the background. It is carried by amber and by type, the way Stripe is warm via its accent and Vercel is cool via its blue while both keep a pure surface. Tinting the dark surface warm is the cream/AI-slop move by another route.

**The Status-Is-Not-Only-Color Rule.** Every agent state (pending / running / done / error) carries a shape, icon, or label in addition to its hue. Color-blind operators read state without relying on green-vs-red.

## 3. Typography

**Display Font:** `[single well-tuned UI sans — e.g. Inter / Geist — to be chosen at implementation]` (with `system-ui, sans-serif` fallback)
**Body Font:** same family, lighter weights
**Label/Mono Font:** `[a tuned monospace — e.g. JetBrains Mono / Geist Mono / Berkeley Mono — to be chosen at implementation]` (with `ui-monospace, monospace` fallback)

**Character:** One family carries the entire UI — headings, labels, buttons, body — tuned and weight-differentiated rather than paired with a second display face (a serif display would read as marketing, not instrument). The monospace is not decoration: it is the *voice of the machine*. Anything the engine emits — streaming tokens, agent IDs, the `__manager__`/`__leader__` sentinels, JSON worker output, run IDs, wave structure — is set in mono so it is visually distinct from the human-authored UI chrome around it.

### Hierarchy
Fixed rem scale (product UI views at consistent DPI — no fluid clamp headings that shrink in a sidebar). Tight ratio (~1.2) — this UI has many type elements; exaggerated contrast is noise.
- **Display** (`[weight ~600, ~1.75rem, lh 1.2 — to be resolved]`): Page titles (Dashboard, a crew name). The largest type in the app; restrained by app-UI standards.
- **Headline** (`[weight ~600, ~1.25rem — to be resolved]`): Section and panel headers (a wave label, "Final Answer").
- **Title** (`[weight ~500, ~1rem — to be resolved]`): Agent names on run panels, crew cards.
- **Body** (`[weight ~400, ~0.9375rem, lh ~1.6 — to be resolved]`): Prose — the Leader's final answer, descriptions. Capped 65–75ch for readable prose.
- **Label** (`[weight ~500, ~0.8125rem — to be resolved]`): Status pills, metadata, form labels. Sentence case, not all-caps tracked eyebrows.
- **Mono / Data** (`[~0.875rem, lh ~1.5 — to be resolved]`): Token streams, JSON output, IDs. Denser line-height; may run wider than 75ch (it's data, not prose).

### Named Rules
**The Machine-Speaks-Mono Rule.** Everything the engine emits is monospace; everything the human-facing UI says is sans. The reader can tell model output from app chrome at a glance, without a label.

**The No-Eyebrow Rule.** No tiny uppercase tracked kicker above sections. Hierarchy comes from size and weight, not from 2023-era all-caps labels.

## 4. Elevation

Flat by default, with tonal layering for structure. On a dark surface, depth is built from **lightness steps** (surface → panel → lifted panel), not drop shadows — heavy shadows on dark read as muddy and 2014-app. Shadows appear only as a response to *state*: a soft amber-tinted glow under a live/running element, a subtle lift on hover or focus. Resting surfaces cast nothing.

### Shadow Vocabulary (sparingly)
- **Live Glow** (`[box-shadow: 0 0 0 1px amber, 0 4px 24px amber/15% — to be resolved]`): A diffuse amber halo under the *active* agent/wave only. This is the one place glow is earned — it is the visual heartbeat of a live run.
- **Hover Lift** (`[box-shadow: 0 2px 12px rgba(0,0,0,0.4) — to be resolved]`): A quiet lift on interactive cards on hover/focus-visible.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest; depth is tonal (lightness steps), not shadow. A shadow is a response to state (live, hover, focus), never ambient decoration. Audit test: if a resting card has a drop shadow, it's wrong.

## 5. Components

<!-- No component library exists yet — components land on the next Scan-mode run, built to the rules above. Documented here only as intent. -->

`[Components to be specified during implementation. The agent-panel — a per-worker card showing status pill, live mono token stream, and final JSON — is the project's signature component and should be designed first, to the One Voice and Machine-Speaks-Mono rules.]`

## 6. Do's and Don'ts

### Do:
- **Do** keep the surface a chroma-0 near-black; let amber and type carry all warmth (the Warmth-Lives-in-the-Signal Rule).
- **Do** reserve amber for live / active / selected / primary-action only — ≤10% of any screen (the One Voice Rule).
- **Do** set everything the engine emits (tokens, JSON, IDs, sentinels) in monospace; everything human-authored in sans (the Machine-Speaks-Mono Rule).
- **Do** convey agent status with shape/icon/label *and* color, never color alone.
- **Do** build depth from tonal lightness steps; reserve shadow/glow for live and hover/focus state.
- **Do** spend the design budget on the run view — it is the hero; waves laid top-to-bottom mirror execution.
- **Do** hold muted and placeholder text to ≥4.5:1 on the dark surface; no light-gray-for-elegance.
- **Do** honor `prefers-reduced-motion` — token streaming stays readable as a crossfade/instant update with motion off.

### Don't:
- **Don't** make it look like a **toy/playful AI app** — no chat bubbles, emoji, pastels, or gumdrop buttons. This is an instrument.
- **Don't** make it look like **generic SaaS landing slop** — no gradient hero, no centered metric-card template, no cartoon illustration, no rounded-purple-everything. The app opens into work, not a pitch.
- **Don't** make it look like a **heavy enterprise console** — no gray-on-gray clutter, dropdown soup, or cramped 1990s admin density.
- **Don't** make it look like **cream/warm-minimal editorial** — no beige/parchment/paper surface. Editorial clarity, not editorial warmth-as-texture.
- **Don't** tint the dark surface warm "because the brand feels warm" — that's the cream move by another route.
- **Don't** use `background-clip: text` gradient text, decorative glassmorphism, side-stripe `border-left` accents, or the hero-metric template (shared absolute bans).
- **Don't** use display/serif fonts or all-caps tracked eyebrows in UI labels and buttons.
- **Don't** put ambient drop shadows on resting surfaces, or animate anything that isn't reporting real state.
