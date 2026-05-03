import pytest
from xoloapi.abac.dto import CreateABACEventDTO, CreateABACPolicyDTO, ABACEvaluateDTO
from xoloapi.abac.service import ABACService
from xoloapi.abac.value_objects import Effect
from tests.abac.conftest import ACCOUNT_ID


def _allow_policy(
    subject: str = "Teacher",
    resource: str = "Grades",
    location: str = "*",
    time_start: str | None = None,
    time_end: str | None = None,
    action: str = "read",
) -> CreateABACPolicyDTO:
    return CreateABACPolicyDTO(
        name   = "Allow Policy",
        effect = Effect.ALLOW,
        events = [CreateABACEventDTO(
            subject    = subject,
            resource   = resource,
            location   = location,
            time_start = time_start,
            time_end   = time_end,
            action     = action,
        )],
    )


def _deny_policy(subject: str = "Teacher", resource: str = "Grades", action: str = "read") -> CreateABACPolicyDTO:
    return CreateABACPolicyDTO(
        name   = "Deny Policy",
        effect = Effect.DENY,
        events = [CreateABACEventDTO(subject=subject, resource=resource, action=action)],
    )


def _request(subject: str = "Teacher", resource: str = "Grades", action: str = "read", **kw) -> ABACEvaluateDTO:
    return ABACEvaluateDTO(subject=subject, resource=resource, action=action, **kw)


# ── CRUD ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_policy_returns_generated_id(abac_service: ABACService):
    result = await abac_service.create_policy(ACCOUNT_ID, _allow_policy())
    assert result.is_ok
    policy_id = result.unwrap()
    assert policy_id.startswith("ap-")


@pytest.mark.asyncio
async def test_list_policies_empty(abac_service: ABACService):
    result = await abac_service.list_policies(ACCOUNT_ID)
    assert result.is_ok
    assert result.unwrap() == []


@pytest.mark.asyncio
async def test_list_policies_returns_created(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy())
    await abac_service.create_policy(ACCOUNT_ID, _deny_policy())

    result = await abac_service.list_policies(ACCOUNT_ID)
    assert result.is_ok
    assert len(result.unwrap()) == 2


@pytest.mark.asyncio
async def test_get_policy_round_trip(abac_service: ABACService):
    policy_id = (await abac_service.create_policy(ACCOUNT_ID, _allow_policy())).unwrap()

    result = await abac_service.get_policy(ACCOUNT_ID, policy_id)
    assert result.is_ok
    policy = result.unwrap()
    assert policy["policy_id"] == policy_id
    assert policy["effect"] == Effect.ALLOW


@pytest.mark.asyncio
async def test_get_nonexistent_policy_returns_err(abac_service: ABACService):
    result = await abac_service.get_policy(ACCOUNT_ID, "ghost-id")
    assert result.is_err


@pytest.mark.asyncio
async def test_delete_policy(abac_service: ABACService):
    policy_id = (await abac_service.create_policy(ACCOUNT_ID, _allow_policy())).unwrap()

    del_result = await abac_service.delete_policy(ACCOUNT_ID, policy_id)
    assert del_result.is_ok

    get_result = await abac_service.get_policy(ACCOUNT_ID, policy_id)
    assert get_result.is_err


@pytest.mark.asyncio
async def test_events_get_generated_ids(abac_service: ABACService):
    policy_id = (await abac_service.create_policy(ACCOUNT_ID, _allow_policy())).unwrap()
    policy    = (await abac_service.get_policy(ACCOUNT_ID, policy_id)).unwrap()

    assert len(policy["events"]) == 1
    assert policy["events"][0]["event_id"].startswith("ev-")


# ── Evaluate: basic ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_allow_on_match(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy())

    result = await abac_service.evaluate(ACCOUNT_ID, _request())
    assert result.is_ok
    decision = result.unwrap()
    assert decision.allowed is True
    assert decision.matched_policy is not None


@pytest.mark.asyncio
async def test_evaluate_deny_on_match(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _deny_policy())

    result = await abac_service.evaluate(ACCOUNT_ID, _request())
    assert result.is_ok
    assert result.unwrap().allowed is False


