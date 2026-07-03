from routedeck_core import (
    RouteDeckGraphNavigationController,
    RouteDeckGraphState,
    RouteDeckOperation,
    RouteDeckOperationPolicy,
    RouteDeckOperationRequestPolicy,
    RouteDeckProjection,
    RouteDeckRouteActionIds,
    RouteDeckSurface,
    RouteDeckSurfaceRegistry,
    route_deck_action,
    route_deck_field,
)


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


def test_operation_request_policy_validates_navigation_and_builds_review_state() -> None:
    registry = RouteDeckSurfaceRegistry(active_components_by_node={"home": "Home", "detail": "Detail"})
    navigation = RouteDeckGraphNavigationController(surface_registry=registry)
    policy = RouteDeckOperationRequestPolicy(
        navigation=navigation,
        surface_registry=registry,
        route_actions=RouteDeckRouteActionIds(
            open_node="route.open_node",
            switch_surface="route.switch_surface",
            back="route.back",
            forward="route.forward",
            cancel="route.cancel",
        ),
    )
    state = RouteDeckGraphState(node="home")
    projection = RouteDeckProjection(
        current_context="home",
        graph_node="home",
        legal_operations=[
            RouteDeckOperation(
                id="route.open_node",
                label="Open detail",
                execution_mode="auto",
                target_node="detail",
            )
        ],
        surfaces={
            "detail": RouteDeckSurface(
                name="detail",
                surface_id="detail.active",
                component="Detail",
                role="active",
            )
        },
        navigation={"current": {"node_id": "home"}, "back_stack": [], "forward_stack": []},
    )

    payload = policy.validated_payload(
        state=state,
        operation=projection.legal_operations[0],
        args={"node_id": "detail"},
        projection=projection,
    )

    assert payload == {"node_id": "detail", "params": {}}

    review_state = policy.review_state_for_operation(
        state=state,
        operation=RouteDeckOperation(id="draft.publish", label="Publish", execution_mode="review"),
        args={"draft_id": "draft_1"},
    )

    assert review_state.pending_operation_id == "draft.publish"
    assert review_state.pending_operation_args == {"draft_id": "draft_1"}
    assert review_state.active_surface_id == "operation_review.draft.publish"
