import pytest
from xoloapi.abac.domain.aggregates import ABACEvent, ABACPolicy
from xoloapi.abac.domain.value_objects import (
    Action, Effect, GeoPoint, Location, Resource, Subject, TimeWindow, TimeWindowMode,
)
from xoloapi.abac.infrastructure.mongo_abac_repository import MongoABACRepository
from tests.abac.conftest import ACCOUNT_ID


def _make_policy(policy_id: str, effect: Effect = Effect.ALLOW) -> ABACPolicy:
    return ABACPolicy(
        account_id = ACCOUNT_ID,
        policy_id  = policy_id,
        name       = f"Policy {policy_id}",
        effect     = effect,
        events     = [
            ABACEvent(
                event_id = "ev-1",
                subject  = Subject(value="Teacher"),
                resource = Resource(value="Grades"),
                location = Location(center=None),
                time     = TimeWindow(start=None, end=None),
                action   = Action(value="read"),
            )
        ],
    )


# ── Create ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_returns_policy_id(abac_repo: MongoABACRepository):
    result = await abac_repo.save(_make_policy("p-001"), raw_events=[])
    assert result.is_ok
    assert result.unwrap() == "p-001"


@pytest.mark.asyncio
async def test_created_record_is_persisted(abac_repo: MongoABACRepository):
    await abac_repo.save(_make_policy("p-002"), raw_events=[])

    found = await abac_repo.find_by_id(ACCOUNT_ID, "p-002")
    assert found.is_ok
    opt = found.unwrap()
    assert opt.is_some
    stored = opt.unwrap()
    assert stored.policy_id == "p-002"
    assert stored.effect == Effect.ALLOW
    assert len(stored.events) == 1
    assert stored.events[0].subject.value == "Teacher"


# ── List ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_all_empty(abac_repo: MongoABACRepository):
    result = await abac_repo.find_all(ACCOUNT_ID)
    assert result.is_ok
    assert result.unwrap() == []


@pytest.mark.asyncio
async def test_list_all_returns_all_records(abac_repo: MongoABACRepository):
    await abac_repo.save(_make_policy("p-a"), raw_events=[])
    await abac_repo.save(_make_policy("p-b"), raw_events=[])
    await abac_repo.save(_make_policy("p-c"), raw_events=[])

    result = await abac_repo.find_all(ACCOUNT_ID)
    assert result.is_ok
    ids = {r.policy_id for r in result.unwrap()}
    assert ids == {"p-a", "p-b", "p-c"}


# ── Get ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_nonexistent_returns_none(abac_repo: MongoABACRepository):
    result = await abac_repo.find_by_id(ACCOUNT_ID, "does-not-exist")
    assert result.is_ok
    assert result.unwrap().is_none


@pytest.mark.asyncio
async def test_get_preserves_deny_effect(abac_repo: MongoABACRepository):
    await abac_repo.save(_make_policy("p-deny", effect=Effect.DENY), raw_events=[])

    result = await abac_repo.find_by_id(ACCOUNT_ID, "p-deny")
    assert result.is_ok
    stored = result.unwrap().unwrap()
    assert stored.effect == Effect.DENY


# ── Delete ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_existing_returns_true(abac_repo: MongoABACRepository):
    await abac_repo.save(_make_policy("p-del"), raw_events=[])

    result = await abac_repo.delete(ACCOUNT_ID, "p-del")
    assert result.is_ok
    assert result.unwrap() is True


@pytest.mark.asyncio
async def test_delete_removes_from_db(abac_repo: MongoABACRepository):
    await abac_repo.save(_make_policy("p-gone"), raw_events=[])
    await abac_repo.delete(ACCOUNT_ID, "p-gone")

    result = await abac_repo.find_by_id(ACCOUNT_ID, "p-gone")
    assert result.is_ok
    assert result.unwrap().is_none


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_err(abac_repo: MongoABACRepository):
    result = await abac_repo.delete(ACCOUNT_ID, "ghost-id")
    assert result.is_err


# ── Events ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_events_are_stored_with_all_fields(abac_repo: MongoABACRepository):
    policy = ABACPolicy(
        account_id = ACCOUNT_ID,
        policy_id  = "p-events",
        name       = "Timed Geo Policy",
        effect     = Effect.ALLOW,
        events     = [
            ABACEvent(
                event_id = "ev-timed",
                subject  = Subject(value="Doctor"),
                resource = Resource(value="PatientChart"),
                location = Location(center=GeoPoint(lat=41.0, lng=-87.0), radius_km=2.0),
                time     = TimeWindow(mode=TimeWindowMode.DATETIME, start="2026-01-01T08:00", end="2026-12-31T17:00"),
                action   = Action(value="write"),
            )
        ],
    )
    await abac_repo.save(policy, raw_events=[])

    stored = (await abac_repo.find_by_id(ACCOUNT_ID, "p-events")).unwrap().unwrap()
    ev = stored.events[0]
    assert ev.subject.value    == "Doctor"
    assert ev.time.start       == "2026-01-01T08:00"
    assert ev.time.end         == "2026-12-31T17:00"
    assert ev.action.value     == "write"
    assert ev.location.center.lat == pytest.approx(41.0)
    assert ev.location.center.lng == pytest.approx(-87.0)
    assert ev.location.radius_km  == pytest.approx(2.0)
