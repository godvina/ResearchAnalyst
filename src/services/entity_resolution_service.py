"""Entity Resolution Service — fuzzy + LLM-powered entity deduplication.

Identifies and merges duplicate entity nodes in Neptune that refer to the
same real-world entity but have different canonical names (e.g. "Jeffrey
Epstein" vs "Jeffrey E. Epstein" vs "J. Epstein").

Strategy (hybrid):
1. Pull all entity nodes for a case from Neptune via Gremlin
2. Group by entity_type (only compare within same type)
3. Fast fuzzy pass: Jaro-Winkler similarity + normalization rules
4. Optional LLM pass: send ambiguous candidate pairs to Bedrock
5. Build merge clusters (transitive closure)
6. Execute merges in Neptune: re-link edges, sum occurrences, drop duplicates
7. Update OpenSearch persons metadata to reflect merged names

Runs inside a Lambda (VPC) since Neptune is not publicly accessible.
"""

import json
import logging
import re
import ssl
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Similarity thresholds ---
AUTO_MERGE_THRESHOLD = 0.92   # Above this: merge without LLM
LLM_REVIEW_THRESHOLD = 0.78  # Between this and auto: ask LLM
# Below LLM_REVIEW_THRESHOLD: skip


@dataclass
class MergeCandidate:
    name_a: str
    name_b: str
    entity_type: str
    similarity: float
    method: str = ""       # "auto" | "llm_confirmed" | "llm_rejected" | "rule"
    llm_reasoning: str = ""


@dataclass
class MergeCluster:
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    entity_type: str = ""
    total_occurrences: int = 0


# =====================================================================
# String normalization & similarity
# =====================================================================

def normalize_name(name: str) -> str:
    """Normalize an entity name for comparison."""
    s = name.strip().lower()
    for prefix in ("mr.", "mrs.", "ms.", "dr.", "prof.", "hon.", "rev."):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".,;:")
    return s


def jaro_winkler(s1: str, s2: str) -> float:
    """Jaro-Winkler similarity (0.0 to 1.0)."""
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    match_dist = max(len1, len2) // 2 - 1
    if match_dist < 0:
        match_dist = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_dist)
        end = min(i + match_dist + 1, len2)
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    jaro = (matches / len1 + matches / len2 +
            (matches - transpositions / 2) / matches) / 3
    prefix_len = 0
    for i in range(min(4, len1, len2)):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break
    return jaro + prefix_len * 0.1 * (1 - jaro)


def _is_initial_match(short: str, long: str) -> bool:
    """Check if short is an initial-based variant of long.
    'J. Epstein' matches 'Jeffrey Epstein'.
    """
    short_parts = short.split()
    long_parts = long.split()
    if len(short_parts) < 2 or len(long_parts) < 2:
        return False
    if short_parts[-1] != long_parts[-1]:
        return False
    short_firsts = short_parts[:-1]
    long_firsts = long_parts[:-1]
    if len(short_firsts) > len(long_firsts):
        return False
    for sf, lf in zip(short_firsts, long_firsts):
        sf_clean = sf.rstrip(".")
        if len(sf_clean) == 1:
            if sf_clean != lf[0]:
                return False
        elif jaro_winkler(sf_clean, lf) < 0.85:
            return False
    return True


def _is_reversed_name(a: str, b: str) -> bool:
    """'Epstein, Jeffrey' vs 'Jeffrey Epstein'."""
    if "," in a and "," not in b:
        parts = [p.strip() for p in a.split(",", 1)]
        if len(parts) == 2:
            reconstructed = f"{parts[1]} {parts[0]}"
            return jaro_winkler(normalize_name(reconstructed), normalize_name(b)) > 0.92
    if "," in b and "," not in a:
        return _is_reversed_name(b, a)
    return False


def _is_reference_id(name: str) -> bool:
    """Check if a name looks like a document/reference ID (e.g. EFTA00001515).

    These are alphanumeric codes that should only merge on exact match,
    not fuzzy similarity.
    """
    s = name.strip()
    # Pattern: letters followed by digits, or all-caps with digits
    if re.match(r"^[A-Z]{2,}[\d]+$", s):
        return True
    # Pattern: digits with dashes/dots (case numbers, bates numbers)
    if re.match(r"^[\d][\d\-\.]+[\d]$", s):
        return True
    return False


