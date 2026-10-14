#!/usr/bin/env python3
"""Idempotent authorization-v2 migration runner.

Run with ``--dry-run`` first. A completion marker prevents accidental reruns;
``--force`` is available for an interrupted/manual recovery after inspection.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
import sys
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient

# Direct script execution sets sys.path to ``scripts/`` rather than the
# application root. Keep the documented command usable in source checkouts and
# in the production image without requiring a caller-provided PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xoloapi.db.constants import CollectionNames as C


MIGRATION_ID = "authorization-v2-2026-10"
BACKUP_COLLECTIONS = [
    C.ACCOUNTS_COLLECTION_NAME,
    C.USERS_COLLECTION_NAME,
    C.SECURITY_GROUPS_COLLECTION_NAME,
    C.GROUP_MEMBERS_COLLECTION_NAME,
    C.ACL_RESOURCE_POLICIES_COLLECTION_NAME,
    C.RBAC_ROLES_COLLECTION_NAME,
    C.RBAC_ASSIGNMENTS_COLLECTION_NAME,
    C.ABAC_POLICIES_COLLECTION_NAME,
    C.NGAC_NODES_COLLECTION_NAME,
    C.NGAC_ASSIGNMENTS_COLLECTION_NAME,
    C.NGAC_ASSOCIATIONS_COLLECTION_NAME,
    C.NOTIFICATIONS_COLLECTION_NAME,
    C.NOTIFICATION_RECEIPTS_COLLECTION_NAME,
]


def normalize_group_name(value: str) -> tuple[str, str]:
    display = " ".join(value.strip().split())
    return display, display.casefold()


async def backup(db, suffix: str, dry_run: bool) -> dict[str, int]:
    counts = {}
    existing = set(await db.list_collection_names())
    for name in BACKUP_COLLECTIONS:
        if name not in existing:
            counts[name] = 0
            continue
        docs = await db[name].find({}).to_list(length=None)
        counts[name] = len(docs)
        if docs and not dry_run:
            destination = db[f"backup_{suffix}_{name}"]
            await destination.insert_many(docs)
    return counts


async def run(args) -> None:
    client = AsyncIOMotorClient(args.uri)
    db = client[args.database]
    markers = db[C.MIGRATIONS_COLLECTION_NAME]
    if await markers.find_one({"_id": MIGRATION_ID, "status": "complete"}) and not args.force:
        print(f"{MIGRATION_ID}: already complete")
        client.close()
        return

    started = dt.datetime.now(dt.timezone.utc)
    suffix = started.strftime("%Y%m%dT%H%M%SZ")
    report: dict = {"migration": MIGRATION_ID, "dry_run": args.dry_run, "started_at": started, "counts": {}}
    try:
        report["counts"]["backups"] = await backup(db, suffix, args.dry_run)

        missing_timezone = await db[C.ACCOUNTS_COLLECTION_NAME].count_documents({"timezone": {"$exists": False}})
        report["counts"]["accounts_timezone"] = missing_timezone
        if not args.dry_run:
            await db[C.ACCOUNTS_COLLECTION_NAME].update_many(
                {"timezone": {"$exists": False}}, {"$set": {"timezone": "UTC"}}
            )

        users_normalized = 0
        user_collisions = defaultdict(list)
        async for user in db[C.USERS_COLLECTION_NAME].find(
            {}, {"_id": 1, "key": 1, "account_id": 1, "username": 1, "normalized_username": 1}
        ):
            normalized_username = user.get("username", "").strip().casefold()
            user_collisions[(user.get("account_id"), normalized_username)].append(
                user.get("key", str(user["_id"]))
            )
            if user.get("normalized_username") != normalized_username:
                users_normalized += 1
                if not args.dry_run:
                    await db[C.USERS_COLLECTION_NAME].update_one(
                        {"_id": user["_id"]}, {"$set": {"normalized_username": normalized_username}}
                    )
        report["counts"]["users_normalized"] = users_normalized
        user_collisions = {
            f"{account}:{username}": ids
            for (account, username), ids in user_collisions.items()
            if len(ids) > 1
        }
        report["user_collisions"] = user_collisions
        if user_collisions:
            raise RuntimeError(
                f"Case-insensitive username collisions require manual resolution: {user_collisions}"
            )

        account_timezones = {
            doc["account_id"]: doc.get("timezone", "UTC")
            async for doc in db[C.ACCOUNTS_COLLECTION_NAME].find({}, {"_id": 0, "account_id": 1, "timezone": 1})
        }
        abac_changes = 0
        async for policy in db[C.ABAC_POLICIES_COLLECTION_NAME].find({}):
            changes = {}
            if "matcher_version" not in policy:
                changes["matcher_version"] = "legacy_v1"
            if "timezone" not in policy:
                changes["timezone"] = account_timezones.get(policy.get("account_id"), "UTC")
            if changes:
                abac_changes += 1
                if not args.dry_run:
                    await db[C.ABAC_POLICIES_COLLECTION_NAME].update_one({"_id": policy["_id"]}, {"$set": changes})
        report["counts"]["abac_policies"] = abac_changes

        groups = await db[C.SECURITY_GROUPS_COLLECTION_NAME].find({}).to_list(length=None)
        collisions = defaultdict(list)
        normalized = []
        for group in groups:
            display, key = normalize_group_name(group["name"])
            collisions[(group["account_id"], key)].append(group["group_id"])
            normalized.append((group, display, key))
        collisions = {f"{account}:{name}": ids for (account, name), ids in collisions.items() if len(ids) > 1}
        report["collisions"] = collisions
        if collisions:
            raise RuntimeError(f"Group-name collisions require manual resolution: {collisions}")
        report["counts"]["groups_normalized"] = len(normalized)
        if not args.dry_run:
            for group, display, key in normalized:
                await db[C.SECURITY_GROUPS_COLLECTION_NAME].update_one(
                    {"_id": group["_id"]},
                    {"$set": {"name": display, "normalized_name": key, "is_active": group.get("is_active", True)}},
                )

        legacy_assignments = await db[C.RBAC_ASSIGNMENTS_COLLECTION_NAME].count_documents({"subject_type": {"$exists": False}})
        report["counts"]["legacy_rbac_assignments_purged"] = legacy_assignments
        if not args.dry_run:
            await db[C.RBAC_ASSIGNMENTS_COLLECTION_NAME].delete_many({"subject_type": {"$exists": False}})

            await db[C.SECURITY_GROUPS_COLLECTION_NAME].create_index(
                [("account_id", 1), ("normalized_name", 1)], unique=True,
                partialFilterExpression={"normalized_name": {"$type": "string"}},
                name="uq_group_account_normalized_name",
            )
            await db[C.USERS_COLLECTION_NAME].create_index(
                [("account_id", 1), ("normalized_username", 1)], unique=True,
                partialFilterExpression={"normalized_username": {"$type": "string"}},
                name="uq_user_account_normalized_username",
            )
            await db[C.GROUP_MEMBERS_COLLECTION_NAME].create_index(
                [("account_id", 1), ("group_id", 1), ("user_id", 1)], unique=True,
                name="uq_group_membership",
            )
            await db[C.ACL_RESOURCE_POLICIES_COLLECTION_NAME].create_index(
                [("account_id", 1), ("resource_id", 1)], unique=True,
                name="uq_acl_resource_policy",
            )
            await db[C.RBAC_ASSIGNMENTS_COLLECTION_NAME].create_index(
                [("account_id", 1), ("subject_type", 1), ("subject_id", 1), ("role_id", 1)], unique=True,
                name="uq_rbac_assignment",
            )
            await db[C.RBAC_PERMISSION_CATALOG_COLLECTION_NAME].create_index(
                [("account_id", 1), ("permission", 1)], unique=True, name="uq_permission_catalog"
            )
            # Compound sparse indexes still include documents where account_id
            # exists and the binding is null. Partial indexes are required so
            # any number of abstract, unbound nodes remain valid.
            index_info = await db[C.NGAC_NODES_COLLECTION_NAME].index_information()
            for index_name in ("uq_ngac_user_binding", "uq_ngac_resource_binding"):
                if index_name in index_info:
                    await db[C.NGAC_NODES_COLLECTION_NAME].drop_index(index_name)
            await db[C.NGAC_NODES_COLLECTION_NAME].create_index(
                [("account_id", 1), ("user_id", 1)], unique=True,
                partialFilterExpression={"user_id": {"$type": "string"}},
                name="uq_ngac_user_binding",
            )
            await db[C.NGAC_NODES_COLLECTION_NAME].create_index(
                [("account_id", 1), ("resource_id", 1)], unique=True,
                partialFilterExpression={"resource_id": {"$type": "string"}},
                name="uq_ngac_resource_binding",
            )
            await db[C.NGAC_ASSIGNMENTS_COLLECTION_NAME].create_index(
                [("account_id", 1), ("from_id", 1), ("to_id", 1)], unique=True,
                name="uq_ngac_assignment_pair",
            )
            await db[C.NGAC_ASSOCIATIONS_COLLECTION_NAME].create_index(
                [("account_id", 1), ("user_attribute_id", 1), ("object_attribute_id", 1)], unique=True,
                name="uq_ngac_association_pair",
            )
            await db[C.AUTHORIZATION_AUDIT_COLLECTION_NAME].create_index(
                [("account_id", 1), ("timestamp", -1), ("_id", -1)], name="authorization_audit_cursor"
            )
            await db[C.NOTIFICATIONS_COLLECTION_NAME].create_index(
                [("expires_at", 1)], expireAfterSeconds=0, name="notification_ttl"
            )
            await db[C.NOTIFICATIONS_COLLECTION_NAME].create_index(
                [("account_id", 1), ("model", 1), ("timestamp", -1), ("_id", -1)],
                name="notification_cursor",
            )
            await db[C.NOTIFICATION_RECEIPTS_COLLECTION_NAME].create_index(
                [("account_id", 1), ("notification_id", 1), ("recipient_id", 1)],
                unique=True, name="uq_notification_receipt",
            )
            completed = dt.datetime.now(dt.timezone.utc)
            await db[C.AUTHORIZATION_AUDIT_COLLECTION_NAME].insert_one({
                "_id": f"aud-{uuid4().hex}",
                "timestamp": completed,
                "account_id": "*",
                "model": "migration",
                "actor_type": "migration",
                "actor_id": MIGRATION_ID,
                "action": "MIGRATION_COMPLETE",
                "target": MIGRATION_ID,
                "before": None,
                "after": report,
                "correlation_id": MIGRATION_ID,
            })
            await markers.replace_one(
                {"_id": MIGRATION_ID},
                {"_id": MIGRATION_ID, "status": "complete", "started_at": started, "completed_at": completed, "report": report},
                upsert=True,
            )
        print(report)
    except Exception as exc:
        report["error"] = str(exc)
        if not args.dry_run:
            await markers.replace_one(
                {"_id": MIGRATION_ID},
                {"_id": MIGRATION_ID, "status": "failed", "started_at": started, "failed_at": dt.datetime.now(dt.timezone.utc), "report": report},
                upsert=True,
            )
        print(report)
        raise
    finally:
        client.close()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default=os.environ.get("XOLO_MONGODB_URI", "mongodb://localhost:27018/?replicaSet=xolo-rs"))
    parser.add_argument("--database", default=os.environ.get("XOLO_MONGODB_DATABASE_NAME", "xolo"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
