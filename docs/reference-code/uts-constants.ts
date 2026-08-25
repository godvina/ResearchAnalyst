/**
 * ══════════════════════════════════════════════════════════════════════════
 * UTS Analytical Integrity — Shared Constants & Helpers
 * ══════════════════════════════════════════════════════════════════════════
 *
 * Single source of truth for the UTS 5-vector model and IC (ICD 203)
 * analytical-integrity labelling. Per .kiro/steering/uts-analytical-integrity.md
 * EVERY intelligence output must show:
 *   1. WHICH UTS vector(s) the evidence arrived through
 *   2. Whether a statement is KNOWN (observed) or ASSESSED (inferred)
 *   3. Confidence + IC-standard Words of Estimative Probability
 *   4. What's MISSING (collection gaps)
 *
 * REUSE NOTE: `UTS_META` was previously hardcoded inside CaseFile.tsx. It lives
 * here now so CaseFile, IntelligenceBrief and every case page render identical
 * badges. Do not redefine these maps locally.
 *
 * The `UtsVector` union is NOT redefined here — it is re-exported from the
 * canonical definition in theory-scoring/types.ts.
 */

import type { UtsVector } from '@/lib/theory-scoring/types';

export type { UtsVector };

/** Canonical vector order. Used for the 5-dot coverage indicator. */
export const UTS_VECTORS: readonly UtsVector[] = [
  'online',
  'financial',
  'electronic',
  'visual',
  'travel',
] as const;

/** Icon / label / colour per vector. Colours match the steering doc exactly. */
export const UTS_META: Record<UtsVector, {
  icon: string;
  label: string;
  cls: string;
  border: string;
  /** What this vector detects — shown in tooltips. */
  detects: string;
}> = {
  online: {
    icon: '🌐', label: 'ONLINE', cls: 'text-blue-400', border: 'border-blue-400/40',
    detects: 'Digital footprint, OSINT, social media, dark web',
  },
  financial: {
    icon: '💰', label: 'FINANCIAL', cls: 'text-green-400', border: 'border-green-400/40',
    detects: 'Transactions, wire transfers, trade invoices, crypto',
  },
  electronic: {
    icon: '📡', label: 'ELECTRONIC', cls: 'text-purple-400', border: 'border-purple-400/40',
    detects: 'Cell/device signals, AIS transponders, IoT',
  },
  visual: {
    icon: '👁️', label: 'VISUAL', cls: 'text-amber-400', border: 'border-amber-400/40',
    detects: 'CCTV, LPR, physical surveillance, imagery',
  },
  travel: {
    icon: '✈️', label: 'TRAVEL', cls: 'text-cyan-400', border: 'border-cyan-400/40',
    detects: 'PNR, border crossings, hotel, rental, movement',
  },
};

// ── Analytical integrity: KNOWN vs ASSESSED ─────────────────────────────────

export type EvidenceClass = 'KNOWN' | 'ASSESSED';

/**
 * IC-standard Words of Estimative Probability (Kent 1964 / ICD 203).
 * Never use non-standard hedges ("maybe", "could be") — pick from this list.
 */
export const WEP_TERMS = [
  { term: 'almost certainly', min: 95, max: 99 },
  { term: 'very likely', min: 80, max: 95 },
  { term: 'likely', min: 55, max: 80 },
  { term: 'roughly even chance', min: 45, max: 55 },
  { term: 'unlikely', min: 20, max: 45 },
  { term: 'very unlikely', min: 5, max: 20 },
  { term: 'almost no chance', min: 1, max: 5 },
] as const;

/** Map a 0-100 probability to the correct IC WEP term. */
export function wepForProbability(p: number): string {
  const hit = WEP_TERMS.find((w) => p >= w.min && p <= w.max);
  return hit ? hit.term : 'roughly even chance';
}

/**
 * Classify a statement as KNOWN (documented observation) or ASSESSED (inference).
 *
 * Heuristic, deliberately conservative: any hedging/inferential language means
 * the statement is a judgement, not an observation, so it must be labelled
 * ASSESSED. This errs toward ASSESSED, which is the safe direction — the
 * steering doc forbids presenting AI conclusions as facts.
 */
const INFERENCE_MARKERS = [
  'likely', 'suggests', 'indicates', 'consistent with', 'appears', 'assessed',
  'probable', 'probably', 'suspected', 'believed', 'may ', 'might ', 'could ',
  'inferred', 'implies', 'pattern matches', 'suggesting', 'potential',
];

export function classifyEvidence(text: string): EvidenceClass {
  const t = (text || '').toLowerCase();
  return INFERENCE_MARKERS.some((m) => t.includes(m)) ? 'ASSESSED' : 'KNOWN';
}

