"""
Neptune Gremlin query helpers for the Executive Succession Planning module.
Uses the existing Neptune connection pattern from the Research Analyst platform.

All queries are scoped by tenant_id for multi-tenant isolation.
Node IDs follow convention: succession:{tenant_id}:{type}:{uuid}

Target cluster: neptunedbcluster-qoxzlhiau0ao (shared with Intelligence Research domain)
"""

import logging
from datetime import datetime
from typing import Optional

from gremlin_python.process.traversal import T, P, Order
from gremlin_python.process.graph_traversal import __

logger = logging.getLogger(__name__)


class SuccessionGraphService:
    """Neptune graph operations for succession planning.

    Provides upsert, edge creation, and query methods scoped by tenant_id.
    Uses fold/coalesce pattern for idempotent upserts.
    """

    def __init__(self, neptune_connection):
        """Initialize with existing Neptune connection from Research Analyst platform.

        Args:
            neptune_connection: Connection object with a .traversal() method
                that returns a GraphTraversalSource (g).
        """
        self._conn = neptune_connection

    def _node_id(self, tenant_id: str, node_type: str, uuid: str) -> str:
        """Generate namespaced node ID to prevent collisions with Intelligence Research domain."""
        return f"succession:{tenant_id}:{node_type}:{uuid}"

    # =========================================================================
    # UPSERT OPERATIONS
    # =========================================================================

    def upsert_executive(self, tenant_id: str, executive_id: str, properties: dict) -> str:
        """Create or update an Executive node.

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Unique identifier for the executive.
            properties: Dict of node properties (name, current_title, sector, etc.)

        Returns:
            The generated node ID.
        """
        node_id = self._node_id(tenant_id, 'person', executive_id)
        g = self._conn.traversal()

        traversal = (
            g.V(node_id)
            .fold()
            .coalesce(
                __.unfold(),
                __.addV('Executive').property(T.id, node_id)
            )
            .property('tenant_id', tenant_id)
            .property('domain', 'succession')
        )

        for key, value in properties.items():
            if value is not None:
                traversal = traversal.property(key, value)

        traversal.next()
        logger.info("Upserted Executive node: %s", node_id)
        return node_id

    def upsert_organization(self, tenant_id: str, org_id: str, properties: dict) -> str:
        """Create or update an Organization node.

        Args:
            tenant_id: Tenant isolation key.
            org_id: Unique identifier for the organization.
            properties: Dict of node properties (name, sector, country, etc.)

        Returns:
            The generated node ID.
        """
        node_id = self._node_id(tenant_id, 'org', org_id)
        g = self._conn.traversal()

        traversal = (
            g.V(node_id)
            .fold()
            .coalesce(
                __.unfold(),
                __.addV('Organization').property(T.id, node_id)
            )
            .property('tenant_id', tenant_id)
            .property('domain', 'succession')
        )

        for key, value in properties.items():
            if value is not None:
                traversal = traversal.property(key, value)

        traversal.next()
        logger.info("Upserted Organization node: %s", node_id)
        return node_id

    def upsert_role(self, tenant_id: str, role_id: str, properties: dict) -> str:
        """Create or update a Role node.

        Args:
            tenant_id: Tenant isolation key.
            role_id: Unique identifier for the role.
            properties: Dict of node properties (title, role_type, sector, etc.)

        Returns:
            The generated node ID.
        """
        node_id = self._node_id(tenant_id, 'role', role_id)
        g = self._conn.traversal()

        traversal = (
            g.V(node_id)
            .fold()
            .coalesce(
                __.unfold(),
                __.addV('Role').property(T.id, node_id)
            )
            .property('tenant_id', tenant_id)
            .property('domain', 'succession')
        )

        for key, value in properties.items():
            if value is not None:
                traversal = traversal.property(key, value)

        traversal.next()
        logger.info("Upserted Role node: %s", node_id)
        return node_id

    def upsert_competency(self, tenant_id: str, name: str, category: str,
                          criterion_index: int) -> str:
        """Create or update a Competency node.

        Args:
            tenant_id: Tenant isolation key.
            name: Display name (e.g. "Strategic Vision").
            category: personal_attribute | professional_attribute | master_variable
            criterion_index: Position in scoring model (1-25 criteria, 1-15 master vars).

        Returns:
            The generated node ID.
        """
        slug = name.lower().replace(' ', '_')
        node_id = self._node_id(tenant_id, 'competency', slug)
        g = self._conn.traversal()

        (
            g.V(node_id)
            .fold()
            .coalesce(
                __.unfold(),
                __.addV('Competency').property(T.id, node_id)
            )
            .property('tenant_id', tenant_id)
            .property('domain', 'succession')
            .property('name', name)
            .property('category', category)
            .property('criterion_index', criterion_index)
            .next()
        )
        return node_id

    def upsert_cultural_context(self, tenant_id: str, country: str,
                                globe_cluster: str, hofstede: dict) -> str:
        """Create or update a CulturalContext node for a country.

        Args:
            tenant_id: Tenant isolation key.
            country: ISO 3166-1 alpha-2 code.
            globe_cluster: GLOBE cultural cluster name.
            hofstede: Dict with keys: power_distance, individualism,
                uncertainty_avoidance, masculinity, long_term_orientation, indulgence.

        Returns:
            The generated node ID.
        """
        node_id = self._node_id(tenant_id, 'culture', country.lower())
        g = self._conn.traversal()

        traversal = (
            g.V(node_id)
            .fold()
            .coalesce(
                __.unfold(),
                __.addV('CulturalContext').property(T.id, node_id)
            )
            .property('tenant_id', tenant_id)
            .property('domain', 'succession')
            .property('country', country)
            .property('globe_cluster', globe_cluster)
        )

        for dim, value in hofstede.items():
            if value is not None:
                traversal = traversal.property(dim, float(value))

        traversal.next()
        return node_id

    # =========================================================================
    # EDGE OPERATIONS
    # =========================================================================

    def add_held_role(self, tenant_id: str, executive_id: str, role_id: str,
                      properties: dict) -> None:
        """Add HELD_ROLE edge between Executive and Role.

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Executive node UUID.
            role_id: Role node UUID.
            properties: Edge properties (start_date, end_date, tenure_months,
                performance_rating, is_rotational, is_pnl_responsibility,
                is_cross_functional).
        """
        exec_node = self._node_id(tenant_id, 'person', executive_id)
        role_node = self._node_id(tenant_id, 'role', role_id)
        g = self._conn.traversal()

        traversal = (
            g.V(exec_node).as_('e')
            .V(role_node).as_('r')
            .coalesce(
                __.select('e').outE('HELD_ROLE').where(__.inV().as_('r')),
                __.select('e').addE('HELD_ROLE').to(__.select('r'))
            )
        )

        for key, value in properties.items():
            if value is not None:
                traversal = traversal.property(key, value)

        traversal.next()

    def add_demonstrates(self, tenant_id: str, executive_id: str, competency_name: str,
                         score: int, source: str, assessed_at: str,
                         confidence: float = 0.8) -> None:
        """Add DEMONSTRATES edge (Executive demonstrates a Competency at a score).

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Executive node UUID.
            competency_name: Human-readable competency name (slugified for ID).
            score: Integer 1-10.
            source: Assessment platform that produced this score.
            assessed_at: ISO 8601 datetime string.
            confidence: Float 0-1, reliability of the score.
        """
        exec_node = self._node_id(tenant_id, 'person', executive_id)
        comp_slug = competency_name.lower().replace(' ', '_')
        comp_node = self._node_id(tenant_id, 'competency', comp_slug)
        g = self._conn.traversal()

        # Ensure competency node exists
        g.V(comp_node).fold().coalesce(
            __.unfold(),
            __.addV('Competency').property(T.id, comp_node)
                .property('name', competency_name)
                .property('tenant_id', tenant_id)
                .property('domain', 'succession')
        ).next()

        # Upsert edge
        (
            g.V(exec_node).as_('e')
            .V(comp_node).as_('c')
            .coalesce(
                __.select('e').outE('DEMONSTRATES').where(__.inV().as_('c')),
                __.select('e').addE('DEMONSTRATES').to(__.select('c'))
            )
            .property('score', score)
            .property('assessment_source', source)
            .property('assessed_at', assessed_at)
            .property('confidence', confidence)
            .next()
        )

    def add_connection(self, tenant_id: str, exec_a_id: str, exec_b_id: str,
                       relationship_type: str, strength: float,
                       recency_years: float) -> None:
        """Add CONNECTED_TO edge between two Executives with time-decayed weight.

        Decay formula: decayed_weight = strength * 0.5^(recency_years / 3.0)
        Half-life of 3 years means a connection loses half its weight every 3 years.

        Args:
            tenant_id: Tenant isolation key.
            exec_a_id: First executive UUID.
            exec_b_id: Second executive UUID.
            relationship_type: One of: board_coservice, alumni, former_colleagues,
                mentor_mentee, tribal_family, military_unit, wasta.
            strength: Float 0-1, base relationship strength.
            recency_years: Years since last active contact.
        """
        node_a = self._node_id(tenant_id, 'person', exec_a_id)
        node_b = self._node_id(tenant_id, 'person', exec_b_id)
        decayed_weight = strength * (0.5 ** (recency_years / 3.0))

        g = self._conn.traversal()
        (
            g.V(node_a).as_('a')
            .V(node_b).as_('b')
            .coalesce(
                __.select('a').outE('CONNECTED_TO').where(__.inV().as_('b')),
                __.select('a').addE('CONNECTED_TO').to(__.select('b'))
            )
            .property('relationship_type', relationship_type)
            .property('strength', strength)
            .property('recency_years', recency_years)
            .property('decayed_weight', decayed_weight)
            .next()
        )

    def add_succession(self, tenant_id: str, executive_id: str, role_id: str,
                       readiness_level: str, readiness_score: float) -> None:
        """Add SUCCEEDS edge (Executive is successor candidate for Role).

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Executive node UUID.
            role_id: Role node UUID.
            readiness_level: One of: emergency, accelerated, planned.
            readiness_score: Float 0-100.
        """
        exec_node = self._node_id(tenant_id, 'person', executive_id)
        role_node = self._node_id(tenant_id, 'role', role_id)
        g = self._conn.traversal()
        now = datetime.utcnow().isoformat()

        (
            g.V(exec_node).as_('e')
            .V(role_node).as_('r')
            .coalesce(
                __.select('e').outE('SUCCEEDS').where(__.inV().as_('r')),
                __.select('e').addE('SUCCEEDS').to(__.select('r'))
            )
            .property('readiness_level', readiness_level)
            .property('readiness_score', readiness_score)
            .property('assigned_at', now)
            .property('last_evaluated', now)
            .next()
        )

    def add_scored_for(self, tenant_id: str, executive_id: str, role_id: str,
                       role_config_id: str, composite_score: float,
                       scoring_decision_id: str) -> None:
        """Add SCORED_FOR edge (scoring engine output linking candidate to role).

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Executive node UUID.
            role_id: Role node UUID.
            role_config_id: FK to Aurora succession.role_configurations.
            composite_score: Float 0-100.
            scoring_decision_id: FK to Aurora succession.scoring_decisions.
        """
        exec_node = self._node_id(tenant_id, 'person', executive_id)
        role_node = self._node_id(tenant_id, 'role', role_id)
        g = self._conn.traversal()
        now = datetime.utcnow().isoformat()

        (
            g.V(exec_node).as_('e')
            .V(role_node).as_('r')
            .coalesce(
                __.select('e').outE('SCORED_FOR').where(__.inV().as_('r')),
                __.select('e').addE('SCORED_FOR').to(__.select('r'))
            )
            .property('role_config_id', role_config_id)
            .property('composite_score', composite_score)
            .property('scoring_decision_id', scoring_decision_id)
            .property('scored_at', now)
            .next()
        )

    def add_works_at(self, tenant_id: str, executive_id: str, org_id: str,
                     start_date: str, title: str, is_current: bool = True,
                     end_date: Optional[str] = None) -> None:
        """Add WORKS_AT edge between Executive and Organization.

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Executive node UUID.
            org_id: Organization node UUID.
            start_date: ISO 8601 date.
            title: Title held at this organization.
            is_current: Whether this is the current position.
            end_date: ISO 8601 date (None if current).
        """
        exec_node = self._node_id(tenant_id, 'person', executive_id)
        org_node = self._node_id(tenant_id, 'org', org_id)
        g = self._conn.traversal()

        traversal = (
            g.V(exec_node).as_('e')
            .V(org_node).as_('o')
            .coalesce(
                __.select('e').outE('WORKS_AT').where(__.inV().as_('o')),
                __.select('e').addE('WORKS_AT').to(__.select('o'))
            )
            .property('start_date', start_date)
            .property('title', title)
            .property('is_current', is_current)
        )

        if end_date:
            traversal = traversal.property('end_date', end_date)

        traversal.next()

    # =========================================================================
    # QUERY OPERATIONS
    # =========================================================================

    def get_candidate_scores(self, tenant_id: str, executive_id: str) -> list[dict]:
        """Get all DEMONSTRATES edges (competency scores) for a candidate.

        Used by: Scoring Engine to retrieve criterion scores for composite calculation.

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Executive node UUID.

        Returns:
            List of dicts with competency, score, source, assessed_at, confidence.
        """
        exec_node = self._node_id(tenant_id, 'person', executive_id)
        g = self._conn.traversal()

        results = (
            g.V(exec_node)
            .outE('DEMONSTRATES')
            .project('competency', 'score', 'source', 'assessed_at', 'confidence')
            .by(__.inV().values('name'))
            .by(__.values('score'))
            .by(__.values('assessment_source'))
            .by(__.values('assessed_at'))
            .by(__.values('confidence'))
            .toList()
        )
        return results

    def get_career_trajectory(self, tenant_id: str, executive_id: str) -> list[dict]:
        """Get career trajectory (HELD_ROLE edges) ordered chronologically.

        Used by: Scoring Engine trajectory prediction, CAPER Module.

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Executive node UUID.

        Returns:
            List of dicts with role, org, start_date, end_date, tenure_months,
            performance_rating, is_rotational, is_pnl.
        """
        exec_node = self._node_id(tenant_id, 'person', executive_id)
        g = self._conn.traversal()

        results = (
            g.V(exec_node)
            .outE('HELD_ROLE')
            .order().by('start_date', Order.asc)
            .project('role', 'org', 'start_date', 'end_date', 'tenure_months',
                     'performance_rating', 'is_rotational', 'is_pnl')
            .by(__.inV().values('title'))
            .by(__.inV().out('WORKS_AT').values('name').fold())
            .by(__.values('start_date'))
            .by(__.coalesce(__.values('end_date'), __.constant('current')))
            .by(__.values('tenure_months'))
            .by(__.coalesce(__.values('performance_rating'), __.constant(0)))
            .by(__.coalesce(__.values('is_rotational'), __.constant(False)))
            .by(__.coalesce(__.values('is_pnl_responsibility'), __.constant(False)))
            .toList()
        )
        return results

    def get_relationship_network(self, tenant_id: str, executive_id: str,
                                 min_weight: float = 0.1) -> dict:
        """Get relationship network (degree-1 connections filtered by decay weight).

        Filters out very weak connections (decayed_weight < min_weight) to keep
        the network analysis meaningful. Performance target: < 2s for 1M nodes.

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Executive node UUID.
            min_weight: Minimum decayed_weight threshold (default 0.1).

        Returns:
            Dict with center_node, connections list, and total_edges count.
        """
        exec_node = self._node_id(tenant_id, 'person', executive_id)
        g = self._conn.traversal()

        connections = (
            g.V(exec_node)
            .bothE('CONNECTED_TO')
            .has('decayed_weight', P.gte(min_weight))
            .project('other_id', 'other_name', 'relationship_type',
                     'strength', 'decayed_weight')
            .by(__.otherV().id_())
            .by(__.otherV().values('name'))
            .by(__.values('relationship_type'))
            .by(__.values('strength'))
            .by(__.values('decayed_weight'))
            .toList()
        )

        return {
            'center_node': executive_id,
            'connections': connections,
            'total_edges': len(connections)
        }

    def compute_centrality(self, tenant_id: str, executive_id: str) -> dict:
        """Compute degree centrality and betweenness estimate for a candidate.

        Degree centrality = connections / (total_executives - 1).
        Betweenness is approximated as degree * 1.2 (full betweenness is O(V*E)
        and too expensive for real-time scoring on large graphs).

        The combined_centrality value feeds into the Scoring Engine as one of the
        15 master variables.

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Executive node UUID.

        Returns:
            Dict with degree_centrality, betweenness_centrality, combined_centrality,
            total_connections, and low_confidence flag.
        """
        exec_node = self._node_id(tenant_id, 'person', executive_id)
        g = self._conn.traversal()

        # Degree: count of CONNECTED_TO edges
        degree = g.V(exec_node).bothE('CONNECTED_TO').count().next()

        # Total Executive nodes for this tenant (denominator)
        total_nodes = (
            g.V()
            .has('tenant_id', tenant_id)
            .has('domain', 'succession')
            .hasLabel('Executive')
            .count()
            .next()
        )

        degree_centrality = degree / max(total_nodes - 1, 1)

        # Betweenness proxy (full computation deferred to batch job)
        betweenness_estimate = min(degree_centrality * 1.2, 1.0)

        combined = (degree_centrality + betweenness_estimate) / 2.0

        return {
            'degree_centrality': round(min(degree_centrality, 1.0), 4),
            'betweenness_centrality': round(min(betweenness_estimate, 1.0), 4),
            'combined_centrality': round(min(combined, 1.0), 4),
            'total_connections': degree,
            'low_confidence': degree < 3
        }

    def get_shared_connections(self, tenant_id: str, executive_id: str,
                               target_org_id: str) -> dict:
        """Find shared connections between a candidate and target org's leadership.

        Identifies executives that the candidate knows who currently work at the
        target organization. Used for network strength scoring.

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Executive node UUID.
            target_org_id: Target organization UUID.

        Returns:
            Dict with shared_count, shared_connections list, zero_connections flag.
        """
        exec_node = self._node_id(tenant_id, 'person', executive_id)
        org_node = self._node_id(tenant_id, 'org', target_org_id)
        g = self._conn.traversal()

        shared = (
            g.V(exec_node)
            .out('CONNECTED_TO')
            .where(__.out('WORKS_AT').hasId(org_node))
            .project('name', 'title', 'relationship_type')
            .by(__.values('name'))
            .by(__.values('current_title'))
            .by(
                __.inE('CONNECTED_TO')
                .where(__.outV().hasId(exec_node))
                .values('relationship_type')
            )
            .toList()
        )

        return {
            'shared_count': len(shared),
            'shared_connections': shared,
            'zero_connections': len(shared) == 0
        }

    def get_succession_pipeline(self, tenant_id: str, role_id: str) -> dict:
        """Get all candidates on the succession pipeline for a role.

        Groups candidates by readiness_level (emergency/accelerated/planned)
        and computes heat map strength:
          - STRONG: 3+ emergency-ready candidates
          - ADEQUATE: 1-2 emergency-ready
          - WEAK: no emergency-ready but has accelerated/planned
          - EMPTY: no candidates at all

        Args:
            tenant_id: Tenant isolation key.
            role_id: Role node UUID.

        Returns:
            Dict with role_id, strength, emergency/accelerated/planned lists,
            and total_candidates count.
        """
        role_node = self._node_id(tenant_id, 'role', role_id)
        g = self._conn.traversal()

        candidates = (
            g.V(role_node)
            .inE('SUCCEEDS')
            .project('candidate_id', 'candidate_name', 'readiness_level',
                     'readiness_score', 'last_evaluated')
            .by(__.outV().id_())
            .by(__.outV().values('name'))
            .by(__.values('readiness_level'))
            .by(__.values('readiness_score'))
            .by(__.values('last_evaluated'))
            .toList()
        )

        # Group by readiness scenario
        emergency = [c for c in candidates if c['readiness_level'] == 'emergency']
        accelerated = [c for c in candidates if c['readiness_level'] == 'accelerated']
        planned = [c for c in candidates if c['readiness_level'] == 'planned']

        # Determine heat map strength
        ready_now = len(emergency)
        if ready_now >= 3:
            strength = 'STRONG'
        elif ready_now >= 1:
            strength = 'ADEQUATE'
        elif len(accelerated) + len(planned) > 0:
            strength = 'WEAK'
        else:
            strength = 'EMPTY'

        return {
            'role_id': role_id,
            'strength': strength,
            'emergency': emergency,
            'accelerated': accelerated,
            'planned': planned,
            'total_candidates': len(candidates)
        }

    def get_executive_by_id(self, tenant_id: str, executive_id: str) -> Optional[dict]:
        """Retrieve an Executive node's properties.

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Executive node UUID.

        Returns:
            Dict of all node properties, or None if not found.
        """
        node_id = self._node_id(tenant_id, 'person', executive_id)
        g = self._conn.traversal()

        results = g.V(node_id).valueMap(True).toList()
        if not results:
            return None
        return results[0]

    def delete_executive(self, tenant_id: str, executive_id: str) -> bool:
        """Delete an Executive node and all connected edges (GDPR right-to-erasure).

        Args:
            tenant_id: Tenant isolation key.
            executive_id: Executive node UUID.

        Returns:
            True if node was found and deleted, False if not found.
        """
        node_id = self._node_id(tenant_id, 'person', executive_id)
        g = self._conn.traversal()

        exists = g.V(node_id).hasNext()
        if exists:
            g.V(node_id).drop().iterate()
            logger.info("Deleted Executive node (GDPR erasure): %s", node_id)
            return True
        return False
