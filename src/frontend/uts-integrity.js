/**
 * ============================================================================
 * UTS Analytical Integrity — Shared Constants & Helpers (vanilla JS port)
 * ============================================================================
 *
 * Faithful port of Finding Fentanyl's frontend/src/lib/uts-constants.ts, per the
 * governing standard .kiro/steering/uts-analytical-integrity.md. Single source of
 * truth for the UTS 5-vector model + IC (ICD 203) analytical-integrity labelling
 * for the vanilla-JS Research Analyst frontend.
 *
 * Every intelligence output must show:
 *   1. WHICH UTS vector(s) the evidence arrived through
 *   2. Whether a statement is KNOWN (observed) or ASSESSED (inferred)
 *   3. Confidence + IC-standard Words of Estimative Probability (WEP)
 *   4. What's MISSING (collection gaps)
 *
 * Do NOT redefine these maps in individual pages — import this file and reuse.
 * Exposes window.UTS.*
 */
(function (global) {
  'use strict';

  // Canonical vector order — used for the 5-dot coverage indicator.
  const UTS_VECTORS = ['online', 'financial', 'electronic', 'visual', 'travel'];

  // Icon / label / color per vector. Hex values mirror the Tailwind text-*-400
  // classes named in the steering doc, so the vanilla UI matches the React app.
  const UTS_META = {
    online:     { icon: '🌐', label: 'ONLINE',     color: '#60a5fa', detects: 'Digital footprint, OSINT, social media, dark web' },
    financial:  { icon: '💰', label: 'FINANCIAL',  color: '#4ade80', detects: 'Transactions, wire transfers, trade invoices, crypto' },
    electronic: { icon: '📡', label: 'ELECTRONIC', color: '#c084fc', detects: 'Cell/device signals, AIS transponders, IoT' },
    visual:     { icon: '👁️', label: 'VISUAL',     color: '#fbbf24', detects: 'CCTV, LPR, physical surveillance, imagery' },
    travel:     { icon: '✈️', label: 'TRAVEL',     color: '#22d3ee', detects: 'PNR, border crossings, hotel, rental, movement' },
  };

  // ── KNOWN vs ASSESSED ──────────────────────────────────────────────────
  // Any hedging/inferential language => ASSESSED (a judgement, not an
  // observation). Errs toward ASSESSED, the safe direction per the steering doc.
  const INFERENCE_MARKERS = [
    'likely', 'suggests', 'indicates', 'consistent with', 'appears', 'assessed',
    'probable', 'probably', 'suspected', 'believed', 'may ', 'might ', 'could ',
    'inferred', 'implies', 'pattern matches', 'suggesting', 'potential', 'anomalous',
  ];
  function classifyEvidence(text) {
    const t = (text || '').toLowerCase();
    return INFERENCE_MARKERS.some((m) => t.includes(m)) ? 'ASSESSED' : 'KNOWN';
  }

  // ── Words of Estimative Probability (Kent 1964 / ICD 203) ───────────────
  const WEP_TERMS = [
    { term: 'almost certainly', min: 95, max: 100 },
    { term: 'very likely', min: 80, max: 95 },
    { term: 'likely', min: 55, max: 80 },
    { term: 'roughly even chance', min: 45, max: 55 },
    { term: 'unlikely', min: 20, max: 45 },
    { term: 'very unlikely', min: 5, max: 20 },
    { term: 'almost no chance', min: 0, max: 5 },
  ];
  function wepForProbability(p) {
    const hit = WEP_TERMS.find((w) => p >= w.min && p <= w.max);
    return hit ? hit.term : 'roughly even chance';
  }

  // ── Vector derivation from free text ────────────────────────────────────
  // Explicit keyword sets (auditable, not ML). Tuned for UAP report language
  // while keeping the five canonical vectors.
  const VECTOR_KEYWORDS = {
    financial: ['transaction', 'wire', 'invoice', 'bank', 'payment', 'funds', 'insurance', 'cost'],
    electronic: [
      'radar', 'radio', 'signal', 'transponder', 'electromagnetic', 'electrical',
      'instrument', 'sensor', 'flir', 'device', 'interference', 'telemetry', 'sonar',
      'frequency', 'detector', 'magnetometer', 'compass',
    ],
    travel: [
      'flight', 'aircraft', 'airline', 'airport', 'pilot', 'runway', 'altitude',
      'vessel', 'ship', 'naval', 'maritime', 'crossing', 'border', 'highway', 'road',
    ],
    visual: [
      'saw', 'observed', 'sighting', 'witness', 'photo', 'photograph', 'video',
      'footage', 'camera', 'cctv', 'imagery', 'satellite', 'telescope', 'binoculars',
      'daylight', 'nocturnal', 'visible', 'appeared', 'shape', 'lights', 'glowing',
    ],
    online: [
      'report', 'reported', 'database', 'nuforc', 'mufon', 'nicap', 'press', 'news',
      'forum', 'website', 'archive', 'record', 'filed', 'document', 'declassified',
    ],
  };
  function deriveVectors(text) {
    const t = (text || '').toLowerCase();
    return UTS_VECTORS.filter((v) => VECTOR_KEYWORDS[v].some((k) => t.includes(k)));
  }

  // ── Coverage ────────────────────────────────────────────────────────────
  const EMPTY_COVERAGE = { online: false, financial: false, electronic: false, visual: false, travel: false };
  function computeCoverage(texts) {
    const cov = Object.assign({}, EMPTY_COVERAGE);
    (texts || []).forEach((t) => deriveVectors(t).forEach((v) => { cov[v] = true; }));
    return cov;
  }
  function activeVectorCount(cov) {
    return UTS_VECTORS.filter((v) => cov[v]).length;
  }

  // Per-vector "what to task next" when a vector has no coverage. UAP-flavored
  // but grounded in the collection-gap requirement of the steering doc.
  const COLLECTION_RECOMMENDATIONS = {
    online: 'Task OSINT sweep — cross-reference NUFORC/MUFON/NICAP archives and contemporaneous press for independent reports of the same event.',
    financial: 'Rarely applicable to UAP; where relevant, pull insurance/damage claims or procurement records tied to affected assets.',
    electronic: 'Request radar/ATC logs, FLIR imagery, and any RF/EM instrument data for the time window; task sonar review for trans-medium cases.',
    visual: 'Obtain photographs, video, CCTV, or satellite imagery for the location/time; seek additional eyewitness accounts with vantage points.',
    travel: 'Pull flight/ATC records and aircrew statements; for maritime cases request vessel logs and naval sensor tracks.',
  };

  // ── Confidence per ICD 203 ──────────────────────────────────────────────
  // Driven by BREADTH of collection, not model certainty. HIGH requires >=2
  // vectors AND >=3 sources — a single-vector single-source finding is LOW.
  function confidenceLevelFrom(activeVectors, sourceCount) {
    if (activeVectors >= 3 && sourceCount >= 3) return 'HIGH';
    if (activeVectors >= 2 && sourceCount >= 2) return 'MODERATE';
    return 'LOW';
  }
  function confidenceBasis(activeVectors, sourceCount, level) {
    const gaps = 5 - activeVectors;
    const base = sourceCount + ' source' + (sourceCount === 1 ? '' : 's')
      + ' across ' + activeVectors + ' of 5 UTS collection vectors';
    if (level === 'HIGH') return base + '. Multi-vector corroboration satisfied.';
    if (level === 'MODERATE') return base + '. Corroborated but ' + gaps + ' vector' + (gaps === 1 ? '' : 's') + ' uncollected — see gaps.';
    return base + '. Single-channel reliance; treat as fragmentary until additional vectors are collected.';
  }

  // ── Rendering helpers (return HTML strings for vanilla pages) ────────────
  function vectorBadge(v) {
    const m = UTS_META[v];
    if (!m) return '';
    return '<span class="uts-badge" style="color:' + m.color + ';border-color:' + m.color
      + '66" title="' + m.detects + '">' + m.icon + ' ' + m.label + '</span>';
  }
  function coverageDots(cov) {
    const dots = UTS_VECTORS.map((v) => {
      const on = cov[v];
      const m = UTS_META[v];
      return '<span class="uts-dot" title="' + m.label + (on ? '' : ' — GAP') + '" style="color:'
        + (on ? m.color : '#4a5568') + '">' + (on ? '\u25CF' : '\u25CB') + '</span>';
    }).join('');
    const n = activeVectorCount(cov);
    return '<span class="uts-coverage">' + dots + ' <span class="uts-coverage-count">' + n + '/5 vectors</span></span>';
  }
  function classBadge(cls) {
    if (cls === 'KNOWN') return '<span class="ev-known">KNOWN</span>';
    return '<span class="ev-assessed">ASSESSED</span>';
  }

  global.UTS = {
    UTS_VECTORS, UTS_META, WEP_TERMS, EMPTY_COVERAGE, COLLECTION_RECOMMENDATIONS,
    classifyEvidence, wepForProbability, deriveVectors, computeCoverage,
    activeVectorCount, confidenceLevelFrom, confidenceBasis,
    vectorBadge, coverageDots, classBadge,
  };
})(window);
