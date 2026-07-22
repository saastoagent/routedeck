# `@routedeck/react`

React bindings and interaction surfaces for RouteDeck.

This alpha package contains the provider, typed hooks, surface host, navigation
controls, review and private-form UI, status components, conversation
presentation, a bootstrap/recovery boundary, and the optional navgraph
inspector. It depends on
`@routedeck/core`; products keep their own visual components and design system.

The package has not been published to npm yet. For current source-workspace
setup and examples, see the [RouteDeck repository](https://github.com/saastoagent/routedeck).

```tsx
import { RouteDeckBootstrapBoundary } from "@routedeck/react";

<RouteDeckBootstrapBoundary
  store={store}
  loading={<ProductLoading />}
  recovery={(state) => <ProductRecovery state={state} />}
>
  <App />
</RouteDeckBootstrapBoundary>;
```

The boundary starts an idle store, renders children only when bootstrap and
navigation recovery are complete, and passes normalized recovery state to the
product. The product owns wording, styling, and policy such as button placement;
it calls only the actions present in `state.actions`. Use the headless
`useRouteDeckBootstrapRecovery(store)` hook for a custom composition.

RouteDeck is alpha software. Public API changes are recorded in the repository
changelog; security reports follow the repository security policy.
