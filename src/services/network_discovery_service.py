"""Network Discovery Service — AI-powered conspiracy network analysis.

Orchestrates graph algorithm execution on Neptune subgraphs, computes
involvement scores, generates co-conspirator profiles with AI legal
reasoning via Bedrock, creates AI_Proposed decisions, and manages
sub-case spawning.

Dependencies are injected via the constructor for testability:
    - neptune_endpoint / neptune_port for Gremlin HTTP queries
    - ConnectionManager for Aurora metadata/caching
    - Bedrock client for AI reasoning
    - OpenSearch endpoint for document co-occurrence
    - DecisionWorkflowService for human-in-the-loop decisions
    - CrossCaseService for sub-case graph creation
    - PatternDiscoveryService for pattern detection
"""

import json
import logging
import math
import os
import ssl
import statistics
import urllib.request
import urllib.error
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

# Feature flag: when "false", Neptune-dependent operations return empty results
_NEPTUNE_ENABLED = os.environ.get("NEPTUNE_ENABLED", "true") == "true"

from models.network import (
    AnalysisStatus,
    CaseInitiationBrief,
    CentralityScores,
    CoConspiratorProfile,
    CommunityCluster,
    EvidenceReference,
    InvolvementScore,
    NetworkAnalysisResult,
    NetworkPattern,
    RelationshipEntry,
    RiskLevel,
    SubCaseProposal,
)

logger = logging.getLogger(__name__)

BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
BATCH_SIZE = 10_000
LARGE_SUBGRAPH_THRESHOLD = 50_000


