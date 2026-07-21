# `@routedeck/core`

Framework-neutral browser contracts and state primitives for RouteDeck.

This alpha package contains the generated transport contracts, HTTP and SSE
client, authoritative observable store, route/history adapter, conversation
client, and private-form client state. It does not contain React components.

The package has not been published to npm yet. For current source-workspace
setup and examples, see the [RouteDeck repository](https://github.com/saastoagent/routedeck).

```ts
import { createRouteDeckAgentClient, createRouteDeckStore } from "@routedeck/core";
```

RouteDeck is alpha software. Public API changes are recorded in the repository
changelog; security reports follow the repository security policy.
