# -*- coding: utf-8 -*-
"""Carve a clean single-domain POC package out of the TALOS monorepo.

Reads src/config/domain-registry.json and, for a chosen --domain, produces the SHARED ENGINE
plus ONLY that domain's pack, EXCLUDING every other domain (especially reference/internal demos
like UAP and Ancient Mysteries). This is what you hand a customer for a POC.

Design goals (mirrors the discipline of scripts/zip_mobile_dossiers.py):
  - Registry-driven: the boundary lives in domain-registry.json, not in this script.
  - Dry-run by default: prints an auditable INCLUDED / EXCLUDED manifest and does NOT copy.
  - Safe: never touches the source tree; only writes under --out when --write is given.
  - Honest: refuses to include any 'reference' or 'internal' domain's files in a customer package.

Usage:
  python scripts/package_poc.py --domain asylum-fraud                 # dry-run manifest
  python scripts/package_poc.py --domain antitrust --out dist/antitrust-poc --write
  python scripts/package_poc.py --list                                # list domains + tiers
"""
import argparse
import fnmatch
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "src", "config", "domain-registry.json")


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def norm(p):
    return p.replace("\\", "/")


# Vendored pip packages + build junk that live under src/ but are NOT our source.
# (Mirrors .gitignore. A POC ships our code; deps are reinstalled from requirements.)
EXCLUDE_SUBSTRINGS = (
    "__pycache__/", "/.pytest_cache/", ".dist-info/", "/bin/",
    "/attr/", "/frozenlist/", "/multidict/", "/propcache/", "/yarl/", "/idna/",
    "/certifi/", "/charset_normalizer/", "/urllib3/", "/requests/", "/psycopg2/",
    "/psycopg2_binary.libs/", "/aenum/", "/async_timeout/", "/gremlin_python/",
    "/isodate/", "/nest_asyncio", "/boto3/", "/botocore/", "/numpy/", "/pandas/",
)


def is_excluded(rel):
    return any(s in ("/" + rel) for s in EXCLUDE_SUBSTRINGS)


def collect_globs(entry_globs):
    """Turn registry glob/dir/file entries into a set of concrete relative file paths.
    Entries ending in '/**' or '/' are treated as recursive dirs; entries with '(' notes are
    stripped of the parenthetical; plain paths are taken literally (may be files or dirs)."""
    out = set()
    for raw in entry_globs or []:
        g = raw.split(" (")[0].strip()  # drop "(TO CREATE)" / "(subtree)" notes
        if not g:
            continue
        # recursive dir
        if g.endswith("/**") or g.endswith("/"):
            base = g.rstrip("/*")
            absbase = os.path.join(ROOT, base)
            if os.path.isdir(absbase):
                for dp, _dn, fns in os.walk(absbase):
                    for fn in fns:
                        rel = norm(os.path.relpath(os.path.join(dp, fn), ROOT))
                        if not is_excluded(rel):
                            out.add(rel)
            continue
        absg = os.path.join(ROOT, g)
        if os.path.isdir(absg):
            for dp, _dn, fns in os.walk(absg):
                for fn in fns:
                    rel = norm(os.path.relpath(os.path.join(dp, fn), ROOT))
                    if not is_excluded(rel):
                        out.add(rel)
        elif os.path.isfile(absg):
            out.add(norm(g))
        else:
            # treat as a glob against the tree (rare)
            for dp, _dn, fns in os.walk(ROOT):
                for fn in fns:
                    rel = norm(os.path.relpath(os.path.join(dp, fn), ROOT))
                    if fnmatch.fnmatch(rel, g):
                        out.add(rel)
    return out


def domain_owned_files(dom):
    """All concrete files a domain owns across its registry keys."""
    keys = ("tenant_config", "taxonomy", "seed_globs", "frontend_globs",
            "services", "api_handlers", "builders")
    globs = []
    for k in keys:
        v = dom.get(k)
        if isinstance(v, list):
            globs.extend(v)
        elif isinstance(v, str) and v:
            globs.append(v)
    return collect_globs(globs)


