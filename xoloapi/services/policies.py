# xoloapi/services/policies.py
from option import Err,Result,Ok
from typing import Dict,List
from xolo.abac.models import AccessRequest
from xoloapi.repositories.policies import ABACPoliciesRepository
from xolo.abac.graph import GraphBuilder
from xolo.abac.communities import CommunityDetector
from xolo.abac.evaluator import CommunityPolicyEvaluator

class PolicyService:
    def __init__(self,
                 repository: ABACPoliciesRepository,
                 graph_builder:GraphBuilder,
                 community_detector:CommunityDetector,
                 evaluator: CommunityPolicyEvaluator

    ):
        self.repository         = repository
        self.graph_builder      = graph_builder
        self.community_detector = community_detector
        self.evaluator = evaluator


    def evaluate_request(self, access_request: AccessRequest) -> Result[str,Exception]:
        result = self.evaluator.evaluate(request=access_request)
        return Ok(result)


    def prepare_communities(self)->Result[Dict[str, List[str]],Exception]:
        policies_result=  self.repository.list_policies()
        if policies_result.is_err:
            return Err(Exception("Failed to get policies"))
        policies = policies_result.unwrap()
        graph = self.graph_builder.build_event_graph(policies=policies)
        event_communities, event_to_community = self.community_detector.detect_communities(graph)
        event_to_policy:Dict[str,str] = {node_id: data.get("policy_id") for node_id, data in graph.nodes(data=True)}
        policies_by_community = self.community_detector.map_policies_to_communities(event_to_policy, event_to_community)
        self.evaluator.run(policies=policies,policies_by_community=policies_by_community)
        return Ok(policies_by_community)
        
