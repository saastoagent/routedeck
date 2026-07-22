# Hello World

This tutorial gives you the smallest useful RouteDeck success: compile one
feature-owned node into a validated application and bind its exact product
implementations. It needs no model key, database, Docker service, or frontend.

You will prove this path:

```text
Feature -> Application -> compile_app -> CompiledApplication -> bind_app
```

## Prerequisites

- Python 3.11 or newer.
- Git, only to obtain the public source checkout.

The registry packages are not yet claimed as published, so install from source.

## 1. Clone and create an environment

Windows PowerShell:

```powershell
git clone https://github.com/saastoagent/routedeck.git
Set-Location .\routedeck
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

macOS or Linux:

```bash
git clone https://github.com/saastoagent/routedeck.git
cd routedeck
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## 2. Run the example

Windows PowerShell:

```powershell
python .\examples\hello-world\hello_world.py
```

macOS or Linux:

```bash
python examples/hello-world/hello_world.py
```

Expected output:

```text
RouteDeck application: hello-world
Entry node: hello.home
Route: /
Nodes: hello.home
```

## 3. Read the application

The complete example is in
[`examples/hello-world/hello_world.py`](https://github.com/saastoagent/routedeck/blob/main/examples/hello-world/hello_world.py).
Its essential declarations are:

```python
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
```

- `Node` is a product-facing location. It is not an LLM graph node.
- `Feature` owns complete nodes and gives them a namespace.
- `Application` selects features and one entry node.
- `compile_app(...)` validates and freezes the complete navgraph.
- `bind_app(...)` checks that every declared handler, provider, and guard has
  exactly one correctly shaped implementation. This app declares none, so its
  exact binding maps are empty.

## 4. Make the compiler catch a mistake

Change the application entry node to an undeclared ID:

```python
entry_node=NodeRef(id="hello.missing")
```

Run the script again. RouteDeck stops at compilation with:

```text
RouteDeckValidationError: Entry node is not declared: hello.missing
```

Restore `hello.home`. The important lesson is that invalid product topology is
a startup error, not a runtime guess.

## What this example does not prove

It does not open a durable runtime, execute an operation, mount HTTP routes,
run an agent, or render React. It proves the authoring and compilation
contract only. RouteDeck intentionally keeps those layers explicit.

## Next

Read [Core Concepts](./Core-Concepts.md), then add product behavior with
[Applications and the Navgraph](./Applications-and-the-Navgraph.md) and
[Operations and Supervision](./Operations-and-Supervision.md).