// ── Vector derivation ───────────────────────────────────────────────────────

/**
 * Keyword sets used to infer which collection channel a finding arrived through.
 * These are intentionally explicit rather than ML-based so an analyst can audit
 * exactly why a badge appeared.
 */
const VECTOR_KEYWORDS: Record<UtsVector, string[]> = {
  financial: [
    'transaction', 'wire', 'transfer', 'invoice', 'crypto', 'bitcoin', 'tron',
    'usdt', 'bank', 'account', 'cash', 'deposit', 'laundering', 'sar', 'str',
    'payment', 'remittance', 'funds', 'shell', 'trust', 'casino', 'junket',
    'chip', 'settlement', '$', 'aud', 'usd', 'million', 'billion', 'austrac',
    'fincen', 'structuring', 'value transfer', 'hawala', 'underground banking',
  ],
  electronic: [
    'encrypted', 'signal', 'whatsapp', 'wickr', 'ais', 'transponder', 'cell',
    'phone', 'device', 'imei', 'sim', 'intercept', 'telemetry', 'gps',
    'comms', 'communication', 'messaging', 'app', 'wiretap', 'metadata',
  ],
  travel: [
    'flight', 'travel', 'visa', 'passport', 'border', 'airport', 'pnr',
    'i-94', 'tecs', 'apis', 'crossing', 'tourist', 'entry', 'departure',
    'itinerary', 'hotel', 'vessel', 'voyage', 'port', 'shipment', 'container',
    'cargo', 'transit', 'mothership', 'yacht', 'maritime',
  ],
  visual: [
    'cctv', 'surveillance', 'imagery', 'satellite', 'photo', 'lpr',
    'observed', 'sighting', 'physical surveillance', 'camera', 'footage',
    'seized', 'seizure', 'inspection', 'search warrant', 'raid',
  ],
  online: [
    'osint', 'website', 'domain', 'social media', 'dark web', 'darknet',
    'forum', 'marketplace', 'press release', 'doj', 'indictment', 'court',
    'icij', 'leak', 'registry', 'filing', 'report', 'news', 'media release',
    'open source', 'publicly',
  ],
};

/**
 * Infer the UTS vectors a single finding arrived through.
 * Returns [] when nothing matches — callers should treat that as "unattributed"
 * rather than inventing a vector.
 */
export function deriveVectors(text: string): UtsVector[] {
  const t = (text || '').toLowerCase();
  return UTS_VECTORS.filter((v) => VECTOR_KEYWORDS[v].some((k) => t.includes(k)));
}

export type UtsCoverage = Record<UtsVector, boolean>;

export const EMPTY_COVERAGE: UtsCoverage = {
  online: false, financial: false, electronic: false, visual: false, travel: false,
};

/** Union the vectors across many findings into a single coverage map. */
export function computeCoverage(texts: string[]): UtsCoverage {
  const cov: UtsCoverage = { ...EMPTY_COVERAGE };
  for (const t of texts) for (const v of deriveVectors(t)) cov[v] = true;
  return cov;
}

export function activeVectorCount(cov: UtsCoverage): number {
  return UTS_VECTORS.filter((v) => cov[v]).length;
}

/**
 * Specific collection action to task when a vector has no coverage.
 * The steering doc requires gaps be actionable, not just flagged.
 */
export const COLLECTION_RECOMMENDATIONS: Record<UtsVector, string> = {
  online: 'Task OSINT sweep — dark-web marketplace monitoring, corporate registry pulls, social-media link analysis on named subjects.',
  financial: 'Request FinCEN SAR/STR pull and correspondent-bank subpoena on identified accounts; task AUSTRAC/FIU cross-reference.',
  electronic: 'Request cell-tower dump and device metadata for the subject window; task AIS transponder history on implicated vessels.',
  visual: 'Task CCTV/LPR pull at identified premises and ports; request satellite imagery of the transfer locations.',
  travel: 'Pull APIS/PNR and I-94 records for named subjects; request border-crossing and hotel records for the activity window.',
};

/**
 * Confidence level per ICD 203, driven by BREADTH of collection, not by how
 * confident the model feels. HIGH requires corroboration across >= 2 vectors
 * AND >= 3 sources — a single-vector single-source finding can never be HIGH.
 */
export function confidenceLevelFrom(
  activeVectors: number,
  sourceCount: number,
): 'HIGH' | 'MODERATE' | 'LOW' {
  if (activeVectors >= 3 && sourceCount >= 3) return 'HIGH';
  if (activeVectors >= 2 && sourceCount >= 2) return 'MODERATE';
  return 'LOW';
}