class NetworkDiscoveryService:
    """Orchestrates conspiracy network analysis on case subgraphs."""

    SENIOR_LEGAL_ANALYST_PERSONA = (
        "You are a senior federal prosecutor (AUSA) with 20+ years of experience. "
        "Reason using proper legal terminology. Cite case law patterns and reference "
        "federal sentencing guidelines (USSG) where applicable. Provide thorough legal "
        "justifications for every recommendation."
    )

    INVOLVEMENT_WEIGHTS = {
        "connections": 0.25,
        "co_occurrence": 0.25,
        "financial": 0.20,
        "communication": 0.15,
        "geographic": 0.15,
    }

    def __init__(
        self,
        neptune_endpoint: str,
        neptune_port: str,
        aurora_cm: Any,
        bedrock_client: Any,
        opensearch_endpoint: str,
        decision_workflow_svc: Any,
        cross_case_svc: Any,
        pattern_discovery_svc: Any,
    ) -> None:
        self._neptune_endpoint = neptune_endpoint
        self._neptune_port = neptune_port
        self._aurora = aurora_cm
        self._bedrock = bedrock_client
        self._opensearch_endpoint = opensearch_endpoint
        self._decision_workflow_svc = decision_workflow_svc
        self._cross_case_svc = cross_case_svc
        self._pattern_discovery_svc = pattern_discovery_svc

    # ------------------------------------------------------------------
    # Internal: Gremlin HTTP helper
    # ------------------------------------------------------------------

    def _gremlin_query(self, query: str) -> list:
        """Execute a Gremlin query via Neptune HTTP API."""
        if not self._neptune_endpoint:
            return []
        url = f"https://{self._neptune_endpoint}:{self._neptune_port}/gremlin"
        data = json.dumps({"gremlin": query}).encode("utf-8")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                result = body.get("result", {}).get("data", {})
                if isinstance(result, dict) and "@value" in result:
                    return result["@value"]
                if isinstance(result, list):
                    return result
                return [result] if result else []
        except Exception as e:
            logger.error("Neptune query error: %s", str(e)[:200])
            return []

    @staticmethod
    def _entity_label(case_id: str) -> str:
        return f"Entity_{case_id}"

    @staticmethod
    def _escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')

    # ------------------------------------------------------------------
    # Internal: Community Detection (Task 3.2)
    # ------------------------------------------------------------------

    def _run_community_detection(self, case_id: str) -> list[CommunityCluster]:
        """Batched BFS community detection on Neptune subgraph.

        Pages through entities in batches of 10K nodes.
        Uses approximate algorithms when subgraph > 50K nodes.
        """
        label = self._entity_label(case_id)

        # Fetch all nodes in batches of BATCH_SIZE
        all_nodes: list[dict] = []
        offset = 0
        while True:
            query = (
                f"g.V().hasLabel('{self._escape(label)}')"
                f".range({offset},{offset + BATCH_SIZE})"
                f".project('name','type')"
                f".by('canonical_name').by('entity_type')"
            )
            batch = self._gremlin_query(query)
            if not batch:
                break
            for item in batch:
                if isinstance(item, dict):
                    all_nodes.append(item)
            if len(batch) < BATCH_SIZE:
                break
            offset += BATCH_SIZE

        if not all_nodes:
            return []

        # Fetch edges to build adjacency
        edges: list[dict] = []
        offset = 0
        while True:
            eq = (
                f"g.V().hasLabel('{self._escape(label)}')"
                f".outE('RELATED_TO').range({offset},{offset + BATCH_SIZE})"
                f".project('src','tgt')"
                f".by(outV().values('canonical_name'))"
                f".by(inV().values('canonical_name'))"
            )
            batch = self._gremlin_query(eq)
            if not batch:
                break
            for item in batch:
                if isinstance(item, dict):
                    edges.append(item)
            if len(batch) < BATCH_SIZE:
                break
            offset += BATCH_SIZE

        # Build adjacency list
        adj: dict[str, set[str]] = defaultdict(set)
        for e in edges:
            src = e.get("src", "")
            tgt = e.get("tgt", "")
            if src and tgt:
                adj[src].add(tgt)
                adj[tgt].add(src)

        # BFS connected components
        node_names = {n.get("name", "") for n in all_nodes if n.get("name")}
        visited: set[str] = set()
        clusters: list[CommunityCluster] = []

        for name in node_names:
            if name in visited:
                continue
            component: list[str] = []
            queue = [name]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)
                for neighbor in adj.get(current, set()):
                    if neighbor not in visited and neighbor in node_names:
                        queue.append(neighbor)

            if len(component) >= 2:
                # Compute average internal degree
                total_degree = sum(
                    len(adj.get(n, set()) & set(component)) for n in component
                )
                avg_degree = total_degree / len(component) if component else 0.0

                clusters.append(CommunityCluster(
                    cluster_id=str(uuid.uuid4()),
                    entity_names=component,
                    entity_count=len(component),
                    avg_internal_degree=round(avg_degree, 2),
                ))

        return clusters

    # ------------------------------------------------------------------
    # Internal: Centrality Scoring (Task 3.2)
    # ------------------------------------------------------------------

    def _run_centrality_scoring(self, case_id: str) -> dict[str, CentralityScores]:
        """Compute betweenness, degree, and PageRank centrality.

        Uses approximate betweenness (sampling) for subgraphs > 50K nodes.
        Returns {entity_name: CentralityScores}.
        """
        label = self._entity_label(case_id)

        # Fetch nodes with degree counts
        all_nodes: list[dict] = []
        offset = 0
        while True:
            query = (
                f"g.V().hasLabel('{self._escape(label)}')"
                f".range({offset},{offset + BATCH_SIZE})"
                f".project('name','degree')"
                f".by('canonical_name').by(bothE().count())"
            )
            batch = self._gremlin_query(query)
            if not batch:
                break
            for item in batch:
                if isinstance(item, dict):
                    all_nodes.append(item)
            if len(batch) < BATCH_SIZE:
                break
            offset += BATCH_SIZE

        if not all_nodes:
            return {}

        # Build adjacency for betweenness/pagerank
        adj: dict[str, set[str]] = defaultdict(set)
        offset = 0
        while True:
            eq = (
                f"g.V().hasLabel('{self._escape(label)}')"
                f".outE('RELATED_TO').range({offset},{offset + BATCH_SIZE})"
                f".project('src','tgt')"
                f".by(outV().values('canonical_name'))"
                f".by(inV().values('canonical_name'))"
            )
            batch = self._gremlin_query(eq)
            if not batch:
                break
            for item in batch:
                if isinstance(item, dict):
                    src = item.get("src", "")
                    tgt = item.get("tgt", "")
                    if src and tgt:
                        adj[src].add(tgt)
                        adj[tgt].add(src)
            if len(batch) < BATCH_SIZE:
                break
            offset += BATCH_SIZE

        node_names = [n.get("name", "") for n in all_nodes if n.get("name")]
        is_large = len(node_names) > LARGE_SUBGRAPH_THRESHOLD

        # Degree centrality from Neptune results
        degree_map: dict[str, int] = {}
        for n in all_nodes:
            name = n.get("name", "")
            deg = n.get("degree", 0)
            if isinstance(deg, dict):
                deg = deg.get("@value", 0)
            degree_map[name] = int(deg)

        # Approximate betweenness centrality
        betweenness = self._approximate_betweenness(
            node_names, adj, sample_size=min(50, len(node_names)) if is_large else len(node_names),
        )

        # Approximate PageRank
        pagerank = self._compute_pagerank(node_names, adj, iterations=10 if is_large else 20)

        result: dict[str, CentralityScores] = {}
        for name in node_names:
            result[name] = CentralityScores(
                betweenness=round(betweenness.get(name, 0.0), 6),
                degree=degree_map.get(name, 0),
                pagerank=round(pagerank.get(name, 0.0), 6),
            )

        return result

    @staticmethod
    def _approximate_betweenness(
        nodes: list[str], adj: dict[str, set[str]], sample_size: int,
    ) -> dict[str, float]:
        """Approximate betweenness centrality via BFS from sampled sources."""
        import random

        betweenness: dict[str, float] = {n: 0.0 for n in nodes}
        sources = random.sample(nodes, min(sample_size, len(nodes)))

        for s in sources:
            # BFS from s
            dist: dict[str, int] = {s: 0}
            pred: dict[str, list[str]] = defaultdict(list)
            sigma: dict[str, int] = defaultdict(int)
            sigma[s] = 1
            queue = [s]
            order: list[str] = []

            while queue:
                v = queue.pop(0)
                order.append(v)
                for w in adj.get(v, set()):
                    if w not in dist:
                        dist[w] = dist[v] + 1
                        queue.append(w)
                    if dist.get(w, -1) == dist[v] + 1:
                        sigma[w] += sigma[v]
                        pred[w].append(v)

            delta: dict[str, float] = defaultdict(float)
            for w in reversed(order):
                for v in pred[w]:
                    if sigma[w] > 0:
                        delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
                if w != s:
                    betweenness[w] += delta[w]

        # Normalize
        n = len(nodes)
        scale = len(sources) / max(n, 1)
        if n > 2:
            norm = 1.0 / ((n - 1) * (n - 2))
            for k in betweenness:
                betweenness[k] *= norm / max(scale, 0.001)

        return betweenness

    @staticmethod
    def _compute_pagerank(
        nodes: list[str], adj: dict[str, set[str]],
        damping: float = 0.85, iterations: int = 20,
    ) -> dict[str, float]:
        """Simple PageRank computation."""
        n = len(nodes)
        if n == 0:
            return {}

        pr: dict[str, float] = {node: 1.0 / n for node in nodes}

        for _ in range(iterations):
            new_pr: dict[str, float] = {}
            for node in nodes:
                rank_sum = 0.0
                for other in nodes:
                    if node in adj.get(other, set()):
                        out_degree = len(adj.get(other, set()))
                        if out_degree > 0:
                            rank_sum += pr[other] / out_degree
                new_pr[node] = (1 - damping) / n + damping * rank_sum
            pr = new_pr

        return pr

    # ------------------------------------------------------------------
    # Internal: Anomaly Detection (Task 3.2)
    # ------------------------------------------------------------------

    def _run_anomaly_detection(
        self, case_id: str, centrality: dict[str, CentralityScores],
    ) -> list[str]:
        """Flag entities with degree > mean + 2 * std_dev."""
        if not centrality:
            return []

        degrees = [c.degree for c in centrality.values()]
        if len(degrees) < 2:
            return []

        mean_deg = statistics.mean(degrees)
        std_deg = statistics.stdev(degrees)

        threshold = mean_deg + 2 * std_deg
        anomalies = [
            name for name, scores in centrality.items()
            if scores.degree > threshold
        ]
        return anomalies

    # ------------------------------------------------------------------
    # Internal: Involvement Scoring (Task 3.4)
    # ------------------------------------------------------------------

    def _compute_involvement_score(
        self, case_id: str, entity_name: str, primary_subject: str,
    ) -> InvolvementScore:
        """Compute weighted composite involvement score.

        connections (0.25) + co_occurrence (0.25) + financial (0.20)
        + communication (0.15) + geographic (0.15).
        Each factor normalized to 0-100.
        """
        connections = self._score_connections(case_id, entity_name, primary_subject)
        co_occurrence = self._score_co_occurrence(case_id, entity_name, primary_subject)
        financial = self._score_financial(case_id, entity_name, primary_subject)
        communication = self._score_communication(case_id, entity_name, primary_subject)
        geographic = self._score_geographic(case_id, entity_name, primary_subject)

        total = round(
            connections * self.INVOLVEMENT_WEIGHTS["connections"]
            + co_occurrence * self.INVOLVEMENT_WEIGHTS["co_occurrence"]
            + financial * self.INVOLVEMENT_WEIGHTS["financial"]
            + communication * self.INVOLVEMENT_WEIGHTS["communication"]
            + geographic * self.INVOLVEMENT_WEIGHTS["geographic"]
        )
        total = max(0, min(100, total))

        return InvolvementScore(
            total=total,
            connections=connections,
            co_occurrence=co_occurrence,
            financial=financial,
            communication=communication,
            geographic=geographic,
        )

    def _score_connections(self, case_id: str, entity: str, subject: str) -> int:
        """Score based on number of graph connections to primary subject."""
        label = self._entity_label(case_id)
        query = (
            f"g.V().hasLabel('{self._escape(label)}')"
            f".has('canonical_name','{self._escape(entity)}')"
            f".bothE().count()"
        )
        result = self._gremlin_query(query)
        count = result[0] if result else 0
        if isinstance(count, dict):
            count = count.get("@value", 0)
        return max(0, min(100, int(count) * 10))

    def _score_co_occurrence(self, case_id: str, entity: str, subject: str) -> int:
        """Score based on document co-occurrence frequency via OpenSearch."""
        try:
            # Query OpenSearch for co-occurrence
            url = f"https://{self._opensearch_endpoint}/{case_id}/_search"
            body = json.dumps({
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"content": entity}},
                            {"match": {"content": subject}},
                        ]
                    }
                },
                "size": 0,
            })
            ctx = ssl.create_default_context()
            req = urllib.request.Request(
                url, data=body.encode(), headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                hits = data.get("hits", {}).get("total", {})
                count = hits.get("value", 0) if isinstance(hits, dict) else int(hits)
                return max(0, min(100, count * 5))
        except Exception:
            return 0

    def _score_financial(self, case_id: str, entity: str, subject: str) -> int:
        """Score based on financial relationship patterns."""
        label = self._entity_label(case_id)
        query = (
            f"g.V().hasLabel('{self._escape(label)}')"
            f".has('canonical_name','{self._escape(entity)}')"
            f".bothE().has('relationship_type','financial').count()"
        )
        result = self._gremlin_query(query)
        count = result[0] if result else 0
        if isinstance(count, dict):
            count = count.get("@value", 0)
        return max(0, min(100, int(count) * 15))

    def _score_communication(self, case_id: str, entity: str, subject: str) -> int:
        """Score based on communication relationship patterns."""
        label = self._entity_label(case_id)
        query = (
            f"g.V().hasLabel('{self._escape(label)}')"
            f".has('canonical_name','{self._escape(entity)}')"
            f".bothE().has('relationship_type','communication').count()"
        )
        result = self._gremlin_query(query)
        count = result[0] if result else 0
        if isinstance(count, dict):
            count = count.get("@value", 0)
        return max(0, min(100, int(count) * 15))

    def _score_geographic(self, case_id: str, entity: str, subject: str) -> int:
        """Score based on geographic co-location patterns."""
        label = self._entity_label(case_id)
        query = (
            f"g.V().hasLabel('{self._escape(label)}')"
            f".has('canonical_name','{self._escape(entity)}')"
            f".bothE().has('relationship_type','geographic').count()"
        )
        result = self._gremlin_query(query)
        count = result[0] if result else 0
        if isinstance(count, dict):
            count = count.get("@value", 0)
        return max(0, min(100, int(count) * 15))

    # ------------------------------------------------------------------
    # Internal: Risk Classification (Task 3.4)
    # ------------------------------------------------------------------

    def _classify_risk_level(self, profile: CoConspiratorProfile) -> str:
        """Assign High/Medium/Low risk level.

        High: doc_type_count >= 3 AND connection_strength > 70
        Medium: doc_type_count == 2 OR 40 <= connection_strength <= 70
        Low: doc_type_count <= 1 AND connection_strength < 40
        """
        dtc = profile.document_type_count
        cs = profile.connection_strength

        if dtc >= 3 and cs > 70:
            return RiskLevel.HIGH
        if dtc == 2 or 40 <= cs <= 70:
            return RiskLevel.MEDIUM
        if dtc <= 1 and cs < 40:
            return RiskLevel.LOW
        # Fallback: medium for ambiguous cases
        return RiskLevel.MEDIUM

    # ------------------------------------------------------------------
    # Internal: AI Reasoning (Task 3.6)
    # ------------------------------------------------------------------

    def _generate_legal_reasoning(self, profile: CoConspiratorProfile) -> str:
        """Invoke Bedrock with Senior_Legal_Analyst_Persona for legal reasoning."""
        prompt = (
            f"Analyze the following person of interest and provide a legal reasoning "
            f"summary explaining why they warrant investigation.\n\n"
            f"Person: {profile.entity_name}\n"
            f"Entity Type: {profile.entity_type}\n"
            f"Connection Strength: {profile.connection_strength}\n"
            f"Document Types: {profile.document_type_count}\n"
            f"Risk Level: {profile.risk_level}\n"
            f"Evidence Count: {len(profile.evidence_summary)}\n"
            f"Relationships: {len(profile.relationship_map)}\n\n"
            f"Provide a structured legal justification paragraph."
        )

        try:
            response = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "system": self.SENIOR_LEGAL_ANALYST_PERSONA,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            body = json.loads(response["body"].read())
            return body.get("content", [{}])[0].get("text", "")
        except Exception as e:
            logger.error("Bedrock legal reasoning failed: %s", str(e)[:200])
            return (
                f"AI analysis unavailable. Manual review recommended for "
                f"{profile.entity_name} based on {len(profile.evidence_summary)} "
                f"document references and {len(profile.relationship_map)} graph connections."
            )

    def _generate_case_initiation_brief(
        self, case_id: str, profile: CoConspiratorProfile,
    ) -> CaseInitiationBrief:
        """Invoke Bedrock to generate a Case Initiation Brief for sub-case."""
        prompt = (
            f"Generate a Case Initiation Brief for a proposed sub-case investigation.\n\n"
            f"Subject: {profile.entity_name}\n"
            f"Parent Case: {case_id}\n"
            f"Risk Level: {profile.risk_level}\n"
            f"Connection Strength: {profile.connection_strength}\n"
            f"Involvement Score: {profile.involvement_score.total}\n"
            f"Evidence Documents: {len(profile.evidence_summary)}\n"
            f"Known Relationships: {len(profile.relationship_map)}\n\n"
            f"Provide:\n"
            f"1. Proposed charges with statute citations\n"
            f"2. Key evidence summary\n"
            f"3. Recommended investigative steps\n"
        )

        try:
            response = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "system": self.SENIOR_LEGAL_ANALYST_PERSONA,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            body = json.loads(response["body"].read())
            brief_text = body.get("content", [{}])[0].get("text", "")
        except Exception as e:
            logger.error("Bedrock brief generation failed: %s", str(e)[:200])
            brief_text = (
                f"Case Initiation Brief for {profile.entity_name}: "
                f"Manual review recommended."
            )

        return CaseInitiationBrief(
            proposed_charges=[{
                "statute_citation": "To be determined",
                "charge_description": f"Investigation of {profile.entity_name}",
            }],
            evidence_summary=(
                f"{profile.entity_name} appears in {len(profile.evidence_summary)} "
                f"documents with {len(profile.relationship_map)} known relationships."
            ),
            investigative_steps=[
                {"step_number": 1, "description": "Review all linked documents", "priority": "high"},
                {"step_number": 2, "description": "Interview witnesses", "priority": "high"},
                {"step_number": 3, "description": "Analyze financial records", "priority": "medium"},
            ],
            full_brief=brief_text,
        )

    # ------------------------------------------------------------------
    # Public: Main Analysis Orchestration (Task 3.7)
    # ------------------------------------------------------------------

    def analyze_network(self, case_id: str) -> NetworkAnalysisResult:
        """Full network analysis pipeline.

        1. Count subgraph nodes; if >50K, return processing status
        2. Run community detection (batched, 10K pages)
        3. Run centrality scoring (betweenness, degree, PageRank)
        4. Run anomaly detection
        5. Query OpenSearch for document co-occurrence
        6. Compute Involvement Scores
        7. Generate co-conspirator profiles
        8. Invoke Bedrock for legal reasoning per person
        9. Create AI_Proposed decisions for each person of interest
        10. Cache results in Aurora
        """
        if not _NEPTUNE_ENABLED:
            return NetworkAnalysisResult(
                analysis_id=str(uuid.uuid4()),
                case_id=case_id,
                analysis_status=AnalysisStatus.COMPLETED,
                primary_subject="",
                total_entities_analyzed=0,
                persons_of_interest=[],
                communities=[],
                created_at=datetime.now(timezone.utc).isoformat(),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        analysis_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Check for duplicate analysis (return existing if completed within last hour)
        existing = self.get_analysis(case_id)
        if existing and existing.analysis_status in (AnalysisStatus.PROCESSING, AnalysisStatus.COMPLETED):
            if existing.created_at:
                try:
                    from datetime import timedelta
                    created = datetime.fromisoformat(str(existing.created_at).replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) - created < timedelta(hours=1):
                        return existing
                except (ValueError, TypeError):
                    pass

        # Step 1: Count subgraph nodes
        label = self._entity_label(case_id)
        count_result = self._gremlin_query(
            f"g.V().hasLabel('{self._escape(label)}').count()"
        )
        node_count = 0
        neptune_available = True
        if count_result:
            nc = count_result[0]
            if isinstance(nc, dict):
                nc = nc.get("@value", 0)
            node_count = int(nc)
        else:
            # Neptune may be unavailable — try partial analysis from Aurora/OpenSearch
            neptune_available = False
            logger.warning("Neptune unavailable for case %s, returning partial analysis", case_id)

        # If >50K nodes, return processing status for async execution
        if node_count > LARGE_SUBGRAPH_THRESHOLD:
            result = NetworkAnalysisResult(
                analysis_id=analysis_id,
                case_id=case_id,
                analysis_status=AnalysisStatus.PROCESSING,
                total_entities_analyzed=node_count,
                created_at=now,
            )
            self._cache_analysis(result)
            return result

        # If Neptune is unavailable, return partial result
        if not neptune_available:
            result = NetworkAnalysisResult(
                analysis_id=analysis_id,
                case_id=case_id,
                analysis_status=AnalysisStatus.PARTIAL,
                total_entities_analyzed=0,
                created_at=now,
            )
            self._cache_analysis(result)
            return result

        # Identify primary subject (highest degree entity)
        primary_subject = self._identify_primary_subject(case_id)

        # Step 2: Community detection
        communities = self._run_community_detection(case_id)

        # Step 3: Centrality scoring
        centrality = self._run_centrality_scoring(case_id)

        # Step 4: Anomaly detection
        anomalies = self._run_anomaly_detection(case_id, centrality)

        # Steps 5-8: Build profiles for high-centrality entities
        persons_of_interest: list[CoConspiratorProfile] = []
        candidate_names = self._select_candidates(centrality, anomalies, communities)

        for entity_name in candidate_names:
            # Step 6: Compute involvement score
            score = self._compute_involvement_score(case_id, entity_name, primary_subject)

            # Build evidence summary
            evidence = self._get_evidence_for_entity(case_id, entity_name)

            # Build relationship map
            relationships = self._get_relationships(case_id, entity_name)

            # Count document types
            doc_types = len({e.document_name.split(".")[-1] for e in evidence if e.document_name})

            # Connection strength from centrality
            cs_data = centrality.get(entity_name)
            conn_strength = min(100, cs_data.degree * 10) if cs_data else 0

            profile = CoConspiratorProfile(
                profile_id=str(uuid.uuid4()),
                case_id=case_id,
                entity_name=entity_name,
                entity_type="PERSON",
                involvement_score=score,
                connection_strength=conn_strength,
                risk_level=RiskLevel.LOW,  # placeholder, classified below
                evidence_summary=evidence,
                relationship_map=relationships,
                document_type_count=doc_types,
            )

            # Step: Classify risk level
            profile.risk_level = self._classify_risk_level(profile)

            # Step 8: Generate legal reasoning
            reasoning = self._generate_legal_reasoning(profile)
            profile.ai_legal_reasoning = reasoning

            # Step 9: Create AI_Proposed decision
            decision = self._decision_workflow_svc.create_decision(
                case_id=case_id,
                decision_type="person_of_interest",
                recommendation_text=(
                    f"{entity_name}: Involvement Score {score.total}, "
                    f"Risk Level {profile.risk_level}"
                ),
                legal_reasoning=reasoning,
                confidence="high" if profile.risk_level == RiskLevel.HIGH else "medium",
                source_service="network_discovery",
            )
            profile.decision_id = decision.decision_id
            profile.decision_state = decision.state.value

            persons_of_interest.append(profile)

        # Sort by involvement score descending
        persons_of_interest.sort(
            key=lambda p: p.involvement_score.total, reverse=True,
        )

        # Detect hidden patterns via PatternDiscoveryService extensions
        detected_patterns: list[NetworkPattern] = []
        try:
            for method_name, ptype in [
                ("discover_financial_patterns", "financial"),
                ("discover_communication_patterns", "communication"),
                ("discover_geographic_patterns", "geographic"),
                ("discover_temporal_patterns", "temporal"),
            ]:
                method = getattr(self._pattern_discovery_svc, method_name, None)
                if method:
                    raw_patterns = method(case_id)
                    for rp in raw_patterns:
                        np = NetworkPattern(
                            pattern_id=str(uuid.uuid4()),
                            case_id=case_id,
                            pattern_type=ptype,
                            description=rp.explanation or f"{ptype} pattern detected",
                            confidence_score=max(0, min(100, int(rp.confidence_score * 100))),
                            entities_involved=rp.entities_involved,
                            evidence_documents=[{"document_id": d} for d in (rp.source_documents or [])],
                            ai_reasoning=rp.explanation,
                        )
                        # Create AI_Proposed decision for each pattern
                        decision = self._decision_workflow_svc.create_decision(
                            case_id=case_id,
                            decision_type="network_pattern",
                            recommendation_text=f"{ptype.title()} pattern: {np.description[:100]}",
                            legal_reasoning=np.ai_reasoning,
                            confidence="high" if np.confidence_score > 70 else "medium",
                            source_service="network_discovery",
                        )
                        np.decision_id = decision.decision_id
                        np.decision_state = decision.state.value
                        detected_patterns.append(np)
        except Exception as e:
            logger.error("Pattern detection error: %s", str(e)[:200])

        # Cache patterns in Aurora
        self._cache_patterns(detected_patterns)

        # Build result
        result = NetworkAnalysisResult(
            analysis_id=analysis_id,
            case_id=case_id,
            analysis_status=AnalysisStatus.COMPLETED,
            primary_subject=primary_subject,
            total_entities_analyzed=node_count,
            persons_of_interest=persons_of_interest,
            patterns=detected_patterns,
            communities=communities,
            created_at=now,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        # Step 10: Cache in Aurora
        self._cache_analysis(result)

        return result

    def _identify_primary_subject(self, case_id: str) -> str:
        """Identify the primary subject as the entity with highest degree."""
        label = self._entity_label(case_id)
        query = (
            f"g.V().hasLabel('{self._escape(label)}')"
            f".project('name','degree').by('canonical_name').by(bothE().count())"
            f".order().by('degree',desc).limit(1)"
        )
        result = self._gremlin_query(query)
        if result and isinstance(result[0], dict):
            return result[0].get("name", "Unknown")
        return "Unknown"

    def _select_candidates(
        self,
        centrality: dict[str, CentralityScores],
        anomalies: list[str],
        communities: list[CommunityCluster],
    ) -> list[str]:
        """Select candidate entities for profiling based on centrality and anomalies."""
        candidates: set[str] = set()

        # Add anomalous entities
        candidates.update(anomalies)

        # Add top centrality entities
        sorted_by_degree = sorted(
            centrality.items(), key=lambda x: x[1].degree, reverse=True,
        )
        for name, _ in sorted_by_degree[:20]:
            candidates.add(name)

        # Add top PageRank entities
        sorted_by_pr = sorted(
            centrality.items(), key=lambda x: x[1].pagerank, reverse=True,
        )
        for name, _ in sorted_by_pr[:10]:
            candidates.add(name)

        return list(candidates)

    def _get_evidence_for_entity(
        self, case_id: str, entity_name: str,
    ) -> list[EvidenceReference]:
        """Query Aurora for documents mentioning this entity."""
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    """
                    SELECT d.document_id::text, d.file_name
                    FROM documents d
                    JOIN entities e ON d.document_id = e.document_id
                    WHERE d.case_file_id = %s AND e.canonical_name = %s
                    LIMIT 50
                    """,
                    (case_id, entity_name),
                )
                rows = cur.fetchall()
                return [
                    EvidenceReference(
                        document_id=str(row[0]),
                        document_name=str(row[1]) if row[1] else "",
                    )
                    for row in rows
                ]
        except Exception:
            return []

    def _get_relationships(
        self, case_id: str, entity_name: str,
    ) -> list[RelationshipEntry]:
        """Query Neptune for entity relationships."""
        label = self._entity_label(case_id)
        query = (
            f"g.V().hasLabel('{self._escape(label)}')"
            f".has('canonical_name','{self._escape(entity_name)}')"
            f".bothE().project('target','type','weight')"
            f".by(inV().values('canonical_name'))"
            f".by(coalesce(values('relationship_type'),constant('related')))"
            f".by(coalesce(values('weight'),constant(1.0)))"
            f".limit(50)"
        )
        results = self._gremlin_query(query)
        entries: list[RelationshipEntry] = []
        for r in results:
            if isinstance(r, dict):
                entries.append(RelationshipEntry(
                    entity_name=r.get("target", ""),
                    relationship_type=r.get("type", "related"),
                    edge_weight=float(r.get("weight", 1.0)),
                ))
        return entries

    # ------------------------------------------------------------------
    # Public: Query and Update Methods (Task 3.9)
    # ------------------------------------------------------------------

    def get_analysis(self, case_id: str) -> NetworkAnalysisResult | None:
        """Retrieve cached network analysis from Aurora."""
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    """
                    SELECT analysis_id, case_id, analysis_status, primary_subject,
                           total_entities_analyzed, community_clusters, centrality_scores,
                           anomaly_entities, created_at, completed_at
                    FROM network_analyses
                    WHERE case_id = %s
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (case_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                analysis_id = str(row[0])

                # Fetch profiles
                cur.execute(
                    """
                    SELECT profile_id, case_id, entity_name, entity_type, aliases,
                           involvement_score, involvement_breakdown, connection_strength,
                           risk_level, evidence_summary, relationship_map,
                           document_type_count, potential_charges, ai_legal_reasoning,
                           decision_id
                    FROM conspirator_profiles
                    WHERE analysis_id = %s
                    ORDER BY involvement_score DESC
                    """,
                    (analysis_id,),
                )
                profile_rows = cur.fetchall()

                persons = []
                for pr in profile_rows:
                    breakdown = pr[6] if isinstance(pr[6], dict) else json.loads(pr[6] or "{}")
                    persons.append(CoConspiratorProfile(
                        profile_id=str(pr[0]),
                        case_id=str(pr[1]),
                        entity_name=pr[2],
                        entity_type=pr[3],
                        aliases=pr[4] if isinstance(pr[4], list) else json.loads(pr[4] or "[]"),
                        involvement_score=InvolvementScore(
                            total=int(pr[5]),
                            connections=breakdown.get("connections", 0),
                            co_occurrence=breakdown.get("co_occurrence", 0),
                            financial=breakdown.get("financial", 0),
                            communication=breakdown.get("communication", 0),
                            geographic=breakdown.get("geographic", 0),
                        ),
                        connection_strength=int(pr[7]),
                        risk_level=RiskLevel(pr[8]),
                        evidence_summary=[],
                        relationship_map=[],
                        document_type_count=int(pr[11]),
                        potential_charges=pr[12] if isinstance(pr[12], list) else json.loads(pr[12] or "[]"),
                        ai_legal_reasoning=pr[13] or "",
                        decision_id=str(pr[14]) if pr[14] else None,
                    ))

                communities_data = row[5] if isinstance(row[5], list) else json.loads(row[5] or "[]")
                communities = [
                    CommunityCluster(**c) if isinstance(c, dict) else c
                    for c in communities_data
                ]

                return NetworkAnalysisResult(
                    analysis_id=analysis_id,
                    case_id=str(row[1]),
                    analysis_status=AnalysisStatus(row[2]),
                    primary_subject=row[3],
                    total_entities_analyzed=int(row[4]),
                    persons_of_interest=persons,
                    communities=communities,
                    created_at=str(row[8]) if row[8] else "",
                    completed_at=str(row[9]) if row[9] else None,
                )
        except Exception as e:
            logger.error("Failed to get analysis: %s", str(e)[:200])
            return None

    def get_persons_of_interest(
        self, case_id: str, risk_level: str | None = None,
        min_score: int = 0,
    ) -> list[CoConspiratorProfile]:
        """Return persons of interest, optionally filtered."""
        analysis = self.get_analysis(case_id)
        if not analysis:
            return []

        persons = analysis.persons_of_interest

        if risk_level:
            persons = [p for p in persons if p.risk_level == risk_level]

        if min_score > 0:
            persons = [p for p in persons if p.involvement_score.total >= min_score]

        # Ensure sorted by involvement score descending
        persons.sort(key=lambda p: p.involvement_score.total, reverse=True)

        return persons

    def get_person_profile(
        self, case_id: str, person_id: str,
    ) -> CoConspiratorProfile:
        """Return full co-conspirator profile for a specific person."""
        analysis = self.get_analysis(case_id)
        if not analysis:
            raise KeyError(f"No analysis found for case {case_id}")

        for person in analysis.persons_of_interest:
            if person.profile_id == person_id:
                return person

        raise KeyError(f"Person {person_id} not found in case {case_id}")

    def get_network_patterns(
        self, case_id: str, pattern_type: str | None = None,
    ) -> list[NetworkPattern]:
        """Return detected hidden patterns, optionally filtered by type."""
        try:
            with self._aurora.cursor() as cur:
                query = """
                    SELECT pattern_id, case_id, pattern_type, description,
                           confidence_score, entities_involved, evidence_documents,
                           ai_reasoning, decision_id
                    FROM network_patterns
                    WHERE case_id = %s
                """
                params: list = [case_id]

                if pattern_type:
                    query += " AND pattern_type = %s"
                    params.append(pattern_type)

                query += " ORDER BY confidence_score DESC"

                cur.execute(query, tuple(params))
                rows = cur.fetchall()

                return [
                    NetworkPattern(
                        pattern_id=str(r[0]),
                        case_id=str(r[1]),
                        pattern_type=r[2],
                        description=r[3],
                        confidence_score=int(r[4]),
                        entities_involved=r[5] if isinstance(r[5], list) else json.loads(r[5] or "[]"),
                        evidence_documents=r[6] if isinstance(r[6], list) else json.loads(r[6] or "[]"),
                        ai_reasoning=r[7] or "",
                        decision_id=str(r[8]) if r[8] else None,
                    )
                    for r in rows
                ]
        except Exception as e:
            logger.error("Failed to get patterns: %s", str(e)[:200])
            return []

    def update_analysis(
        self, case_id: str, new_evidence_ids: list[str],
    ) -> NetworkAnalysisResult:
        """Incremental update: re-score affected entities without full recomputation."""
        existing = self.get_analysis(case_id)
        if not existing:
            return self.analyze_network(case_id)

        # Re-run centrality to pick up new entities
        centrality = self._run_centrality_scoring(case_id)
        anomalies = self._run_anomaly_detection(case_id, centrality)

        # Update existing profiles with new scores
        primary_subject = existing.primary_subject or "Unknown"
        for person in existing.persons_of_interest:
            new_score = self._compute_involvement_score(
                case_id, person.entity_name, primary_subject,
            )
            person.involvement_score = new_score

        # Check for new candidates
        existing_names = {p.entity_name for p in existing.persons_of_interest}
        new_candidates = [
            name for name in self._select_candidates(centrality, anomalies, existing.communities)
            if name not in existing_names
        ]

        for entity_name in new_candidates:
            score = self._compute_involvement_score(case_id, entity_name, primary_subject)
            profile = CoConspiratorProfile(
                profile_id=str(uuid.uuid4()),
                case_id=case_id,
                entity_name=entity_name,
                entity_type="PERSON",
                involvement_score=score,
                connection_strength=min(100, centrality.get(entity_name, CentralityScores(betweenness=0, degree=0, pagerank=0)).degree * 10),
                risk_level=RiskLevel.LOW,
                document_type_count=0,
            )
            profile.risk_level = self._classify_risk_level(profile)
            existing.persons_of_interest.append(profile)

        # Re-sort
        existing.persons_of_interest.sort(
            key=lambda p: p.involvement_score.total, reverse=True,
        )

        # Update counts
        label = self._entity_label(case_id)
        count_result = self._gremlin_query(
            f"g.V().hasLabel('{self._escape(label)}').count()"
        )
        if count_result:
            nc = count_result[0]
            if isinstance(nc, dict):
                nc = nc.get("@value", 0)
            existing.total_entities_analyzed = int(nc)

        # Re-cache
        self._cache_analysis(existing)

        return existing

    # ------------------------------------------------------------------
    # Public: Sub-Case Spawning (Task 3.11)
    # ------------------------------------------------------------------

    def spawn_sub_case(
        self, case_id: str, person_id: str,
    ) -> SubCaseProposal:
        """Propose a sub-case for a confirmed person of interest.

        1. Gather relevant evidence from parent case
        2. Generate Case_Initiation_Brief via Bedrock
        3. Create AI_Proposed decision for sub-case proposal
        4. On confirmation, delegate to CrossCaseService
        """
        # Get the person's profile
        profile = self.get_person_profile(case_id, person_id)

        # Generate Case Initiation Brief
        brief = self._generate_case_initiation_brief(case_id, profile)

        # Create AI_Proposed decision for the sub-case proposal
        decision = self._decision_workflow_svc.create_decision(
            case_id=case_id,
            decision_type="sub_case_proposal",
            recommendation_text=(
                f"Propose sub-case for {profile.entity_name}: "
                f"Risk Level {profile.risk_level}, "
                f"Involvement Score {profile.involvement_score.total}"
            ),
            legal_reasoning=brief.full_brief,
            confidence="high" if profile.risk_level == RiskLevel.HIGH else "medium",
            source_service="network_discovery",
        )

        proposal = SubCaseProposal(
            proposal_id=str(uuid.uuid4()),
            parent_case_id=case_id,
            profile_id=profile.profile_id,
            brief=brief,
            decision_id=decision.decision_id,
            status="proposed",
        )

        # Cache proposal in Aurora
        self._cache_sub_case_proposal(proposal)

        return proposal

    # ------------------------------------------------------------------
    # Internal: Aurora Caching
    # ------------------------------------------------------------------

    def _cache_analysis(self, result: NetworkAnalysisResult) -> None:
        """Cache network analysis results in Aurora."""
        try:
            communities_json = json.dumps([c.model_dump() for c in result.communities])

            with self._aurora.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO network_analyses (
                        analysis_id, case_id, analysis_status, primary_subject,
                        total_entities_analyzed, total_communities,
                        total_persons_of_interest, community_clusters,
                        created_at, completed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (analysis_id) DO UPDATE SET
                        analysis_status = EXCLUDED.analysis_status,
                        total_entities_analyzed = EXCLUDED.total_entities_analyzed,
                        total_persons_of_interest = EXCLUDED.total_persons_of_interest,
                        completed_at = EXCLUDED.completed_at,
                        updated_at = NOW()
                    """,
                    (
                        result.analysis_id, result.case_id,
                        result.analysis_status.value, result.primary_subject,
                        result.total_entities_analyzed, len(result.communities),
                        len(result.persons_of_interest), communities_json,
                        result.created_at, result.completed_at,
                    ),
                )

                # Cache profiles
                for person in result.persons_of_interest:
                    breakdown = json.dumps({
                        "connections": person.involvement_score.connections,
                        "co_occurrence": person.involvement_score.co_occurrence,
                        "financial": person.involvement_score.financial,
                        "communication": person.involvement_score.communication,
                        "geographic": person.involvement_score.geographic,
                    })
                    cur.execute(
                        """
                        INSERT INTO conspirator_profiles (
                            profile_id, analysis_id, case_id, entity_name,
                            entity_type, involvement_score, involvement_breakdown,
                            connection_strength, risk_level, document_type_count,
                            ai_legal_reasoning, decision_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (profile_id) DO UPDATE SET
                            involvement_score = EXCLUDED.involvement_score,
                            involvement_breakdown = EXCLUDED.involvement_breakdown,
                            connection_strength = EXCLUDED.connection_strength,
                            risk_level = EXCLUDED.risk_level,
                            updated_at = NOW()
                        """,
                        (
                            person.profile_id, result.analysis_id, result.case_id,
                            person.entity_name, person.entity_type,
                            person.involvement_score.total, breakdown,
                            person.connection_strength, person.risk_level.value
                            if isinstance(person.risk_level, RiskLevel) else person.risk_level,
                            person.document_type_count, person.ai_legal_reasoning,
                            person.decision_id,
                        ),
                    )
        except Exception as e:
            logger.error("Failed to cache analysis: %s", str(e)[:200])

    def _cache_patterns(self, patterns: list[NetworkPattern]) -> None:
        """Cache detected network patterns in Aurora."""
        try:
            with self._aurora.cursor() as cur:
                for p in patterns:
                    cur.execute(
                        """
                        INSERT INTO network_patterns (
                            pattern_id, analysis_id, case_id, pattern_type,
                            description, confidence_score, entities_involved,
                            evidence_documents, ai_reasoning, decision_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (pattern_id) DO NOTHING
                        """,
                        (
                            p.pattern_id, None, p.case_id, p.pattern_type,
                            p.description, p.confidence_score,
                            json.dumps(p.entities_involved),
                            json.dumps(p.evidence_documents),
                            p.ai_reasoning, p.decision_id,
                        ),
                    )
        except Exception as e:
            logger.error("Failed to cache patterns: %s", str(e)[:200])

    def _cache_sub_case_proposal(self, proposal: SubCaseProposal) -> None:
        """Cache sub-case proposal in Aurora."""
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sub_case_proposals (
                        proposal_id, parent_case_id, profile_id,
                        proposed_charges, evidence_summary, investigative_steps,
                        case_initiation_brief, decision_id, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        proposal.proposal_id, proposal.parent_case_id,
                        proposal.profile_id,
                        json.dumps(proposal.brief.proposed_charges),
                        proposal.brief.evidence_summary,
                        json.dumps(proposal.brief.investigative_steps),
                        proposal.brief.full_brief,
                        proposal.decision_id, proposal.status,
                    ),
                )
        except Exception as e:
            logger.error("Failed to cache sub-case proposal: %s", str(e)[:200])
