# xoloapi/controllers/policies.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from xolo.abac.models import Policy, AccessRequest
from xoloapi.repositories.policies import ABACPoliciesRepository
from xoloapi.services.policies import PolicyService
from xolo.abac.graph import GraphBuilder
from xolo.abac.communities import CommunityDetector
from xolo.abac.evaluator import CommunityPolicyEvaluator
from fastapi import Body

router  = APIRouter(prefix="/policies")



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
def delete_policy(
    policy_id: str,
    repo: ABACPoliciesRepository = Depends(get_repo),
    service: PolicyService = Depends(get_service)
):
    if not repo.delete_policy(policy_id).unwrap_or(False):
        raise HTTPException(status_code=404, detail="Policy not found")

    # Eliminar en caliente de la memoria del evaluador
    service.evaluator.remove_policy(policy_id)

    return {"detail": "Policy deleted from repo and evaluator"}

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

@router.post("/evaluate/batch")
def evaluate_batch_requests(
    requests: List[AccessRequest] = Body(...),
    service: PolicyService = Depends(get_service)
):
    results = []
    for req in requests:
        res = service.evaluate_request(req)
        if res.is_ok:
            results.append(res.unwrap())
        else:
            results.append({
                "result": "error",
                "policy_id": None,
                "event_id": None,
                "error": str(res.unwrap_err())
            })
    return results

@router.put("/{policy_id}")
def update_policy(
    policy_id: str,
    updated_policy: Policy,
    service: PolicyService = Depends(get_service)
):
    res = service.update_policy(policy_id, updated_policy)
    if res.is_err:
        raise HTTPException(status_code=500, detail="Failed to update policy")
    return {"detail": "Policy updated successfully"}

@router.post("/inject")
def inject_policy(
    policy: Policy,
    service: PolicyService = Depends(get_service)
):
    # Validar que las comunidades ya estén preparadas
    if not service.evaluator.policies_by_community:
        raise HTTPException(
            status_code=400,
            detail="Communities must be prepared before injecting policies"
        )

    res = service.create_policy_incremental(policy)
    if res.is_err:
        raise HTTPException(status_code=500, detail="Failed to inject policy into evaluator")

    return {"detail": "Policy injected into evaluator successfully"}
