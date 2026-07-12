from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from medusa_agent.composition import compile_medusa_app_spec
from routedeck_core.contracts.projection import (
    ClassifiedValue,
    DataClassification,
    PublicEntityHandle,
)
from routedeck_core.contracts.session import (
    LocationParameter,
    PrivateEntityBinding,
    PublicSurfaceState,
    RouteDeckSession,
)
from routedeck_core.navigation.routes import PublicRouteKeyValidator
from routedeck_core.navigation.engine import NavigationEngine
from routedeck_core.projection.projector import ProjectionProjector
from routedeck_core.state.reducer import PublicSessionStateStored, reduce_session
from routedeck_core.contracts.surfaces import SurfaceSpec
from routedeck_core.validation import RouteDeckValidationError
from routedeck_testing.factories import session_factory


@dataclass(frozen=True)
class CatalogValidator:
    allowed_handles: frozenset[str] = frozenset({"t-shirt", "product-handle-1"})

    def is_valid(self, key: str, value: str) -> bool:
        return key == "product_handle" and value in self.allowed_handles


def _validator() -> PublicRouteKeyValidator:
    return CatalogValidator()


def _product_route(handle: str) -> tuple[LocationParameter, ...]:
    return (LocationParameter(name="product_handle", value=handle),)


def _product_surface_state(
    handle: str,
    *,
    title: str = "Test product",
    extra_values: tuple[ClassifiedValue, ...] = (),
) -> PublicSurfaceState:
    return PublicSurfaceState(
        surface_id="catalog.product_detail",
        values=(
            ClassifiedValue(
                name="product",
                value={
                    "interaction_handle": f"{handle}-interaction",
                    "product_handle": handle,
                    "title": title,
                    "image_urls": [],
                    "options": [],
                    "variants": [
                        {
                            "interaction_handle": "variant-handle-1",
                            "title": "Default",
                            "price": {"amount": 1000, "currency_code": "usd"},
                            "inventory_status": "in_stock",
                            "option_values": [],
                        }
                    ],
                },
                classification=DataClassification.PUBLIC,
            ),
            *extra_values,
        ),
    )


def _grid_surface_state() -> PublicSurfaceState:
    return PublicSurfaceState(
        surface_id="catalog.product_grid",
        values=(
            ClassifiedValue(
                name="products",
                value=[],
                classification=DataClassification.PUBLIC,
            ),
            ClassifiedValue(
                name="count",
                value=0,
                classification=DataClassification.PUBLIC,
            ),
        ),
    )


def _with_surface_state(
    session: RouteDeckSession,
    surface_state: PublicSurfaceState,
) -> RouteDeckSession:
    return session.model_copy(
        update={
            "public_state": session.public_state.model_copy(
                update={"surface_state": (surface_state,)}
            )
        }
    )


def test_sensitive_values_and_private_ids_never_project() -> None:
    app = compile_medusa_app_spec()
    session = session_factory(
        app=app,
        node_id="catalog.product",
        route_params=_product_route("product-handle-1"),
        contact_email="buyer@example.test",
        private_entity_id="prod_private_123",
        public_entity_handle="product-handle-1",
        entity_kind="product",
        allowed_operation_ids=(
            "catalog.open_product",
            "catalog.select_variant",
            "cart.add_item",
        ),
    )
    session = _with_surface_state(
        session,
        _product_surface_state("product-handle-1"),
    )

    projection = ProjectionProjector(
        app,
        public_key_validator=_validator(),
    ).project(session)
    rendered = projection.model_dump_json()

    assert "buyer@example.test" not in rendered
    assert "prod_private_123" not in rendered
    assert "product-handle-1" in rendered


def test_projection_uses_current_node_legal_operations_and_rich_surfaces() -> None:
    app = compile_medusa_app_spec()
    session = session_factory(app=app, node_id="buyer.home")

    projection = ProjectionProjector(app).project(session)

    assert projection.current.node_id == "buyer.home"
    assert projection.surfaces["active"].component == "buyer.welcome"
    assert set(projection.legal_operation_ids) == {"catalog.list", "cart.create"}
    assert projection.session_version == session.session_version
    assert projection.projection_version == session.projection_version


