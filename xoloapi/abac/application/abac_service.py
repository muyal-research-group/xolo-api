import datetime

from nanoid import generate
from option import Result, Ok, Err

from xoloapi.errors.base import XoloException, NotFoundError
from xoloapi.abac.domain.aggregates import ABACAccessRequest, ABACDecision, ABACEvent, ABACPolicy
from xoloapi.abac.domain.repositories import IABACRepository
from xoloapi.abac.domain.services import ABACEvaluator
from xoloapi.abac.domain.value_objects import Effect, MatcherVersion


class ABACService:

    def __init__(self, repository: IABACRepository) -> None:
        self._repo      = repository
        self._evaluator = ABACEvaluator()

    async def create_policy(self, account_id: str, name: str, effect: Effect, events: list[ABACEvent], timezone: str = "UTC") -> Result[str, XoloException]:
        policy_id = f"ap-{generate(size=10)}"
        policy = ABACPolicy(
            account_id = account_id,
            policy_id  = policy_id,
            name       = name,
            effect     = effect,
            events     = events,
            matcher_version = MatcherVersion.GLOB_V2,
            timezone = timezone,
        )
        return await self._repo.save(policy, raw_events=[])

    async def get_policy(self, account_id: str, policy_id: str) -> Result[ABACPolicy, XoloException]:
        result = await self._repo.find_by_id(account_id, policy_id)
        if result.is_err:
            return result
        opt = result.unwrap()
        if opt.is_none:
            return Err(NotFoundError("ABACPolicy", policy_id))
        return Ok(opt.unwrap())

    async def list_policies(self, account_id: str) -> Result[list[ABACPolicy], XoloException]:
        return await self._repo.find_all(account_id)

    async def update_policy(self, account_id: str, policy_id: str, name: str, effect: Effect, events: list[ABACEvent], timezone: str | None = None) -> Result[str, XoloException]:
        existing = await self.get_policy(account_id, policy_id)
        if existing.is_err:
            return Err(existing.unwrap_err())

        updated = ABACPolicy(
            account_id = account_id,
            policy_id  = policy_id,
            name       = name,
            effect     = effect,
            events     = events,
            matcher_version = existing.unwrap().matcher_version,
            timezone = timezone or existing.unwrap().timezone,
            created_at = existing.unwrap().created_at,
            updated_at = datetime.datetime.now(datetime.timezone.utc),
        )
        return await self._repo.save(updated, raw_events=[])

    async def upgrade_matcher(self, account_id: str, policy_id: str) -> Result[str, XoloException]:
        existing = await self.get_policy(account_id, policy_id)
        if existing.is_err:
            return Err(existing.unwrap_err())
        policy = existing.unwrap().model_copy(update={"matcher_version": MatcherVersion.GLOB_V2})
        return await self._repo.save(policy, raw_events=[])

    async def delete_policy(self, account_id: str, policy_id: str) -> Result[bool, XoloException]:
        return await self._repo.delete(account_id, policy_id)

    async def evaluate(self, account_id: str, request: ABACAccessRequest) -> Result[ABACDecision, XoloException]:
        policies_result = await self._repo.find_all(account_id)
        if policies_result.is_err:
            return policies_result

        decision = self._evaluator.evaluate(request, policies_result.unwrap())
        return Ok(decision)