def compute_similarity(name_a: str, name_b: str, entity_type: str) -> float:
    """Type-aware similarity between two entity names."""
    norm_a = normalize_name(name_a)
    norm_b = normalize_name(name_b)

    if norm_a == norm_b:
        return 1.0

    # Exact-match types: phone, email, account, financial, date — check before reference ID
    if entity_type in ("phone_number", "email", "account_number", "financial_amount", "date"):
        digits_a = re.sub(r"\D", "", norm_a)
        digits_b = re.sub(r"\D", "", norm_b)
        if digits_a and digits_b:
            return 1.0 if digits_a == digits_b else 0.0

    # Reference IDs / document numbers: exact match only
    if _is_reference_id(name_a) or _is_reference_id(name_b):
        return 1.0 if norm_a == norm_b else 0.0

    if entity_type == "person":
        # Single-word names are too ambiguous for fuzzy matching
        if len(norm_a.split()) < 2 or len(norm_b.split()) < 2:
            return 1.0 if norm_a == norm_b else 0.0
        if _is_initial_match(norm_a, norm_b) or _is_initial_match(norm_b, norm_a):
            return 0.95
        if _is_reversed_name(name_a, name_b):
            return 0.97

    return jaro_winkler(norm_a, norm_b)


# =====================================================================
# Neptune Gremlin helpers (runs inside Lambda / VPC)
# =====================================================================

def _gremlin_http(endpoint: str, port: str, query: str, timeout: int = 30) -> list:
    """Execute a Gremlin query via Neptune HTTP API."""
    url = f"https://{endpoint}:{port}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        result = body.get("result", {}).get("data", {})
        if isinstance(result, dict) and "@value" in result:
            return result["@value"]
        if isinstance(result, list):
            return result
        return [result] if result else []


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def _gs_val(v):
    """Unwrap a GraphSON @value wrapper if present."""
    if isinstance(v, dict) and "@value" in v:
        return v["@value"]
    return v


def _parse_graphson_map(item) -> dict:
    """Parse a GraphSON map (from project() step) into a plain dict.

    Neptune returns project() results as either:
    - Plain dict: {"name": "Jeffrey Epstein", "type": "person", ...}
    - GraphSON map: {"@type": "g:Map", "@value": ["name", "Jeffrey Epstein", "type", "person", ...]}
    """
    if not item:
        return {}

    # Already a plain dict with our expected keys
    if isinstance(item, dict) and "name" in item:
        return {k: _gs_val(v) for k, v in item.items()}

    # GraphSON g:Map format: {"@type": "g:Map", "@value": [k1, v1, k2, v2, ...]}
    if isinstance(item, dict) and item.get("@type") == "g:Map":
        kv_list = item.get("@value", [])
        result = {}
        for i in range(0, len(kv_list) - 1, 2):
            key = _gs_val(kv_list[i])
            val = _gs_val(kv_list[i + 1])
            result[str(key)] = val
        return result

    # List of alternating keys/values (sometimes Neptune returns this)
    if isinstance(item, list) and len(item) >= 2:
        result = {}
        for i in range(0, len(item) - 1, 2):
            key = _gs_val(item[i])
            val = _gs_val(item[i + 1])
            result[str(key)] = val
        return result

    # Fallback: try to use as-is if it's a dict
    if isinstance(item, dict):
        return {k: _gs_val(v) for k, v in item.items()}

    return {}

# =====================================================================
# LLM confirmation prompt
# =====================================================================

_LLM_MERGE_PROMPT = """\
You are an entity resolution expert for investigative case files.

Given two entity names from the same case, determine if they refer to the
SAME real-world entity. Consider:
- Name variations (initials, middle names, suffixes)
- Spelling differences or OCR errors
- Abbreviations and nicknames

Entity type: {entity_type}
Name A: "{name_a}"
Name B: "{name_b}"

Respond with ONLY a JSON object:
{{"same_entity": true/false, "confidence": 0.0-1.0, "reasoning": "brief explanation"}}
"""


# =====================================================================
# Main service
# =====================================================================

