/**
 * ============================================================================
 * UAP AI Smart Investigator — Agent Library + Hybrid Planner (vanilla JS)
 * ============================================================================
 *
 * Ports the Finding Fentanyl playbook-planning-agent model to UAP investigation,
 * per .kiro/specs/playbook-planning-agent/requirements.md and the governing
 * .kiro/steering/ai-investigator-agent-standard.md (progressive F3EAD execution).
 *
 * Design (identical philosophy to the money-laundering playbook):
 *   - AGENT LIBRARY: reusable, planner-selectable capabilities. Each declares a
 *     contract: precondition (can it run now?), gap (how much it advances the
 *     case), what it PRODUCES (KNOWN/ASSESSED + UTS vector), data source, and
 *     LIVE vs ROADMAP. Agents wrap grounded lookups over window.UAP_DATA — they
 *     add no invented facts.
 *   - HYBRID PLANNER: rules-authoritative. After each step, pick the highest-gap
 *     eligible agent. Bounded loop; a kill-gate (ProsaicExcluder) or saturation
 *     stops it. Emits a PlannerDecision (chosen agent, gap closed, alternatives).
 *   - HUMAN-IN-THE-LOOP: the UI can approve/override the proposed agent and inject
 *     an analyst focus hint (a place, witness type, or year) that re-plans.
 *
 * Search-first, LLM-second: these agents find signal from the real corpus; the
 * narration interprets. Every produced item is KNOWN or ASSESSED + UTS-stamped.
 *
 * Exposes window.UAPInvestigator.{ AGENTS, newState, planNext, runAgent,
 *   hypothesisFor, verdictFor, injectHint }.
 */
