import pytest
from xoloapi.abac.models import ABACEventRecord, ABACPolicyRecord
from xoloapi.abac.repository import ABACRepository
from xoloapi.abac.value_objects import Effect
from tests.abac.conftest import ACCOUNT_ID


def _make_record(policy_id: str, effect: Effect = Effect.ALLOW) -> ABACPolicyRecord:
    return ABACPolicyRecord(
        account_id = ACCOUNT_ID,
        policy_id = policy_id,
        name      = f"Policy {policy_id}",
        effect    = effect,
        events    = [
            ABACEventRecord(
                event_id = "ev-1",
                subject  = "Teacher",
                resource = "Grades",
                location = "*",
                action   = "read",
            )
        ],
    )


# ── Create ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_returns_policy_id(abac_repo: ABACRepository):
    record = _make_record("p-001")
    result = await abac_repo.create(record)
    assert result.is_ok
    assert result.unwrap() == "p-001"


@pytest.mark.asyncio
async def test_created_record_is_persisted(abac_repo: ABACRepository):
    record = _make_record("p-002")
    await abac_repo.create(record)

    found = await abac_repo.get(ACCOUNT_ID, "p-002")
    assert found.is_ok
    stored = found.unwrap()
    assert stored.policy_id == "p-002"
    assert stored.effect == Effect.ALLOW
    assert len(stored.events) == 1
    assert stored.events[0].subject == "Teacher"


# ── List ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_all_empty(abac_repo: ABACRepository):
    result = await abac_repo.list_all(ACCOUNT_ID)
    assert result.is_ok
    assert result.unwrap() == []


@pytest.mark.asyncio
async def test_list_all_returns_all_records(abac_repo: ABACRepository):
    await abac_repo.create(_make_record("p-a"))
    await abac_repo.create(_make_record("p-b"))
    await abac_repo.create(_make_record("p-c"))

    result = await abac_repo.list_all(ACCOUNT_ID)
    assert result.is_ok
    ids = {r.policy_id for r in result.unwrap()}
    assert ids == {"p-a", "p-b", "p-c"}


# ── Get ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_nonexistent_returns_err(abac_repo: ABACRepository):
    result = await abac_repo.get(ACCOUNT_ID, "does-not-exist")
    assert result.is_err


@pytest.mark.asyncio
async def test_get_preserves_deny_effect(abac_repo: ABACRepository):
    record = _make_record("p-deny", effect=Effect.DENY)
    await abac_repo.create(record)

    result = await abac_repo.get(ACCOUNT_ID, "p-deny")
    assert result.is_ok
    assert result.unwrap().effect == Effect.DENY


# ── Delete ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_existing_returns_true(abac_repo: ABACRepository):
    await abac_repo.create(_make_record("p-del"))

    result = await abac_repo.delete(ACCOUNT_ID, "p-del")
    assert result.is_ok
    assert result.unwrap() is True


@pytest.mark.asyncio
async def test_delete_removes_from_db(abac_repo: ABACRepository):
    await abac_repo.create(_make_record("p-gone"))
    await abac_repo.delete(ACCOUNT_ID, "p-gone")

    result = await abac_repo.get(ACCOUNT_ID, "p-gone")
    assert result.is_err


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_err(abac_repo: ABACRepository):
    result = await abac_repo.delete(ACCOUNT_ID, "ghost-id")
    assert result.is_err


# ── Events ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_events_are_stored_with_all_fields(abac_repo: ABACRepository):
    record = ABACPolicyRecord(
        account_id = ACCOUNT_ID,
        policy_id = "p-events",
        name      = "Timed Policy",
        effect    = Effect.ALLOW,
        events    = [
            ABACEventRecord(
                event_id   = "ev-timed",
                subject    = "Doctor",
                resource   = "PatientChart",
                location   = "Hospital",
                time_start = "08:00",
                time_end   = "17:00",
                action     = "write",
            )
        ],
    )
    await abac_repo.create(record)

    stored = (await abac_repo.get(ACCOUNT_ID, "p-events")).unwrap()
    ev = stored.events[0]
    assert ev.subject    == "Doctor"
    assert ev.time_start == "08:00"
    assert ev.time_end   == "17:00"
    assert ev.action     == "write"