def test_projection_preserves_rich_current_surfaces_navigation_and_status() -> None:
    app = compile_medusa_app_spec()
    browsed = NavigationEngine(app).open(
        session_factory(app=app, node_id="buyer.home"),
        node_id="catalog.browse",
    )
    browsed = browsed.model_copy(
        update={
            "public_state": browsed.public_state.model_copy(
                update={
                    "status_code": "catalog_ready",
                    "status_message": "Products are current.",
                    "surface_state": (_grid_surface_state(),),
                }
            )
        }
    )

    projection = ProjectionProjector(app).project(browsed)

    assert projection.surfaces.active.component == "catalog.product_grid"
    assert tuple(surface.component for surface in projection.surfaces.frame) == (
        "catalog.frame",
    )
    assert tuple(surface.component for surface in projection.surfaces.peer) == (
        "catalog.product_grid",
    )
    assert tuple(surface.component for surface in projection.surfaces.status) == (
        "catalog.status",
    )
    assert tuple(surface.component for surface in projection.surfaces.error) == (
        "catalog.error",
    )
    assert tuple(surface.component for surface in projection.surfaces.diagnostic) == (
        "catalog.diagnostic",
    )
    assert projection.navigation.current.node_id == "catalog.browse"
    assert projection.navigation.route_template == "/products"
    assert projection.navigation.can_back is True
    assert projection.navigation.can_cancel is True
    assert projection.navigation.back_node_id == "buyer.home"
    assert projection.navigation.can_forward is False
    assert projection.status.code == "catalog_ready"
    assert projection.status.message == "Products are current."
    assert set(projection.diagnostics.declared_provider_ids) == {
        "catalog.product",
        "catalog.products",
        "cart.current",
    }


def test_recursive_classification_redaction_is_default_deny() -> None:
    app = compile_medusa_app_spec()
    session = session_factory(
        app=app,
        node_id="catalog.product",
        route_params=_product_route("product-handle-1"),
        contact_email="buyer@example.test",
        private_entity_id="prod_private_123",
        public_entity_handle="product-handle-1",
        entity_kind="product",
        allowed_operation_ids=(
            "catalog.open_product",
            "catalog.select_variant",
            "cart.add_item",
        ),
    )
    surface_state = _product_surface_state(
        "product-handle-1",
        title="visible-label",
        extra_values=(
            ClassifiedValue(
                name="private",
                value={"nested": {"value": "private-nested-value"}},
                classification=DataClassification.PRIVATE,
            ),
            ClassifiedValue(
                name="sensitive",
                value={"nested": {"value": "sensitive-nested-value"}},
                classification=DataClassification.SENSITIVE,
            ),
        ),
    )
    session = _with_surface_state(session, surface_state)

    rendered = (
        ProjectionProjector(
            app,
            public_key_validator=_validator(),
        )
        .project(session)
        .model_dump_json()
    )

    assert "visible-label" in rendered
    assert "private-nested-value" not in rendered
    assert "sensitive-nested-value" not in rendered
    assert "buyer@example.test" not in rendered
    assert "prod_private_123" not in rendered


def test_projection_fails_loudly_for_unknown_nodes_and_surface_state() -> None:
    app = compile_medusa_app_spec()
    projector = ProjectionProjector(app)

    with pytest.raises(RouteDeckValidationError):
        projector.project(session_factory(app=app, node_id="missing.node"))

    session = session_factory(app=app, node_id="buyer.home")
    unknown_surface = PublicSurfaceState(surface_id="missing.surface")
    session = session.model_copy(
        update={
            "public_state": session.public_state.model_copy(
                update={"surface_state": (unknown_surface,)}
            )
        }
    )
    with pytest.raises(RouteDeckValidationError):
        projector.project(session)


def test_projection_rejects_current_location_without_history_identity() -> None:
    app = compile_medusa_app_spec()
    session = session_factory(app=app, node_id="buyer.home")
    session = session.model_copy(
        update={"current": session.current.model_copy(update={"entry_id": None})}
    )

    with pytest.raises(RouteDeckValidationError, match="history entry ID"):
        ProjectionProjector(app).project(session)


def test_surface_props_must_be_public_and_declared_by_schema() -> None:
    app = compile_medusa_app_spec()
    projector = ProjectionProjector(app, public_key_validator=_validator())
    session = session_factory(
        app=app,
        node_id="catalog.product",
        route_params=_product_route("t-shirt"),
    )
    undeclared = PublicSurfaceState(
        surface_id="catalog.product_detail",
        values=(
            ClassifiedValue(
                name="undeclared",
                value={"private": "must-not-project"},
                classification=DataClassification.PUBLIC,
            ),
        ),
    )
    invalid = session.model_copy(
        update={
            "public_state": session.public_state.model_copy(
                update={"surface_state": (undeclared,)}
            )
        }
    )

    with pytest.raises(RouteDeckValidationError) as captured:
        projector.project(invalid)
    assert "must-not-project" not in str(captured.value)


def test_public_surface_object_schemas_must_be_default_deny() -> None:
    with pytest.raises(ValidationError):
        SurfaceSpec(
            id="test.surface",
            component="test.surface",
            public_props_schema={
                "type": "object",
                "properties": {"label": {"type": "string"}},
            },
        )


