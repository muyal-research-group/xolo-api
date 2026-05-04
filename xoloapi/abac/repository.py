from option import Err, Ok, Result

from xoloapi.abac.domain.aggregates import ABACEvent, ABACPolicy
from xoloapi.abac.domain.value_objects import Action, Location, Resource, Subject, TimeWindow
from xoloapi.abac.infrastructure.mongo_abac_repository import MongoABACRepository
from xoloapi.abac.models import ABACEventRecord, ABACPolicyRecord
from xoloapi.db.constants import CollectionNames
from xoloapi.errors.base import NotFoundError, XoloException


def _to_domain(record: ABACPolicyRecord) -> ABACPolicy:
    return ABACPolicy(
        account_id=record.account_id,
        policy_id=record.policy_id,
        name=record.name,
        effect=record.effect,
        events=[
            ABACEvent(
                event_id=event.event_id,
                subject=Subject(value=event.subject),
                resource=Resource(value=event.resource),
                location=Location(value=event.location),
                time=TimeWindow(start=event.time_start, end=event.time_end),
                action=Action(value=event.action),
            )
            for event in record.events
        ],
    )


def _to_record(policy: ABACPolicy) -> ABACPolicyRecord:
    return ABACPolicyRecord(
        account_id=policy.account_id,
        policy_id=policy.policy_id,
        name=policy.name,
        effect=policy.effect,
        events=[
            ABACEventRecord(
                event_id=event.event_id,
                subject=event.subject.value,
                resource=event.resource.value,
                location=event.location.value,
                time_start=event.time.start,
                time_end=event.time.end,
                action=event.action.value,
            )
            for event in policy.events
        ],
    )


class ABACRepository:
    def __init__(self, db, collection_name: str = CollectionNames.ABAC_POLICIES_COLLECTION_NAME) -> None:
        self._repo = MongoABACRepository(db=db, collection_name=collection_name)

    async def create(self, record: ABACPolicyRecord) -> Result[str, XoloException]:
        return await self._repo.save(_to_domain(record), raw_events=[])

    async def get(self, account_id: str, policy_id: str) -> Result[ABACPolicyRecord, XoloException]:
        result = await self._repo.find_by_id(account_id, policy_id)
        if result.is_err:
            return result

        opt = result.unwrap()
        if opt.is_none:
            return Err(NotFoundError("ABACPolicy", policy_id))

        return Ok(_to_record(opt.unwrap()))

    async def list_all(self, account_id: str) -> Result[list[ABACPolicyRecord], XoloException]:
        result = await self._repo.find_all(account_id)
        if result.is_err:
            return result
        return Ok([_to_record(policy) for policy in result.unwrap()])

    async def delete(self, account_id: str, policy_id: str) -> Result[bool, XoloException]:
        return await self._repo.delete(account_id, policy_id)


__all__ = ["ABACRepository", "ABACEventRecord", "ABACPolicyRecord"]
