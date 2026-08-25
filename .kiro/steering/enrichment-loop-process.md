# AI Research Enrichment Loop — Standard Operating Procedure

## When to Use
Any time you're building a knowledge base / entity library from source material (mythology, crime patterns, intelligence analysis, etc.), follow this loop AUTOMATICALLY without being asked.

## The Loop

### Step 1: Initial Extraction
- Process available source texts through Bedrock
- Extract entities, relationships, events
- Score against existing patterns/signatures

### Step 2: Gap Assessment
After initial extraction, assess:
- Which patterns have WEAK coverage (<3 independent sources)?
- Which geographic/cultural areas are MISSING entirely?
- What's the entity count per tradition?

### Step 3: Targeted Enrichment (Round 1)
- Search for texts that fill the identified gaps
- Prioritize by SIGNAL DENSITY (mythology/cosmogony > history > poetry > administrative)
- Process new texts, merge into library

### Step 4: Diminishing Returns Assessment (MANDATORY)
After each round, evaluate EVERY tradition/source area:

| Question | If YES → | If NO → |
|----------|----------|---------|
| Would more data from this tradition change which patterns fire? | CONTINUE | STOP |
| Would new entities strengthen cross-tradition connections? | CONTINUE | STOP |
| Is there a KNOWN text we're missing that is THE source? | GET IT | STOP |
| Would deeper data serve a specific user need (e.g., "going to Ireland")? | GET IT | STOP |
| Are we just adding secondary figures that don't affect scoring? | STOP | — |

### Step 5: Declare "Point of Goodness"
STOP enriching when:
- Every pattern has 5+ independent cultural confirmations
- Every major geographic tradition is represented
- Adding more texts would increase count but NOT change detection confidence
- Marginal entities are secondary figures (minor gods, place names) not cross-cultural connectors

### Step 6: Document and Move On
State clearly:
- "Enrichment complete. X entities across Y sources and Z traditions."
- "Point of goodness reached because: [specific reason]"
- "Exception for future: [any known texts worth getting later]"
- Move to embedding/scoring (Phase 3)

## Rules
- NEVER do more than 3 enrichment rounds without checking diminishing returns
- ALWAYS assess before each round — don't just blindly add more
- The goal is PATTERN DETECTION QUALITY, not entity count
- 200-300 entities across 8+ traditions is typically sufficient for cross-cultural pattern matching
- User-specific context (e.g., "I'm going to Ireland") overrides the general stop criteria for targeted deepening
- Cost should stay under $1 total for the enrichment phase (Haiku @ ~$0.025/call)

## Anti-Patterns (NEVER do these)
- ❌ Add texts just because they exist and are famous
- ❌ Deep-dive a tradition that already has 5+ entities matching all patterns
- ❌ Process administrative/legal/liturgical texts for mythology patterns
- ❌ Add more Greek heroes when the pattern is already confirmed from 8 traditions
- ❌ Enrich without first asking "will this change what patterns fire?"


## MANDATORY: Step D after EVERY dataset (do not skip)
After merging ANY new dataset (national source, NGO, scientific corpus, seed), you MUST return to
the gap-mining step BEFORE adding the next dataset:
1. Re-run the global scan (re-does Tier 1 + fires all signatures over the whole combined corpus).
2. **Step D — gap-mine the firing corpus:** isolate Tier-1 survivors that fire 0–1 signatures
   (near-misses), cluster their recurring vocabulary, and author the data-supported NEW signatures
   (frequency + cited example required; no "looks right" signatures).
3. Re-score existing seeds (no regressions), re-run the global scan, record the firing-count/country
   delta (the compounding lift).
Only THEN move to the next dataset. Tool: `scripts/mine_signature_gaps.py`.
Canonical detail lives in `taxonomy-enrichment-master-loop.md` (step 3/4). This is the step that
produced the "iteration 3/4" gold in the money-laundering work.