@pytest.mark.parametrize(
    "schema",
    (
        {"properties": {}, "additionalProperties": False},
        {
            "type": ["object", "null"],
            "properties": {},
            "additionalProperties": False,
        },
        {"type": "string"},
        {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {"type": "string"},
                    "prefixItems": [
                        {
                            "type": "object",
                            "properties": {"secret": {"type": "string"}},
                            "additionalProperties": False,
                        }
                    ],
                }
            },
            "additionalProperties": False,
        },
    ),
)
def test_public_surface_schema_cannot_bypass_object_default_deny(
    schema: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        SurfaceSpec(
            id="test.surface",
            component="test.surface",
            public_props_schema=schema,
        )


def test_public_surface_schema_is_deeply_immutable() -> None:
    source = {
        "type": "object",
        "properties": {"label": {"type": "string"}},
        "additionalProperties": False,
    }
    surface = SurfaceSpec(
        id="test.surface",
        component="test.surface",
        public_props_schema=source,
    )
    source["properties"]["leak"] = {"type": "string"}

    assert "leak" not in surface.public_props_schema_value()["properties"]
    with pytest.raises(TypeError):
        surface.public_props_schema["leak"] = {"type": "string"}  # type: ignore[index]


def test_redacted_only_state_change_does_not_change_projection_version() -> None:
    app = compile_medusa_app_spec()
    projector = ProjectionProjector(app, public_key_validator=_validator())
    initial = session_factory(
        app=app,
        node_id="catalog.product",
        route_params=_product_route("t-shirt"),
    )
    initial = _with_surface_state(initial, _product_surface_state("t-shirt"))
    private_only_surface_state = _product_surface_state(
        "t-shirt",
        extra_values=(
            ClassifiedValue(
                name="private",
                value="private-surface-sentinel",
                classification=DataClassification.PRIVATE,
            ),
        ),
    )

    changed = reduce_session(
        initial,
        PublicSessionStateStored(
            state=initial.public_state.model_copy(
                update={"surface_state": (private_only_surface_state,)}
            )
        ),
    )

    assert changed.session_version == initial.session_version + 1
    assert changed.projection_version == initial.projection_version
    assert projector.project(changed) == projector.project(initial).model_copy(
        update={"session_version": changed.session_version}
    )


def test_reordering_disabled_operations_does_not_change_projection_version() -> None:
    app = compile_medusa_app_spec()
    projector = ProjectionProjector(app, public_key_validator=_validator())
    initial = session_factory(
        app=app,
        node_id="catalog.product",
        route_params=_product_route("t-shirt"),
    )
    initial = _with_surface_state(initial, _product_surface_state("t-shirt"))
    initial = initial.model_copy(
        update={
            "public_state": initial.public_state.model_copy(
                update={
                    "disabled_operation_ids": (
                        "catalog.select_variant",
                        "cart.add_item",
                    )
                }
            )
        }
    )
    changed = reduce_session(
        initial,
        PublicSessionStateStored(
            state=initial.public_state.model_copy(
                update={
                    "disabled_operation_ids": (
                        "cart.add_item",
                        "catalog.select_variant",
                    )
                }
            )
        ),
    )

    assert changed.session_version == initial.session_version + 1
    assert changed.projection_version == initial.projection_version
    assert projector.project(changed) == projector.project(initial).model_copy(
        update={"session_version": changed.session_version}
    )


def test_projection_rejects_a_session_from_an_incompatible_navgraph() -> None:
    app = compile_medusa_app_spec()

    with pytest.raises(RouteDeckValidationError, match="session_upgrade_required"):
        ProjectionProjector(app).project(session_factory(node_id="buyer.home"))


def test_projection_revalidates_public_route_keys_before_exposing_them() -> None:
    app = compile_medusa_app_spec()
    forged = session_factory(
        app=app,
        node_id="catalog.product",
        route_params=_product_route("prod_private_123"),
    )

    with pytest.raises(RouteDeckValidationError):
        ProjectionProjector(
            app,
            public_key_validator=_validator(),
        ).project(forged)


def test_projection_excludes_entity_kinds_not_declared_at_current_node() -> None:
    app = compile_medusa_app_spec()
    session = session_factory(app=app, node_id="buyer.home")
    session = session.model_copy(
        update={
            "private_state": session.private_state.model_copy(
                update={
                    "entity_bindings": (
                        PrivateEntityBinding(
                            entity_kind="order",
                            public_handle="order-handle-1",
                            private_id="order_private_123",
                            allowed_operation_ids=("catalog.list",),
                        ),
                    )
                }
            ),
            "public_state": session.public_state.model_copy(
                update={
                    "entity_handles": (
                        PublicEntityHandle(
                            entity_kind="order",
                            handle="order-handle-1",
                        ),
                    )
                }
            ),
        }
    )

    rendered = ProjectionProjector(app).project(session).model_dump_json()

    assert "order-handle-1" not in rendered
    assert "order_private_123" not in rendered
