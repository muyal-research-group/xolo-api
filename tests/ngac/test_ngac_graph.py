"""
Pure unit tests for NGACGraph — no database, no I/O.

Each test builds an in-memory graph from raw model objects and runs the
access-check algorithm directly.
"""
import pytest
from xoloapi.ngac.enums import NodeType
from xoloapi.ngac.graph import NGACGraph
from xoloapi.ngac.models import NGACAssignment, NGACAssociation, NGACNode

ACCOUNT_ID = "acc-ngac-graph"


# ── Helpers ────────────────────────────────────────────────────────────────

def node(node_id: str, node_type: NodeType, name: str = "") -> NGACNode:
    return NGACNode(account_id=ACCOUNT_ID, node_id=node_id, node_type=node_type, name=name or node_id)


def assign(from_id: str, to_id: str, idx: int = 0) -> NGACAssignment:
    return NGACAssignment(account_id=ACCOUNT_ID, assignment_id=f"a-{idx}", from_id=from_id, to_id=to_id)


def assoc(ua: str, oa: str, ops: list[str], idx: int = 0) -> NGACAssociation:
    return NGACAssociation(account_id=ACCOUNT_ID, association_id=f"as-{idx}", user_attribute_id=ua,
                           object_attribute_id=oa, operations=ops)


def graph(nodes, assignments, associations) -> NGACGraph:
    return NGACGraph(nodes=nodes, assignments=assignments, associations=associations)


# ── Basic allow / deny ─────────────────────────────────────────────────────

def test_allow_direct_path():
    """User → UA → PC, Object → OA → PC, UA --read--> OA → allow."""
    g = graph(
        nodes=[
            node("u",  NodeType.USER),
            node("ua", NodeType.USER_ATTRIBUTE),
            node("o",  NodeType.OBJECT),
            node("oa", NodeType.OBJECT_ATTRIBUTE),
            node("pc", NodeType.POLICY_CLASS),
        ],
        assignments=[
            assign("u",  "ua", 0),
            assign("ua", "pc", 1),
            assign("o",  "oa", 2),
            assign("oa", "pc", 3),
        ],
        associations=[assoc("ua", "oa", ["read"])],
    )
    allowed, reason = g.check("u", "o", "read")
    assert allowed is True, reason


def test_deny_user_not_in_any_ua():
    g = graph(
        nodes=[
            node("u",  NodeType.USER),
            node("ua", NodeType.USER_ATTRIBUTE),
            node("o",  NodeType.OBJECT),
            node("oa", NodeType.OBJECT_ATTRIBUTE),
            node("pc", NodeType.POLICY_CLASS),
        ],
        assignments=[
            # user is NOT assigned to ua
            assign("ua", "pc", 0),
            assign("o",  "oa", 1),
            assign("oa", "pc", 2),
        ],
        associations=[assoc("ua", "oa", ["read"])],
    )
    allowed, reason = g.check("u", "o", "read")
    assert allowed is False
    assert "Denied" in reason or "policy class" in reason.lower()


def test_deny_wrong_operation():
    """User has 'read' through association, tries 'write'."""
    g = graph(
        nodes=[
            node("u",  NodeType.USER),
            node("ua", NodeType.USER_ATTRIBUTE),
            node("o",  NodeType.OBJECT),
            node("oa", NodeType.OBJECT_ATTRIBUTE),
            node("pc", NodeType.POLICY_CLASS),
        ],
        assignments=[
            assign("u",  "ua", 0), assign("ua", "pc", 1),
            assign("o",  "oa", 2), assign("oa", "pc", 3),
        ],
        associations=[assoc("ua", "oa", ["read"])],
    )
    allowed, _ = g.check("u", "o", "write")
    assert allowed is False


def test_deny_no_policy_class_governing_object():
    """Object has no path to any PC → immediate deny."""
    g = graph(
        nodes=[
            node("u",  NodeType.USER),
            node("ua", NodeType.USER_ATTRIBUTE),
            node("o",  NodeType.OBJECT),
            node("oa", NodeType.OBJECT_ATTRIBUTE),
            # no PC node
        ],
        assignments=[
            assign("u",  "ua", 0),
            assign("o",  "oa", 1),
            # OA is not connected to any PC
        ],
        associations=[assoc("ua", "oa", ["read"])],
    )
    allowed, reason = g.check("u", "o", "read")
    assert allowed is False
    assert "not governed" in reason.lower()


# ── AND rule ───────────────────────────────────────────────────────────────

