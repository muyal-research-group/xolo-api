from option import Ok, Result

from xoloapi.abac.application.abac_service import ABACService as ApplicationABACService
from xoloapi.abac.models import ABACPolicyRecord
from xoloapi.errors.base import XoloException


def _to_record(policy) -> ABACPolicyRecord:
    return ABACPolicyRecord(
        account_id=policy.account_id,
        policy_id=policy.policy_id,
        name=policy.name,
        effect=policy.effect,
        events=[
            {
                "event_id": event.event_id,
                "subject": event.subject.value,
                "resource": event.resource.value,
                "location": event.location.value,
                "time_start": event.time.start,
                "time_end": event.time.end,
                "action": event.action.value,
            }
            for event in policy.events
        ],
    )


class ABACService:
    def __init__(self, repository, evaluator=None) -> None:
        self._service = ApplicationABACService(repository=repository._repo if hasattr(repository, "_repo") else repository)

    async def create_policy(self, account_id: str, dto) -> Result[str, XoloException]:
        return await self._service.create_policy(account_id, dto)

    async def get_policy(self, account_id: str, policy_id: str) -> Result[ABACPolicyRecord, XoloException]:
        result = await self._service.get_policy(account_id, policy_id)
        if result.is_err:
            return result
        return Ok(_to_record(result.unwrap()))

    async def list_policies(self, account_id: str) -> Result[list[ABACPolicyRecord], XoloException]:
        result = await self._service.list_policies(account_id)
        if result.is_err:
            return result
        return Ok([_to_record(policy) for policy in result.unwrap()])

    async def delete_policy(self, account_id: str, policy_id: str) -> Result[bool, XoloException]:
        return await self._service.delete_policy(account_id, policy_id)

    async def evaluate(self, account_id: str, dto):
        return await self._service.evaluate(account_id, dto)


__all__ = ["ABACService"]
