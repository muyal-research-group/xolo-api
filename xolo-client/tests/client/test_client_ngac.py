from xolo.client.client import XoloClient
from xolo.client import models as M


def test_ngac_methods_return_expected_dtos(
    protected_client: XoloClient,
    make_signed_up_user,
    rand_name,
    unwrap_ok,
    unwrap_ok_list,
):
    user = make_signed_up_user()

    policy_class = unwrap_ok(
        protected_client.create_ngac_node(
            name=rand_name("policy-class"),
            node_type="policy_class",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.CreatedNGACNodeResponseDTO,
    )
    user_attribute = unwrap_ok(
        protected_client.create_ngac_node(
            name=rand_name("user-attribute"),
            node_type="user_attribute",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.CreatedNGACNodeResponseDTO,
    )
    object_attribute = unwrap_ok(
        protected_client.create_ngac_node(
            name=rand_name("object-attribute"),
            node_type="object_attribute",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.CreatedNGACNodeResponseDTO,
    )
    user_node = unwrap_ok(
        protected_client.create_ngac_node(
            name=rand_name("user-node"),
            node_type="user",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.CreatedNGACNodeResponseDTO,
    )
    object_node = unwrap_ok(
        protected_client.create_ngac_node(
            name=rand_name("object-node"),
            node_type="object",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.CreatedNGACNodeResponseDTO,
    )

    all_nodes = unwrap_ok_list(
        protected_client.list_ngac_nodes(
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.NGACNodeDTO,
    )
    assert any(item.node_id == user_attribute.node_id for item in all_nodes)

    user_attribute_nodes = unwrap_ok_list(
        protected_client.list_ngac_nodes(
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
            node_type="user_attribute",
        ),
        M.NGACNodeDTO,
    )
    assert any(item.node_id == user_attribute.node_id for item in user_attribute_nodes)

    fetched_node = unwrap_ok(
        protected_client.get_ngac_node(
            node_id=user_attribute.node_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.NGACNodeDTO,
    )
    assert fetched_node.node_id == user_attribute.node_id
    assert fetched_node.node_type == "user_attribute"

    assignment_pairs = [
        (user_attribute.node_id, policy_class.node_id),
        (object_attribute.node_id, policy_class.node_id),
        (user_node.node_id, user_attribute.node_id),
        (object_node.node_id, object_attribute.node_id),
    ]
    for from_id, to_id in assignment_pairs:
        assignment = unwrap_ok(
            protected_client.ngac_assign(
                from_id=from_id,
                to_id=to_id,
                token=user.auth.access_token,
                temporal_secret=user.auth.temporal_secret,
            ),
            M.NGACAssignmentMutationResponseDTO,
        )
        assert assignment.from_id == from_id
        assert assignment.to_id == to_id

    assignments = unwrap_ok_list(
        protected_client.list_ngac_assignments(
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.NGACAssignmentDTO,
    )
    assert any(
        item.from_id == user_node.node_id and item.to_id == user_attribute.node_id
        for item in assignments
    )

    association = unwrap_ok(
        protected_client.ngac_associate(
            user_attribute_id=user_attribute.node_id,
            object_attribute_id=object_attribute.node_id,
            operations=["read"],
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.NGACAssociationMutationResponseDTO,
    )
    assert association.user_attribute_id == user_attribute.node_id
    assert association.object_attribute_id == object_attribute.node_id
    assert association.operations == ["read"]

    associations = unwrap_ok_list(
        protected_client.list_ngac_associations(
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.NGACAssociationDTO,
    )
    listed_association = next(
        item
        for item in associations
        if item.user_attribute_id == user_attribute.node_id
        and item.object_attribute_id == object_attribute.node_id
    )
    assert listed_association.operations == ["read"]

    decision = unwrap_ok(
        protected_client.ngac_check(
            user_id=user_node.node_id,
            object_id=object_node.node_id,
            operation="read",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.NGACDecisionDTO,
    )
    assert decision.allowed is True
    assert decision.user_id == user_node.node_id
    assert decision.object_id == object_node.node_id
    assert decision.operation == "read"

    for from_id, to_id in assignment_pairs:
        removed_assignment = unwrap_ok(
            protected_client.ngac_remove_assignment(
                from_id=from_id,
                to_id=to_id,
                token=user.auth.access_token,
                temporal_secret=user.auth.temporal_secret,
            ),
            M.NGACAssignmentMutationResponseDTO,
        )
        assert removed_assignment.from_id == from_id
        assert removed_assignment.to_id == to_id

    removed_association = unwrap_ok(
        protected_client.ngac_remove_association(
            association_id=listed_association.association_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.NGACAssociationDeletionResponseDTO,
    )
    assert removed_association.ok is True
    assert removed_association.association_id == listed_association.association_id

    for created_node in [user_node, object_node, user_attribute, object_attribute, policy_class]:
        deleted_node = unwrap_ok(
            protected_client.delete_ngac_node(
                node_id=created_node.node_id,
                token=user.auth.access_token,
                temporal_secret=user.auth.temporal_secret,
            ),
            M.DeletedNGACNodeResponseDTO,
        )
        assert deleted_node.ok is True
        assert deleted_node.node_id == created_node.node_id
