import pytest
from xolo.abac.models import Policy,AccessRequest
from xolo.abac.loader import PolicyLoader,AccessRequestLoader
from xolo.abac.graph import GraphBuilder
from xolo.abac.communities import CommunityDetector
from xolo.abac.evaluator import CommunityPolicyEvaluator

ps = PolicyLoader.from_file("tests/policies/policies.json")
ce = CommunityPolicyEvaluator(
    policies= ps
)

def test_from_json_policy():
    p = Policy.from_json("tests/policies/p1.json")
    assert p.policy_id == "P1"

def test_from_file_policies():
    ps = PolicyLoader.from_file("tests/policies/policies.json")
    assert len(ps)==10

def test_from_file_access_reqs():
    ps = AccessRequestLoader.from_file("tests/policies/requests.json")
    assert len(ps) == 20

    
def test_from_json_access_request():
    p = AccessRequest.from_json("tests/policies/r1.json")
    assert p.subject.value == "Medico"


def test_graph_builder():
    policies = PolicyLoader.from_file("tests/policies/policies.json")
    gb       = GraphBuilder()
    res      = gb.build_event_graph(policies=policies)
    assert len(res.edges) == 25 and len(res.nodes) == 25


def test_communities_detector():
    policies = PolicyLoader.from_file("tests/policies/policies.json")
    gb       = GraphBuilder()
    graph      = gb.build_event_graph(policies=policies)
    cd = CommunityDetector()
    x = cd.detect_communities(graph=graph)

def test_remove_policy():
    r = ce.remove_policy(policy_id="P1")
    assert len(ce.policies) == 9

def test_add_policy():
    r = ce.add_policy(policy= ps[0])
    assert len(ce.policies) == 10

def test_update_policy():
    p = ps[0]
    p.policy_id = "P1"
    r = ce.update_policy(
        updated_policy=p
    )
    assert len(ce.policies) == 10
