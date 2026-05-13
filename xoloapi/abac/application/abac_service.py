from nanoid import generate
from option import Result, Ok, Err

from xoloapi.errors.base import XoloException, NotFoundError
from xoloapi.abac.domain.aggregates import ABACAccessRequest, ABACDecision, ABACEvent, ABACPolicy
from xoloapi.abac.domain.repositories import IABACRepository
from xoloapi.abac.domain.services import ABACEvaluator
from xoloapi.abac.domain.value_objects import (
    Action, Effect, GeoPoint, Location, Resource, Subject, TimeWindow,
)
from xoloapi.abac.dto import ABACEvaluateDTO, CreateABACPolicyDTO


class ABACService:

    def __init__(self, repository: IABACRepository) -> None:
        self._repo      = repository
        self._evaluator = ABACEvaluator()

    async def create_policy(self, account_id: str, dto: CreateABACPolicyDTO) -> Result[str, XoloException]:
        policy_id = f"ap-{generate(size=10)}"
        events = [
            ABACEvent(
                event_id = f"ev-{generate(size=8)}",
                subject  = Subject(value=ev.subject),
                resource = Resource(value=ev.resource),
                location = Location(
                    center=GeoPoint(lat=ev.location.lat, lng=ev.location.lng) if ev.location else None,
                    radius_km=ev.location.radius_km if ev.location else 1.0,
                ),
                time     = TimeWindow(mode=ev.time_mode, start=ev.time_start, end=ev.time_end),
                action   = Action(value=ev.action),
            )
            for ev in dto.events
        ]
        policy = ABACPolicy(
            account_id = account_id,
            policy_id = policy_id,
            name      = dto.name,
            effect    = dto.effect,
            events    = events,
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

    async def update_policy(self, account_id: str, policy_id: str, dto: CreateABACPolicyDTO) -> Result[str, XoloException]:
        existing = await self.get_policy(account_id, policy_id)
        if existing.is_err:
            return Err(existing.unwrap_err())

        events = [
            ABACEvent(
                event_id = f"ev-{generate(size=8)}",
                subject  = Subject(value=ev.subject),
                resource = Resource(value=ev.resource),
                location = Location(
                    center=GeoPoint(lat=ev.location.lat, lng=ev.location.lng) if ev.location else None,
                    radius_km=ev.location.radius_km if ev.location else 1.0,
                ),
                time     = TimeWindow(mode=ev.time_mode, start=ev.time_start, end=ev.time_end),
                action   = Action(value=ev.action),
            )
            for ev in dto.events
        ]
        updated = ABACPolicy(
            account_id = account_id,
            policy_id = policy_id,
            name      = dto.name,
            effect    = dto.effect,
            events    = events,
        )
        return await self._repo.save(updated, raw_events=[])

    async def delete_policy(self, account_id: str, policy_id: str) -> Result[bool, XoloException]:
        return await self._repo.delete(account_id, policy_id)

    async def evaluate(self, account_id: str, dto: ABACEvaluateDTO) -> Result[ABACDecision, XoloException]:
        policies_result = await self._repo.find_all(account_id)
        if policies_result.is_err:
            return policies_result

        request  = ABACAccessRequest(
            subject  = dto.subject,
            resource = dto.resource,
            location = GeoPoint(lat=dto.location.lat, lng=dto.location.lng) if dto.location else None,
            time     = dto.time,
            action   = dto.action,
        )
        decision = self._evaluator.evaluate(request, policies_result.unwrap())
        return Ok(decision)
