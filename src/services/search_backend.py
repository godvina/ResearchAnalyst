"""SearchBackend Protocol and IndexDocumentRequest for multi-backend search."""

from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from models.search import FacetedFilter, SearchResult


@dataclass
class IndexDocumentRequest:
    """Payload for indexing a single document into a search backend."""

    document_id: str
    case_file_id: str
    text: str
    embedding: list[float]
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class SearchBackend(Protocol):
    """Protocol defining the contract for search backend implementations."""

    def index_documents(
        self,
        case_id: str,
        documents: list[IndexDocumentRequest],
    ) -> int:
        """Index one or more documents. Returns count of successfully indexed docs."""
        ...

    def search(
        self,
        case_id: str,
        query: str,
        *,
        mode: str = "semantic",
        embedding: Optional[list[float]] = None,
        filters: Optional[FacetedFilter] = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """Search indexed documents. Returns results sorted by relevance."""
        ...

    def delete_documents(
        self,
        case_id: str,
        document_ids: Optional[list[str]] = None,
    ) -> int:
        """Delete indexed documents for a case. If document_ids is None, delete all.
        Returns count of deleted documents."""
        ...

    @property
    def supported_modes(self) -> list[str]:
        """Return the search modes this backend supports."""
        ...
