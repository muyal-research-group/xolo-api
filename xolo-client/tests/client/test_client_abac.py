from xolo.client.client import XoloClient
from xolo.client import models as M


def test_abac_methods_return_expected_dtos(
    protected_client: XoloClient,
    make_signed_up_user,
    rand_name,
    unwrap_ok,
    unwrap_ok_list,
):
    user = make_signed_up_user()

    created_policy = unwrap_ok(
        protected_client.create_abac_policy(
            name=rand_name("abac"),
            effect="ALLOW",
            events=[
                {
                    "subject": "Doctor",
                    "resource": "Chart",
                    "action": "read",
                }
            ],
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.CreatedABACPolicyResponseDTO,
    )
    assert created_policy.ok is True
    assert created_policy.policy_id

    policies = unwrap_ok_list(
        protected_client.list_abac_policies(
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.ABACPolicyDTO,
    )
    listed_policy = next(item for item in policies if item.policy_id == created_policy.policy_id)
    assert listed_policy.name

    fetched_policy = unwrap_ok(
        protected_client.get_abac_policy(
            policy_id=created_policy.policy_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.ABACPolicyDTO,
    )
    assert fetched_policy.policy_id == created_policy.policy_id
    assert fetched_policy.name == listed_policy.name
    assert isinstance(fetched_policy.events, list)
    assert fetched_policy.events
    assert isinstance(fetched_policy.events[0], M.ABACEventRecordDTO)

    decision = unwrap_ok(
        protected_client.evaluate_abac(
            subject="Doctor",
            resource="Chart",
            action="read",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.ABACDecisionDTO,
    )
    assert decision.allowed is True
    assert isinstance(decision.reason, str)

    deleted_policy = unwrap_ok(
        protected_client.delete_abac_policy(
            policy_id=created_policy.policy_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.DeletedABACPolicyResponseDTO,
    )
    assert deleted_policy.ok is True
    assert deleted_policy.policy_id == created_policy.policy_id
