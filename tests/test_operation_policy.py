from routedeck_core import RouteDeckOperationPolicy, route_deck_action, route_deck_field


def test_operation_policy_maps_navigation_action_to_surface_operation() -> None:
    action = route_deck_action("browse.open", "Browse", category="navigation")
    operation = RouteDeckOperationPolicy(target_nodes_by_action={"browse.open": "browse"}).operation_for_action(action)

    assert operation.id == "browse.open"
    assert operation.invocation_kind == "surface"
    assert operation.execution_mode == "auto"
    assert operation.safety_class == "navigation"
    assert operation.can_dispatch_now is True
    assert operation.target_node == "browse"


def test_operation_policy_blocks_dispatch_when_required_args_are_missing() -> None:
    action = route_deck_action(
        "item.open",
        "Open item",
        category="setup",
        invocation_kind="entity_selector",
        fields=[route_deck_field(key="item_id", label="Item ID", required=True)],
    )
    operation = RouteDeckOperationPolicy().operation_for_action(action)

    assert operation.required_args == ["item_id"]
    assert operation.missing_args == ["item_id"]
    assert operation.can_dispatch_now is False


def test_operation_policy_uses_payload_and_defaults_to_satisfy_required_args() -> None:
    action = route_deck_action(
        "item.open",
        "Open item",
        category="setup",
        fields=[
            route_deck_field(key="item_id", label="Item ID", required=True),
            route_deck_field(key="view", label="View", required=True, default="summary"),
        ],
        payload={"item_id": "public_1"},
    )
    operation = RouteDeckOperationPolicy().operation_for_action(action)

    assert operation.required_args == ["item_id", "view"]
    assert operation.missing_args == []
    assert operation.can_dispatch_now is True
    assert operation.payload == {"item_id": "public_1"}


def test_operation_policy_applies_review_ids_and_category_safety() -> None:
    action = route_deck_action("draft.publish", "Publish", category="deployment")
    operation = RouteDeckOperationPolicy(
        review_action_ids=["draft.publish"],
        safety_class_by_category={"deployment": "write_external"},
    ).operation_for_action(action)

    assert operation.execution_mode == "review"
    assert operation.safety_class == "write_external"
