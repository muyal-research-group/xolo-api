from fastapi import APIRouter, HTTPException,Depends
from typing import List
from xolo.abac.models import Policy, AccessRequest
from xoloapi.repositories.policies import ABACPoliciesRepository
from xoloapi.services.policies import PolicyService
from xolo.abac.graph import GraphBuilder
from xolo.abac.communities import CommunityDetector
from xolo.abac.evaluator import CommunityPolicyEvaluator
# from xolo.repository import InMemoryRepository

router  = APIRouter(prefix="/api/v4/policies")



repo    = ABACPoliciesRepository()
def get_repo():
    global repo
    return repo

service = PolicyService(
    repository         = repo,
    graph_builder      = GraphBuilder(),
    community_detector = CommunityDetector(),
    evaluator          = CommunityPolicyEvaluator()
)
def get_service():
    global service
    return service

# ---------- Policy Endpoints ----------

@router.post("/")
def create_policy(policies: List[Policy], repo:ABACPoliciesRepository = Depends(get_repo)):
    res = repo.create_policies(policies)
    if res.is_err:
        raise HTTPException(status_code=500, detail="Failed to create policy")
    return { "n_added":res.unwrap()}

@router.get("/")
def list_policies(repo:ABACPoliciesRepository = Depends(get_repo)):
    res = repo.list_policies()
    if res.is_err:
        raise HTTPException(status_code=500, detail="Failed to get policies")
    return res.unwrap()

@router.get("/{policy_id}")
def get_policy(policy_id: str,repo:ABACPoliciesRepository = Depends(get_repo)):
    policy_result = repo.get_policy(policy_id)
    if policy_result.is_err:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy_result.unwrap()

@router.delete("/{policy_id}")
def delete_policy(policy_id: str,repo:ABACPoliciesRepository = Depends(get_repo)):
    if not repo.delete_policy(policy_id).unwrap_or(False):
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"detail": "Policy deleted"}

@router.post("/prepare")
def prepare_communities(service:PolicyService = Depends(get_service)):
    res = service.prepare_communities()
    if res.is_err:
        raise HTTPException(status_code=500, detail="Failed to prepare communities")
    return res.unwrap()

@router.post("/evaluate")
def evaluate_request(req: AccessRequest,service:PolicyService = Depends(get_service)):
    res = service.evaluate_request(req)
    if res.is_err:
        raise HTTPException(status_code=500, detail="Failed to evaluate request")
    return res.unwrap()
