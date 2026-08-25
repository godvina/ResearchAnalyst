# Playbook Planning Agent — Requirements

## Introduction

Today the Investigation Playbook (`frontend/src/lib/playbook/`) is a real multi-step
engine (Dispatcher → Runner → Synthesizer), but the Runner executes a **fixed,
pre-authored step order**. A gate can stop the run, but nothing looks at what a
step *found* and decides the next relevant step. This spec turns that scripted
procedure into a genuine **planning agent**: it takes case variables and, after
each step, plans the next best investigative action based on what it just learned —
while keeping a human in the loop and every conclusion grounded and auditable.

This is an **EXTEND** of the existing engine, not a rebuild. We keep the
Dispatcher, Synthesizer, `CaseFile`, the step-trace UI, the kill-gate discipline,
and the real-data grounding (OFAC, FinCEN citations, signature vectors). We add
three things: an **Agent Library** (reusable, planner-selectable capabilities), a
**hybrid planner** (rules propose the next agent, LLM confirms/narrates), and
**human-in-the-loop** controls (approve / override / inject via a search bar).

## Governing principles (non-negotiable)

- **Search-first, LLM-second** (`vector-search-routing`): tools/agents find the
  signal mathematically; the LLM interprets and narrates — it never scores or
  invents. The planner's default path is **rules-authoritative**; the LLM writes
  the human-readable rationale and may only reorder among rule-legal options.
- **Analytical integrity** (`uts-analytical-integrity`): every produced fact is
  labeled KNOWN vs ASSESSED, stamped with a UTS vector, and marked LIVE vs
  ROADMAP. Subpoena/law-gated feeds are never fabricated.
- **Human accountability**: the analyst — not the AI — owns what enters the case
  file. Accept/reject and injected leads are written to the audit trail.
- **Demo-grade determinism**: the loop is bounded and must never stall or infinite-loop.
- **Reuse-before-build**: no new brief/graph/case components; reuse
  `IntelligenceBrief`, `InvestigationGraph`, `NeedleTag`, `CaseFile`.

## Doctrine framing

The loop is presented as **F3EAD** (Find, Fix, Finish, Exploit, Analyze,
Disseminate) so it reads in the vocabulary IC/HSI buyers use:

- FIND → Dispatch matches the lead to a Play (analyst confirms).
- FIX → planner selects & runs an Agent → OBSERVE the result.
- FINISH → kill-gate / saturation / analyst says "enough".
- EXPLOIT → each result updates case state; analyst can inject via the search bar.
- ANALYZE → LLM narrates what was found and what gap remains.
- DISSEMINATE → Synthesizer → `CaseFile` (the shipped product).

## Requirements

### REQ-1: Agent Library (reusable capabilities)
- A registry (`agents.ts`) of named capabilities, each declaring: `id`, `label`,
  `description`, the bound tool, an **input/precondition contract** (predicate over
  case state), what it **produces** (KNOWN/ASSESSED + UTS vector), cost/latency
  hint, and LIVE-vs-ROADMAP data dependency.
- Agents wrap the EXISTING tools (`calc`, `knn`, `graph.neighbors`, OFAC screen,
  LLM assessor) — no new detection logic.
- Agents are **domain-agnostic where possible** (OwnershipExpander, SanctionsScreener,
  SignatureMatcher, CapacityCalculator, TimingAssessor) so new Playbooks compose
  existing agents rather than write new code.
- `listAgents()` / `getAgent(id)` exposed; the registry is the single source of
  truth for the Agent Library UI.

### REQ-2: Hybrid Planner (plan → act → observe)
- A `planner.ts` loop: given current case **state** (vars, KNOWN/ASSESSED evidence,
  entities, signatures, open gaps, budget), it selects the **next best Agent** by
  the biggest current gap (rules), then the LLM **confirms/reorders among
  rule-legal options** and writes the rationale.
- Emits a `PlannerDecision` per step: chosen agent, the gap it closes, the
  alternatives considered, and confidence.
- **Bounded**: max-step budget, kill-gate honored, and a saturation stop (no new
  entities/signatures → synthesize).
- Deterministic fallback: if the LLM is unavailable, the rules alone drive the loop.

### REQ-3: Planner-driven Runner (ML Play first)
- Refactor `runner.ts` so the money-laundering Play runs the planner loop:
  planner picks agent → execute → fold evidence into state → repeat.
- Preserve the current **fixed-order execution as a fallback** for other Plays
  (no regression to drug-trafficking).
- Keep `StepTrace` + checkpointing (`incremental-save-standard`); attach the
  `PlannerDecision` to each `StepTrace`.

### REQ-4: Narrated F3EAD trace (the demo centerpiece)
- The Agent page (`/investigate/playbook`) step trace shows, per step: which Agent
  was chosen and **WHY** (the gap), the **alternatives considered**, and the
  KNOWN/ASSESSED evidence + LIVE/ROADMAP + UTS badge.
- The **next proposed step** renders as a pending decision the analyst can act on.
- Extend the existing trace panel; no new page, reuse components.

### REQ-5: Human-in-the-loop controls
- **Approve/Run** the proposed step (Guided mode default) or **Auto-run** to
  saturation (toggle).
- **Override**: pick a different rule-legal agent than the one proposed; planner
  re-plans from there.
- **Direct/Search bar** (always available): the analyst injects a name, entity, or
  focus string mid-investigation. A **name** gets structured handling (targets the
  Sanctions/Ownership agents on that name next); **free text** becomes a planner
  hint. Injected input is added to state tagged **human-sourced (KNOWN)** and the
  planner re-plans.
- (Pass 2) **Accept/Reject** per evidence item, written to the audit trail
  (`analyst-approval` chain link) with analyst id + timestamp; rejecting removes
  the item and the planner re-plans without it.

### REQ-6: Agent Library reference view
- A browsable catalog at `/investigate/playbook/agents`: every agent with its
  capability, input contract, output, UTS vector, KNOWN/ASSESSED, cost, LIVE/ROADMAP,
  and "which Playbooks use me". Reads the registry so it can't drift. Cross-linked
  from the Library and Agent pages.

### REQ-7: Verification
- `getDiagnostics` clean on all touched files.
- `/api/playbook/run` returns a planner-driven trace for an ML lead.
- New/edited routes return HTTP 200.
- Regression: DEVELOP (high-ratio) and CLOSED (low-ratio kill-gate) demo leads
  still behave correctly; drug-trafficking Play unchanged.

## Build phases

- **Pass 1 (this build):** REQ-1, REQ-2, REQ-3, REQ-4, REQ-5 (approve/override/
  inject + Guided/Auto toggle), REQ-6, REQ-7.
- **Pass 2 (follow-up):** per-evidence Accept/Reject wired to the audit trail, and
  a fully resumable step-by-step run (pause between every step).

## Out of scope
- Full LLM autonomy (planner choosing outside rule-legal options) — future toggle.
- New detection tools/signatures — the agents wrap existing capabilities only.
- Geospatial map work — different feature, different workspace.
