from typing import Dict, List
from xolo.abac.models import Policy, Event
from option import Ok,Err,Result

class ABACPoliciesRepository:
    def __init__(self):
        self.policies: Dict[str, Policy] = {}
        # self.events: Dict[str, Event] = {}

    # ---------- Policy ----------
    def create_policies(self,policies:List[Policy])->Result[int, Exception]:
        n=0
        for p in policies:
            res = self.create_policy(policy=p)
            if res.is_ok:
                n+=1
        return Ok(n)
    def create_policy(self, policy: Policy) -> Result[Policy,Exception]:
        self.policies[policy.policy_id] = policy
        return Ok(policy)

    def get_policy(self, policy_id: str) -> Result[Policy,Exception]:
        res = self.policies.get(policy_id,None)
        if res is None:
            return Err(Exception("Policy not found"))
        return Ok(res)

    def list_policies(self) -> Result[List[Policy],Exception]:
        policies = list(self.policies.values() )
        print(policies)
        return Ok(policies)

    def delete_policy(self, policy_id: str) -> Result[bool,Exception]:
        return Ok(self.policies.pop(policy_id, None) is not None)

    # # ---------- Event ----------
    # def create_event(self, event: Event) -> Result[Event,Exception]:
    #     self.events[event.event_id] = event
    #     return Ok(event)

    # def get_event(self, event_id: str) -> Result[Event,Exception]:
    #     return Ok(self.events.get(event_id))

    # def list_events(self) -> Result[List[Event],Exception]:
    #     return Ok(list(self.events.values()))

    # def delete_event(self, event_id: str) -> Result[bool,Exception]:
    #     return Ok(self.events.pop(event_id, None) is not None)