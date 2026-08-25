# TALOS Domain-Pack Standard

**One engine, swappable domain packs.** This is the contract that lets us run many use cases
(HSI, Asylum Fraud, Counterfeiting, Antitrust, plus reference demos like UAP and Ancient
Mysteries) from a single monorepo — and carve out a clean single-domain package for any customer
POC without hand-editing.

This doc doubles as the **"start here" onboarding for colleagues.**

---

## 1. Mental model

TALOS = **shared engine** + **domain packs**.

- **Shared engine** (domain-agnostic, always shipped): CDK infrastructure, the single {proxy+}
  Lambda API, the ~100 core services (entity extraction, ingestion, search, graph, audit, proof
  engine), the generic frontend (investigator, prosecutor, pattern-library, workbench, network
  discovery), and the shared backend: **Neptune + OpenSearch + Aurora + Bedrock**.
- **Domain pack** (per use case): a tenant config, a taxonomy, seed data, optional domain
  frontend page(s), and optional domain-specific services + one route prefix.

Everything a use case needs beyond the engine lives in its pack. Nothing in the engine
hardcodes a domain.

## 2. Why the packs are cleanly separable (verified)

Audit (2026-08) of the main router `src/lambdas/api/case_files.py`: **every domain sub-handler is
imported lazily inside its route branch**, e.g.

```python
if path.startswith("/pre-case/"):
    from lambdas.api.pre_case_handler import dispatch_handler as pc_intel_dispatch
    return pc_intel_dispatch(event, context)
```

There are **no unconditional top-level imports of domain-specific services** in the shared router.
Consequence: removing a domain pack (its handler + services + data + frontend) does **not** break
the engine or any other pack — Python never executes that import unless the path is called, and a
removed domain's paths are only ever called by its (also-removed) frontend. **No refactor is
required for clean packaging.**

## 3. The pack convention (follow this for every new domain)

A domain with id `<domain>` owns, by naming convention:

| Piece | Location |
|-------|----------|
| Tenant config | `src/config/tenants/<domain>.json` |
| Taxonomy | `src/data/<domain>-taxonomy.json` |
| Seed data | `src/data/<domain>-seed/**` (or a `conspiracy-seed/<name>/` folder) |
| Frontend page(s) | `src/frontend/<domain>-*.html` + `<domain>-*.js` |
| Domain services | `src/services/<domain>_*.py` (lazily imported) |
| API handler | `src/lambdas/api/<domain>_handler.py` + one route prefix in `case_files.py` |
| Registry entry | one object in `src/config/domain-registry.json` |

Anything not matching a pack's globs is treated as shared engine.

## 4. The registry: `src/config/domain-registry.json`

Single source of truth for what demos exist and which files each owns. Drives two things:

1. **The `DEMO_TIER` frontend toggle** (which demos show to whom).
2. **`scripts/package_poc.py`** (what goes in a customer carve-out).

Each domain has a **tier**:

- **`serious`** — real client/mission use cases (Asylum Fraud, HSI, Counterfeiting, Antitrust,
  Sex-Trafficking). Safe for customer POCs and serious colleague demos.
- **`reference`** — harmless "prove-the-approach" demos (UAP, Ancient Mysteries, Conspiracy
  Theories). **Excluded from every customer package.** Shown to colleagues only when `DEMO_TIER=all`.
- **`internal`** — dev/experimental or separate products (Succession). Not for external audiences.

Entries with `"needs_owner_confirmation": true` were inferred from code and **you should verify or
correct them** (esp. HSI, Compass, Counterfeiting, Succession tier). Compass in particular was not
found in this repo — it may live in the connected Finding Fentanyl / TALOS frontend project.

## 5. Two audiences, two delivery modes (same registry)

### Customers → carved-out single-domain package
```
python scripts/package_poc.py --domain asylum-fraud --out dist/asylum-poc
```
Emits the shared engine + only that domain's pack; excludes every other domain, especially all
`reference`/`internal` ones. The UAP and Ancient Mysteries demos never appear in a customer package.
Use for: anything a customer sees, clones, or deploys.

### Colleagues → full monorepo + `DEMO_TIER` toggle
Colleagues get the whole repo (nothing hidden), but the frontend defaults to `DEMO_TIER='serious'`
so the reference demos are hidden until someone flips `config.js` to `'all'`. Frame the reference
demos as **worked examples that prove the pattern engine generalizes**, not toys.

## 6. Shared vs. isolated infrastructure (the one real decision)

- **Shared infra** (many tenants on one deployed Neptune/OpenSearch/Aurora, separated by
  `tenant_id` / index prefix / Aurora schema): cheap and fast. Use for **your own demos and internal
  proofs**. This is the "Finding Fentanyl reuses Research Analyst's endpoints" model.
- **Isolated deployment** (a `package_poc.py` output deployed in the customer's own account): use for
  **anything a customer touches or owns**, because you cannot give a customer access to a cluster
  that also holds another customer's data.

Rule of thumb: **shared for us, isolated for them.**

## 7. Adding a new demo (checklist)

1. Create `src/config/tenants/<domain>.json` (proof standard, s3 prefix, aurora schema, index prefix).
2. Create `src/data/<domain>-taxonomy.json` and `src/data/<domain>-seed/`.
3. (Optional) Add `src/frontend/<domain>-*.html/js` and a lazily-imported
   `src/lambdas/api/<domain>_handler.py` + one route branch in `case_files.py`.
4. Add one entry to `src/config/domain-registry.json` with the correct `tier` and file globs.
5. Done — it's automatically toggleable (DEMO_TIER) and packageable (package_poc.py).
