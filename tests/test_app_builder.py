from __future__ import annotations

from routedeck_core import (
    RouteDeckApp,
    RouteDeckGraphMessage,
    RouteDeckGraphNavigationController,
    RouteDeckGraphState,
    RouteDeckOperationPolicy,
    RouteDeckOperationRequestPolicy,
    RouteDeckRouteActionIds,
    RouteDeckRuntimeBase,
    RouteDeckSurfaceRegistry,
    route_deck_action,
    route_deck_node,
)


class BuilderState(RouteDeckGraphState):
    pass


class BuilderSurfaceRegistry(RouteDeckSurfaceRegistry):
    pass


class BuilderNavigationController(RouteDeckGraphNavigationController):
    pass


class BuilderOperationPolicy(RouteDeckOperationPolicy):
    pass


class BuilderOperationRequestPolicy(RouteDeckOperationRequestPolicy):
    pass


class BuilderRuntime(RouteDeckRuntimeBase[BuilderState, RouteDeckGraphMessage]):
    async def execute_action(self, operation_id, state, payload):
        raise AssertionError(f"Unexpected builder action: {operation_id}")


BUILDER_MANIFEST = (
    RouteDeckRuntimeBase.manifest_builder("builder-runtime")
    .add_node(
        route_deck_node(
            "home",
            "Home",
            lane="workspace",
            description="Builder home.",
            actions=["route.open_node"],
            allowed_surfaces={"main": ["home"]},
            default_surfaces={"main": "home"},
        )
    )
    .add_action(route_deck_action("route.open_node", "Open node", category="navigation", invocation_kind="hidden"))
    .build()
)


def test_route_deck_app_compiles_runtime_from_product_declarations() -> None:
    route_actions = RouteDeckRouteActionIds(
        open_node="route.open_node",
        switch_surface="route.switch_surface",
        back="route.back",
        forward="route.forward",
        cancel="route.cancel",
    )

    runtime = (
        RouteDeckApp(BuilderState, runtime_base=BuilderRuntime, name="BuilderCompiledRuntime")
        .manifest(BUILDER_MANIFEST)
        .initial_node("home")
        .surfaces(BuilderSurfaceRegistry)
        .navigation(BuilderNavigationController)
        .operation_policy(BuilderOperationPolicy)
        .operation_requests(BuilderOperationRequestPolicy)
        .route_actions(route_actions)
        .operation_review_component("BuilderReviewSurface")
        .compile()
    )

    assert isinstance(runtime, BuilderRuntime)
    assert type(runtime).__name__ == "BuilderCompiledRuntime"
    assert runtime.State is BuilderState
    assert runtime.manifest is BUILDER_MANIFEST
    assert runtime.initial_node == "home"
    assert runtime.route_action_ids == route_actions
    assert runtime.operation_review_component == "BuilderReviewSurface"
    assert isinstance(runtime._surface_registry, BuilderSurfaceRegistry)
    assert isinstance(runtime._navigation, BuilderNavigationController)
    assert isinstance(runtime._operation_policy, BuilderOperationPolicy)
    assert isinstance(runtime._operation_requests, BuilderOperationRequestPolicy)


def test_route_deck_app_requires_manifest_before_compile() -> None:
    try:
        RouteDeckApp(BuilderState, runtime_base=BuilderRuntime).compile()
    except TypeError as exc:
        assert "manifest" in str(exc)
    else:
        raise AssertionError("RouteDeckApp.compile() should require a manifest declaration")


def test_route_deck_app_does_not_expose_projection_as_product_extension() -> None:
    app = RouteDeckApp(BuilderState, runtime_base=BuilderRuntime)

    assert not hasattr(app, "projector")