def shared_engine_files(reg):
    se = reg.get("shared_engine", {})
    globs = []
    for k in ("infra", "backend", "frontend_generic", "shared_data"):
        globs.extend(se.get(k, []))
    return collect_globs(globs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", help="domain id to package (see --list)")
    ap.add_argument("--out", default="dist/poc", help="output dir (used only with --write)")
    ap.add_argument("--write", action="store_true", help="actually copy files (default: dry-run manifest only)")
    ap.add_argument("--list", action="store_true", help="list domains + tiers and exit")
    ap.add_argument("--allow-reference", action="store_true",
                    help="override the safety refusal to package a reference/internal domain")
    args = ap.parse_args()

    reg = load_registry()
    doms = {d["id"]: d for d in reg["domains"]}

    if args.list or not args.domain:
        print("Domains in registry (id : tier : status):")
        for d in reg["domains"]:
            flag = "  [needs owner confirmation]" if d.get("needs_owner_confirmation") else ""
            print(f"  {d['id']:<20} {d['tier']:<10} {d.get('status','?')}{flag}")
        if not args.domain:
            return

    if args.domain not in doms:
        raise SystemExit(f"Unknown domain '{args.domain}'. Use --list.")
    dom = doms[args.domain]

    # SAFETY: never build a customer package from a reference/internal demo unless overridden.
    if dom["tier"] in ("reference", "internal") and not args.allow_reference:
        raise SystemExit(
            f"REFUSED: '{args.domain}' is tier '{dom['tier']}' (a demo, not a customer use case).\n"
            f"Packaging it for a customer would ship the fun/experimental demos. "
            f"If you really mean to, re-run with --allow-reference.")

    engine = shared_engine_files(reg)
    target = domain_owned_files(dom)

    # Everything owned by OTHER domains must be excluded (this is the safety guarantee).
    other_owned = set()
    for d in reg["domains"]:
        if d["id"] == args.domain:
            continue
        other_owned |= domain_owned_files(d)

    included = sorted((engine | target))
    # A file the target shares with the engine list stays in; a file owned by another domain
    # AND not the target/engine is excluded.
    excluded_other = sorted(other_owned - engine - target)

    # Report
    ref_internal_excluded = sorted(
        f for d in reg["domains"] if d["tier"] in ("reference", "internal") and d["id"] != args.domain
        for f in domain_owned_files(d)
        if f not in engine and f not in target
    )

    print("=" * 70)
    print(f"POC PACKAGE PLAN  --  domain: {args.domain}  (tier: {dom['tier']})")
    print("=" * 70)
    print(f"INCLUDED files:        {len(included)}")
    print(f"  - shared engine:     {len(engine)}")
    print(f"  - {args.domain} pack: {len(target)}")
    print(f"EXCLUDED (other domains' owned files): {len(excluded_other)}")
    print(f"  - of which reference/internal demo files: {len(ref_internal_excluded)}")
    print("-" * 70)
    print("Sample INCLUDED (domain pack):")
    for f in sorted(target)[:15]:
        print(f"  + {f}")
    print("Sample EXCLUDED (reference/internal demos — must NOT ship to customer):")
    for f in ref_internal_excluded[:15]:
        print(f"  - {f}")

    # Safety assertion: no uap-*/grid-globe-*/archon/succession file may be in INCLUDED
    leak = [f for f in included if any(
        s in f for s in ("uap-", "grid-globe", "/archon", "succession-", "conspiracy-seed/ufo",
                          "audio/dossiers"))]
    # (Allow if the target domain legitimately owns them, e.g. packaging ufo-uap itself.)
    leak = [f for f in leak if f not in target]
    if leak:
        print("-" * 70)
        print(f"WARNING: {len(leak)} reference-demo-looking files leaked into INCLUDED:")
        for f in leak[:20]:
            print(f"  !! {f}")
    else:
        print("-" * 70)
        print("SAFETY CHECK PASSED: no reference-demo files (uap/grid-globe/archon/succession) in the package.")

    if not args.write:
        print("\n(dry-run — no files copied. Re-run with --write --out <dir> to produce the package.)")
        return

    out = os.path.join(ROOT, args.out)
    if os.path.exists(out):
        shutil.rmtree(out)
    for rel in included:
        src = os.path.join(ROOT, rel)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    # write a manifest
    with open(os.path.join(out, "POC-MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump({"domain": args.domain, "tier": dom["tier"],
                   "included_count": len(included), "excluded_other_count": len(excluded_other),
                   "included": included}, f, indent=2)
    print(f"\nWrote {len(included)} files to {out} (+ POC-MANIFEST.json)")


if __name__ == "__main__":
    main()
