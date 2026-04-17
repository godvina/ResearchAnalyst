"""CaseFile Compatibility Service — backward-compatible shim wrapping MatterService.

Maps legacy case_id-based calls to the new Matter model, translating field names
(matter_id→case_id, matter_name→topic_name) and status enums (MatterStatus↔CaseFileStatus)
so existing analysis modules continue to work without changes.
"""

from typing import Optional

from models.case_file import CaseFile, CaseFileStatus, SearchTier
from models.hierarchy import Matter, MatterStatus
from services.matter_service import MatterService

# Bidirectional mapping between CaseFileStatus and MatterStatus values.
_CASE_TO_MATTER: dict[CaseFileStatus, MatterStatus] = {
    CaseFileStatus.CREATED: MatterStatus.CREATED,
    CaseFileStatus.INGESTING: MatterStatus.INGESTING,
    CaseFileStatus.INDEXED: MatterStatus.INDEXED,
    CaseFileStatus.INVESTIGATING: MatterStatus.INVESTIGATING,
    CaseFileStatus.ARCHIVED: MatterStatus.ARCHIVED,
    CaseFileStatus.ERROR: MatterStatus.ERROR,
}

_MATTER_TO_CASE: dict[MatterStatus, CaseFileStatus] = {
    v: k for k, v in _CASE_TO_MATTER.items()
}


def _matter_to_case_file(matter: Matter) -> CaseFile:
    """Translate a Matter model instance into a legacy CaseFile."""
    case_status = _MATTER_TO_CASE.get(
        matter.status, CaseFileStatus(matter.status.value)
    )
    search_tier = (
        SearchTier(matter.search_tier)
        if matter.search_tier in {t.value for t in SearchTier}
        else SearchTier.STANDARD
    )

    return CaseFile(
        case_id=matter.matter_id,
        topic_name=matter.matter_name,
        description=matter.description,
        status=case_status,
        created_at=matter.created_at,
        parent_case_id=None,
        s3_prefix=matter.s3_prefix,
        neptune_subgraph_label=matter.neptune_subgraph_label,
        document_count=matter.total_documents,
        entity_count=matter.total_entities,
        relationship_count=matter.total_relationships,
        last_activity=matter.last_activity,
        error_details=matter.error_details,
        search_tier=search_tier,
    )


class CaseFileCompatService:
    """Wraps MatterService to accept case_id (= matter_id) calls from legacy code."""

    def __init__(self, matter_service: MatterService, default_org_id: str) -> None:
        self._matter_service = matter_service
        self._default_org_id = default_org_id

    def get_case_file(self, case_id: str) -> CaseFile:
        """Retrieve a case file by ID, delegating to MatterService.get_matter."""
        if self._default_org_id:
            matter = self._matter_service.get_matter(case_id, self._default_org_id)
            return _matter_to_case_file(matter)

        # No org_id — query case_files directly
        with self._matter_service._db.cursor() as cur:
            cur.execute(
                """SELECT case_id, topic_name, description, status, created_at,
                          s3_prefix, neptune_subgraph_label, document_count,
                          entity_count, relationship_count, last_activity,
                          error_details, search_tier
                   FROM case_files WHERE case_id = %s""",
                (case_id,),
            )
            r = cur.fetchone()
        if r is None:
            raise KeyError(f"Case file not found: {case_id}")
        return CaseFile(
            case_id=str(r[0]), topic_name=r[1], description=r[2] or "",
            status=CaseFileStatus(r[3]) if r[3] in {s.value for s in CaseFileStatus} else CaseFileStatus.CREATED,
            created_at=r[4], parent_case_id=None, s3_prefix=r[5] or "",
            neptune_subgraph_label=r[6] or "", document_count=r[7] or 0,
            entity_count=r[8] or 0, relationship_count=r[9] or 0,
            last_activity=r[10], error_details=r[11],
            search_tier=SearchTier(r[12]) if r[12] in {t.value for t in SearchTier} else SearchTier.STANDARD,
        )

    def list_case_files(self, **kwargs) -> list[CaseFile]:
        """List case files, delegating to MatterService.list_matters.

        Falls back to querying the legacy case_files table directly if no
        org_id is configured (backward compatibility).
        """
        if self._default_org_id:
            matters = self._matter_service.list_matters(self._default_org_id, **kwargs)
            return [_matter_to_case_file(m) for m in matters]

        # No org_id — query case_files table directly (legacy mode)
        # Join with documents table to get real doc counts instead of stale metadata
        with self._matter_service._db.cursor() as cur:
            cur.execute(
                """SELECT cf.case_id, cf.topic_name, cf.description, cf.status, cf.created_at,
                          cf.s3_prefix, cf.neptune_subgraph_label,
                          GREATEST(
                              COALESCE(d.doc_count, 0),
                              COALESCE(cf.document_count, 0)
                          ) as document_count,
                          cf.entity_count, cf.relationship_count, cf.last_activity,
                          cf.error_details, cf.search_tier
                   FROM case_files cf
                   LEFT JOIN (
                       SELECT case_file_id, COUNT(*) as doc_count
                       FROM documents
                       GROUP BY case_file_id
                   ) d ON d.case_file_id = cf.case_id
                   ORDER BY cf.created_at DESC"""
            )
            rows = cur.fetchall()

        results = []
        for r in rows:
            results.append(CaseFile(
                case_id=str(r[0]),
                topic_name=r[1],
                description=r[2] or "",
                status=CaseFileStatus(r[3]) if r[3] in {s.value for s in CaseFileStatus} else CaseFileStatus.CREATED,
                created_at=r[4],
                parent_case_id=None,
                s3_prefix=r[5] or "",
                neptune_subgraph_label=r[6] or "",
                document_count=r[7] or 0,
                entity_count=r[8] or 0,
                relationship_count=r[9] or 0,
                last_activity=r[10],
                error_details=r[11],
                search_tier=SearchTier(r[12]) if r[12] in {t.value for t in SearchTier} else SearchTier.STANDARD,
            ))
        return results

    def create_case_file(
        self,
        topic_name: str,
        description: str,
        parent_case_id: Optional[str] = None,
        search_tier: Optional[str] = None,
    ) -> CaseFile:
        """Create a case file by delegating to MatterService.create_matter."""
        matter = self._matter_service.create_matter(
            org_id=self._default_org_id,
            matter_name=topic_name,
            description=description,
        )
        return _matter_to_case_file(matter)

    def update_status(
        self,
        case_id: str,
        status: CaseFileStatus,
        error_details: Optional[str] = None,
    ) -> CaseFile:
        """Update status, translating CaseFileStatus → MatterStatus."""
        if isinstance(status, str):
            status = CaseFileStatus(status)

        matter_status = _CASE_TO_MATTER[status]
        matter = self._matter_service.update_status(
            case_id, self._default_org_id, matter_status, error_details=error_details
        )
        return _matter_to_case_file(matter)

    def archive_case_file(self, case_id: str) -> CaseFile:
        """Archive a case file by setting its status to ARCHIVED."""
        return self.update_status(case_id, CaseFileStatus.ARCHIVED)

    def delete_case_file(self, case_id: str) -> None:
        """Delete a case file by delegating to MatterService.delete_matter."""
        self._matter_service.delete_matter(case_id, self._default_org_id)
