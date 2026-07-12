from __future__ import annotations

import asyncio

from routedeck_core import (
    RouteDeckActionResult,
    RouteDeckDispatchInput,
    RouteDeckFieldSpec,
    RouteDeckGraphMessage,
    RouteDeckGraphNavigationLocation,
    RouteDeckGraphNavigationController,
    RouteDeckGraphState,
    RouteDeckOperationPolicy,
    RouteDeckOperationRequestPolicy,
    RouteDeckProjection,
    RouteDeckRouteActionIds,
    RouteDeckRuntimeBase,
    RouteDeckSurface,
    RouteDeckSurfaceRegistry,
    build_projection,
    route_deck_action,
    route_deck_edge,
    route_deck_node,
)


class ToyState(RouteDeckGraphState):
    selected_account_id: str | None = None


class ToySurface(RouteDeckSurface):
    pass


class DeclaredSurfaceRegistry(RouteDeckSurfaceRegistry):
    pass


class DeclaredNavigationController(RouteDeckGraphNavigationController):
    pass


class DeclaredOperationPolicy(RouteDeckOperationPolicy):
    pass


class DeclaredOperationRequestPolicy(RouteDeckOperationRequestPolicy):
    pass


class ToyRuntime(RouteDeckRuntimeBase[ToyState, RouteDeckGraphMessage]):
    State = ToyState
    Surface = ToySurface
    initial_node = "home"
    operation_review_component = "ToyReviewSurface"

    manifest = (
        RouteDeckRuntimeBase.manifest_builder("toy-runtime")
        .add_node(
            route_deck_node(
                "home",
                "Home",
                lane="workspace",
                description="Toy home.",
                actions=["route.open_node", "toy.configure"],
                allowed_surfaces={"main": ["home"]},
                default_surfaces={"main": "home"},
            )
        )
        .add_node(
            route_deck_node(
                "detail",
                "Detail",
                lane="workspace",
                description="Toy detail.",
                parent="home",
                actions=[
                    "route.switch_surface",
                    "route.back",
                    "toy.configure",
                    "toy.finish",
                ],
                allowed_surfaces={"active": ["summary", "logs"]},
                default_surfaces={"active": "summary"},
            )
        )
        .add_action(
            route_deck_action(
                "route.open_node",
                "Open node",
                category="navigation",
                invocation_kind="hidden",
            )
        )
        .add_action(
            route_deck_action(
                "route.switch_surface",
                "Switch surface",
                category="navigation",
                invocation_kind="hidden",
            )
        )
        .add_action(
            route_deck_action(
                "route.back", "Back", category="navigation", invocation_kind="hidden"
            )
        )
        .add_action(
            route_deck_action(
                "route.forward",
                "Forward",
                category="navigation",
                invocation_kind="hidden",
            )
        )
        .add_action(
            route_deck_action(
                "route.cancel",
                "Cancel",
                category="navigation",
                invocation_kind="hidden",
            )
        )
        .add_action(
            route_deck_action(
                "toy.configure",
                "Configure",
                kind="form",
                fields=[
                    RouteDeckFieldSpec(key="account_id", label="Account", required=True)
                ],
            )
        )
        .add_action(route_deck_action("toy.finish", "Finish", invocation_kind="direct"))
        .add_edge(route_deck_edge("home", "detail", action_id="route.open_node"))
        .build()
    )

    def active_surfaces(self, state: ToyState) -> list[ToySurface]:
        if state.node == "detail":
            return [
                ToySurface(
                    name="active",
                    surface_id="detail.summary",
                    component="ToyDetailSurface",
                    variant="summary",
                    role="active",
                    label="Summary",
                ),
                ToySurface(
                    name="logs",
                    surface_id="detail.logs",
                    component="ToyDetailSurface",
                    variant="logs",
                    role="active",
                    label="Logs",
                ),
            ]
        return [
            ToySurface(
                name="main",
                surface_id="home.active",
                component="ToyHomeSurface",
                variant="home",
                role="active",
                label="Home",
            )
        ]

    async def execute_action(
        self,
        operation_id: str,
        state: ToyState,
        payload: dict[str, object],
    ) -> RouteDeckActionResult[ToyState, RouteDeckGraphMessage]:
        if operation_id == "toy.configure":
            state.selected_account_id = str(payload["account_id"])
            return RouteDeckActionResult(
                state=state,
                messages=[RouteDeckGraphMessage(content="Configured account.")],
            )
        if operation_id == "toy.finish":
            state.node = "home"
            return RouteDeckActionResult(state=state)
        raise AssertionError(f"Unexpected business action: {operation_id}")


class ProjectingRuntime(ToyRuntime):
    async def project_state(
        self,
        state: ToyState,
        *,
        context: dict[str, object],
        projection_version: int = 1,
    ) -> RouteDeckProjection:
        return build_projection(
            self.manifest,
            current_node=state.node,
            surfaces=[
                RouteDeckSurface(
                    name="active",
                    surface_id="custom.active",
                    component="CustomSurface",
                    role="active",
                )
            ],
            navigation={
                "current": {
                    "node_id": state.node,
                    "surface_id": "custom.active",
                    "params": {},
                }
            },
            projection_version=projection_version,
        )


class LocatedRuntime(ToyRuntime):
    def base_location_for_state(
        self, state: ToyState, context: dict[str, object]
    ) -> str | None:
        return "/workspace/detail?tab=summary#top"


class DeclaredComponentRuntime(ToyRuntime):
    SurfaceRegistry = DeclaredSurfaceRegistry
    NavigationController = DeclaredNavigationController
    OperationPolicy = DeclaredOperationPolicy
    OperationRequestPolicy = DeclaredOperationRequestPolicy