def test_and_rule_user_satisfies_both_pcs():
    """
    Object → OA1 → PC1 and OA2 → PC2.
    User → UA1 → PC1 and UA2 → PC2.
    Associations: (UA1, OA1, read), (UA2, OA2, read).
    Should allow.
    """
    g = graph(
        nodes=[
            node("u",   NodeType.USER),
            node("ua1", NodeType.USER_ATTRIBUTE),
            node("ua2", NodeType.USER_ATTRIBUTE),
            node("o",   NodeType.OBJECT),
            node("oa1", NodeType.OBJECT_ATTRIBUTE),
            node("oa2", NodeType.OBJECT_ATTRIBUTE),
            node("pc1", NodeType.POLICY_CLASS),
            node("pc2", NodeType.POLICY_CLASS),
        ],
        assignments=[
            assign("u",   "ua1", 0), assign("ua1", "pc1", 1),
            assign("u",   "ua2", 2), assign("ua2", "pc2", 3),
            assign("o",   "oa1", 4), assign("oa1", "pc1", 5),
            assign("o",   "oa2", 6), assign("oa2", "pc2", 7),
        ],
        associations=[
            assoc("ua1", "oa1", ["read"], 0),
            assoc("ua2", "oa2", ["read"], 1),
        ],
    )
    allowed, reason = g.check("u", "o", "read")
    assert allowed is True, reason


def test_and_rule_user_missing_one_pc():
    """
    Same as above but user is NOT connected to PC2.
    Should deny — AND rule fails.
    """
    g = graph(
        nodes=[
            node("u",   NodeType.USER),
            node("ua1", NodeType.USER_ATTRIBUTE),
            node("ua2", NodeType.USER_ATTRIBUTE),
            node("o",   NodeType.OBJECT),
            node("oa1", NodeType.OBJECT_ATTRIBUTE),
            node("oa2", NodeType.OBJECT_ATTRIBUTE),
            node("pc1", NodeType.POLICY_CLASS),
            node("pc2", NodeType.POLICY_CLASS),
        ],
        assignments=[
            assign("u",   "ua1", 0), assign("ua1", "pc1", 1),
            # user is NOT connected to ua2 / pc2
            assign("ua2", "pc2", 2),
            assign("o",   "oa1", 3), assign("oa1", "pc1", 4),
            assign("o",   "oa2", 5), assign("oa2", "pc2", 6),
        ],
        associations=[
            assoc("ua1", "oa1", ["read"], 0),
            assoc("ua2", "oa2", ["read"], 1),
        ],
    )
    allowed, reason = g.check("u", "o", "read")
    assert allowed is False
    assert "pc2" in reason.lower() or "policy class" in reason.lower()


# ── Hierarchy traversal ────────────────────────────────────────────────────

def test_ua_hierarchy_grants_access():
    """
    User → UA1 → UA2 → PC.
    Association is on UA2, not UA1.
    User should still be granted access through hierarchy.
    """
    g = graph(
        nodes=[
            node("u",   NodeType.USER),
            node("ua1", NodeType.USER_ATTRIBUTE, "Junior"),
            node("ua2", NodeType.USER_ATTRIBUTE, "Senior"),
            node("o",   NodeType.OBJECT),
            node("oa",  NodeType.OBJECT_ATTRIBUTE),
            node("pc",  NodeType.POLICY_CLASS),
        ],
        assignments=[
            assign("u",   "ua1", 0),
            assign("ua1", "ua2", 1),  # hierarchy: Junior inherits Senior
            assign("ua2", "pc",  2),
            assign("o",   "oa",  3),
            assign("oa",  "pc",  4),
        ],
        associations=[assoc("ua2", "oa", ["read"])],
    )
    allowed, reason = g.check("u", "o", "read")
    assert allowed is True, reason


def test_oa_hierarchy_grants_access():
    """
    Object → OA1 → OA2 → PC.
    Association is on OA2, not OA1.
    Access should be granted through OA hierarchy.
    """
    g = graph(
        nodes=[
            node("u",   NodeType.USER),
            node("ua",  NodeType.USER_ATTRIBUTE),
            node("o",   NodeType.OBJECT),
            node("oa1", NodeType.OBJECT_ATTRIBUTE, "Specific"),
            node("oa2", NodeType.OBJECT_ATTRIBUTE, "General"),
            node("pc",  NodeType.POLICY_CLASS),
        ],
        assignments=[
            assign("u",   "ua",  0),
            assign("ua",  "pc",  1),
            assign("o",   "oa1", 2),
            assign("oa1", "oa2", 3),  # hierarchy
            assign("oa2", "pc",  4),
        ],
        associations=[assoc("ua", "oa2", ["read"])],
    )
    allowed, reason = g.check("u", "o", "read")
    assert allowed is True, reason


# ── Multiple UAs ───────────────────────────────────────────────────────────