/** Human-readable justification for the confidence level. */
export function confidenceBasis(
  activeVectors: number,
  sourceCount: number,
  level: 'HIGH' | 'MODERATE' | 'LOW',
): string {
  const gaps = 5 - activeVectors;
  const base = `${sourceCount} source${sourceCount === 1 ? '' : 's'} across ${activeVectors} of 5 UTS collection vectors`;
  if (level === 'HIGH') return `${base}. Multi-vector corroboration satisfied.`;
  if (level === 'MODERATE') return `${base}. Corroborated but ${gaps} vector${gaps === 1 ? '' : 's'} uncollected — see gaps.`;
  return `${base}. Single-channel reliance; treat as fragmentary until additional vectors are collected.`;
}

// ── Source citation resolution ──────────────────────────────────────────────

/**
 * Case `source` fields are inconsistent: some hold a real URL, others hold only
 * a citation string ("AFP Pacific Transnational Crime Unit Intelligence
 * Assessment, 2026"). Rendering the latter inside <a href> produces a broken
 * link, so callers must use this to decide.
 *
 * For citation-only sources we link to the issuing body's official
 * publications index — verifiable and useful — rather than inventing a
 * deep link to a document we cannot confirm exists.
 */
const AGENCY_INDEX: Array<{ match: RegExp; agency: string; url: string }> = [
  { match: /\bAFP\b|Australian Federal Police/i, agency: 'Australian Federal Police', url: 'https://www.afp.gov.au/news-centre' },
  { match: /AUSTRAC/i, agency: 'AUSTRAC', url: 'https://www.austrac.gov.au/about-us/media-release' },
  { match: /NZ Police|New Zealand Police/i, agency: 'New Zealand Police', url: 'https://www.police.govt.nz/news' },
  { match: /UNODC/i, agency: 'UNODC', url: 'https://www.unodc.org/unodc/en/data-and-analysis/index.html' },
  { match: /ICIJ|Offshore Leaks/i, agency: 'ICIJ', url: 'https://offshoreleaks.icij.org/' },
  { match: /TRM Labs/i, agency: 'TRM Labs', url: 'https://www.trmlabs.com/research' },
  { match: /USCG|Coast Guard/i, agency: 'U.S. Coast Guard', url: 'https://www.news.uscg.mil/' },
  { match: /DEA/i, agency: 'DEA', url: 'https://www.dea.gov/press-releases' },
  { match: /\bDOJ\b|Department of Justice/i, agency: 'U.S. DOJ', url: 'https://www.justice.gov/news' },
  { match: /Fiji Police/i, agency: 'Fiji Police Force', url: 'https://www.police.gov.fj/' },
  { match: /Tonga Police/i, agency: 'Tonga Police', url: 'https://www.police.gov.to/' },
  { match: /Papua New Guinea|RPNGC/i, agency: 'RPNG Constabulary', url: 'https://www.rpngc.gov.pg/' },
  { match: /Vanuatu FIU/i, agency: 'Vanuatu FIU', url: 'https://www.fiu.gov.vu/' },
  { match: /BSP Financial/i, agency: 'BSP Financial Group', url: 'https://www.bsp.com.pg/' },
  { match: /FATF/i, agency: 'FATF', url: 'https://www.fatf-gafi.org/en/publications.html' },
];

export interface ResolvedSource {
  /** Text to display. */
  citation: string;
  /** Href to use, or null when nothing verifiable exists. */
  url: string | null;
  /** True when the URL points at the exact document; false when it's an index. */
  isDirect: boolean;
  /** Issuing body, when identifiable. */
  agency?: string;
}

export function resolveSource(source?: string): ResolvedSource | null {
  if (!source || !source.trim()) return null;
  const s = source.trim();

  // Already a real URL — link straight to the document.
  if (/^https?:\/\//i.test(s)) {
    let agency: string | undefined;
    try {
      agency = new URL(s).hostname.replace(/^www\./, '');
    } catch {
      agency = undefined;
    }
    return { citation: s, url: s, isDirect: true, agency };
  }

  // Citation string — link to the issuing body's official index.
  //
  // Multi-source citations are common ("ICIJ Offshore Leaks + AUSTRAC
  // cross-reference"). Pick the agency mentioned EARLIEST in the string, which
  // is the primary/originating source. Matching in array order instead would
  // credit whichever agency happens to sit higher in AGENCY_INDEX.
  let best: { agency: string; url: string; at: number } | null = null;
  for (const a of AGENCY_INDEX) {
    const m = s.match(a.match);
    if (m && m.index !== undefined && (best === null || m.index < best.at)) {
      best = { agency: a.agency, url: a.url, at: m.index };
    }
  }

  return {
    citation: s,
    url: best ? best.url : null,
    isDirect: false,
    agency: best?.agency,
  };
}
