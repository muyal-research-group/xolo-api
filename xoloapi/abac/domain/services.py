"""Pure, stateless ABAC evaluator — domain service."""
from typing import List

from xoloapi.abac.domain.aggregates import ABACAccessRequest, ABACDecision, ABACPolicy
from xoloapi.abac.domain.value_objects import Effect


class ABACEvaluator:
    """DENY always wins; first ALLOW grants; no match → default DENY."""

    def evaluate(self, request: ABACAccessRequest, policies: List[ABACPolicy]) -> ABACDecision:
        first_allow: tuple[str, str] | None = None
        matched_policy_ids: list[str] = []
        matched_event_ids: list[str] = []
        warnings = []
        if request.location is None:
            warnings.append("omitted_context:location")
        if request.time is None:
            warnings.append("omitted_context:time")

        for policy in policies:
            for event in policy.events:
                if not event.matches(request, policy.matcher_version, policy.timezone):
                    continue

                matched_policy_ids.append(policy.policy_id)
                matched_event_ids.append(event.event_id)

                if policy.effect == Effect.DENY:
                    return ABACDecision(
                        allowed        = False,
                        matched_policy = policy.policy_id,
                        matched_event  = event.event_id,
                        reason         = "Explicit DENY policy matched",
                        matched_policy_ids=matched_policy_ids,
                        matched_event_ids=matched_event_ids,
                        request_context=request.model_dump(),
                        warnings=warnings,
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
                matched_policy_ids=matched_policy_ids,
                matched_event_ids=matched_event_ids,
                request_context=request.model_dump(),
                warnings=warnings,
            )

        return ABACDecision(
            allowed=False, reason="No matching policy (default deny)",
            matched_policy_ids=matched_policy_ids, matched_event_ids=matched_event_ids,
            request_context=request.model_dump(), warnings=warnings,
        )