class EntityResolutionService:
    """Hybrid fuzzy + LLM entity resolution for Neptune knowledge graphs."""

    def __init__(
        self,
        neptune_endpoint: str,
        neptune_port: str = "8182",
        bedrock_client: Any = None,
        model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
        opensearch_endpoint: Optional[str] = None,
    ):
        self._endpoint = neptune_endpoint
        self._port = neptune_port
        self._bedrock = bedrock_client
        self._model_id = model_id
        self._os_endpoint = opensearch_endpoint

    def _gremlin(self, query: str, timeout: int = 30) -> list:
        return _gremlin_http(self._endpoint, self._port, query, timeout)

    # ------------------------------------------------------------------
    # Step 1: Fetch entities from Neptune
    # ------------------------------------------------------------------

    def fetch_entities(self, case_id: str) -> list[dict]:
        """Fetch all entity nodes from Neptune for a case."""
        label = _escape(f"Entity_{case_id}")
        q = (
            f"g.V().hasLabel('{label}')"
            f".project('name','type','occ','conf')"
            f".by('canonical_name').by('entity_type')"
            f".by('occurrence_count').by('confidence')"
        )
        raw = self._gremlin(q, timeout=120)

        # Debug: log sample of raw response to diagnose GraphSON format
        if raw:
            sample = raw[:3]
            logger.info("Raw sample (first 3): %s", json.dumps(sample, default=str)[:1000])

        entities = []
        for r in raw:
            parsed = _parse_graphson_map(r)
            if not parsed:
                continue
            entities.append({
                "name": str(parsed.get("name", "")),
                "type": str(parsed.get("type", "")),
                "occurrence_count": int(_gs_val(parsed.get("occ", 1))),
                "confidence": float(_gs_val(parsed.get("conf", 0.5))),
            })

        # Log type distribution
        from collections import Counter
        type_dist = Counter(e["type"] for e in entities)
        logger.info("Fetched %d entities for case %s, types: %s",
                     len(entities), case_id[:8], dict(type_dist.most_common(10)))
        return entities

    # ------------------------------------------------------------------
    # Step 2: Find merge candidates (fuzzy pass)
    # ------------------------------------------------------------------

    def find_candidates(
        self, entities: list[dict], max_per_type: int = 5000,
    ) -> list[MergeCandidate]:
        """Compare entities within each type, return merge candidates."""
        by_type: dict[str, list[dict]] = defaultdict(list)
        for e in entities:
            by_type[e["type"]].append(e)

        candidates: list[MergeCandidate] = []
        for etype, group in by_type.items():
            # Sort by occurrence count descending so we compare the most
            # important entities first when capping
            occ_lookup: dict[str, int] = {}
            for e in group:
                name = e["name"]
                occ_lookup[name] = max(occ_lookup.get(name, 0), e.get("occurrence_count", 1))
            names = sorted(occ_lookup.keys(), key=lambda n: occ_lookup[n], reverse=True)
            if len(names) > max_per_type:
                logger.warning("Type '%s' has %d names, capping at %d (by occurrence count)",
                               etype, len(names), max_per_type)
                names = names[:max_per_type]

            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    sim = compute_similarity(names[i], names[j], etype)
                    if sim >= LLM_REVIEW_THRESHOLD:
                        method = "auto" if sim >= AUTO_MERGE_THRESHOLD else "needs_llm"
                        candidates.append(MergeCandidate(
                            name_a=names[i], name_b=names[j],
                            entity_type=etype, similarity=sim,
                            method=method,
                        ))

        candidates.sort(key=lambda c: c.similarity, reverse=True)
        logger.info("Found %d merge candidates across %d types",
                     len(candidates), len(by_type))
        return candidates

    # ------------------------------------------------------------------
    # Step 3: LLM confirmation for ambiguous pairs
    # ------------------------------------------------------------------

    def confirm_with_llm(self, candidates: list[MergeCandidate]) -> list[MergeCandidate]:
        """Send ambiguous candidates to Bedrock for confirmation."""
        if not self._bedrock:
            logger.warning("No Bedrock client — skipping LLM confirmation")
            # Treat needs_llm as rejected without LLM
            for c in candidates:
                if c.method == "needs_llm":
                    c.method = "skipped_no_llm"
            return candidates

        for c in candidates:
            if c.method != "needs_llm":
                continue
            try:
                prompt = _LLM_MERGE_PROMPT.format(
                    entity_type=c.entity_type,
                    name_a=c.name_a, name_b=c.name_b,
                )
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 256,
                    "messages": [{"role": "user", "content": prompt}],
                })
                resp = self._bedrock.invoke_model(
                    modelId=self._model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=body,
                )
                text = json.loads(resp["body"].read())["content"][0]["text"]
                # Parse JSON from response
                obj_start = text.find("{")
                obj_end = text.rfind("}") + 1
                if obj_start >= 0 and obj_end > obj_start:
                    result = json.loads(text[obj_start:obj_end])
                    if result.get("same_entity"):
                        c.method = "llm_confirmed"
                    else:
                        c.method = "llm_rejected"
                    c.llm_reasoning = result.get("reasoning", "")
                else:
                    c.method = "llm_rejected"
            except Exception as exc:
                logger.warning("LLM confirm failed for %s / %s: %s",
                               c.name_a, c.name_b, str(exc)[:200])
                c.method = "llm_error"

        return candidates


    # ------------------------------------------------------------------
    # Step 4: Build merge clusters (transitive closure)
    # ------------------------------------------------------------------

    def build_clusters(
        self, candidates: list[MergeCandidate], entities: list[dict],
    ) -> list[MergeCluster]:
        """Group confirmed candidates into merge clusters via union-find."""
        # Only use confirmed merges
        confirmed = [
            c for c in candidates
            if c.method in ("auto", "llm_confirmed", "rule")
        ]
        if not confirmed:
            return []

        # Union-Find
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent[x], parent[x])
                x = parent[x]
            return x

        def union(a: str, b: str):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for c in confirmed:
            union(c.name_a, c.name_b)

        # Group by root
        groups: dict[str, list[str]] = defaultdict(list)
        all_names = set()
        for c in confirmed:
            all_names.add(c.name_a)
            all_names.add(c.name_b)
        for name in all_names:
            groups[find(name)].append(name)

        # Build occurrence lookup
        occ_lookup: dict[str, int] = {}
        type_lookup: dict[str, str] = {}
        for e in entities:
            occ_lookup[e["name"]] = e.get("occurrence_count", 1)
            type_lookup[e["name"]] = e.get("type", "")

        # Pick canonical name = highest occurrence count in each cluster
        clusters: list[MergeCluster] = []
        for members in groups.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda n: occ_lookup.get(n, 0), reverse=True)
            canonical = members[0]
            aliases = members[1:]
            total_occ = sum(occ_lookup.get(n, 0) for n in members)
            clusters.append(MergeCluster(
                canonical_name=canonical,
                aliases=aliases,
                entity_type=type_lookup.get(canonical, ""),
                total_occurrences=total_occ,
            ))

        logger.info("Built %d merge clusters from %d confirmed pairs",
                     len(clusters), len(confirmed))
        return clusters

    # ------------------------------------------------------------------
    # Step 5: Execute merges in Neptune
    # ------------------------------------------------------------------

    def execute_merges(self, case_id: str, clusters: list[MergeCluster],
                       dry_run: bool = False, max_degree: int = 500) -> dict:
        """Merge duplicate nodes in Neptune. Re-link edges, drop aliases.

        Skips alias nodes with degree > max_degree to avoid Gremlin timeouts
        on high-connectivity nodes.

        Returns summary: {merged, edges_relinked, nodes_dropped, skipped_high_degree, errors}
        """
        label = _escape(f"Entity_{case_id}")
        stats = {"merged": 0, "edges_relinked": 0, "nodes_dropped": 0,
                 "skipped_high_degree": 0, "errors": []}

        for cluster in clusters:
            canonical = _escape(cluster.canonical_name)
            etype = _escape(cluster.entity_type)

            if dry_run:
                stats["merged"] += 1
                stats["nodes_dropped"] += len(cluster.aliases)
                continue

            for alias in cluster.aliases:
                alias_esc = _escape(alias)
                try:
                    # Check degree of alias node — skip if too high
                    q_degree = (
                        f"g.V().hasLabel('{label}')"
                        f".has('canonical_name','{alias_esc}')"
                        f".bothE().count()"
                    )
                    degree_result = self._gremlin(q_degree)
                    degree = degree_result[0] if degree_result else 0
                    if isinstance(degree, dict):
                        degree = degree.get("@value", 0)
                    if int(degree) > max_degree:
                        logger.info("Skipping alias '%s' (degree %d > %d)",
                                    alias[:50], degree, max_degree)
                        stats["skipped_high_degree"] += 1
                        continue

                    # Re-link outgoing edges from alias → canonical
                    q_out = (
                        f"g.V().hasLabel('{label}')"
                        f".has('canonical_name','{alias_esc}')"
                        f".outE('RELATED_TO').as('e')"
                        f".inV().as('target')"
                        f".select('e').properties().as('props')"
                        f".select('e','target')"
                    )
                    # Simpler approach: get edge count, then re-create
                    q_count_out = (
                        f"g.V().hasLabel('{label}')"
                        f".has('canonical_name','{alias_esc}')"
                        f".outE('RELATED_TO').count()"
                    )
                    out_count = self._gremlin(q_count_out)
                    out_n = out_count[0] if out_count else 0
                    if isinstance(out_n, dict):
                        out_n = out_n.get("@value", 0)

                    # Re-link incoming edges
                    q_count_in = (
                        f"g.V().hasLabel('{label}')"
                        f".has('canonical_name','{alias_esc}')"
                        f".inE('RELATED_TO').count()"
                    )
                    in_count = self._gremlin(q_count_in)
                    in_n = in_count[0] if in_count else 0
                    if isinstance(in_n, dict):
                        in_n = in_n.get("@value", 0)

                    # Use Gremlin to move outgoing edges
                    if out_n > 0:
                        q_move_out = (
                            f"g.V().hasLabel('{label}')"
                            f".has('canonical_name','{alias_esc}')"
                            f".outE('RELATED_TO').as('e')"
                            f".inV().as('t')"
                            f".V().hasLabel('{label}')"
                            f".has('canonical_name','{canonical}')"
                            f".addE('RELATED_TO').to(select('t'))"
                            f".property('relationship_type',"
                            f"select('e').values('relationship_type'))"
                            f".property('confidence',"
                            f"select('e').values('confidence'))"
                        )
                        try:
                            self._gremlin(q_move_out, timeout=60)
                        except Exception:
                            # Fallback: just drop alias edges (data loss but safe)
                            logger.warning("Edge move failed for alias '%s', will drop", alias)

                    # Move incoming edges
                    if in_n > 0:
                        q_move_in = (
                            f"g.V().hasLabel('{label}')"
                            f".has('canonical_name','{alias_esc}')"
                            f".inE('RELATED_TO').as('e')"
                            f".outV().as('s')"
                            f".select('s')"
                            f".addE('RELATED_TO')"
                            f".to(V().hasLabel('{label}')"
                            f".has('canonical_name','{canonical}'))"
                            f".property('relationship_type',"
                            f"select('e').values('relationship_type'))"
                            f".property('confidence',"
                            f"select('e').values('confidence'))"
                        )
                        try:
                            self._gremlin(q_move_in, timeout=60)
                        except Exception:
                            logger.warning("Incoming edge move failed for alias '%s'", alias)

                    stats["edges_relinked"] += int(out_n) + int(in_n)

                    # Update canonical node occurrence count
                    q_update = (
                        f"g.V().hasLabel('{label}')"
                        f".has('canonical_name','{canonical}')"
                        f".property('occurrence_count',{cluster.total_occurrences})"
                    )
                    self._gremlin(q_update)

                    # Drop alias node and its old edges
                    q_drop = (
                        f"g.V().hasLabel('{label}')"
                        f".has('canonical_name','{alias_esc}')"
                        f".drop()"
                    )
                    self._gremlin(q_drop)
                    stats["nodes_dropped"] += 1

                except Exception as exc:
                    err_msg = f"Merge failed for '{alias}' → '{cluster.canonical_name}': {str(exc)[:200]}"
                    logger.error(err_msg)
                    stats["errors"].append(err_msg)

            stats["merged"] += 1

        logger.info("Merge complete: %d clusters, %d nodes dropped, %d edges relinked, %d errors",
                     stats["merged"], stats["nodes_dropped"],
                     stats["edges_relinked"], len(stats["errors"]))
        return stats

    # ------------------------------------------------------------------
    # Step 6: Update OpenSearch persons metadata
    # ------------------------------------------------------------------

    def update_opensearch(self, case_id: str, clusters: list[MergeCluster]) -> int:
        """Update OpenSearch documents to reflect merged entity names.

        For each cluster, find docs referencing alias names in the 'persons'
        field and replace with the canonical name.
        """
        if not self._os_endpoint:
            logger.info("No OpenSearch endpoint — skipping metadata update")
            return 0

        updated = 0
        index_name = f"case_{case_id.replace('-', '_')}"

        for cluster in clusters:
            for alias in cluster.aliases:
                # Search for docs with this alias in persons field
                search_body = json.dumps({
                    "size": 1000,
                    "query": {"term": {"persons": alias}},
                    "_source": ["document_id", "persons"],
                })
                try:
                    resp = self._os_request("POST", f"/{index_name}/_search", search_body)
                    hits = resp.get("hits", {}).get("hits", [])
                    if not hits:
                        continue

                    # Bulk update: replace alias with canonical in persons array
                    bulk_lines = []
                    for hit in hits:
                        doc_id = hit["_id"]
                        persons = hit["_source"].get("persons", [])
                        new_persons = [
                            cluster.canonical_name if p == alias else p
                            for p in persons
                        ]
                        # Deduplicate
                        new_persons = list(dict.fromkeys(new_persons))
                        bulk_lines.append(json.dumps(
                            {"update": {"_index": index_name, "_id": doc_id}}
                        ))
                        bulk_lines.append(json.dumps(
                            {"doc": {"persons": new_persons}}
                        ))

                    if bulk_lines:
                        bulk_payload = "\n".join(bulk_lines) + "\n"
                        self._os_request("POST", "/_bulk", bulk_payload,
                                         content_type="application/x-ndjson")
                        updated += len(hits)

                except Exception as exc:
                    logger.warning("OpenSearch update failed for alias '%s': %s",
                                   alias, str(exc)[:200])

        logger.info("Updated %d OpenSearch documents with merged entity names", updated)
        return updated

    def _os_request(self, method: str, path: str, body: str = "",
                    content_type: str = "application/json") -> dict:
        """Make a SigV4-signed request to OpenSearch Serverless."""
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest
        import botocore.session

        url = f"https://{self._os_endpoint}{path}"
        session = botocore.session.get_session()
        credentials = session.get_credentials().get_frozen_credentials()

        aws_request = AWSRequest(
            method=method, url=url,
            data=body.encode("utf-8") if body else b"",
            headers={"Content-Type": content_type, "Host": self._os_endpoint},
        )
        SigV4Auth(credentials, "aoss", "us-east-1").add_auth(aws_request)

        req = urllib.request.Request(
            url, data=body.encode("utf-8") if body else None,
            headers=dict(aws_request.headers), method=method,
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def resolve(self, case_id: str, dry_run: bool = False,
                use_llm: bool = True, max_degree: int = 500) -> dict:
        """Run the full entity resolution pipeline for a case.

        Returns:
            {
                "case_id": str,
                "entities_fetched": int,
                "candidates_found": int,
                "clusters": int,
                "merge_stats": {...},
                "opensearch_updated": int,
                "dry_run": bool,
                "cluster_details": [...]
            }
        """
        # 1. Fetch
        entities = self.fetch_entities(case_id)

        # 2. Find candidates
        candidates = self.find_candidates(entities)

        # 3. LLM confirmation (optional)
        if use_llm:
            candidates = self.confirm_with_llm(candidates)

        # 4. Build clusters
        clusters = self.build_clusters(candidates, entities)

        # 5. Execute merges in Neptune
        merge_stats = self.execute_merges(case_id, clusters, dry_run=dry_run,
                                          max_degree=max_degree)

        # 6. Update OpenSearch
        os_updated = 0
        if not dry_run and clusters:
            os_updated = self.update_opensearch(case_id, clusters)

        cluster_details = [
            {
                "canonical": c.canonical_name,
                "aliases": c.aliases,
                "type": c.entity_type,
                "total_occurrences": c.total_occurrences,
            }
            for c in clusters
        ]

        return {
            "case_id": case_id,
            "entities_fetched": len(entities),
            "candidates_found": len(candidates),
            "clusters": len(clusters),
            "merge_stats": merge_stats,
            "opensearch_updated": os_updated,
            "dry_run": dry_run,
            "cluster_details": cluster_details,
        }
