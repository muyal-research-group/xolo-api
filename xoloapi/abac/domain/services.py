"""Pure, stateless ABAC evaluator — domain service."""
from typing import List

from xoloapi.abac.domain.aggregates import ABACAccessRequest, ABACDecision, ABACPolicy
from xoloapi.abac.domain.value_objects import Effect


class ABACEvaluator:
    """DENY always wins; first ALLOW grants; no match → default DENY."""

    def evaluate(self, request: ABACAccessRequest, policies: List[ABACPolicy]) -> ABACDecision:
        first_allow: tuple[str, str] | None = None

        for policy in policies:
            for event in policy.events:
                if not event.matches(request):
                    continue

                if policy.effect == Effect.DENY:
                    return ABACDecision(
                        allowed        = False,
                        matched_policy = policy.policy_id,
                        matched_event  = event.event_id,
                        reason         = "Explicit DENY policy matched",
                    )

                if first_allow is None:
                    first_allow = (policy.policy_id, event.event_id)

        if first_allow:
            policy_id, event_id = first_allow
            return ABACDecision(
                allowed        = True,
                matched_policy = policy_id,
                matched_event  = event_id,
                reason         = "ALLOW policy matched",
            )

        return ABACDecision(allowed=False, reason="No matching policy (default deny)")
