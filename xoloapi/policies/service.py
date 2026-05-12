"""Application service for the community-detection ABAC policy system."""
import xoloapi.config as Cfg
from typing import Dict, List
from option import Ok, Err, Result
from xoloapi.log import Log

from xolo.abac.communities import CommunityDetector
from xolo.abac.evaluator import CommunityPolicyEvaluator
from xolo.abac.graph import GraphBuilder
from xolo.abac.models import AccessRequest, Policy

from xoloapi.logging import build_log_payload
from xoloapi.policies.repository import PoliciesRepository

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)

class PolicyService:

    def __init__(
        self,
        repository:         PoliciesRepository,
        graph_builder:      GraphBuilder,
        community_detector: CommunityDetector,
        evaluator:          CommunityPolicyEvaluator,
    ) -> None:
        self.repository         = repository
        self.graph_builder      = graph_builder
        self.community_detector = community_detector
        self.evaluator          = evaluator

    def evaluate_request(self, request: AccessRequest) -> Result[str, Exception]:
        log.debug(build_log_payload("policies.evaluate.attempt"))
        return Ok(self.evaluator.evaluate(request=request))

    def prepare_communities(self) -> Result[Dict[str, List[str]], Exception]:
        policies_result = self.repository.list_policies()
        if policies_result.is_err:
            log.error(build_log_payload("policies.prepare.error", error=policies_result.unwrap_err()))
            return Err(Exception("Failed to get policies"))
        policies = policies_result.unwrap()
        graph = self.graph_builder.build_event_graph(policies=policies)
        event_communities, event_to_community = self.community_detector.detect_communities(graph)
        event_to_policy: Dict[str, str] = {
            node_id: data.get("policy_id")
            for node_id, data in graph.nodes(data=True)
        }
        policies_by_community = self.community_detector.map_policies_to_communities(
            event_to_policy, event_to_community
        )
        self.evaluator.run(policies=policies, policies_by_community=policies_by_community)
        log.info(build_log_payload("policies.prepare.service", policy_count=len(policies), community_count=len(policies_by_community)))
        return Ok(policies_by_community)

    def update_policy(self, policy_id: str, updated: Policy) -> Result[bool, Exception]:
        result = self.repository.update_policy(policy_id, updated)
        if result.is_err:
            log.error(build_log_payload("policies.update.error", error=result.unwrap_err(), policy_id=policy_id))
            return result
        self.evaluator.update_policy(updated)
        log.info(build_log_payload("policies.update.service", policy_id=policy_id))
        return Ok(True)

    def create_policy_incremental(self, policy: Policy) -> Result[bool, Exception]:
        res = self.repository.create_policy(policy)
        if res.is_err:
            log.error(build_log_payload("policies.inject.error", error=res.unwrap_err(), policy_id=policy.policy_id))
            return res
        if self.evaluator.policies_by_community:
            self.evaluator.add_policy(policy)
        log.info(build_log_payload("policies.inject.service", policy_id=policy.policy_id))
        return Ok(True)
