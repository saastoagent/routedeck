from __future__ import annotations

import routedeck_core
from routedeck_core import context, contracts, navigation, ports, projection, state
from routedeck_core.context.scope import ContextScopeBuilder
from routedeck_core.contracts.events import RouteDeckEvent
from routedeck_core.contracts.projection import PublicProjection
from routedeck_core.contracts.session import RouteDeckSession
from routedeck_core.navigation.deep_links import DeepLinkEngine
from routedeck_core.navigation.engine import NavigationEngine
from routedeck_core.ports.session_store import RouteDeckSessionStore
from routedeck_core.contracts.operations import OperationRequest
from routedeck_core.ports.executor import OperationExecutor
from routedeck_core.supervision import RouteDeckOperationRunner
from routedeck_core.projection.projector import ProjectionProjector
from routedeck_core.state.aggregate import RouteDeckSessionAggregate


def test_canonical_task4_apis_have_small_stable_package_exports() -> None:
    assert contracts.RouteDeckSession is RouteDeckSession
    assert contracts.RouteDeckEvent is RouteDeckEvent
    assert context.ContextScopeBuilder is ContextScopeBuilder
    assert navigation.NavigationEngine is NavigationEngine
    assert navigation.DeepLinkEngine is DeepLinkEngine
    assert projection.ProjectionProjector is ProjectionProjector
    assert ports.RouteDeckSessionStore is RouteDeckSessionStore
    assert state.RouteDeckSessionAggregate is RouteDeckSessionAggregate

    assert routedeck_core.RouteDeckSession is RouteDeckSession
    assert routedeck_core.PublicProjection is PublicProjection
    assert routedeck_core.RouteDeckEvent is RouteDeckEvent
    assert routedeck_core.NavigationEngine is NavigationEngine
    assert routedeck_core.DeepLinkEngine is DeepLinkEngine
    assert routedeck_core.ProjectionProjector is ProjectionProjector
    assert routedeck_core.ContextScopeBuilder is ContextScopeBuilder
    assert routedeck_core.RouteDeckSessionStore is RouteDeckSessionStore


def test_task5_supervision_contracts_have_intentional_package_exports() -> None:
    assert contracts.OperationRequest is OperationRequest
    assert ports.OperationExecutor is OperationExecutor
    assert routedeck_core.RouteDeckOperationRunner is RouteDeckOperationRunner