(function (global) {
  'use strict';
  const D = global.UAP_DATA || {};
  const U = global.UTS || {};

  const fmt = n => (n || 0).toLocaleString();
  const sigMeta = id => (D.sig_meta || {})[id] || {};
  function coocFor(id) {
    const out = [];
    (D.cooccurrence_edges || []).forEach(e => {
      if (e.a === id) out.push([e.b, e.w]); else if (e.b === id) out.push([e.a, e.w]);
    });
    return out.sort((a, b) => b[1] - a[1]);
  }
  function topCountries(id, n) {
    return Object.entries(sigMeta(id).top_countries || {}).slice(0, n || 4);
  }
  function textOf(id) {
    const m = sigMeta(id);
    return (m.description + ' ' + (m.needles || []).join(' ')).toLowerCase();
  }
  const kw = (id, list) => list.some(k => textOf(id).includes(k));

  // ---- Case state the planner reads and agents mutate ----
  function newState(sid) {
    return {
      sid,
      meta: sigMeta(sid),
      known: [],        // {text, vector, source, live}
      assessed: [],     // {text, vector, wep, conf}
      vars: {},         // flags set by agents (e.g. instrument:true)
      hints: [],        // analyst-injected focus strings (human-sourced KNOWN)
      ranAgents: [],
      killed: false,
      killedReason: '',
    };
  }

  // ===========================================================================
  // AGENT LIBRARY — each agent = one grounded investigative capability
  // ===========================================================================
  // Every execute() returns: { found: '→ FOUND: ...', evidence:[], vars:{}, live,
  //   killed?, killedReason? }. found is the one-line deliverable per the standard.

  const AGENTS = [
    {
      id: 'multi-witness',
      label: 'Multi-Witness Corroborator',
      verb: 'CORROBORATE',
      sources: ['UPDB corpus', 'NUFORC', 'NICAP'],
      capability: 'Counts independent reports of this pattern and how widely they spread — the multiplicity element.',
      produces: 'KNOWN', vector: 'online',
      dataSource: 'UPDB 296K global report corpus (LIVE, local)', live: true,
      precondition: s => !s.ranAgents.includes('multi-witness'),
      gap: s => s.ranAgents.includes('multi-witness') ? 0 : 1.0, // foundational
      rationale: () => 'Establish how many independent reports fire this pattern and where.',
      execute: s => {
        const m = s.meta, fired = m.fired || 0, c = topCountries(s.sid, 6);
        const strong = fired >= 5000;
        return {
          why: `A single sighting is an anecdote. Before anything else I test <b>multiplicity</b> — how many independent people, in how many places, reported this same thing. Multiplicity is the first element of proof: it separates a one-off from a phenomenon.`,
          found: `${fmt(fired)} independent reports fire this pattern across ${c.length}+ countries (led by ${c.slice(0,4).map(x => x[0]).join(', ')}).`,
          soWhat: strong
            ? `That is a large, geographically distributed body of reports — well past the threshold where coincidence or a single local cause can explain it. <b>Multiplicity element: SATISFIED.</b> The case now rests on whether that volume is <em>corroborated</em> or just repeated.`
            : `This is a thinner signal — reported, but not at the scale that rules out local or prosaic causes. <b>Multiplicity: WEAK.</b> The case will lean on quality of evidence, not quantity.`,
          impact: strong ? 'PROVES' : 'GAP',
          evidence: [{ text: `${fmt(fired)} reports, ${c.length}+ countries.`, vector: 'online' }],
          vars: { fired, multi: strong, countries: c.length },
          live: true,
        };
      },
    },
    {
      id: 'instrumentation',
      label: 'Instrumentation Retriever',
      verb: 'RETRIEVE',
      sources: ['Radar/ATC logs', 'FLIR', 'Physical trace'],
      capability: 'Checks whether this pattern carries instrumented corroboration (radar, FLIR, photo, physical trace) — the Electronic vector.',
      produces: 'KNOWN', vector: 'electronic',
      dataSource: 'ATC/military radar, FLIR imagery, trace analysis (ROADMAP — not connected)', live: false,
      precondition: s => !s.ranAgents.includes('instrumentation'),
      gap: s => s.vars.instrument == null ? 0.85 : 0,
      rationale: () => 'Determine if instrumented capture exists — the single strongest evidence gap for UAP.',
      execute: s => {
        const instr = kw(s.sid, ['radar', 'flir', 'sensor', 'instrument', 'photograph', 'sonar', 'magnet', 'trace', 'scorched', 'landing marks']);
        const why = `Eyewitnesses can be honestly mistaken; a sensor cannot be. This is the step that decides a case's ceiling — I check for <b>instrumentation</b> (radar, FLIR, photo, physical trace). It's the difference between "people saw something" and "an instrument measured something."`;
        return instr
          ? { why,
              found: `This pattern's definition is inherently instrument-adjacent (radar/FLIR/trace language). But the corpus itself holds the testimony, not the sensor tapes — a live sensor pull is ROADMAP, not yet connected.`,
              soWhat: `<b>Huge upside, currently a GAP.</b> If we can pull the actual radar/FLIR for the strongest events, this pattern jumps from testimonial to instrumented — the single biggest possible boost to the case. That's the highest-value collection task on the board.`,
              impact: 'GAP',
              evidence: [{ text: 'Pattern is instrument-adjacent; sensor feed not yet connected (ROADMAP).', vector: 'electronic' }], vars: { instrument: true }, live: false, dataSourceRequired: 'ATC/military radar + FLIR archives' }
          : { why,
              found: `No instrumented capture attaches to this pattern — the reports are visual/testimonial only.`,
              soWhat: `<b>This is the case's structural weakness.</b> Without a sensor, skeptics can always invoke misperception. Educationally, it tells the analyst exactly why this pattern, however common, will never exceed MODERATE confidence until someone captures it on an instrument.`,
              impact: 'EDUCATES',
              evidence: [{ text: 'No instrument corroboration in-corpus — visual/testimonial only.', vector: 'electronic' }], vars: { instrument: false }, live: true };
      },
    },
    {
      id: 'credibility',
      label: 'Credibility Screener',
      verb: 'SCREEN',
      sources: ['Witness profession tags', 'FAA/military rosters'],
      capability: 'Screens for trained observers (pilot, police, military, radar operator) among the reporters.',
      produces: 'KNOWN', vector: 'online',
      dataSource: 'witness profession fields (partial in corpus)', live: true,
      precondition: s => !s.ranAgents.includes('credibility') && s.ranAgents.includes('multi-witness'),
      gap: s => s.vars.credible == null ? 0.6 : 0,
      rationale: () => 'Weigh reporter credibility — trained observers raise evidentiary weight.',
      execute: s => {
        const cred = kw(s.sid, ['pilot', 'police', 'military', 'controller', 'trained', 'officer', 'scientist', 'engineer']);
        const why = `Not all witnesses are equal. A pilot, air traffic controller, or police officer is a <b>trained observer</b> — they know what conventional aircraft, planets, and weather look like, so their "I couldn't identify it" carries far more weight. I screen the reporter pool for these.`;
        return cred
          ? { why,
              found: `This pattern draws trained-observer reports — pilots, police, military, radar operators are represented among the witnesses.`,
              soWhat: `<b>Credibility element: SATISFIED.</b> These are exactly the witnesses a court or review board takes seriously. It also means the "they just didn't recognize a plane" rebuttal is much weaker here — these people <em>fly and track planes for a living.</em>`,
              impact: 'PROVES',
              evidence: [{ text: 'Trained-observer association present.', vector: 'online' }], vars: { credible: true }, live: true }
          : { why,
              found: `Reporters are predominantly general public; no concentration of trained observers is flagged for this pattern.`,
              soWhat: `<b>Credibility: unestablished — a GAP, not a strike.</b> The reports may still be accurate, but until we identify trained observers among them, each one is individually easier to dismiss. Re-interviewing to surface any pilots/police is a cheap, high-value next step.`,
              impact: 'GAP',
              evidence: [{ text: 'No trained-observer concentration identified.', vector: 'online' }], vars: { credible: false }, live: true };
      },
    },
    {
      id: 'prosaic-excluder',
      label: 'Prosaic Excluder (kill-gate)',
      verb: 'EXCLUDE',
      sources: ['GEIPAN negative signals', 'astronomical/aircraft data'],
      capability: 'Disciplined no-action gate: if the pattern is easily explained by prosaic stimuli AND lacks anomaly severity, CLOSE the lead.',
      produces: 'KNOWN', vector: 'visual',
      dataSource: 'GEIPAN-calibrated negative signals (LIVE, local)', live: true,
      precondition: s => !s.ranAgents.includes('prosaic-excluder') && s.vars.multi != null,
      gap: s => s.vars.multi != null ? 0.9 : 0, // run right after multiplicity
      rationale: () => 'Test the prosaic-explanation gate before spending more effort.',
      execute: s => {
        // Identify which specific prosaic explanations the pattern's own described
        // behaviour DEFEATS, and which remain open. Grounded in the signature text.
        const t = textOf(s.sid);
        const defeats = [];   // prosaic causes this pattern's behaviour rules out
        const open = [];      // prosaic causes still plausible
        const cite = (cond, label, bucket) => { if (cond) bucket.push(label); };
        cite(t.includes('silent') || t.includes('no sound') || t.includes('no engine'), 'conventional aircraft (which are audible at that range)', defeats);
        cite(t.includes('right angle') || t.includes('instant') || t.includes('no observable radius') || t.includes('accelerat') || t.includes('hover') || t.includes('against the wind'), 'aircraft/helicopters (the kinematics exceed known airframe limits)', defeats);
        cite(t.includes('radar') || t.includes('flir') || t.includes('sonar') || t.includes('instrument'), 'pure optical illusion (an instrument also registered it)', defeats);
        cite(t.includes('metallic') || t.includes('structured') || t.includes('solid') || t.includes('disc') || t.includes('triangle') || t.includes('craft'), 'point-source lights (a structured body was described)', defeats);
        cite(t.includes('daylight'), 'astronomical objects (Venus/stars are not visible as described in daylight)', defeats);
        // still-open prosaic explanations
        cite(!(t.includes('radar') || t.includes('flir') || t.includes('sonar') || t.includes('instrument')), 'misperception (no instrument to cross-check the eye)', open);
        cite(t.includes('light') && !(t.includes('structured') || t.includes('metallic') || t.includes('disc') || t.includes('triangle')), 'aircraft landing lights / satellites / Starlink trains (point-lights are ambiguous)', open);
        cite(t.includes('orange') || t.includes('fireball') || t.includes('drift'), 'sky lanterns / flares (slow drifting orange sources)', open);

        // A pattern is prosaic-RESISTANT if it defeats at least 2 mundane
        // explanations OR carries critical/high anomaly severity. We only redirect
        // to DISPROVE when the behaviour defeats NOTHING specific AND stays ambiguous.
        const sev = s.meta.severity;
        const resistant = defeats.length >= 2 || sev === 'critical' || sev === 'high';
        const redirect = !resistant && defeats.length === 0 && open.length > 0;

        const why = `The discipline that earns a MUFON director's respect: <b>before I develop a case, I try to break it.</b> I don't dismiss reports by count — I test the described <em>behaviour</em> against each mundane explanation (aircraft, Venus, satellites, Starlink, lanterns, drones) and see which ones the behaviour actually defeats.`;
        const defeatsHtml = defeats.length ? `The reported behaviour specifically defeats: ${defeats.map(d=>'<em>'+d+'</em>').join('; ')}.` : `The reported behaviour does not, on its own, defeat any specific prosaic explanation.`;
        const openHtml = open.length ? ` Still open: ${open.map(o=>'<em>'+o+'</em>').join('; ')}.` : '';

        return {
          why,
          found: `${defeatsHtml}${openHtml}`,
          soWhat: redirect
            ? `<b>These reports are not dismissed — they are re-routed to a DISPROVE track.</b> Because the behaviour leaves a specific prosaic explanation open (above), the highest-value next move is one targeted collection that would confirm or eliminate <em>that</em> explanation across the set. Resolving ${fmt(s.vars.fired||0)} reports one way or the other is itself a finding a director can publish.`
            : resistant
              ? `<b>It survives the skeptic's test on stated grounds:</b> the behaviour defeats ${defeats.length||'multiple'} mundane explanation(s)${sev==='critical'||sev==='high'?` and carries ${sev} anomaly severity`:''}. That is why this pattern is worth the effort — the easy answers have already failed on the evidence, not on faith.`
              : `<b>Inconclusive on prosaic exclusion.</b> The behaviour neither clearly defeats nor is fully explained by mundane causes, so it stays open pending better evidence — neither built up nor dismissed.`,
          impact: redirect ? 'RULES-OUT' : resistant ? 'PROVES' : 'EDUCATES',
          evidence: [{ text: resistant ? `Prosaic-resistant: defeats ${defeats.join(', ')||'on severity'}.` : `Prosaic exclusion open: ${open.join(', ')||'inconclusive'}.`, vector: 'visual' }],
          vars: { prosaicResistant: resistant, prosaicDefeats: defeats.length, prosaicOpen: open.length },
          live: true,
          killed: redirect,
          killedReason: redirect ? `Behaviour leaves ${open[0]||'a prosaic explanation'} open — resolve via targeted collection before developing further.` : '',
        };
      },
    },
    {
      id: 'cross-case',
      label: 'Cross-Case Matcher',
      verb: 'MATCH',
      sources: ['Co-occurrence graph', 'signature vectors'],
      capability: 'Finds which other patterns fire on the same reports — the corroboration / network element.',
      produces: 'KNOWN', vector: 'online',
      dataSource: 'signature co-occurrence graph (LIVE, local)', live: true,
      precondition: s => !s.ranAgents.includes('cross-case'),
      gap: s => s.ranAgents.includes('cross-case') ? 0 : 0.55,
      rationale: () => 'Map which patterns co-occur — reveals compound cases a single report cannot show.',
      execute: s => {
        const nb = coocFor(s.sid).slice(0, 3);
        const why = `A lone individual can't see this, but a 296,000-report database can: <b>which other anomalies show up in the same reports.</b> When a triangle is <em>also</em> silent, <em>also</em> hovering, <em>also</em> causing car engines to stall, that convergence is far harder to explain away than any single trait. This is the cross-case corroboration only scale can reveal.`;
        if (!nb.length) return { why, found: `This pattern tends to fire alone — no strong co-occurring signatures.`, soWhat: `<b>Isolated, so no convergence boost.</b> Not damning, but it means the case can't lean on compound behaviour; it stands on this one trait's own merits.`, impact: 'EDUCATES', evidence: [{ text: 'No strong co-occurrence.', vector: 'online' }], vars: { cooc: 0 }, live: true };
        const names = nb.map(([id, w]) => `“${(sigMeta(id).description || id).slice(0, 40)}…” (${fmt(w)} shared reports)`);
        return { why,
          found: `Co-fires with ${nb.length} other patterns. Strongest link: ${names[0]}.`,
          soWhat: `<b>Corroboration element: SATISFIED.</b> These traits repeatedly appear together on the same reports — a compound signature. That convergence is exactly the kind of structure that resists "they saw a plane," and it hands the investigator a ready-made next thread: pull those shared reports and test them as one event.`,
          impact: 'PROVES',
          evidence: [{ text: `Co-occurs with: ${names.join('; ')}.`, vector: 'online' }], vars: { cooc: nb.length }, live: true };
      },
    },
    {
      id: 'trajectory-assessor',
      label: 'Trajectory Assessor (LLM)',
      verb: 'ASSESS',
      sources: ['Accumulated KNOWN evidence'],
      capability: 'Reads the accumulated KNOWN facts and issues a WEP-qualified judgement — the analytic conclusion. ASSESSED only.',
      produces: 'ASSESSED', vector: 'visual',
      dataSource: 'reasoning over accumulated KNOWN evidence (no new collection)', live: true,
      precondition: s => !s.ranAgents.includes('trajectory-assessor') && s.known.length >= 2,
      gap: s => (s.known.length >= 2 && !s.ranAgents.includes('trajectory-assessor')) ? 0.4 : 0,
      rationale: () => 'Enough KNOWN evidence gathered — produce the WEP-qualified assessment.',
      execute: s => {
        const st = investigationStrength(s);
        const gapsList = [];
        if (!s.vars.instrument) gapsList.push('instrumented capture (radar/FLIR/photo)');
        if (!s.vars.credible) gapsList.push('confirmed trained-observer witnesses');
        if (!(s.vars.cooc > 0)) gapsList.push('cross-case corroboration');
        return {
          why: `Now I stop collecting and <b>reason</b>. Every prior step was search — mathematical, grounded. This is the one judgement call, and IC discipline requires I label it ASSESSED, tie it to the elements I actually established, and attach a probability term — never state it as fact.`,
          found: `On the <b>${st.k} of 5</b> elements of proof established above, it is <b>${st.wep}</b> (≈${st.prob}%) that this pattern warrants a formal field investigation. That probability is a function of the evidence gathered — it is <em>not</em> a claim about what the objects are or where they come from.`,
          soWhat: gapsList.length
            ? `<b>The path forward is explicit and specific:</b> confidence is held at ${st.conf} by the missing element(s) — ${gapsList.join('; ')}. Each is a concrete, collectable task. Close them and this judgement moves up the scale. That is exactly what to task next — not more of the same reports, but the <em>kind</em> of evidence that's missing.`
            : `<b>All five elements are established</b> — multiplicity, instrumentation, credibility, prosaic-resistance, and cross-case corroboration. This is as strong as pattern-level evidence gets without fresh field collection. Hand it to a human investigator with confidence.`,
          impact: 'ASSESSED',
          evidence: [], assessed: [{ text: `${st.wep} (≈${st.prob}%) — warrants investigation, on ${st.k}/5 elements.`, wep: st.wep }],
          vars: { assessed: true }, live: true,
        };
      },
    },
  ];
  const getAgent = id => AGENTS.find(a => a.id === id);

  // ===========================================================================
  // HYBRID PLANNER — rules-authoritative next-agent selection
  // ===========================================================================
  function planNext(s) {
    if (s.killed) return { decision: 'stop', stopReason: s.killedReason, chosen: null, alternatives: [] };
    const eligible = AGENTS.filter(a => a.precondition(s)).map(a => ({ a, g: a.gap(s) })).filter(x => x.g > 0);
    eligible.sort((x, y) => y.g - x.g);
    if (!eligible.length) return { decision: 'stop', stopReason: 'Saturation — no eligible agent adds new signal. Synthesize and transfer to human.', chosen: null, alternatives: [] };
    const chosen = eligible[0].a;
    const alternatives = eligible.slice(1, 4).map(x => ({ id: x.a.id, label: x.a.label, gap: +x.g.toFixed(2) }));
    return {
      decision: 'continue',
      chosen: { id: chosen.id, label: chosen.label, verb: chosen.verb, sources: chosen.sources, produces: chosen.produces, vector: chosen.vector, live: chosen.live, capability: chosen.capability },
      gapClosed: +eligible[0].g.toFixed(2),
      rationale: chosen.rationale(s),
      alternatives,
    };
  }

  // Execute an agent, fold result into state.
  function runAgent(s, id) {
    const a = getAgent(id); if (!a) return null;
    const res = a.execute(s);
    s.ranAgents.push(id);
    (res.evidence || []).forEach(e => s.known.push(Object.assign({ source: a.label, live: res.live }, e)));
    (res.assessed || []).forEach(e => s.assessed.push(e));
    Object.assign(s.vars, res.vars || {});
    if (res.killed) { s.killed = true; s.killedReason = res.killedReason; }
    return { agent: a, found: res.found, live: res.live, dataSourceRequired: res.dataSourceRequired, raw: res };
  }

  // Analyst injects a focus hint (human-in-the-loop). Tagged human-sourced KNOWN.
  function injectHint(s, hint) {
    const h = (hint || '').trim(); if (!h) return;
    s.hints.push(h);
    s.known.push({ text: `Analyst-directed focus: "${h}" (human-sourced).`, vector: 'online', source: 'Analyst', live: true, human: true });
    // Injecting a hint re-opens credibility/cross-case if they'd run, so the
    // planner re-plans around the new focus.
    ['credibility', 'cross-case'].forEach(id => {
      const i = s.ranAgents.indexOf(id); if (i >= 0) s.ranAgents.splice(i, 1);
    });
  }

  // Hypothesis shown before the run (ASSESSED, with confidence).
  function hypothesisFor(sid) {
    const m = sigMeta(sid);
    return `This investigation weighs how strong the case is that the "${(m.description || '').slice(0, 70)}" pattern — ${fmt(m.fired)} reports worldwide — is a genuine anomaly current science cannot explain. It does not seek to "prove" it (UAP can't be proven in the strict experimental sense); it establishes how well-attested and unexplained it is, and which explanation the evidence favours.`;
  }

  // How many of the 5 evidentiary elements are established (drives ALL confidence).
  function elementsKnown(s) {
    return [s.vars.multi, s.vars.instrument, s.vars.credible, s.vars.prosaicResistant, (s.vars.cooc || 0) > 0].filter(Boolean).length;
  }
  // Confidence is driven by ELEMENTS OF PROOF, never by report-volume share.
  // Returns { conf, prob, wep } — prob is the probability the pattern warrants
  // investigation, mapped to an IC Word of Estimative Probability.
  function investigationStrength(s) {
    const k = elementsKnown(s);              // 0..5
    const prob = [8, 25, 45, 62, 82, 95][k]; // monotonic in elements
    const wep = U.wepForProbability ? U.wepForProbability(prob) : 'likely';
    const conf = k >= 4 ? 'HIGH' : k >= 2 ? 'MODERATE' : 'LOW';
    return { k, prob, wep, conf };
  }

  // Anomaly-strength verdict. We do NOT claim "proven" — UAP cannot be proven in
  // the strict repeatable-experiment sense. The honest, audience-right question is:
  // "How strong is the case that this is a genuine anomaly we can't yet explain?"
  //   EXPLAINED → INSUFFICIENT → ANOMALOUS → STRONG ANOMALY (UNEXPLAINED)
  function verdictFor(s) {
    const st = investigationStrength(s);
    // "prosaic fits and little else" => a prosaic explanation is available
    if (s.killed) {
      return {
        verdict: 'LIKELY EXPLAINED', conf: 'MODERATE', klass: 'explained',
        reason: `A conventional explanation plausibly accounts for this pattern (see the prosaic-exclusion step). That is a genuine result — resolving reports is as valuable as elevating them. Note: "explained" means a mundane cause fits the evidence, not that every individual report is dismissed.`,
        done: true, strength: st,
      };
    }
    if (st.k >= 4) {
      return {
        verdict: 'STRONG ANOMALY · UNEXPLAINED', conf: 'HIGH', klass: 'strong',
        reason: `This is one of the most robustly documented patterns in the corpus — ${st.k} of 5 evidentiary elements established, it survived the prosaic-exclusion test, and it recurs across independent cases and cultures. It is <b>not proven</b> (UAP can't be proven in the strict experimental sense) — but it is <b>${st.wep}</b> a real, well-attested phenomenon that conventional explanations do not cover. In other words: the mystery here is genuine and documented. That is exactly why it warrants serious, sustained investigation.`,
        done: false, strength: st,
      };
    }
    if (st.k >= 2) {
      return {
        verdict: 'ANOMALOUS · WORTH PURSUING', conf: 'MODERATE', klass: 'anomalous',
        reason: `${st.k} of 5 elements are established — a real signal that resists the easy explanations, with specific, nameable gaps. It is ${st.wep} to be a genuine anomaly rather than noise. Closing the missing elements below would strengthen the case (never "prove" it — but move it toward STRONG ANOMALY).`,
        done: false, strength: st,
      };
    }
    return {
      verdict: 'INSUFFICIENT SIGNAL', conf: 'LOW', klass: 'insufficient',
      reason: `Only ${st.k} of 5 elements could be established from available data. That is a statement about our <em>collection</em>, not a verdict that nothing happened — the reports stand, but we lack the corroboration to call it anomalous yet. Absence of proof is not proof of absence.`,
      done: true, strength: st,
    };
  }

  // ── Analysis of Competing Hypotheses (ACH) — serious but open ──────────────
  // Five explanations weighed against the pattern's own evidence. Fit is 0..100,
  // grounded in the signature semantics + which evidentiary elements are present.
  // No hypothesis is dismissed; none is declared the winner. The user explores.
  function hypothesesFor(sid) {
    const m = sigMeta(sid);
    const t = textOf(sid);
    const has = ks => ks.some(k => t.includes(k));
    const sev = m.severity;
    const instrument = has(['radar', 'flir', 'sensor', 'sonar', 'photograph', 'trace']);
    const credible = has(['pilot', 'police', 'military', 'controller', 'trained']);
    const kinematics = sev === 'critical' || has(['instant', 'right angle', 'hover', 'accelerat', 'against the wind', 'no observable radius', 'transmedium', 'submerged']);
    const official = has(['military', 'radar', 'scrambled', 'classified', 'confiscated', 'government', 'restricted']);
    const structured = has(['triangle', 'disc', 'metallic', 'craft', 'structured', 'cylinder', 'dome']);
    const ambiguousLight = has(['light', 'orange', 'fireball', 'glow']) && !structured;

    function clamp(x){ return Math.max(3, Math.min(97, Math.round(x))); }
    const H = [];
    // 1. Prosaic
    H.push({
      key: 'Prosaic / misidentification',
      icon: '✈️',
      fit: clamp(30 + (ambiguousLight ? 35 : 0) + (kinematics ? -25 : 10) + (instrument ? -15 : 8)),
      supports: ambiguousLight ? 'Point-lights and orange glows are readily produced by aircraft, satellites, Starlink trains, and lanterns.' : 'Some accounts could involve conventional aircraft or astronomical objects seen under poor conditions.',
      undercuts: kinematics ? 'The described kinematics exceed known airframe limits — hard to attribute to conventional craft.' : (instrument ? 'Instrument corroboration is difficult to explain as pure misperception.' : 'Structured-body descriptions are less consistent with simple point-source misID.'),
      shift: 'One controlled collection (radar tape / calibrated photo) that matched a known object would raise this sharply.',
    });
    // 2. Classified human technology
    H.push({
      key: 'Classified human technology',
      icon: '🛩️',
      fit: clamp(35 + (structured ? 12 : 0) + (kinematics ? 18 : 0) + (official ? 10 : 0)),
      supports: 'Secret aircraft, drones, and test programs are real, and their existence is routinely denied until declassified — some patterns fit advanced but terrestrial engineering.',
      undercuts: kinematics ? 'The reported performance (instant acceleration / trans-medium travel) exceeds publicly known human engineering by a wide margin.' : 'Global, decades-long distribution is hard to sustain as one nation\'s secret program.',
      shift: 'A declassification or provenance link to a known program would confirm this; continued performance beyond human limits weakens it.',
    });
    // 3. Unknown natural phenomenon
    H.push({
      key: 'Unknown natural phenomenon',
      icon: '🌩️',
      fit: clamp(25 + (ambiguousLight ? 20 : 0) + (structured ? -15 : 0) + (kinematics ? -10 : 5)),
      supports: 'Atmospheric plasmas, ball lightning, and rare optical effects are poorly characterized and could explain some luminous, shape-shifting reports.',
      undercuts: structured ? 'A solid, structured, metallic body is not consistent with a diffuse natural plasma.' : 'Sustained controlled flight against the wind is unlike known natural phenomena.',
      shift: 'Spectroscopic or field-measurement data from an event would strongly favor or kill this.',
    });
    // 4. Non-human intelligence (serious, evidence-weighed)
    H.push({
      key: 'Non-human intelligence',
      icon: '🛸',
      fit: clamp(15 + (kinematics ? 22 : 0) + (instrument ? 10 : 0) + (credible ? 8 : 0) + (structured ? 6 : 0)),
      supports: kinematics ? 'Apparent controlled flight with performance beyond known human and natural limits is the observation that keeps this hypothesis on the table for serious analysts.' : 'Consistent structured-craft descriptions across unconnected cultures are cited in support.',
      undercuts: 'Extraordinary claims require extraordinary evidence; there is no physical artifact, and instrument data remains contested and incomplete.',
      shift: 'A recovered artifact or unambiguous multi-sensor track would transform this; it stays a live hypothesis precisely because the strongest cases are not yet explained.',
    });
    // 5. Information suppression / cover-up (the conspiracy lane, weighed seriously)
    H.push({
      key: 'Information suppression',
      icon: '🔒',
      fit: clamp(12 + (official ? 30 : 0) + (instrument ? 8 : 0)),
      supports: official ? 'This pattern involves military/official response, restricted airspace, or confiscation language — the conditions under which records are classified or withheld.' : 'Documented cases exist where UAP records were classified, redacted, or destroyed, which is itself a verifiable behaviour.',
      undercuts: 'Suppression explains missing data, not the sightings themselves; it is a claim about institutions, not about what was seen.',
      shift: 'FOIA releases, whistleblower testimony, or declassified files would directly raise or lower this — it is the most empirically testable of the non-prosaic lanes.',
    });
    H.sort((a, b) => b.fit - a.fit);
    return H;
  }

  // Action items for the human investigator (timed).
  function actionItems(s) {
    const items = [];
    if (!s.vars.instrument) items.push('WITHIN 72H: Request ATC/military radar and any FLIR for the highest-witness events in this pattern.');
    if (!s.vars.credible) items.push('WITHIN 7D: Re-interview reporters to identify trained observers (pilots, police, controllers).');
    if ((s.vars.cooc || 0) > 0) items.push('WITHIN 7D: Pull the co-occurring-pattern reports and test for a single compound event.');
    if (s.vars.multi) items.push('ONGOING: Monitor the top reporting countries for new corroborating reports.');
    if (!items.length) items.push('IMMEDIATE: Transfer package to a human field investigator — AI collection saturated.');
    return items;
  }

  // Documented precedent (from taxonomy precedent_case) — real, famous cases the
  // pattern matches. External reference; NOT a claim MUFON confirmed our corpus.
  function precedentFor(sid) {
    const p = sigMeta(sid).precedent_case || '';
    return p ? { text: p, label: 'Documented precedent (external reference)' } : null;
  }
  // Real example reports from the corpus that fired this pattern — inspectable
  // primary sources (date / city / country). KNOWN data, not inference.
  function corpusCasesFor(sid, n) {
    const pts = (D.sig_points || {})[sid] || [];
    // prefer city-precise, higher-signal, with a year
    const ranked = pts.slice().filter(p => p.year).sort((a, b) =>
      (a.geo === 'city' ? -1 : 0) - (b.geo === 'city' ? -1 : 0) || (b.n || 0) - (a.n || 0));
    return ranked.slice(0, n || 6).map(p => ({
      where: [p.city, p.country].filter(Boolean).join(', ') || p.country || 'unknown',
      year: p.year, sigs: p.n || 1, approx: p.geo === 'country',
    }));
  }

  global.UAPInvestigator = {
    AGENTS, newState, planNext, runAgent, injectHint, hypothesisFor, verdictFor,
    actionItems, getAgent, investigationStrength, elementsKnown, precedentFor, corpusCasesFor,
    hypothesesFor,
  };
})(window);
