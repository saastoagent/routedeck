from routedeck_core import (
    RouteDeckLocation,
    RouteDeckNavigationPolicy,
    RouteDeckOperation,
    RouteDeckProjection,
    RouteDeckSurface,
)


def test_navigation_policy_finds_active_surface_from_projection() -> None:
    projection = RouteDeckProjection(
        current_context="workspace",
        graph_node="workspace",
        surfaces={
            "frame": RouteDeckSurface(name="frame", surface_id="workspace.frame", component="Frame"),
            "detail": RouteDeckSurface(
                name="detail",
                surface_id="workspace.detail",
                component="Detail",
                role="active",
            ),
        },
        navigation={
            "current": {"node_id": "workspace", "surface_id": "workspace.detail"},
            "back_stack": [],
            "forward_stack": [],
        },
    )

    policy = RouteDeckNavigationPolicy()

    assert policy.active_surface_ids(projection) == {"workspace.detail"}
    assert policy.active_surface_from_projection(projection) == projection.surfaces["detail"]


def test_navigation_policy_derives_legal_targets_from_operations_and_history() -> None:
    projection = RouteDeckProjection(
        current_context="queue",
        graph_node="queue",
        legal_operations=[
            RouteDeckOperation(
                id="detail.open",
                label="Open detail",
                execution_mode="auto",
                target_node="detail",
            )
        ],
        navigation={
            "current": {"node_id": "queue"},
            "back_stack": [],
            "forward_stack": [],
        },
    )

    targets = RouteDeckNavigationPolicy().legal_target_node_ids(
        projection=projection,
        current_node="queue",
        back_stack=[RouteDeckLocation(node_id="home")],
        forward_stack=[{"node_id": "review", "params": {"tab": "notes"}}],
    )

    assert targets == {"queue", "detail", "home", "review"}


def test_navigation_policy_finds_known_location_from_history() -> None:
    policy = RouteDeckNavigationPolicy()

    location = policy.known_navigation_location(
        node_id="detail",
        back_stack=[
            RouteDeckLocation(node_id="queue"),
            RouteDeckLocation(node_id="detail", surface_id="detail.summary", params={"id": "123"}),
        ],
        forward_stack=[],
    )

    assert location == RouteDeckLocation(node_id="detail", surface_id="detail.summary", params={"id": "123"})


def test_navigation_policy_builds_locations_from_payloads() -> None:
    current = RouteDeckLocation(node_id="detail", surface_id="detail.summary", params={"id": "123"})

    location = RouteDeckNavigationPolicy().location_from_payload(
        current=current,
        payload={"surface_id": "detail.audit"},
        preserve_current_params=True,
    )

    assert location == RouteDeckLocation(node_id="detail", surface_id="detail.audit", params={"id": "123"})


def test_navigation_policy_moves_back_and_forward_without_product_state() -> None:
    policy = RouteDeckNavigationPolicy()
    current = RouteDeckLocation(node_id="detail")
    home = RouteDeckLocation(node_id="home")
    review = RouteDeckLocation(node_id="review")

    back = policy.back_transition(current=current, back_stack=[home], forward_stack=[review])

    assert back is not None
    assert back.target == home
    assert back.back_stack == []
    assert back.forward_stack == [current, review]

    forward = policy.forward_transition(
        current=back.target,
        back_stack=back.back_stack,
        forward_stack=back.forward_stack,
    )

    assert forward is not None
    assert forward.target == current
    assert forward.back_stack == [home]
    assert forward.forward_stack == [review]


def test_navigation_policy_cancel_pops_matching_back_target() -> None:
    current = RouteDeckLocation(node_id="review")
    target = RouteDeckLocation(node_id="detail")

    transition = RouteDeckNavigationPolicy().cancel_transition(
        current=current,
        target=target,
        back_stack=[RouteDeckLocation(node_id="queue"), target],
        forward_stack=[],
    )

    assert transition is not None
    assert transition.target == target
    assert transition.back_stack == [RouteDeckLocation(node_id="queue")]
    assert transition.forward_stack == [current]


def test_navigation_policy_open_transition_pushes_previous_location() -> None:
    current = RouteDeckLocation(node_id="queue")
    target = RouteDeckLocation(node_id="detail", surface_id="detail.summary")

    transition = RouteDeckNavigationPolicy().open_transition(
        current=current,
        target=target,
        back_stack=[RouteDeckLocation(node_id="home")],
    )

    assert transition.target == target
    assert transition.back_stack == [RouteDeckLocation(node_id="home"), current]
    assert transition.forward_stack == []
