"""In-memory repository for the community-detection ABAC policy system.

This system is not MongoDB-backed — policies are held in a process-level dict
and rebuilt on restart.  The repository stays in-memory by design.
"""
from typing import Dict, List
from option import Ok, Err, Result
from xoloapi.log import Log

import xoloapi.config as Cfg
from xolo.abac.models import Policy
from xoloapi.logging import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class PoliciesRepository:

    def __init__(self) -> None:
        self._policies: Dict[str, Policy] = {}

    def create_policies(self, policies: List[Policy]) -> Result[int, Exception]:
        n = 0
        for p in policies:
            res = self.create_policy(p)
            if res.is_ok:
                n += 1
        log.info(build_log_payload("policies.repository.create_many", policy_count=len(policies), added_policy_count=n))
        return Ok(n)

    def create_policy(self, policy: Policy) -> Result[Policy, Exception]:
        self._policies[policy.policy_id] = policy
        log.debug(build_log_payload("policies.repository.create", policy_id=policy.policy_id))
        return Ok(policy)

    def get_policy(self, policy_id: str) -> Result[Policy, Exception]:
        policy = self._policies.get(policy_id)
        if policy is None:
            return Err(Exception(f"Policy '{policy_id}' not found"))
        return Ok(policy)

    def list_policies(self) -> Result[List[Policy], Exception]:
        return Ok(list(self._policies.values()))

    def delete_policy(self, policy_id: str) -> Result[bool, Exception]:
        deleted = self._policies.pop(policy_id, None) is not None
        log.debug(build_log_payload("policies.repository.delete", policy_id=policy_id, deleted=deleted))
        return Ok(deleted)

    def update_policy(self, policy_id: str, updated: Policy) -> Result[Policy, Exception]:
        if policy_id not in self._policies:
            return Err(Exception(f"Policy '{policy_id}' not found"))
        self._policies[policy_id] = updated
        log.debug(build_log_payload("policies.repository.update", policy_id=policy_id))
        return Ok(updated)
