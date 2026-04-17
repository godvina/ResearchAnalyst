"""Default label-based access policy provider."""

from models.access_control import AccessDecision, SecurityLabel
from services.access_policy_provider import AccessPolicyProvider


class LabelBasedProvider(AccessPolicyProvider):
    """Default provider: compares clearance_level rank vs effective_label rank.

    Ignores the groups field entirely. A user with clearance N can access
    any document with effective_label <= N.
    """

    def check_access(
        self, user_context: dict, resource_context: dict
    ) -> AccessDecision:
        clearance = SecurityLabel(user_context["clearance_level"])
        effective = SecurityLabel(resource_context["effective_label"])

        if clearance >= effective:
            return AccessDecision(allowed=True, reason="clearance_sufficient")

        return AccessDecision(
            allowed=False,
            reason=f"clearance_{clearance.name.lower()}_insufficient_for_{effective.name.lower()}",
        )
