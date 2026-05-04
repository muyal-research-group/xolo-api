"""NGAC graph traversal — pure domain service.

Builds an in-memory representation of the policy graph from DB snapshots
and executes the AND-rule access check algorithm.  Upward closures are
memoised inside each instance (one per request).
"""
from __future__ import annotations
from collections import deque
from typing import Dict, FrozenSet, Set, Tuple

from xoloapi.ngac.domain.aggregates import NGACAssignment, NGACAssociation, NGACNode
from xoloapi.ngac.domain.value_objects import NodeType


class NGACGraph:
    """
    Graph direction: assignments point UPWARD (child → parent).
    One instance per access-check request; closures are cached internally.
    """

    def __init__(
        self,
        nodes:        list[NGACNode],
        assignments:  list[NGACAssignment],
        associations: list[NGACAssociation],
    ) -> None:
        self._nodes: Dict[str, NGACNode] = {n.node_id: n for n in nodes}

        self._parents: Dict[str, Set[str]] = {}
        for a in assignments:
            self._parents.setdefault(a.from_id, set()).add(a.to_id)

        self._assoc: Dict[Tuple[str, str], Set[str]] = {}
        for a in associations:
            self._assoc[(a.user_attribute_id, a.object_attribute_id)] = {
                op.lower() for op in a.operations
            }

        self._cache: Dict[str, FrozenSet[str]] = {}

    def upward_closure(self, node_id: str) -> FrozenSet[str]:
        if node_id in self._cache:
            return self._cache[node_id]

        visited: Set[str] = set()
        queue = deque([node_id])
        while queue:
            cur = queue.popleft()
            if cur in visited:
                continue
            visited.add(cur)
            for parent in self._parents.get(cur, ()):
                queue.append(parent)

        result = frozenset(visited)
        self._cache[node_id] = result
        return result

    def check(self, user_id: str, object_id: str, operation: str) -> Tuple[bool, str]:
        """AND rule: access granted only if permitted through every governing Policy Class."""
        op = operation.lower()

        object_closure = self.upward_closure(object_id)
        user_closure   = self.upward_closure(user_id)

        pcs = {
            nid for nid in object_closure
            if nid in self._nodes
            and self._nodes[nid].node_type == NodeType.POLICY_CLASS
        }

        if not pcs:
            return False, "Object is not governed by any policy class"

        for pc_id in pcs:
            user_uas = {
                nid for nid in user_closure
                if nid in self._nodes
                and self._nodes[nid].node_type == NodeType.USER_ATTRIBUTE
                and pc_id in self.upward_closure(nid)
            }
            object_oas = {
                nid for nid in object_closure
                if nid in self._nodes
                and self._nodes[nid].node_type == NodeType.OBJECT_ATTRIBUTE
                and pc_id in self.upward_closure(nid)
            }

            granted = any(
                op in self._assoc.get((ua, oa), ())
                for ua in user_uas
                for oa in object_oas
            )

            if not granted:
                pc_name = self._nodes[pc_id].name if pc_id in self._nodes else pc_id
                return False, f"Denied by policy class '{pc_name}'"

        return True, "Access granted"
