from __future__ import annotations

from typing import Generic, TypeVar

from .models import RouteDeckGraphMessage, RouteDeckGraphState, RouteDeckManifest
from .navigation import RouteDeckGraphNavigationController
from .operations import RouteDeckOperationPolicy, RouteDeckOperationRequestPolicy, RouteDeckRouteActionIds
from .runtime import RouteDeckRuntimeBase
from .surfaces import RouteDeckSurfaceRegistry


StateT = TypeVar("StateT", bound=RouteDeckGraphState)
MessageT = TypeVar("MessageT", bound=RouteDeckGraphMessage)


class RouteDeckApp(Generic[StateT, MessageT]):
    """Product-facing builder for a RouteDeck runtime.

    Products declare their state schema and extension classes here. RouteDeck
    still owns runtime construction, projection, dispatch, navigation, and
    review mechanics through the compiled RouteDeckRuntimeBase subclass.
    """

    def __init__(
        self,
        state: type[StateT],
        *,
        runtime_base: type[RouteDeckRuntimeBase[StateT, MessageT]] = RouteDeckRuntimeBase,
        name: str | None = None,
    ) -> None:
        self._runtime_base = runtime_base
        self._runtime_name = name or f"{runtime_base.__name__}AppRuntime"
        self._runtime_attrs: dict[str, object] = {
            "__module__": runtime_base.__module__,
            "State": state,
        }

    def manifest(self, manifest: RouteDeckManifest) -> "RouteDeckApp[StateT, MessageT]":
        self._runtime_attrs["manifest"] = manifest
        return self

    def initial_node(self, node_id: str) -> "RouteDeckApp[StateT, MessageT]":
        self._runtime_attrs["initial_node"] = node_id
        return self

    def surfaces(
        self,
        registry: type[RouteDeckSurfaceRegistry],
    ) -> "RouteDeckApp[StateT, MessageT]":
        self._runtime_attrs["SurfaceRegistry"] = registry
        return self

    def navigation(
        self,
        controller: type[RouteDeckGraphNavigationController],
    ) -> "RouteDeckApp[StateT, MessageT]":
        self._runtime_attrs["NavigationController"] = controller
        return self

    def operation_policy(
        self,
        policy: type[RouteDeckOperationPolicy],
    ) -> "RouteDeckApp[StateT, MessageT]":
        self._runtime_attrs["OperationPolicy"] = policy
        return self

    def operation_requests(
        self,
        policy: type[RouteDeckOperationRequestPolicy],
    ) -> "RouteDeckApp[StateT, MessageT]":
        self._runtime_attrs["OperationRequestPolicy"] = policy
        return self

    def route_actions(
        self,
        route_actions: RouteDeckRouteActionIds,
    ) -> "RouteDeckApp[StateT, MessageT]":
        self._runtime_attrs["route_action_ids"] = route_actions
        return self

    def operation_review_component(
        self,
        component: str,
    ) -> "RouteDeckApp[StateT, MessageT]":
        self._runtime_attrs["operation_review_component"] = component
        return self

    def runtime_class(self) -> type[RouteDeckRuntimeBase[StateT, MessageT]]:
        if "manifest" not in self._runtime_attrs:
            raise TypeError("RouteDeckApp.compile() requires a manifest declaration")
        return type(
            self._runtime_name,
            (self._runtime_base,),
            dict(self._runtime_attrs),
        )

    def compile(self) -> RouteDeckRuntimeBase[StateT, MessageT]:
        return self.runtime_class()()
