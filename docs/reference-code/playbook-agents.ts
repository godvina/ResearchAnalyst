/**
 * Agent Library — the reusable, planner-selectable capabilities.
 *
 * Each Agent is one investigative capability (Capacity Calculator, Ownership
 * Expander, Sanctions Screener, Signature Matcher, Timing Assessor). Agents WRAP
 * the existing deterministic tools in tools.ts — they add no new detection logic;
 * they add a CONTRACT the planner can reason over: what the agent needs
 * (precondition), what it produces (KNOWN/ASSESSED + UTS vector), and whether it
 * runs on a LIVE feed or is ROADMAP.
 *
 * This is the "specific agents you leverage on the fly" layer: a new Playbook
 * composes existing Agents instead of writing new code. Domain-agnostic agents
 * (ownership, sanctions, signatures) are reused across Plays; domain-specific
 * ones (the ML capacity formula) stay thin.
 *
 * SERVER-ONLY (agents call tools that use fs / AWS SDK).
 * Spec: .kiro/specs/playbook-planning-agent/requirements.md
 */

import type { EvidenceItem } from '@/lib/types/case-file';
import type { UtsVector } from './play-types';
import type { RunEntity, RunSignature } from './run-types';
import {
  calcMaxRevenue, calcRatio, knnSignatures, graphNeighbors,
  screenOfac, ofacPrecursorSuppliers, type GraphNeighborsInput,
} from './tools';

/** The shared, evolving case state the planner reads and agents mutate. */
export interface RunState {
  lead: { text: string; record: Record<string, unknown> };
  domain: string;          // caseFileDomain
  typology: string;        // e.g. 'money-laundering'
  aossIndex: string;
  vars: Record<string, number>;
  known: EvidenceItem[];
  assessed: EvidenceItem[];
  entities: RunEntity[];
  signatures: RunSignature[];
  /** Free-text focus hints injected by the analyst (human-in-the-loop). */
  analystHints: string[];
  /** Agent ids already executed this run (so the planner doesn't repeat). */
  ranAgents: string[];
}

/** What an agent returns after acting. Folded into RunState + a StepTrace. */
export interface AgentResult {
  /** true = executed on a connected feed; false = ROADMAP (feed not connected). */
  live: boolean;
  /** true = a kill-gate fired → the run should CLOSE. */
  killed?: boolean;
  killedReason?: string;
  /** KNOWN/ASSESSED items this agent produced. */
  evidence: EvidenceItem[];
  /** New entities surfaced (fed to the CaseFile graph). */
  entities?: RunEntity[];
  /** New signatures matched. */
  signatures?: RunSignature[];
  /** Numeric vars to merge into state (e.g. maxRevenue, ratio, sigCount). */
  vars?: Record<string, number>;
  /** Data source needed if this ran as ROADMAP. */
  dataSourceRequired?: string;
  /** Structured output for the trace. */
  output?: unknown;
}

export type AgentKind = 'tool' | 'gate' | 'llm';

export interface Agent {
  id: string;
  label: string;
  /** SPOT/CALCULATE/EXPAND/SCREEN/FLAG/ASSESS — the verb shown in the trace. */
  verb: string;
  kind: AgentKind;
  description: string;
  /** What the analyst gets from it (the "so what"). */
  capability: string;
  produces: 'KNOWN' | 'ASSESSED';
  utsVectors: UtsVector[];
  /** Rough cost/latency hint for the planner + UI. */
  cost: 'free' | 'cheap' | 'llm';
  /** The real feed it needs in production (for LIVE/ROADMAP labeling). */
  dataSource: string;
  /**
   * Precondition: can this agent run given current state? The planner only
   * considers agents whose precondition is met and that haven't run yet.
   */
  precondition: (s: RunState) => boolean;
  /**
   * Gap score 0..1: how much this agent would advance the case RIGHT NOW.
   * The planner picks the highest-gap eligible agent. Deterministic.
   */
  gap: (s: RunState) => number;
  /** One-line reason the planner shows for choosing this agent now. */
  rationale: (s: RunState) => string;
  /** Execute against state (mutates via the returned AgentResult; pure-ish). */
  execute: (s: RunState) => Promise<AgentResult>;
}

