from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from medusa_agent.composition import compile_medusa_app
from routedeck_core.context.scope import ContextScopeBuilder
from routedeck_core.contracts.projection import PublicEntityHandle, PublicValue
from routedeck_core.contracts.operations import EntityProvider
from routedeck_core.contracts.session import LocationParameter, PrivateEntityBinding
from routedeck_core.navigation.routes import PublicRouteKeyValidator
from routedeck_core.validation import RouteDeckValidationError
from routedeck_testing.factories import session_factory


@dataclass(frozen=True)
class CatalogValidator:
    def is_valid(self, key: str, value: str) -> bool:
        return key == "product_handle" and value == "product-handle-1"


def _validator() -> PublicRouteKeyValidator:
    return CatalogValidator()


def _product_route() -> tuple[LocationParameter, ...]:
    return (
        LocationParameter(
            name="product_handle",
            value="product-handle-1",
        ),
    )


def test_context_is_scoped_to_current_node_and_requested_operation() -> None:
    app = compile_medusa_app()
    session = session_factory(
        app=app,
        node_id="catalog.product",
        route_params=_product_route(),
        contact_email="buyer@example.test",
    )
    session = session.model_copy(
        update={
            "private_state": session.private_state.model_copy(
                update={
                    "entity_bindings": (
                        PrivateEntityBinding(
                            entity_kind="variant",
                            public_handle="allowed-variant-handle",
                            private_id="variant_private_allowed",
                            allowed_operation_ids=("catalog.select_variant",),
                        ),
                        PrivateEntityBinding(
                            entity_kind="variant",
                            public_handle="blocked-variant-handle",
                            private_id="variant_private_blocked",
                            allowed_operation_ids=("cart.add_item",),
                        ),
                        PrivateEntityBinding(
                            entity_kind="line_item",
                            public_handle="unrelated-line-handle",
                            private_id="line_private_123",
                            allowed_operation_ids=("cart.update_item",),
                        ),
                    )
                }
            ),
            "public_state": session.public_state.model_copy(
                update={
                    "entity_handles": (
                        PublicEntityHandle(
                            entity_kind="variant",
                            handle="allowed-variant-handle",
                            values=(PublicValue(name="title", value="Allowed"),),
                        ),
                        PublicEntityHandle(
                            entity_kind="variant",
                            handle="blocked-variant-handle",
                            values=(PublicValue(name="title", value="Blocked"),),
                        ),
                        PublicEntityHandle(
                            entity_kind="line_item",
                            handle="unrelated-line-handle",
                        ),
                    )
                }
            ),
        }
    )

    context = ContextScopeBuilder(
        app,
        public_key_validator=_validator(),
    ).build(
        session,
        operation_id="catalog.select_variant",
    )
    rendered = context.model_dump_json()

    assert set(context.provider_ids) == {"catalog.variants"}
    assert "allowed-variant-handle" in rendered
    assert "blocked-variant-handle" not in rendered
    assert "unrelated-line-handle" not in rendered
    assert "buyer@example.test" not in rendered
    assert "variant_private_allowed" not in rendered
    assert "variant_private_blocked" not in rendered
    assert "line_private_123" not in rendered


def test_undeclared_operation_has_no_context_fallback() -> None:
    app = compile_medusa_app()
    with pytest.raises(RouteDeckValidationError):
        ContextScopeBuilder(app).build(
            session_factory(app=app, node_id="buyer.home"),
            operation_id="checkout.place_order",
        )


def test_cross_feature_operation_receives_only_its_allowlisted_node_entity() -> None:
    app = compile_medusa_app()
    session = session_factory(
        app=app,
        node_id="catalog.product",
        route_params=_product_route(),
        private_entity_id="variant_private_123",
        public_entity_handle="variant-handle-1",
        entity_kind="variant",
        allowed_operation_ids=("cart.add_item",),
    )

    context = ContextScopeBuilder(
        app,
        public_key_validator=_validator(),
    ).build(
        session,
        operation_id="cart.add_item",
    )

    assert context.provider_ids == ("cart.current",)
    assert tuple(entity.handle for entity in context.entities) == ("variant-handle-1",)
    assert "variant_private_123" not in context.model_dump_json()


def test_context_entity_join_requires_both_handle_and_kind() -> None:
    app = compile_medusa_app()
    line_items = EntityProvider(
        id="test.line_items",
        entity_kind="line_item",
        description="Test-only second entity kind.",
    )
    nodes = tuple(
        node.model_copy(
            update={
                "entity_providers": (*node.entity_providers, line_items),
            }
        )
        if node.id == "catalog.product"
        else node
        for node in app.graph.nodes
    )
    app = replace(
        app,
        graph=app.graph.model_copy(update={"nodes": nodes}),
        nodes={node.id: node for node in nodes},
    )
    session = session_factory(
        app=app,
        node_id="catalog.product",
        route_params=_product_route(),
    )
    session = session.model_copy(
        update={
            "private_state": session.private_state.model_copy(
                update={
                    "entity_bindings": (
                        PrivateEntityBinding(
                            entity_kind="product",
                            public_handle="shared-handle",
                            private_id="prod_private_123",
                            allowed_operation_ids=("cart.add_item",),
                        ),
                    )
                }
            ),
            "public_state": session.public_state.model_copy(
                update={
                    "entity_handles": (
                        PublicEntityHandle(
                            entity_kind="line_item",
                            handle="shared-handle",
                        ),
                    )
                }
            ),
        }
    )

    context = ContextScopeBuilder(
        app,
        public_key_validator=_validator(),
    ).build(session, operation_id="cart.add_item")

    assert context.entities == ()
