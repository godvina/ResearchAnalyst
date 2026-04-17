"""BackendFactory — resolves SearchBackend implementations by tier."""

from models.case_file import SearchTier
from services.search_backend import SearchBackend


class BackendFactory:
    """Factory that resolves SearchBackend implementations by tier.

    Constructed once per Lambda cold start with both backend instances.
    """

    def __init__(
        self,
        aurora_backend: SearchBackend,
        opensearch_backend: SearchBackend | None = None,
    ) -> None:
        self._backends: dict[SearchTier, SearchBackend] = {
            SearchTier.STANDARD: aurora_backend,
        }
        if opensearch_backend is not None:
            self._backends[SearchTier.ENTERPRISE] = opensearch_backend

    def get_backend(self, tier: str | SearchTier) -> SearchBackend:
        """Return the SearchBackend for the given tier.

        Raises ValueError for unknown or unsupported tiers.
        """
        if isinstance(tier, str):
            try:
                tier = SearchTier(tier)
            except ValueError:
                raise ValueError(
                    f"Unknown search tier: '{tier}'. "
                    f"Valid tiers: {[t.value for t in SearchTier]}"
                )
        backend = self._backends.get(tier)
        if backend is None:
            raise ValueError(
                f"No backend configured for tier '{tier.value}'. "
                f"Valid tiers: {[t.value for t in SearchTier]}"
            )
        return backend

    def validate_search_mode(self, tier: str | SearchTier, mode: str) -> None:
        """Raise ValueError if the mode is not supported by the tier's backend."""
        backend = self.get_backend(tier)
        if mode not in backend.supported_modes:
            raise ValueError(
                f"Search mode '{mode}' is not available for {tier} tier. "
                f"Available modes: {backend.supported_modes}"
            )