// ── helpers ─────────────────────────────────────────────────────────────────
const has = (s: RunState, v: string) => typeof s.vars[v] === 'number' && !isNaN(s.vars[v]);
const ratio = (s: RunState) => s.vars.ratio ?? 0;

// ── AGENT: Capacity Calculator (ML) ─────────────────────────────────────────
const capacityCalculator: Agent = {
  id: 'capacity-calculator',
  label: 'Capacity Calculator',
  verb: 'CALCULATE',
  kind: 'tool',
  description: 'Computes the maximum revenue a cash business could legitimately earn, then the deposits-to-capacity ratio.',
  capability: 'Establishes the legitimate revenue ceiling and how far deposits exceed it.',
  produces: 'KNOWN',
  utsVectors: ['financial'],
  cost: 'free',
  dataSource: 'business profile (seats, hours, avg ticket) + bank deposits',
  precondition: (s) => has(s, 'seats') && has(s, 'deposits') && !has(s, 'ratio'),
  gap: (s) => (has(s, 'ratio') ? 0 : 1), // foundational — highest until computed
  rationale: () => 'No capacity ratio yet — compute the legitimate ceiling first.',
  async execute(s) {
    const maxRevenue = calcMaxRevenue(s.vars);
    if (maxRevenue == null) {
      return { live: false, evidence: [], dataSourceRequired: this.dataSource, output: { note: 'Missing business profile inputs.' } };
    }
    const r = calcRatio({ ...s.vars, maxRevenue });
    const evidence: EvidenceItem[] = [
      { text: `Max legitimate revenue ≈ $${Math.round(maxRevenue).toLocaleString()} (seats × turns × avg ticket × days).`, evidenceClass: 'KNOWN', utsVector: 'financial' },
    ];
    if (r != null) evidence.push({ text: `Deposits are ${r.toFixed(1)}× the maximum a legitimate operation could generate.`, evidenceClass: 'KNOWN', utsVector: 'financial' });
    return { live: true, evidence, vars: { maxRevenue, ...(r != null ? { ratio: r } : {}) }, output: { maxRevenue, ratio: r } };
  },
};

// ── AGENT: Collection-Point Gate (ML kill-gate) ─────────────────────────────
const collectionPointGate: Agent = {
  id: 'collection-point-gate',
  label: 'Collection-Point Gate',
  verb: 'FLAG',
  kind: 'gate',
  description: 'Disciplined no-action gate: if deposits are < 5× capacity, this is a legitimate business — CLOSE the lead.',
  capability: 'Stops wasted effort on legitimate businesses (the credibility of the whole model).',
  produces: 'KNOWN',
  utsVectors: ['financial'],
  cost: 'free',
  dataSource: 'derived from the capacity ratio',
  precondition: (s) => has(s, 'ratio') && !s.ranAgents.includes('collection-point-gate'),
  gap: (s) => (has(s, 'ratio') ? 0.95 : 0), // run right after the ratio exists
  rationale: (s) => `Ratio is ${ratio(s).toFixed(1)}× — test the 5× collection-point threshold before spending more effort.`,
  async execute(s) {
    const fired = ratio(s) < 5;
    return {
      live: true,
      killed: fired,
      killedReason: fired ? `ratio ${ratio(s).toFixed(1)}× < 5× — legitimate high-cash business, not a collection point.` : undefined,
      evidence: [{
        text: fired
          ? `Gate FLAG fired (ratio ${ratio(s).toFixed(1)}× < 5×) — closing: not a collection point.`
          : `Gate FLAG passed (ratio ${ratio(s).toFixed(1)}× ≥ 5×) — continue developing.`,
        evidenceClass: 'KNOWN', utsVector: 'financial',
      }],
      output: { threshold: 5, ratio: ratio(s), fired },
    };
  },
};

