from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

from routedeck_core import (
    RouteDeckAvailableEntity,
    RouteDeckBindingExpression,
    RouteDeckDispatchInput,
    RouteDeckDispatchResult,
    RouteDeckEntityOperationBinding,
    RouteDeckEvent,
    RouteDeckIntrospection,
    RouteDeckOperation,
    RouteDeckRuntimeState,
    RouteDeckSurface,
    RouteDeckSurfaceAffordance,
    RouteDeckSurfaceInteractionEvent,
    build_dispatch_state_event,
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
        entity_keys: OpaqueRefStore | None = None,
        cart_refs: OpaqueRefStore | None = None,
        line_refs: OpaqueRefStore | None = None,
        state_store: CommerceStateStore | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.store_client = store_client or MedusaStoreClient(self.settings)
        self.product_refs = product_refs or OpaqueRefStore(prefix="product")
        self.variant_refs = variant_refs or OpaqueRefStore(prefix="variant")
        self.entity_keys = entity_keys or OpaqueRefStore(prefix="entity")
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
        routed_projection = await self._projection_from_deeplink_context(
            context=context,
            products=products,
            setup_state=setup_state,
            session=session,
        )
        if routed_projection is not None:
            return routed_projection
        if state.current_node == "cart" or (state.cart_items and state.cart_ref):
            return self._cart_projection(session, setup_state)
        if state.selected_product_ref:
            product_id = self.product_refs.resolve(state.selected_product_ref)
            product = await self.store_client.get_product(product_id)
            return self._detail_projection(product, setup_state, state.selected_variant_ref)
        if state.current_node == "browse":
            return self._product_list_projection(products, setup_state)
        return self._home_projection(setup_state)

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
        operation_id, args = await self._resolve_dispatch_request(request, context)
        if operation_id not in RESULT_MESSAGES:
            raise ValueError(f"Unknown RouteDeck operation: {operation_id}")

        setup_state = await self._setup_state(context)
        if not setup_state.get("setup", {}).get("ready"):
            raise ValueError(SETUP_UNAVAILABLE_MESSAGE)

        session = self._session_id(context)
        state = self.state_store.for_session(session)

        if operation_id == "catalog.list":
            products = await self.store_client.list_products(limit=12)
            state.current_node = "browse"
            state.selected_product_ref = None
            state.selected_variant_ref = None
            projection = self._product_list_projection(products, setup_state)
            return self._accepted_result(operation_id, projection)

        if operation_id == "catalog.open":
            product_ref = str(args.get("product_ref") or "")
            if not product_ref:
                return await self._guard_result(operation_id, context, "Choose a product before opening details.")
            product = await self.store_client.get_product(self.product_refs.resolve(product_ref))
            state.current_node = "detail"
            state.selected_product_ref = product_ref
            state.selected_variant_ref = None
            projection = self._detail_projection(product, setup_state, None)
            return self._accepted_result(operation_id, projection)

        if operation_id == "variant.select":
            variant_ref = str(args.get("variant_ref") or "")
            if not variant_ref:
                return await self._guard_result(operation_id, context, "Choose a variant first.")
            self.variant_refs.resolve(variant_ref)
            state.current_node = "detail"
            state.selected_variant_ref = variant_ref
            product = await self._selected_product(state)
            projection = self._detail_projection(product, setup_state, variant_ref) if product else await self.projection(context)
            return self._accepted_result(operation_id, projection)

        if operation_id == "cart.create":
            cart = await self._ensure_cart(state)
            state.current_node = "cart"
            projection = self._cart_projection(session, setup_state, cart=cart)
            return self._accepted_result(operation_id, projection)

        if operation_id == "cart.add_item":
            variant_ref = str(args.get("variant_ref") or state.selected_variant_ref or "")
            quantity = int(args.get("quantity") or 0)
            if not variant_ref or quantity < 1:
                return await self._guard_result(operation_id, context, MISSING_CART_ARGS_MESSAGE)
            variant_id = self.variant_refs.resolve(variant_ref)
            cart = await self._ensure_cart(state)
            updated = await self.store_client.add_line_item(cart_id=self.cart_refs.resolve(state.cart_ref or ""), variant_id=variant_id, quantity=quantity)
            state.selected_variant_ref = variant_ref
            state.cart_items = self._public_cart_items(updated)
            state.current_node = "cart"
            projection = self._cart_projection(session, setup_state, cart=updated)
            return self._accepted_result(operation_id, projection)

        if operation_id == "cart.view":
            state.current_node = "cart"
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
            current_node="home",
            operations=[],
            surfaces=[
                RouteDeckSurface(
                    name="active",
                    surface_id="home.setup_status",
                    component="MedusaSetupPanel",
                    variant="setup_status",
                    role="active",
                    surface_kind="peer",
                    props=setup_state,
                )
            ],
            navigation=self._navigation("home", "home.setup_status"),
            navgraph=self._navgraph(current_node="home", current_surface_id="home.setup_status"),
            available_entities=[],
            surface_affordances=[],
            projection_version=self.projection_version,
        )

    def _home_projection(self, setup_state: dict[str, Any]):
        surface_affordances = [
            RouteDeckSurfaceAffordance(
                surface_id="home.agent_start",
                affordance_id="browse_products",
                event="click",
                capability_id="catalog.browse",
                operation_id="catalog.list",
            ),
            RouteDeckSurfaceAffordance(
                surface_id="home.agent_start",
                affordance_id="view_cart",
                event="click",
                capability_id="cart.manage",
                operation_id="cart.view",
            ),
        ]
        return build_projection(
            SLICE3_MANIFEST,
            current_node="home",
            operations=[
                _operation("catalog.list", "Browse products", "read_external", "auto", capability_id="catalog.browse", surface_id="home.agent_start", target_node="browse"),
                _operation("cart.view", "View cart", "navigation", "auto", capability_id="cart.manage", surface_id="home.agent_start", target_node="cart"),
            ],
            surfaces=[
                RouteDeckSurface(
                    name="active",
                    surface_id="home.agent_start",
                    component="MedusaAgentHome",
                    variant="agent_home",
                    role="active",
                    surface_kind="peer",
                    props={
                        "setup": setup_state["setup"],
                        "summary": "Ready to browse demo products or inspect the cart.",
                    },
                )
            ],
            available_entities=[],
            surface_affordances=surface_affordances,
            navigation=self._navigation("home", "home.agent_start"),
            navgraph=self._navgraph(current_node="home", current_surface_id="home.agent_start"),
            projection_version=self.projection_version,
        )

    def _product_list_projection(self, products: list[StoreProduct], setup_state: dict[str, Any]):
        available_entities = self._available_entities_for_products(products, rendered_on=["browse.product_list"])
        surface_affordances = [
            RouteDeckSurfaceAffordance(
                surface_id="browse.product_list",
                affordance_id="view_product",
                event="click",
                capability_id="catalog.browse",
                operation_id="catalog.open",
                entity_keys=[entity.entity_key for entity in available_entities if entity.kind == "product"],
                arg_bindings={
                    "product_ref": RouteDeckBindingExpression(source="entity", path="operation.args.product_ref")
                },
            )
        ]
        return build_projection(
            SLICE3_MANIFEST,
            current_node="browse",
            operations=[
                _operation("catalog.list", "Browse products", "read_external", "auto", capability_id="catalog.browse", surface_id="browse.product_list", target_node="browse"),
                _operation("catalog.open", "View product", "read_external", "review", required_args=["entity_key"], capability_id="catalog.browse", surface_id="browse.product_list"),
                _operation("cart.view", "View cart", "navigation", "auto", capability_id="cart.manage", surface_id="browse.product_list", target_node="cart"),
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
            available_entities=available_entities,
            surface_affordances=surface_affordances,
            navigation=self._navigation("browse", "browse.product_list"),
            navgraph=self._navgraph(current_node="browse", current_surface_id="browse.product_list"),
            projection_version=self.projection_version,
        )

    def _detail_projection(self, product: StoreProduct, setup_state: dict[str, Any], selected_variant_ref: str | None):
        product_payload = self._public_product(product)
        selected_variant_entity_key = self._variant_entity_key_from_ref(selected_variant_ref) if selected_variant_ref else None
        available_entities = self._available_entities_for_products([product], rendered_on=["detail.product_detail"])
        variant_entity_keys = [
            entity.entity_key
            for entity in available_entities
            if entity.kind == "variant"
        ]
        surface_affordances = [
            RouteDeckSurfaceAffordance(
                surface_id="detail.product_detail",
                affordance_id="select_variant",
                event="click",
                capability_id="product.configure",
                operation_id="variant.select",
                entity_keys=variant_entity_keys,
                arg_bindings={
                    "variant_ref": RouteDeckBindingExpression(source="entity", path="operation.args.variant_ref")
                },
            ),
            RouteDeckSurfaceAffordance(
                surface_id="detail.product_detail",
                affordance_id="add_variant_to_cart",
                event="submit",
                capability_id="cart.manage",
                operation_id="cart.add_item",
                entity_keys=variant_entity_keys,
                arg_bindings={
                    "variant_ref": RouteDeckBindingExpression(source="entity", path="operation.args.variant_ref"),
                    "quantity": RouteDeckBindingExpression(source="event", path="quantity"),
                },
            ),
        ]
        return build_projection(
            SLICE3_MANIFEST,
            current_node="detail",
            operations=[
                _operation("catalog.list", "Browse products", "read_external", "auto", capability_id="catalog.browse", surface_id="detail.product_detail", target_node="browse"),
                _operation("variant.select", "Select variant", "state_selection", "review", required_args=["entity_key"], capability_id="product.configure", surface_id="detail.product_detail"),
                _operation("cart.add_item", "Add selected item to cart", "write_external", "review", required_args=["entity_key", "quantity"], capability_id="cart.manage", surface_id="detail.product_detail"),
                _operation("cart.view", "View cart", "navigation", "auto", capability_id="cart.manage", surface_id="detail.product_detail", target_node="cart"),
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
                        "selected_variant_entity_key": selected_variant_entity_key,
                    },
                )
            ],
            available_entities=available_entities,
            surface_affordances=surface_affordances,
            navigation=self._navigation(
                "detail",
                "detail.product_detail",
                product=product,
            ),
            navgraph=self._navgraph(
                current_node="detail",
                current_surface_id="detail.product_detail",
                product=product,
            ),
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
                _operation("catalog.list", "Browse products", "read_external", "auto", capability_id="catalog.browse", surface_id="cart.cart_summary", target_node="browse"),
                _operation("cart.add_item", "Add selected item to cart", "write_external", "review", required_args=["entity_key", "quantity"], capability_id="cart.manage", surface_id="cart.cart_summary"),
                _operation("cart.view", "View cart", "navigation", "auto", capability_id="cart.manage", surface_id="cart.cart_summary", target_node="cart"),
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
                            "items": state.cart_items,
                        },
                    },
                )
            ],
            navigation=self._navigation("cart", "cart.cart_summary"),
            navgraph=self._navgraph(current_node="cart", current_surface_id="cart.cart_summary"),
            projection_version=self.projection_version,
        )

    async def _projection_from_deeplink_context(
        self,
        *,
        context: dict[str, Any],
        products: list[StoreProduct],
        setup_state: dict[str, Any],
        session: str,
    ):
        route_node = str(context.get("rd_node") or "").strip()
        if not route_node:
            return None

        state = self.state_store.for_session(session)
        if route_node == "home":
            state.current_node = "home"
            state.selected_product_ref = None
            state.selected_variant_ref = None
            return self._home_projection(setup_state)

        if route_node == "browse":
            state.current_node = "browse"
            state.selected_product_ref = None
            state.selected_variant_ref = None
            return self._product_list_projection(products, setup_state)

        if route_node == "detail":
            product = self._product_from_deeplink(products, context)
            if product is None:
                state.current_node = "browse"
                return self._product_list_projection(products, setup_state)
            state.current_node = "detail"
            state.selected_product_ref = self.product_refs.remember(product.id)
            state.selected_variant_ref = None
            return self._detail_projection(product, setup_state, None)

        if route_node == "cart":
            state.current_node = "cart"
            return self._cart_projection(session, setup_state)

        state.current_node = "home"
        return self._home_projection(setup_state)

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
            "entity_key": self._entity_key("product", product.id),
            "title": product.title,
            "description": product.description,
            "thumbnail": product.thumbnail,
            "variants": [
                {
                    "entity_key": self._entity_key("variant", variant.id),
                    "title": variant.title,
                    "options": variant.options,
                }
                for variant in product.variants
            ],
        }

    def _product_from_deeplink(self, products: list[StoreProduct], context: dict[str, Any]) -> StoreProduct | None:
        product_handle = str(context.get("rd_product") or "").strip()
        if product_handle:
            return next((product for product in products if product.handle == product_handle), None)

        entity_key = str(context.get("rd_entity") or "").strip()
        if not entity_key:
            return None
        try:
            kind, private_id = _split_entity_value(self.entity_keys.resolve(entity_key.removeprefix("product:")))
        except KeyError:
            return None
        if kind != "product":
            return None
        return next((product for product in products if product.id == private_id), None)

    def _navigation(self, node_id: str, surface_id: str, product: StoreProduct | None = None) -> dict[str, Any]:
        return {
            "current": {
                "node_id": node_id,
                "surface_id": surface_id,
                "deeplink": self._deeplink(node_id, product=product),
            },
            "back_stack": [],
            "forward_stack": [],
        }

    def _navgraph(self, current_node: str, current_surface_id: str, product: StoreProduct | None = None) -> dict[str, Any]:
        node_deeplinks = {
            "home": self._deeplink("home"),
            "browse": self._deeplink("browse"),
            "detail": self._deeplink("detail", product=product) if product else None,
            "cart": self._deeplink("cart"),
        }
        return {
            "current": {
                "node_id": current_node,
                "surface_id": current_surface_id,
                "deeplink": self._deeplink(current_node, product=product),
            },
            "nodes": [
                {
                    "id": node.id,
                    "label": node.label,
                    "surface_id": node.default_surfaces.get("active"),
                    "deeplink": node_deeplinks.get(node.id),
                    "capability_ids": [node.capability_id] if node.capability_id else [],
                    "metadata": {
                        "description": node.description,
                        "allowed_actions": list(node.allowed_actions),
                    },
                }
                for node in SLICE3_MANIFEST.nodes
                if node.show_in_navgraph
            ],
            "edges": [edge.model_dump(mode="json", by_alias=True) for edge in SLICE3_MANIFEST.edges],
            "traversed": [current_node],
            "reachable": [
                edge.to_stage
                for edge in SLICE3_MANIFEST.edges
                if edge.from_stage == current_node
            ],
        }

    def _deeplink(self, node_id: str, product: StoreProduct | None = None) -> dict[str, Any]:
        if node_id == "detail" and product is not None:
            product_path = quote(product.handle, safe="") if product.handle else f"entity/{quote(self._entity_key('product', product.id), safe='')}"
            return {
                "url": f"/detail/{product_path}",
                "resumable": True,
                "requires_auth": False,
                "label": "Product detail",
            }
        if node_id == "cart":
            return {"url": "/cart", "resumable": True, "requires_auth": False, "label": "Cart"}
        if node_id == "home":
            return {"url": "/", "resumable": True, "requires_auth": False, "label": "Home"}
        return {"url": "/browse", "resumable": True, "requires_auth": False, "label": "Browse products"}

    def _public_cart_items(self, cart: StoreCart) -> list[dict[str, Any]]:
        return [
            {
                "entity_key": self._entity_key("cart_item", item.id),
                "title": item.title,
                "quantity": item.quantity,
            }
            for item in cart.items
        ]

    async def _resolve_dispatch_request(self, request: RouteDeckDispatchInput, context: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        operation_id = request.operation_id
        args = dict(request.args)
        if request.surface_event is not None:
            operation_id, event_args = await self._resolve_surface_event(request.surface_event, context)
            args = {**event_args, **args}
        if operation_id and args.get("entity_key"):
            args = {**self._args_from_entity_key(operation_id, str(args["entity_key"])), **args}
        return operation_id, args

    async def _resolve_surface_event(
        self,
        surface_event: RouteDeckSurfaceInteractionEvent,
        context: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        projection = await self.projection(context)
        if not any(
            candidate.surface_id == surface_event.surface_id and candidate.affordance_id == surface_event.affordance_id
            for candidate in projection.surface_affordances
        ):
            surface_node = surface_event.surface_id.split(".", 1)[0]
            if surface_node and surface_node != str(context.get("rd_node") or ""):
                projection = await self.projection({**context, "rd_node": surface_node})
        affordance = next(
            (
                candidate
                for candidate in projection.surface_affordances
                if candidate.surface_id == surface_event.surface_id and candidate.affordance_id == surface_event.affordance_id
            ),
            None,
        )
        if affordance is None or affordance.operation_id is None:
            raise ValueError("Unknown RouteDeck surface affordance.")

        allowed_entity_keys = set(affordance.entity_keys)
        if affordance.entity_key:
            allowed_entity_keys.add(affordance.entity_key)
        if surface_event.entity_key and allowed_entity_keys and surface_event.entity_key not in allowed_entity_keys:
            raise ValueError("RouteDeck surface event entity is not available.")

        entity = None
        if surface_event.entity_key:
            entity = next((candidate for candidate in projection.available_entities if candidate.entity_key == surface_event.entity_key), None)
            if entity is None:
                raise ValueError("RouteDeck surface event entity is not available.")

        args: dict[str, Any] = {}
        for arg_name, binding in affordance.arg_bindings.items():
            value = self._resolve_binding_value(binding, operation_id=affordance.operation_id, entity=entity, surface_event=surface_event)
            if value is not None:
                args[arg_name] = value
        return affordance.operation_id, args

    def _resolve_binding_value(
        self,
        binding: RouteDeckBindingExpression,
        *,
        operation_id: str,
        entity: RouteDeckAvailableEntity | None,
        surface_event: RouteDeckSurfaceInteractionEvent,
    ) -> Any:
        if binding.source == "event":
            return _read_path(surface_event.payload, binding.path)
        if entity is None:
            raise ValueError("RouteDeck surface event requires an entity.")
        operation = next((candidate for candidate in entity.operations if candidate.operation_id == operation_id), None)
        if operation is None:
            raise ValueError("RouteDeck surface event entity does not support this operation.")
        if binding.path.startswith("operation.args."):
            return _read_path(operation.args, binding.path.removeprefix("operation.args."))
        return _read_path(entity.model_dump(mode="json"), binding.path)

    def _args_from_entity_key(self, operation_id: str, entity_key: str) -> dict[str, Any]:
        for entity in self._all_remembered_entities():
            if entity.entity_key != entity_key:
                continue
            operation = next((candidate for candidate in entity.operations if candidate.operation_id == operation_id), None)
            if operation is None:
                raise ValueError("Selected entity does not support that shopping action.")
            return dict(operation.args)
        raise ValueError("Selected entity is not available.")

    def _available_entities_for_products(self, products: list[StoreProduct], rendered_on: list[str]) -> list[RouteDeckAvailableEntity]:
        entities: list[RouteDeckAvailableEntity] = []
        for product in products:
            product_ref = self.product_refs.remember(product.id)
            product_entity = RouteDeckAvailableEntity(
                kind="product",
                entity_key=self._entity_key("product", product.id),
                label=product.title,
                rendered_on=rendered_on,
                operations=[
                    RouteDeckEntityOperationBinding(operation_id="catalog.open", args={"product_ref": product_ref}),
                ],
            )
            entities.append(product_entity)
            for variant in product.variants:
                variant_ref = self.variant_refs.remember(variant.id)
                entities.append(
                    RouteDeckAvailableEntity(
                        kind="variant",
                        entity_key=self._entity_key("variant", variant.id),
                        label=variant.title,
                        parent_label=product.title,
                        rendered_on=rendered_on,
                        operations=[
                            RouteDeckEntityOperationBinding(operation_id="variant.select", args={"variant_ref": variant_ref}),
                            RouteDeckEntityOperationBinding(operation_id="cart.add_item", args={"variant_ref": variant_ref}),
                        ],
                    )
                )
        return entities

    def _all_remembered_entities(self) -> list[RouteDeckAvailableEntity]:
        entities: list[RouteDeckAvailableEntity] = []
        for entity_key, value in self.entity_keys.public_items():
            kind, private_id = _split_entity_value(value)
            if kind == "product":
                product_ref = self.product_refs.remember(private_id)
                operations = [RouteDeckEntityOperationBinding(operation_id="catalog.open", args={"product_ref": product_ref})]
            elif kind == "variant":
                variant_ref = self.variant_refs.remember(private_id)
                operations = [
                    RouteDeckEntityOperationBinding(operation_id="variant.select", args={"variant_ref": variant_ref}),
                    RouteDeckEntityOperationBinding(operation_id="cart.add_item", args={"variant_ref": variant_ref}),
                ]
            else:
                operations = []
            entities.append(RouteDeckAvailableEntity(kind=kind, entity_key=f"{kind}:{entity_key}", label=kind, operations=operations))
        return entities

    def _entity_key(self, kind: str, private_id: str) -> str:
        return f"{kind}:{self.entity_keys.remember(f'{kind}:{private_id}')}"

    def _variant_entity_key_from_ref(self, variant_ref: str | None) -> str | None:
        if not variant_ref:
            return None
        return self._entity_key("variant", self.variant_refs.resolve(variant_ref))

    async def _guard_result(self, operation_id: str, context: dict[str, Any], message: str) -> RouteDeckDispatchResult:
        projection = await self.projection(context)
        state = RouteDeckRuntimeState(projection=projection, status="idle")
        return RouteDeckDispatchResult(
            operation_id=operation_id,
            accepted=False,
            state=state,
            active_surface=projection.surfaces.get("active"),
            messages=[{"content": message}],
            events=[
                build_dispatch_state_event(
                    operation_id=operation_id,
                    event_type="guard_failure",
                    state=state,
                    payload={"message": message},
                )
            ],
        )

    def _accepted_result(self, operation_id: str, projection) -> RouteDeckDispatchResult:
        self.projection_version += 1
        updated_projection = projection.model_copy(update={"projection_version": self.projection_version})
        state = RouteDeckRuntimeState(projection=updated_projection, status="idle")
        return RouteDeckDispatchResult(
            operation_id=operation_id,
            accepted=True,
            state=state,
            active_surface=updated_projection.surfaces.get("active"),
            messages=[{"content": RESULT_MESSAGES[operation_id]}],
            events=[
                build_dispatch_state_event(
                    operation_id=operation_id,
                    state=state,
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
    capability_id: str | None = None,
    surface_id: str | None = None,
    target_node: str | None = None,
) -> RouteDeckOperation:
    missing_args = list(required_args or [])
    return RouteDeckOperation(
        id=operation_id,
        label=label,
        safety_class=safety_class,
        execution_mode=execution_mode,
        required_args=missing_args,
        missing_args=missing_args,
        can_dispatch_now=not missing_args,
        invocation_kind="entity_selector" if missing_args else "direct",
        capability_id=capability_id,
        surface_id=surface_id,
        target_node=target_node,
    )


def _read_path(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for segment in path.split("."):
        if not segment:
            continue
        if not isinstance(value, dict):
            return None
        value = value.get(segment)
    return value


def _split_entity_value(value: str) -> tuple[str, str]:
    kind, separator, private_id = value.partition(":")
    if not separator:
        raise ValueError("Malformed RouteDeck entity key.")
    return kind, private_id
