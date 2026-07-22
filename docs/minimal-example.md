# Minimal RouteDeck Example

This is the smallest useful authoring shape: one feature owns its complete node,
and a tiny composition root selects that feature and entry node.

```python
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
    id="home.index",
    title="Home",
    kind=NodeKind.SECTION,
    route=Route(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
    surfaces=SurfaceSlots(),
)

HOME_FEATURE = Feature(namespace="home", nodes=(HOME,))

APP = Application(
    name="minimal-app",
    entry_node=NodeRef(id="home.index"),
    features=(HOME_FEATURE,),
)

compiled = compile_app(APP)
bound = bind_app(
    compiled,
    FeatureBindings(handlers={}, providers={}, guards={}),
)
```

Real applications add operations, providers, guards, surfaces, route entries,
and node-owned outgoing transitions inside their owning feature. The composition
root still only selects features and the entry node.

The host then supplies session callbacks, persistence configuration, optional
agent graphs, and product implementations to a RouteDeck runtime opener. It
does not construct its own operation runner, navigation runner, or FastAPI
dependency bundle.

Use the standalone Medusa app for a complete real-data example. See
`examples/hello-world/hello_world.py` for the runnable zero-dependency version,
`docs/using-routedeck.md` for the integration sequence and
`docs/route-deck-reference.md` for all contract rules.