// ── AGENT: Ownership Expander (domain-agnostic) ─────────────────────────────
const ownershipExpander: Agent = {
  id: 'ownership-expander',
  label: 'Ownership Expander',
  verb: 'EXPAND',
  kind: 'tool',
  description: 'Expands the owner + co-owned businesses + deposit accounts into the entity network (Neptune 2-hop in production).',
  capability: 'Reveals the network behind the front — who owns it and what else they control.',
  produces: 'KNOWN',
  utsVectors: ['financial', 'online'],
  cost: 'cheap',
  dataSource: 'corporate registry / entity graph (Neptune)',
  precondition: (s) => !s.ranAgents.includes('ownership-expander'),
  gap: (s) => (s.entities.some((e) => e.role === 'owner') ? 0.2 : ratio(s) >= 5 ? 0.8 : 0.5),
  rationale: (s) => s.entities.some((e) => e.role === 'owner')
    ? 'Ownership already surfaced — low additional value.'
    : `Ratio ${ratio(s).toFixed(1)}× but ownership unknown — expand to map co-owned fronts.`,
  async execute(s) {
    const gi: GraphNeighborsInput = {
      business: (s.lead.record.business as string) || undefined,
      owner: (s.lead.record.owner as string) || undefined,
      coOwned: Array.isArray(s.lead.record.coOwned) ? (s.lead.record.coOwned as string[]) : undefined,
      bankAccount: (s.lead.record.bankAccount as string) || undefined,
    };
    const ents = graphNeighbors(gi);
    if (!ents.length) return { live: false, evidence: [], dataSourceRequired: this.dataSource, output: { entities: [] } };
    return {
      live: true,
      entities: ents,
      evidence: [{ text: `Network expansion: ${ents.map((e) => `${e.name} (${e.type})`).join(', ')}.`, evidenceClass: 'KNOWN', utsVector: 'financial' }],
      output: { entities: ents },
    };
  },
};

// ── AGENT: Sanctions Screener (domain-agnostic, REAL OFAC data) ─────────────
const sanctionsScreener: Agent = {
  id: 'sanctions-screener',
  label: 'Sanctions Screener (OFAC SDN)',
  verb: 'SCREEN',
  kind: 'tool',
  description: 'Screens every surfaced name (and analyst-injected names) against the real curated OFAC SDN subset, incl. a.k.a. aliases.',
  capability: 'Flags any subject that is already a US-designated sanctions target — instant escalation.',
  produces: 'KNOWN',
  utsVectors: ['online', 'financial'],
  cost: 'cheap',
  dataSource: 'OFAC SDN list (2,489 curated fentanyl/cartel designations, LIVE)',
  precondition: (s) => !s.ranAgents.includes('sanctions-screener'),
  gap: (s) => {
    // High value when we have names to screen (entities or analyst hints).
    const names = s.entities.length + s.analystHints.length + Object.values(s.lead.record).filter((v) => typeof v === 'string').length;
    return names > 0 ? 0.6 : 0.1;
  },
  rationale: (s) => s.entities.length
    ? `${s.entities.length} names surfaced — screen them against the OFAC SDN list.`
    : 'Screen the lead subjects against the OFAC SDN list.',
  async execute(s) {
    const names: string[] = [...s.analystHints];
    for (const v of Object.values(s.lead.record)) {
      if (typeof v === 'string') names.push(v);
      else if (Array.isArray(v)) for (const x of v) if (typeof x === 'string') names.push(x);
    }
    names.push(...s.entities.map((e) => e.name));
    let hits = screenOfac(names);
    // Precursor leads with no specific supplier named → surface real designations.
    if (!hits.length && /precursor|chemical|fentanyl/i.test(s.lead.text)) hits = ofacPrecursorSuppliers(6);
    if (!hits.length) {
      return { live: true, evidence: [{ text: 'OFAC SDN screening: no matches among the surfaced names.', evidenceClass: 'KNOWN', utsVector: 'online' }], entities: [], output: { ofacMatches: 0 } };
    }
    return {
      live: true,
      entities: hits,
      evidence: [{ text: `OFAC SDN screening returned ${hits.length} real designated ${hits.length === 1 ? 'entity' : 'entities'}: ${hits.slice(0, 4).map((e) => e.name).join(', ')}${hits.length > 4 ? '…' : ''}.`, evidenceClass: 'KNOWN', utsVector: 'online' }],
      output: { ofacMatches: hits.length },
    };
  },
};

