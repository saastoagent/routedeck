from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from routedeck_core import (
    RouteDeckDispatchInput,
    RouteDeckDispatchResult,
    RouteDeckEvent,
    RouteDeckIntrospection,
    RouteDeckOperation,
    RouteDeckRuntimeState,
    RouteDeckSurface,
    build_projection,
)

from core.config import Settings
from services.commerce_refs import OpaqueRefStore
from services.commerce_state import CommerceStateStore
from services.medusa_setup import probe_medusa_setup
from services.medusa_store import MedusaStoreClient, StoreCart, StoreProduct
from services.routedeck_manifest import SLICE3_MANIFEST


SETUP_UNAVAILABLE_MESSAGE = "Local demo Medusa is not connected for product browsing yet."
MISSING_CART_ARGS_MESSAGE = "Choose a variant and quantity before adding an item to cart."
RESULT_MESSAGES = {
    "catalog.list": "Products are ready to browse.",
    "catalog.open": "Product details are ready.",
    "variant.select": "Variant selected.",
    "cart.create": "Cart ready.",
    "cart.add_item": "Added to cart.",
    "cart.view": "Cart summary ready.",
}


class MedusaRouteDeckRuntime:
    def __init__(
        self,
        settings: Settings | None = None,
        store_client: Any | None = None,
        product_refs: OpaqueRefStore | None = None,
        variant_refs: OpaqueRefStore | None = None,
        cart_refs: OpaqueRefStore | None = None,
        line_refs: OpaqueRefStore | None = None,
        state_store: CommerceStateStore | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.store_client = store_client or MedusaStoreClient(self.settings)
        self.product_refs = product_refs or OpaqueRefStore(prefix="product")
        self.variant_refs = variant_refs or OpaqueRefStore(prefix="variant")
        self.cart_refs = cart_refs or OpaqueRefStore(prefix="cart")
        self.line_refs = line_refs or OpaqueRefStore(prefix="line")
        self.state_store = state_store or CommerceStateStore()
        self.projection_version = 1

    async def projection(self, context: dict | None = None):
        context = context or {}
        setup_state = await self._setup_state(context)
        if not setup_state.get("setup", {}).get("ready"):
            return self._setup_projection(setup_state)

        try:
            products = await self.store_client.list_products(limit=12)
        except Exception:
            unavailable = {
                "setup": {
                    "ready": False,
                    "mode": "local-demo",
                    "message": SETUP_UNAVAILABLE_MESSAGE,
                },
                "connections": setup_state.get("connections", []),
            }
            return self._setup_projection(unavailable)

        session = self._session_id(context)
        state = self.state_store.for_session(session)
        if state.cart_items and state.cart_ref:
            return self._cart_projection(session, setup_state)
        if state.selected_product_ref:
            product_id = self.product_refs.resolve(state.selected_product_ref)
            product = await self.store_client.get_product(product_id)
            return self._detail_projection(product, setup_state, state.selected_variant_ref)
        return self._product_list_projection(products, setup_state)

    async def snapshot(self, context: dict | None = None) -> RouteDeckRuntimeState:
        projection = await self.projection(context)
        return RouteDeckRuntimeState(
            projection=projection,
            status="idle",
            graph_state={"node": projection.graph_node},
        )

    async def dispatch(
        self,
        request: RouteDeckDispatchInput,
        context: dict | None = None,
    ) -> RouteDeckDispatchResult:
        context = {**request.context, **(context or {})}
        operation_id = request.operation_id
        if operation_id not in RESULT_MESSAGES:
            raise ValueError(f"Unknown RouteDeck operation: {operation_id}")

        setup_state = await self._setup_state(context)
        if not setup_state.get("setup", {}).get("ready"):
            raise ValueError(SETUP_UNAVAILABLE_MESSAGE)

        session = self._session_id(context)
        state = self.state_store.for_session(session)

        if operation_id == "catalog.list":
            products = await self.store_client.list_products(limit=12)
            projection = self._product_list_projection(products, setup_state)
            return self._accepted_result(operation_id, projection)

        if operation_id == "catalog.open":
            product_ref = str(request.args.get("product_ref") or "")
            if not product_ref:
                return await self._guard_result(operation_id, context, "Choose a product before opening details.")
            product = await self.store_client.get_product(self.product_refs.resolve(product_ref))
            state.selected_product_ref = product_ref
            state.selected_variant_ref = None
            projection = self._detail_projection(product, setup_state, None)
            return self._accepted_result(operation_id, projection)

        if operation_id == "variant.select":
            variant_ref = str(request.args.get("variant_ref") or "")
            if not variant_ref:
                return await self._guard_result(operation_id, context, "Choose a variant first.")
            self.variant_refs.resolve(variant_ref)
            state.selected_variant_ref = variant_ref
            product = await self._selected_product(state)
            projection = self._detail_projection(product, setup_state, variant_ref) if product else await self.projection(context)
            return self._accepted_result(operation_id, projection)

        if operation_id == "cart.create":
            cart = await self._ensure_cart(state)
            projection = self._cart_projection(session, setup_state, cart=cart)
            return self._accepted_result(operation_id, projection)

        if operation_id == "cart.add_item":
            variant_ref = str(request.args.get("variant_ref") or state.selected_variant_ref or "")
            quantity = int(request.args.get("quantity") or 0)
            if not variant_ref or quantity < 1:
                return await self._guard_result(operation_id, context, MISSING_CART_ARGS_MESSAGE)
            variant_id = self.variant_refs.resolve(variant_ref)
            cart = await self._ensure_cart(state)
            updated = await self.store_client.add_line_item(cart_id=self.cart_refs.resolve(state.cart_ref or ""), variant_id=variant_id, quantity=quantity)
            state.selected_variant_ref = variant_ref
            state.cart_items = self._public_cart_items(updated)
            projection = self._cart_projection(session, setup_state, cart=updated)
            return self._accepted_result(operation_id, projection)

        if operation_id == "cart.view":
            projection = self._cart_projection(session, setup_state)
            return self._accepted_result(operation_id, projection)

        raise ValueError(f"Unknown RouteDeck operation: {operation_id}")

    async def inspect(
        self,
        query: dict | None = None,
        context: dict | None = None,
    ) -> RouteDeckIntrospection:
        projection = await self.projection(context)
        return RouteDeckIntrospection(
            current_node=projection.graph_node,
            legal_operations=[operation.model_dump(mode="json") for operation in projection.legal_operations],
            blocked_operations=[],
            guard_explanations=[] if projection.legal_operations else [SETUP_UNAVAILABLE_MESSAGE],
            surfaces={key: surface.model_dump(mode="json") for key, surface in projection.surfaces.items()},
        )

    async def stream(self, context: dict | None = None) -> AsyncIterator[RouteDeckEvent]:
        state = await self.snapshot(context)
        yield RouteDeckEvent(
            event_type="projection_update",
            projection_version=state.projection.projection_version,
            payload={
                "projection": state.projection.model_dump(mode="json"),
                "status": state.status,
            },
        )

    async def _setup_state(self, context: dict[str, Any]) -> dict[str, Any]:
        return await probe_medusa_setup(self.settings, timeout=context.get("probe_timeout", 2.0))

    def _setup_projection(self, setup_state: dict[str, Any]):
        return build_projection(
            SLICE3_MANIFEST,
            current_node="browse",
            operations=[],
            surfaces=[
                RouteDeckSurface(
                    name="active",
                    surface_id="browse.setup_status",
                    component="MedusaSetupPanel",
                    variant="setup_status",
                    role="active",
                    surface_kind="peer",
                    props=setup_state,
                )
            ],
            projection_version=self.projection_version,
        )

    def _product_list_projection(self, products: list[StoreProduct], setup_state: dict[str, Any]):
        return build_projection(
            SLICE3_MANIFEST,
            current_node="browse",
            operations=[
                _operation("catalog.list", "Browse products", "read_external", "auto"),
                _operation("catalog.open", "View product", "read_external", "review", required_args=["product_ref"]),
                _operation("cart.view", "View cart", "navigation", "auto"),
            ],
            surfaces=[
                RouteDeckSurface(
                    name="active",
                    surface_id="browse.product_list",
                    component="MedusaProductList",
                    variant="product_list",
                    role="active",
                    surface_kind="peer",
                    props={"setup": setup_state["setup"], "products": [self._public_product(product) for product in products]},
                )
            ],
            projection_version=self.projection_version,
        )

    def _detail_projection(self, product: StoreProduct, setup_state: dict[str, Any], selected_variant_ref: str | None):
        product_payload = self._public_product(product)
        return build_projection(
            SLICE3_MANIFEST,
            current_node="detail",
            operations=[
                _operation("catalog.list", "Browse products", "read_external", "auto"),
                _operation("variant.select", "Select variant", "state_selection", "review", required_args=["variant_ref"]),
                _operation("cart.add_item", "Add selected item to cart", "write_external", "review", required_args=["variant_ref", "quantity"]),
                _operation("cart.view", "View cart", "navigation", "auto"),
            ],
            surfaces=[
                RouteDeckSurface(
                    name="active",
                    surface_id="detail.product_detail",
                    component="MedusaProductDetail",
                    variant="product_detail",
                    role="active",
                    surface_kind="peer",
                    props={
                        "setup": setup_state["setup"],
                        "product": product_payload,
                        "selected_variant_ref": selected_variant_ref,
                    },
                )
            ],
            projection_version=self.projection_version,
        )

    def _cart_projection(self, session_id: str, setup_state: dict[str, Any], cart: StoreCart | None = None):
        state = self.state_store.for_session(session_id)
        if cart is not None:
            if state.cart_ref is None:
                state.cart_ref = self.cart_refs.remember(cart.id)
            state.cart_items = self._public_cart_items(cart)
        return build_projection(
            SLICE3_MANIFEST,
            current_node="cart",
            operations=[
                _operation("catalog.list", "Browse products", "read_external", "auto"),
                _operation("cart.add_item", "Add selected item to cart", "write_external", "review", required_args=["variant_ref", "quantity"]),
                _operation("cart.view", "View cart", "navigation", "auto"),
            ],
            surfaces=[
                RouteDeckSurface(
                    name="active",
                    surface_id="cart.cart_summary",
                    component="MedusaCartSummary",
                    variant="cart_summary",
                    role="active",
                    surface_kind="peer",
                    props={
                        "setup": setup_state["setup"],
                        "cart": {
                            "cart_ref": state.cart_ref,
                            "items": state.cart_items,
                        },
                    },
                )
            ],
            projection_version=self.projection_version,
        )

    async def _selected_product(self, state) -> StoreProduct | None:
        if not state.selected_product_ref:
            return None
        return await self.store_client.get_product(self.product_refs.resolve(state.selected_product_ref))

    async def _ensure_cart(self, state) -> StoreCart:
        if state.cart_ref:
            return StoreCart(id=self.cart_refs.resolve(state.cart_ref), items=[])
        region = await self.store_client.first_region()
        cart = await self.store_client.create_cart(region_id=region.id)
        state.cart_ref = self.cart_refs.remember(cart.id)
        state.cart_items = self._public_cart_items(cart)
        return cart

    def _public_product(self, product: StoreProduct) -> dict[str, Any]:
        return {
            "product_ref": self.product_refs.remember(product.id),
            "title": product.title,
            "description": product.description,
            "thumbnail": product.thumbnail,
            "variants": [
                {
                    "variant_ref": self.variant_refs.remember(variant.id),
                    "title": variant.title,
                    "options": variant.options,
                }
                for variant in product.variants
            ],
        }

    def _public_cart_items(self, cart: StoreCart) -> list[dict[str, Any]]:
        return [
            {
                "line_ref": self.line_refs.remember(item.id),
                "title": item.title,
                "quantity": item.quantity,
            }
            for item in cart.items
        ]

    async def _guard_result(self, operation_id: str, context: dict[str, Any], message: str) -> RouteDeckDispatchResult:
        projection = await self.projection(context)
        return RouteDeckDispatchResult(
            operation_id=operation_id,
            accepted=False,
            state=RouteDeckRuntimeState(projection=projection, status="idle"),
            active_surface=projection.surfaces.get("active"),
            messages=[{"content": message}],
            events=[
                RouteDeckEvent(
                    event_type="guard_failure",
                    projection_version=projection.projection_version,
                    payload={"message": message},
                )
            ],
        )

    def _accepted_result(self, operation_id: str, projection) -> RouteDeckDispatchResult:
        self.projection_version += 1
        updated_projection = projection.model_copy(update={"projection_version": self.projection_version})
        return RouteDeckDispatchResult(
            operation_id=operation_id,
            accepted=True,
            state=RouteDeckRuntimeState(projection=updated_projection, status="idle"),
            active_surface=updated_projection.surfaces.get("active"),
            messages=[{"content": RESULT_MESSAGES[operation_id]}],
            events=[
                RouteDeckEvent(
                    event_type="operation_completed",
                    projection_version=updated_projection.projection_version,
                    payload={"operation_id": operation_id},
                )
            ],
        )

    @staticmethod
    def _session_id(context: dict[str, Any]) -> str:
        return str(context.get("session_id") or "default")


def _operation(
    operation_id: str,
    label: str,
    safety_class: str,
    execution_mode: str,
    required_args: list[str] | None = None,
) -> RouteDeckOperation:
    return RouteDeckOperation(
        id=operation_id,
        label=label,
        safety_class=safety_class,
        execution_mode=execution_mode,
        required_args=required_args or [],
    )