def test_routedeck_runtime_base_instantiates_declared_extension_components() -> None:
    runtime = DeclaredComponentRuntime()

    assert isinstance(runtime._surface_registry, DeclaredSurfaceRegistry)
    assert isinstance(runtime._navigation, DeclaredNavigationController)
    assert isinstance(runtime._operation_policy, DeclaredOperationPolicy)
    assert isinstance(runtime._operation_requests, DeclaredOperationRequestPolicy)
    assert runtime._operation_requests._route_actions == RouteDeckRouteActionIds(
        open_node="route.open_node",
        switch_surface="route.switch_surface",
        back="route.back",
        forward="route.forward",
        cancel="route.cancel",
    )


def test_routedeck_runtime_base_exposes_route_action_helpers() -> None:
    runtime = ToyRuntime()
    state = ToyState(
        node="detail",
        navigation_back_stack=[
            RouteDeckGraphNavigationLocation(node_id="home", surface_id="home.active")
        ],
        navigation_forward_stack=[
            RouteDeckGraphNavigationLocation(node_id="detail", surface_id="detail.logs")
        ],
    )

    route_actions = [action.id for action in runtime.route_actions_for_state(state)]

    assert route_actions == [
        "route.open_node",
        "route.switch_surface",
        "route.back",
        "route.forward",
        "route.cancel",
    ]
    assert runtime.is_route_action_id("route.back") is True
    assert runtime.is_route_action_id("toy.configure") is False


def test_routedeck_runtime_base_owns_surface_intent_and_presentation_state_helpers() -> (
    None
):
    runtime = ToyRuntime()
    state = ToyState(node="home")
    context: dict[str, object] = {}

    assert runtime.stored_presentation_state_for_state(state, context) == {}
    assert (
        runtime.surface_navigation_id_from_intent({"surface_id": "home.active"})
        == "home.active"
    )
    assert runtime.surface_variant_intent_from_intent(
        {"surface_id": "home.active", "main": "home", 7: "bad", "active": 4}
    ) == {"main": "home"}
    assert (
        runtime.store_surface_intent_for_state(state, {"main": "home"}, context) is True
    )
    assert runtime.stored_presentation_state_for_state(state, context) == {
        "surface_variants": {"main": "home"}
    }


def test_routedeck_runtime_base_adds_active_surface_to_product_base_location() -> None:
    runtime = LocatedRuntime()
    state = ToyState(node="detail", active_surface_id="detail.logs")

    assert (
        runtime.location_for_state(state, {})
        == "/workspace/detail?tab=summary&surface_id=detail.logs#top"
    )


def test_routedeck_runtime_base_owns_projection_dispatch_and_surfaces() -> None:
    async def run() -> None:
        runtime = ToyRuntime()

        state = await runtime.snapshot()
        assert state.projection.graph_node == "home"
        assert state.projection.navigation.current.surface_id == "home.active"
        assert state.projection.surfaces["main"].component == "ToyHomeSurface"
        assert [operation.id for operation in state.projection.legal_operations] == [
            "route.open_node",
            "toy.configure",
        ]

        opened = await runtime.dispatch(
            RouteDeckDispatchInput(
                operation_id="route.open_node",
                args={"node_id": "detail"},
                graph_state=state.graph_state,
            )
        )
        assert opened.state.projection.graph_node == "detail"
        assert opened.state.projection.navigation.current.surface_id == "detail.summary"
        assert opened.active_surface.label == "Summary"
        assert opened.state.graph_state["navigation_back_stack"][0]["node_id"] == "home"

        switched = await runtime.dispatch(
            RouteDeckDispatchInput(
                operation_id="route.switch_surface",
                args={"surface_id": "detail.logs"},
                graph_state=opened.state.graph_state,
            )
        )
        assert switched.state.projection.navigation.current.surface_id == "detail.logs"
        assert switched.active_surface.label == "Logs"

        review = await runtime.dispatch(
            RouteDeckDispatchInput(
                operation_id="toy.configure",
                args={"account_id": "acct_1"},
                graph_state=switched.state.graph_state,
            )
        )
        assert (
            review.state.projection.navigation.current.surface_id
            == "operation_review.toy.configure"
        )
        assert review.active_surface.component == "ToyReviewSurface"
        assert review.state.graph_state["pending_operation_id"] == "toy.configure"
        assert review.state.graph_state["pending_operation_args"] == {
            "account_id": "acct_1"
        }

        committed = await runtime.dispatch(
            RouteDeckDispatchInput(
                operation_id="toy.configure",
                args={"account_id": "acct_1"},
                graph_state=review.state.graph_state,
            )
        )
        assert committed.state.graph_state["selected_account_id"] == "acct_1"
        assert committed.state.graph_state["pending_operation_id"] is None
        assert committed.messages == [
            {"role": "assistant", "content": "Configured account."}
        ]

        finished = await runtime.dispatch(
            RouteDeckDispatchInput(
                operation_id="toy.finish",
                graph_state=opened.state.graph_state,
            )
        )
        assert finished.state.projection.graph_node == "home"
        assert (
            finished.state.graph_state["navigation_back_stack"][-1]["node_id"]
            == "detail"
        )

    asyncio.run(run())


def test_routedeck_runtime_state_syncs_resolved_surface_from_custom_projection() -> (
    None
):
    async def run() -> None:
        runtime = ProjectingRuntime()

        state = await runtime.snapshot({"state": ToyState(node="detail")})

        assert state.projection.navigation.current.surface_id == "custom.active"
        assert state.graph_state["active_surface_id"] == "custom.active"

    asyncio.run(run())
