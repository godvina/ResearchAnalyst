"""Abstract interface for pluggable access policy providers."""

from abc import ABC, abstractmethod

from models.access_control import AccessDecision


class AccessPolicyProvider(ABC):
    """Abstract interface for access policy decisions.

    Implementations receive user and resource context dicts and return
    an AccessDecision. The middleware never hardcodes label comparison
    logic — it always delegates to the configured provider.
    """

    @abstractmethod
    def check_access(
        self, user_context: dict, resource_context: dict
    ) -> AccessDecision:
        """Determine whether the user may access the resource.

        Args:
            user_context: Contains user_id, username, clearance_level, role, groups.
            resource_context: Contains document_id, case_id, effective_label,
                            security_label_override.

        Returns:
            AccessDecision with allowed=True/False and a reason string.
        """
        ...