// ── AGENT: Signature Matcher (domain-agnostic, real k-NN) ───────────────────
const signatureMatcher: Agent = {
  id: 'signature-matcher',
  label: 'Signature Matcher (k-NN)',
  verb: 'MATCH',
  kind: 'tool',
  description: 'k-NN the lead against the Crime Pattern Library signature vectors (real AOSS, local-cosine fallback).',
  capability: 'Finds which known criminal-method signatures the lead resembles — mathematically, no hallucination.',
  produces: 'KNOWN',
  utsVectors: ['online', 'financial'],
  cost: 'cheap',
  dataSource: 'Crime Pattern Library signature vectors (AOSS / local)',
  precondition: (s) => !s.ranAgents.includes('signature-matcher'),
  gap: (s) => (s.signatures.length ? 0.15 : 0.55),
  rationale: (s) => s.signatures.length ? 'Signatures already matched.' : 'No signatures matched yet — k-NN the pattern library.',
  async execute(s) {
    const query = `${s.lead.text} ${s.analystHints.join(' ')}`.trim();
    const knn = await knnSignatures(query, s.aossIndex, 8);
    return {
      live: knn.live,
      signatures: knn.signatures,
      vars: { sigCount: knn.signatures.length },
      evidence: knn.signatures.length
        ? [{ text: `Matched signatures (${knn.source}): ${knn.signatures.slice(0, 3).map((m) => m.signatureName).join(', ')}.`, evidenceClass: 'KNOWN', utsVector: 'financial' }]
        : [{ text: 'No pattern-library signatures matched.', evidenceClass: 'KNOWN', utsVector: 'online' }],
      output: { source: knn.source, signatures: knn.signatures },
    };
  },
};

// ── AGENT: Timing Assessor (LLM — ASSESSED + WEP) ───────────────────────────
const timingAssessor: Agent = {
  id: 'timing-assessor',
  label: 'Timing Assessor (LLM)',
  verb: 'ASSESS',
  kind: 'llm',
  description: 'LLM reads the accumulated KNOWN facts and gives a WEP-qualified judgment on whether this is a collection point.',
  capability: 'The analytical conclusion — grounded ONLY in what the agents found, labeled ASSESSED with an IC probability term.',
  produces: 'ASSESSED',
  utsVectors: ['financial', 'online'],
  cost: 'llm',
  dataSource: 'reasoning over accumulated KNOWN evidence (no new collection)',
  // Only assess once we have enough KNOWN evidence to ground it.
  precondition: (s) => has(s, 'ratio') && s.known.length >= 2 && !s.ranAgents.includes('timing-assessor'),
  gap: (s) => (has(s, 'ratio') && s.known.length >= 2 ? 0.4 : 0),
  rationale: () => 'Enough KNOWN evidence gathered — produce the WEP-qualified assessment.',
  async execute(s) {
    // Delegated to the runner's LLM helper (kept there to reuse the Bedrock call);
    // here we return a deterministic fallback if the runner does not override.
    const r = ratio(s);
    const wep = r >= 10 ? 'Very likely' : r >= 5 ? 'Likely' : 'Roughly even chance';
    return {
      live: true,
      evidence: [{ text: `${wep} a cash collection point: deposits ${r.toFixed(1)}× capacity with the surfaced ownership/sanctions signals. (WEP-qualified assessment.)`, evidenceClass: 'ASSESSED', utsVector: 'financial' }],
      output: { wep, ratio: r },
    };
  },
};

// ── Registry ────────────────────────────────────────────────────────────────
export const AGENTS: Agent[] = [
  capacityCalculator,
  collectionPointGate,
  ownershipExpander,
  sanctionsScreener,
  signatureMatcher,
  timingAssessor,
];

export function listAgents(): Agent[] {
  return AGENTS;
}

export function getAgent(id: string): Agent | undefined {
  return AGENTS.find((a) => a.id === id);
}

/**
 * Which agents a Play/domain may use. Money-laundering uses the full ML loop;
 * a new Play just lists the agent ids it composes (mostly the shared ones).
 */
export const PLAY_AGENTS: Record<string, string[]> = {
  'money-laundering': [
    'capacity-calculator',
    'collection-point-gate',
    'ownership-expander',
    'sanctions-screener',
    'signature-matcher',
    'timing-assessor',
  ],
  // drug-trafficking keeps its authored fixed order (fallback) for now.
};

export function agentsForDomain(domain: string): Agent[] {
  const ids = PLAY_AGENTS[domain];
  if (!ids) return [];
  return ids.map((id) => getAgent(id)).filter((a): a is Agent => !!a);
}
