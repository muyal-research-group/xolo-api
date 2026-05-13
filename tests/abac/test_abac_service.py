import pytest
from xoloapi.abac.dto import CreateABACEventDTO, CreateABACPolicyDTO, ABACEvaluateDTO, GeoPointDTO, GeoZoneDTO
from xoloapi.abac.application.abac_service import ABACService
from xoloapi.abac.domain.value_objects import Effect, TimeWindowMode
from tests.abac.conftest import ACCOUNT_ID

_NYC  = GeoZoneDTO(lat=40.7128, lng=-74.0060, radius_km=1.0)
_NYC_POINT  = GeoPointDTO(lat=40.7128, lng=-74.0060)
_LA_POINT   = GeoPointDTO(lat=34.0522, lng=-118.2437)


def _allow_policy(
    subject: str = "Teacher",
    resource: str = "Grades",
    location: GeoZoneDTO | None = None,
    time_mode: TimeWindowMode = TimeWindowMode.WILDCARD,
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
            time_mode  = time_mode,
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
    assert policy.policy_id == policy_id
    assert policy.effect == Effect.ALLOW


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

    assert len(policy.events) == 1
    assert policy.events[0].event_id.startswith("ev-")


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


# ── Evaluate: location ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_wildcard_location_matches_any(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(location=None))

    for loc in [None, _NYC_POINT, _LA_POINT]:
        result = await abac_service.evaluate(ACCOUNT_ID, _request(location=loc))
        assert result.is_ok
        assert result.unwrap().allowed is True, f"Expected allow for location={loc}"


@pytest.mark.asyncio
async def test_evaluate_specific_location_blocks_distant(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(location=_NYC))

    result = await abac_service.evaluate(ACCOUNT_ID, _request(location=_LA_POINT))
    assert result.is_ok
    assert result.unwrap().allowed is False


@pytest.mark.asyncio
async def test_evaluate_specific_location_allows_nearby(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(location=_NYC))

    result = await abac_service.evaluate(ACCOUNT_ID, _request(location=_NYC_POINT))
    assert result.is_ok
    assert result.unwrap().allowed is True


@pytest.mark.asyncio
async def test_evaluate_no_request_location_passes_geo_policy(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(location=_NYC))

    result = await abac_service.evaluate(ACCOUNT_ID, _request(location=None))
    assert result.is_ok
    assert result.unwrap().allowed is True


# ── Evaluate: time window ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_wildcard_time_matches_any(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy())

    result = await abac_service.evaluate(ACCOUNT_ID, _request(time=None))
    assert result.is_ok
    assert result.unwrap().allowed is True


# ── Evaluate: DATETIME mode ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_datetime_inside_grants(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(
        time_mode=TimeWindowMode.DATETIME,
        time_start="2026-01-01T09:00", time_end="2026-12-31T17:00",
    ))
    result = await abac_service.evaluate(ACCOUNT_ID, _request(time="2026-06-15T12:00"))
    assert result.unwrap().allowed is True


@pytest.mark.asyncio
async def test_evaluate_datetime_boundary_grants(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(
        time_mode=TimeWindowMode.DATETIME,
        time_start="2026-01-01T09:00", time_end="2026-12-31T17:00",
    ))
    for boundary in ["2026-01-01T09:00", "2026-12-31T17:00"]:
        result = await abac_service.evaluate(ACCOUNT_ID, _request(time=boundary))
        assert result.unwrap().allowed is True, f"Expected allow at {boundary}"


@pytest.mark.asyncio
async def test_evaluate_datetime_outside_denies(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(
        time_mode=TimeWindowMode.DATETIME,
        time_start="2026-01-01T09:00", time_end="2026-12-31T17:00",
    ))
    for outside in ["2025-12-31T23:59", "2027-01-01T00:00"]:
        result = await abac_service.evaluate(ACCOUNT_ID, _request(time=outside))
        assert result.unwrap().allowed is False, f"Expected deny at {outside}"


# ── Evaluate: TIME_OF_DAY mode ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_time_of_day_inside_grants(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(
        time_mode=TimeWindowMode.TIME_OF_DAY,
        time_start="09:00", time_end="17:00",
    ))
    result = await abac_service.evaluate(ACCOUNT_ID, _request(time="2026-06-15T12:00"))
    assert result.unwrap().allowed is True


@pytest.mark.asyncio
async def test_evaluate_time_of_day_outside_denies(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(
        time_mode=TimeWindowMode.TIME_OF_DAY,
        time_start="09:00", time_end="17:00",
    ))
    result = await abac_service.evaluate(ACCOUNT_ID, _request(time="2026-06-15T20:00"))
    assert result.unwrap().allowed is False


@pytest.mark.asyncio
async def test_evaluate_time_of_day_midnight_span_grants(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(
        time_mode=TimeWindowMode.TIME_OF_DAY,
        time_start="22:00", time_end="06:00",
    ))
    for t in ["2026-06-15T23:00", "2026-06-16T03:00", "2026-06-16T06:00", "2026-06-15T22:00"]:
        result = await abac_service.evaluate(ACCOUNT_ID, _request(time=t))
        assert result.unwrap().allowed is True, f"Expected allow at {t}"


@pytest.mark.asyncio
async def test_evaluate_time_of_day_midnight_span_outside_denies(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(
        time_mode=TimeWindowMode.TIME_OF_DAY,
        time_start="22:00", time_end="06:00",
    ))
    for t in ["2026-06-15T10:00", "2026-06-15T21:59", "2026-06-16T07:00"]:
        result = await abac_service.evaluate(ACCOUNT_ID, _request(time=t))
        assert result.unwrap().allowed is False, f"Expected deny at {t}"


@pytest.mark.asyncio
async def test_evaluate_time_of_day_none_request_passes(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(
        time_mode=TimeWindowMode.TIME_OF_DAY,
        time_start="09:00", time_end="17:00",
    ))
    result = await abac_service.evaluate(ACCOUNT_ID, _request(time=None))
    assert result.unwrap().allowed is True


# ── Evaluate: DATE mode ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_date_inside_grants(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(
        time_mode=TimeWindowMode.DATE,
        time_start="2026-01-01", time_end="2026-12-31",
    ))
    result = await abac_service.evaluate(ACCOUNT_ID, _request(time="2026-06-15T20:00"))
    assert result.unwrap().allowed is True


@pytest.mark.asyncio
async def test_evaluate_date_outside_denies(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(
        time_mode=TimeWindowMode.DATE,
        time_start="2026-01-01", time_end="2026-12-31",
    ))
    result = await abac_service.evaluate(ACCOUNT_ID, _request(time="2025-12-31T23:59"))
    assert result.unwrap().allowed is False


@pytest.mark.asyncio
async def test_evaluate_date_any_time_of_day_grants(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(
        time_mode=TimeWindowMode.DATE,
        time_start="2026-06-15", time_end="2026-06-15",
    ))
    for t in ["2026-06-15T00:00", "2026-06-15T12:00", "2026-06-15T23:59"]:
        result = await abac_service.evaluate(ACCOUNT_ID, _request(time=t))
        assert result.unwrap().allowed is True, f"Expected allow at {t}"


@pytest.mark.asyncio
async def test_evaluate_date_none_request_passes(abac_service: ABACService):
    await abac_service.create_policy(ACCOUNT_ID, _allow_policy(
        time_mode=TimeWindowMode.DATE,
        time_start="2026-01-01", time_end="2026-12-31",
    ))
    result = await abac_service.evaluate(ACCOUNT_ID, _request(time=None))
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
