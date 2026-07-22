"""Smallest runnable RouteDeck application.

This tutorial example deliberately uses no model, database, HTTP server, or
product fixture. It proves the first RouteDeck contract: a feature-owned node
can be compiled into one validated application and bound to an exact (empty)
set of product implementations.
"""

from routedeck_core import FeatureBindings, bind_app, compile_app
from routedeck_core.app import Application, Feature
from routedeck_core.contracts.application import Node
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    NodeRef,
    Route,
)
from routedeck_core.contracts.surfaces import SurfaceSlots


HOME = Node(
    id="hello.home",
    title="Hello, RouteDeck!",
    kind=NodeKind.SECTION,
    route=Route(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
    surfaces=SurfaceSlots(),
)

HELLO_FEATURE = Feature(namespace="hello", nodes=(HOME,))

HELLO_APP = Application(
    name="hello-world",
    entry_node=NodeRef(id="hello.home"),
    features=(HELLO_FEATURE,),
)


def main() -> None:
    compiled = compile_app(HELLO_APP)
    bound = bind_app(
        compiled,
        FeatureBindings(handlers={}, providers={}, guards={}),
    )
    entry = bound.app.require_node(bound.app.graph.entry_node.id)

    print(f"RouteDeck application: {bound.app.graph.name}")
    print(f"Entry node: {entry.id}")
    print(f"Route: {entry.route.template}")
    print(f"Nodes: {', '.join(bound.app.nodes)}")


if __name__ == "__main__":
    main()
