"""MongoDB implementation of IABACRepository.

Persistence format (one document per policy):
  _id         = policy_id
  name        = str
  effect      = "ALLOW" | "DENY"
  events      = [ { event_id, subject, resource, location,
                     time_start, time_end, action }, ... ]
  created_at  = datetime
"""
import datetime
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from option import Result, Ok, Err, Some, NONE
from xoloapi.log import Log

import xoloapi.config as Cfg
from xoloapi.errors.base import DatabaseError, NotFoundError, XoloException
from xoloapi.abac.domain.aggregates import ABACEvent, ABACPolicy
from xoloapi.abac.domain.repositories import IABACRepository
from xoloapi.abac.domain.value_objects import (
    Action, Effect, GeoPoint, Location, Resource, Subject, TimeWindow, TimeWindowMode,
)
from xoloapi.log.format import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class MongoABACRepository(IABACRepository):

    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str) -> None:
        self._col = db[collection_name]

    # ── Serialisation ─────────────────────────────────────────────────────────

    @staticmethod
    def _event_to_doc(ev: ABACEvent) -> dict:
        center = ev.location.center
        return {
            "event_id":           ev.event_id,
            "subject":            ev.subject.value,
            "resource":           ev.resource.value,
            "location_lat":       center.lat if center is not None else None,
            "location_lng":       center.lng if center is not None else None,
            "location_radius_km": ev.location.radius_km,
            "time_mode":          ev.time.mode.value,
            "time_start":         ev.time.start,
            "time_end":           ev.time.end,
            "action":             ev.action.value,
        }

    @staticmethod
    def _event_from_doc(d: dict) -> ABACEvent:
        lat = d.get("location_lat")
        lng = d.get("location_lng")
        center = GeoPoint(lat=lat, lng=lng) if lat is not None and lng is not None else None
        # Backward compat: old documents without time_mode default to
        # DATETIME if start/end are present, otherwise WILDCARD.
        raw_mode = d.get("time_mode")
        if raw_mode is None:
            raw_mode = "datetime" if d.get("time_start") or d.get("time_end") else "wildcard"
        return ABACEvent(
            event_id = d["event_id"],
            subject  = Subject(value=d["subject"]),
            resource = Resource(value=d["resource"]),
            location = Location(center=center, radius_km=d.get("location_radius_km", 1.0)),
            time     = TimeWindow(
                mode  = TimeWindowMode(raw_mode),
                start = d.get("time_start"),
                end   = d.get("time_end"),
            ),
            action   = Action(value=d["action"]),
        )

    @classmethod
    def _policy_from_doc(cls, doc: dict) -> ABACPolicy:
        return ABACPolicy(
            account_id = doc["account_id"],
            policy_id = doc["_id"],
            name      = doc["name"],
            effect    = Effect(doc["effect"]),
            events    = [cls._event_from_doc(e) for e in doc.get("events", [])],
        )

    # ── IABACRepository ───────────────────────────────────────────────────────

    async def save(self, policy: ABACPolicy, raw_events: list[dict]) -> Result[str, XoloException]:
        try:
            doc = {
                "_id":        policy.policy_id,
                "account_id": policy.account_id,
                "name":       policy.name,
                "effect":     policy.effect.value,
                "events":     [self._event_to_doc(e) for e in policy.events],
                "created_at": datetime.datetime.now(datetime.timezone.utc),
            }
            await self._col.replace_one({"_id": policy.policy_id}, doc, upsert=True)
            return Ok(policy.policy_id)
        except Exception as e:
            log.error(build_log_payload("abac.repository.save.error", error=e, policy_id=policy.policy_id))
            return Err(DatabaseError(cause=e))

    async def find_by_id(self, account_id: str, policy_id: str) -> Result[object, XoloException]:
        try:
            doc = await self._col.find_one({"_id": policy_id, "account_id": account_id})
            return Ok(Some(self._policy_from_doc(doc)) if doc else NONE)
        except Exception as e:
            log.error(build_log_payload("abac.repository.find_by_id.error", error=e, policy_id=policy_id))
            return Err(DatabaseError(cause=e))

    async def find_all(self, account_id: str) -> Result[list[ABACPolicy], XoloException]:
        try:
            cursor = self._col.find({"account_id": account_id})
            docs   = await cursor.to_list(length=None)
            return Ok([self._policy_from_doc(d) for d in docs])
        except Exception as e:
            log.error(build_log_payload("abac.repository.find_all.error", error=e))
            return Err(DatabaseError(cause=e))

    async def delete(self, account_id: str, policy_id: str) -> Result[bool, XoloException]:
        try:
            result = await self._col.delete_one({"_id": policy_id, "account_id": account_id})
            if result.deleted_count == 0:
                return Err(NotFoundError("ABACPolicy", policy_id))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("abac.repository.delete.error", error=e, policy_id=policy_id))
            return Err(DatabaseError(cause=e))