@pytest.mark.asyncio
async def test_evaluate_default_deny_when_no_policy_matches(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(subject="Admin"))

    result = await abac_service.evaluate(ACCOUNT_ID, _request(subject="Teacher"))
    assert result.is_ok
    decision = result.unwrap()
    assert decision.allowed is False
    assert decision.matched_policy is None


@pytest.mark.asyncio
async def test_evaluate_no_policies_returns_deny(abac_service: ABACService):
    result = await abac_service.evaluate(ACCOUNT_ID, _request())
    assert result.is_ok
    assert result.unwrap().allowed is False


# ── Evaluate: DENY overrides ALLOW ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_deny_overrides_allow(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy())
    await abac_service.create_policy(ACCOUNT_ID, _deny_policy())

    result = await abac_service.evaluate(ACCOUNT_ID, _request())
    assert result.is_ok
    assert result.unwrap().allowed is False


# ── Evaluate: wildcards ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_wildcard_location_matches_any(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(location="*"))

    for loc in ["Campus", "Remote", "Hospital", "anywhere"]:
        result = await abac_service.evaluate(ACCOUNT_ID, _request(location=loc))
        assert result.is_ok
        assert result.unwrap().allowed is True, f"Expected allow for location={loc}"


@pytest.mark.asyncio
async def test_evaluate_specific_location_blocks_other(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(location="Campus"))

    result = await abac_service.evaluate(ACCOUNT_ID, _request(location="Remote"))
    assert result.is_ok
    assert result.unwrap().allowed is False


# ── Evaluate: time window ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_time_window_inside_grants(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(time_start="09:00", time_end="17:00"))

    result = await abac_service.evaluate(ACCOUNT_ID, _request(time="12:00"))
    assert result.is_ok
    assert result.unwrap().allowed is True


@pytest.mark.asyncio
async def test_evaluate_time_window_boundary_grants(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(time_start="09:00", time_end="17:00"))

    for boundary in ["09:00", "17:00"]:
        result = await abac_service.evaluate(ACCOUNT_ID, _request(time=boundary))
        assert result.is_ok
        assert result.unwrap().allowed is True, f"Expected allow at boundary {boundary}"


@pytest.mark.asyncio
async def test_evaluate_time_window_outside_denies(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(time_start="09:00", time_end="17:00"))

    for outside in ["08:59", "17:01", "23:00"]:
        result = await abac_service.evaluate(ACCOUNT_ID, _request(time=outside))
        assert result.is_ok
        assert result.unwrap().allowed is False, f"Expected deny at {outside}"


@pytest.mark.asyncio
async def test_evaluate_wildcard_time_matches_any(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(time_start=None, time_end=None))

    result = await abac_service.evaluate(ACCOUNT_ID, _request(time=None))
    assert result.is_ok
    assert result.unwrap().allowed is True


# ── Evaluate: action matching ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_action_mismatch_denies(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(action="read"))

    result = await abac_service.evaluate(ACCOUNT_ID, _request(action="write"))
    assert result.is_ok
    assert result.unwrap().allowed is False


@pytest.mark.asyncio
async def test_evaluate_action_case_insensitive(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(action="READ"))

    result = await abac_service.evaluate(ACCOUNT_ID, _request(action="read"))
    assert result.is_ok
    assert result.unwrap().allowed is True


@pytest.mark.asyncio
async def test_account_isolation(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy())
    await abac_service.create_policy("acc-other", _deny_policy(action="delete"))

    own_result = await abac_service.list_policies(ACCOUNT_ID)
    other_result = await abac_service.list_policies("acc-other")

    assert own_result.is_ok and len(own_result.unwrap()) == 1
    assert other_result.is_ok and len(other_result.unwrap()) == 1

    own_eval = await abac_service.evaluate(ACCOUNT_ID, _request())
    other_eval = await abac_service.evaluate("acc-other", _request(action="delete"))

    assert own_eval.unwrap().allowed is True
    assert other_eval.unwrap().allowed is False