def test_multiple_uas_only_one_matches():
    """User is in two UAs; only one has an association. Should allow."""
    g = graph(
        nodes=[
            node("u",    NodeType.USER),
            node("ua1",  NodeType.USER_ATTRIBUTE, "Role A"),
            node("ua2",  NodeType.USER_ATTRIBUTE, "Role B"),
            node("o",    NodeType.OBJECT),
            node("oa",   NodeType.OBJECT_ATTRIBUTE),
            node("pc",   NodeType.POLICY_CLASS),
        ],
        assignments=[
            assign("u",   "ua1", 0), assign("ua1", "pc", 1),
            assign("u",   "ua2", 2), assign("ua2", "pc", 3),
            assign("o",   "oa",  4), assign("oa",  "pc", 5),
        ],
        associations=[
            # only ua2 has read; ua1 does not
            assoc("ua2", "oa", ["read"]),
        ],
    )
    allowed, reason = g.check("u", "o", "read")
    assert allowed is True, reason


# ── Hospital scenario from idea.md ─────────────────────────────────────────

def test_hospital_scenario_full():
    """
    Dr Smith: Medical Staff → Medical Policy
    Bob:      HR Clerk      → HR Policy
    Chart A:  Patient Records → Medical Policy
    Contract: HR Files        → HR Policy
    """
    g = graph(
        nodes=[
            node("dr-smith",   NodeType.USER,             "Dr. Smith"),
            node("bob",        NodeType.USER,             "Bob"),
            node("chart-a",    NodeType.OBJECT,           "Patient Chart A"),
            node("contract-b", NodeType.OBJECT,           "Contract B"),
            node("med-staff",  NodeType.USER_ATTRIBUTE,   "Medical Staff"),
            node("hr-clerks",  NodeType.USER_ATTRIBUTE,   "HR Clerks"),
            node("pat-recs",   NodeType.OBJECT_ATTRIBUTE, "Patient Records"),
            node("hr-files",   NodeType.OBJECT_ATTRIBUTE, "HR Files"),
            node("med-pc",     NodeType.POLICY_CLASS,     "Medical Policy"),
            node("hr-pc",      NodeType.POLICY_CLASS,     "HR Policy"),
        ],
        assignments=[
            assign("dr-smith",   "med-staff", 0),
            assign("bob",        "hr-clerks", 1),
            assign("chart-a",    "pat-recs",  2),
            assign("contract-b", "hr-files",  3),
            assign("med-staff",  "med-pc",    4),
            assign("pat-recs",   "med-pc",    5),
            assign("hr-clerks",  "hr-pc",     6),
            assign("hr-files",   "hr-pc",     7),
        ],
        associations=[
            assoc("med-staff", "pat-recs", ["read"],         0),
            assoc("hr-clerks", "hr-files", ["read", "write"], 1),
        ],
    )

    assert g.check("dr-smith", "chart-a",    "read")[0] is True
    assert g.check("bob",      "contract-b", "read")[0] is True
    assert g.check("bob",      "chart-a",    "read")[0] is False
    assert g.check("dr-smith", "contract-b", "read")[0] is False


def test_hospital_emergency_and_rule():
    """
    Chart A now belongs to BOTH Medical Policy and Emergency Policy.
    Dr Smith only has Medical clearance → AND rule denies.
    """
    g = graph(
        nodes=[
            node("dr-smith",  NodeType.USER),
            node("chart-a",   NodeType.OBJECT),
            node("med-staff", NodeType.USER_ATTRIBUTE),
            node("emerg-doc", NodeType.USER_ATTRIBUTE),
            node("pat-recs",  NodeType.OBJECT_ATTRIBUTE),
            node("emerg-rec", NodeType.OBJECT_ATTRIBUTE),
            node("med-pc",    NodeType.POLICY_CLASS),
            node("emerg-pc",  NodeType.POLICY_CLASS),
        ],
        assignments=[
            assign("dr-smith",  "med-staff",  0),
            assign("chart-a",   "pat-recs",   1),
            assign("chart-a",   "emerg-rec",  2),
            assign("med-staff", "med-pc",     3),
            assign("pat-recs",  "med-pc",     4),
            assign("emerg-doc", "emerg-pc",   5),
            assign("emerg-rec", "emerg-pc",   6),
        ],
        associations=[
            assoc("med-staff", "pat-recs",  ["read"], 0),
            assoc("emerg-doc", "emerg-rec", ["read"], 1),
        ],
    )

    # Dr Smith satisfies Medical PC but NOT Emergency PC
    allowed, reason = g.check("dr-smith", "chart-a", "read")
    assert allowed is False
    assert "emerg" in reason.lower() or "policy class" in reason.lower()
