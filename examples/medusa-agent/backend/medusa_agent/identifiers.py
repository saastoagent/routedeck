"""Canonical Medusa product identifiers used across feature boundaries."""

from enum import StrEnum


class MedusaOutcomeType(StrEnum):
    ADDED = "added"
    CHECKOUT_FAILED = "checkout_failed"
    CONTINUED = "continued"
    CREATED = "created"
    LISTED = "listed"
    OPENED = "opened"
    ORDER_CREATED = "order_created"
    REMOVED = "removed"
    SAVED = "saved"
    SEARCHED = "searched"
    SELECTED = "selected"
    STARTED = "started"
    UPDATED = "updated"
    VERIFIED = "verified"


class MedusaOperationType:
    CATALOG_LIST = "catalog.list"
    CATALOG_SEARCH = "catalog.search"
    CATALOG_OPEN_PRODUCT = "catalog.open_product"
    CATALOG_OPEN_PRODUCT_BY_ROUTE = "catalog.open_product_by_route"
    CATALOG_SELECT_VARIANT = "catalog.select_variant"
    CATALOG_CONTINUE_SHOPPING = "catalog.continue_shopping"

    CART_CREATE = "cart.create"
    CART_ADD_ITEM = "cart.add_item"
    CART_OPEN = "cart.open"
    CART_UPDATE_ITEM = "cart.update_item"
    CART_REMOVE_ITEM = "cart.remove_item"

    CHECKOUT_START = "checkout.start"
    CHECKOUT_SAVE_CONTACT = "checkout.save_contact"
    CHECKOUT_SELECT_SHIPPING = "checkout.select_shipping"
    CHECKOUT_SELECT_PAYMENT = "checkout.select_payment"
    CHECKOUT_PLACE_ORDER = "checkout.place_order"

    ORDERS_RECONCILE = "orders.reconcile"


class MedusaSurfaceType:
    CHECKOUT_ORDER_REVIEW = "checkout.order_review"


class MedusaAgentPolicyType:
    PROTECTED_CHECKOUT_INPUT = "medusa.checkout.protected_input"


class MedusaSuggestedActionType:
    BROWSE_PRODUCTS = "buyer.browse_products"
    VIEW_CART = "buyer.view_cart"


__all__ = [
    "MedusaAgentPolicyType",
    "MedusaOperationType",
    "MedusaOutcomeType",
    "MedusaSuggestedActionType",
    "MedusaSurfaceType",
]
