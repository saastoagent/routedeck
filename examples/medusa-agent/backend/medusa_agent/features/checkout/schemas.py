from __future__ import annotations

from routedeck_core.contracts.operations import DeliveryPhase

from ...medusa.client.models import MedusaClientFailureKind
from .models import (
    BillingChoice,
    CheckoutFactsState,
    PaymentProviderState,
    ShippingProviderState,
)

CONTACT_FORM_SCHEMA = {
    "type": "object",
    "properties": {
        "form_handle": {"type": "string", "minLength": 1},
        "revision": {"type": "integer", "minimum": 0},
        "complete": {"type": "boolean"},
        "fields": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
        "billing_choices": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [choice.value for choice in BillingChoice],
            },
        },
        "default_billing_choice": {
            "type": "string",
            "enum": [choice.value for choice in BillingChoice],
        },
        "country_choices": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 2, "maxLength": 2},
        },
        "default_country_code": {
            "type": "string",
            "minLength": 2,
            "maxLength": 2,
        },
    },
    "required": [
        "form_handle",
        "revision",
        "complete",
        "fields",
        "billing_choices",
        "default_billing_choice",
        "country_choices",
        "default_country_code",
    ],
    "additionalProperties": False,
}

SHIPPING_OPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "shipping_option_ref": {"type": "string", "minLength": 1},
        "label": {"type": "string", "minLength": 1},
        "amount": {"type": "integer", "minimum": 0},
        "currency_code": {"type": "string", "minLength": 3, "maxLength": 3},
    },
    "required": ["shipping_option_ref", "label", "amount", "currency_code"],
    "additionalProperties": False,
}

SHIPPING_OPTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {
            "type": "string",
            "enum": [state.value for state in ShippingProviderState],
        },
        "options": {"type": "array", "items": SHIPPING_OPTION_SCHEMA},
        "message": {"type": "string", "minLength": 1},
    },
    "required": ["state", "options"],
    "additionalProperties": False,
}

CHECKOUT_STARTED_SCHEMA = CONTACT_FORM_SCHEMA

CONTACT_SAVED_SCHEMA = {
    "type": "object",
    "properties": {
        "form_handle": {"type": "string", "minLength": 1},
        "revision": {"type": "integer", "minimum": 1},
        "contact_saved": {"type": "boolean", "const": True},
        "shipping_state": {
            "type": "string",
            "enum": [state.value for state in ShippingProviderState],
        },
        "shipping_option_count": {"type": "integer", "minimum": 0},
    },
    "required": [
        "form_handle",
        "revision",
        "contact_saved",
        "shipping_state",
        "shipping_option_count",
    ],
    "additionalProperties": False,
}

SHIPPING_SELECTED_SCHEMA = {
    "type": "object",
    "properties": SHIPPING_OPTION_SCHEMA["properties"],
    "required": SHIPPING_OPTION_SCHEMA["required"],
    "additionalProperties": False,
}

CHECKOUT_FACTS_PROVIDER_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {
            "type": "string",
            "enum": [state.value for state in CheckoutFactsState],
        },
        "cart": {
            "type": "object",
            "properties": {
                "private_cart_id": {"type": "string", "minLength": 1},
                "private_region_id": {"type": "string", "minLength": 1},
                "public_cart_handle": {"type": "string", "minLength": 1},
                "currency_code": {"type": "string", "minLength": 3, "maxLength": 3},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "private_variant_id": {"type": "string", "minLength": 1},
                            "title": {"type": "string", "minLength": 1},
                            "variant_title": {"type": "string"},
                            "quantity": {"type": "integer", "minimum": 1},
                            "unit_amount": {"type": "integer"},
                            "total": {"type": "integer"},
                        },
                        "required": [
                            "private_variant_id",
                            "title",
                            "quantity",
                            "unit_amount",
                            "total",
                        ],
                        "additionalProperties": False,
                    },
                },
                "item_count": {"type": "integer", "minimum": 0},
                "subtotal": {"type": "integer"},
                "shipping_total": {"type": "integer"},
                "tax_total": {"type": "integer"},
                "discount_total": {"type": "integer"},
                "total": {"type": "integer"},
                "contact_saved": {"type": "boolean"},
                "billing_complete": {"type": "boolean"},
                "contact_fingerprint": {
                    "type": "string",
                    "minLength": 64,
                    "maxLength": 64,
                },
                "contact_form_handle": {"type": "string", "minLength": 1},
                "shipping_selected": {"type": "boolean"},
                "shipping": {
                    "type": "object",
                    "properties": {
                        "private_option_id": {"type": "string", "minLength": 1},
                        "label": {"type": "string", "minLength": 1},
                        "amount": {"type": "integer"},
                    },
                    "required": ["private_option_id", "label", "amount"],
                    "additionalProperties": False,
                },
                "payment_provider_ids": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "uniqueItems": True,
                },
            },
            "required": [
                "private_cart_id",
                "private_region_id",
                "public_cart_handle",
                "currency_code",
                "items",
                "item_count",
                "subtotal",
                "shipping_total",
                "tax_total",
                "discount_total",
                "total",
                "contact_saved",
                "billing_complete",
                "contact_fingerprint",
                "shipping_selected",
                "payment_provider_ids",
            ],
            "additionalProperties": False,
        },
        "delivery_phase": {
            "type": "string",
            "enum": [phase.value for phase in DeliveryPhase],
        },
        "failure_kind": {
            "type": "string",
            "enum": [kind.value for kind in MedusaClientFailureKind],
        },
        "failure_code": {"type": "string", "minLength": 1},
        "public_message": {"type": "string", "minLength": 1},
    },
    "required": ["state"],
    "additionalProperties": False,
}

PAYMENT_PROVIDER_PROJECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "payment_provider_ref": {"type": "string", "minLength": 1},
        "label": {"type": "string", "minLength": 1},
    },
    "required": ["payment_provider_ref", "label"],
    "additionalProperties": False,
}

PAYMENT_METHOD_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {
            "type": "string",
            "enum": [state.value for state in PaymentProviderState],
        },
        "providers": {
            "type": "array",
            "items": PAYMENT_PROVIDER_PROJECTION_SCHEMA,
        },
        "message": {"type": "string", "minLength": 1},
    },
    "required": ["state", "providers"],
    "additionalProperties": False,
}

PAYMENT_PROVIDER_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {
            "type": "string",
            "enum": [state.value for state in PaymentProviderState],
        },
        "projection": PAYMENT_METHOD_SCHEMA,
        "bindings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "public_handle": {"type": "string", "minLength": 1},
                    "private_id": {"type": "string", "minLength": 1},
                },
                "required": ["public_handle", "private_id"],
                "additionalProperties": False,
            },
        },
        "delivery_phase": {
            "type": "string",
            "enum": [phase.value for phase in DeliveryPhase],
        },
        "failure_kind": {
            "type": "string",
            "enum": [kind.value for kind in MedusaClientFailureKind],
        },
        "failure_code": {"type": "string", "minLength": 1},
    },
    "required": ["state", "projection", "bindings"],
    "additionalProperties": False,
}

PAYMENT_SELECTED_SCHEMA = {
    "type": "object",
    "properties": PAYMENT_PROVIDER_PROJECTION_SCHEMA["properties"],
    "required": PAYMENT_PROVIDER_PROJECTION_SCHEMA["required"],
    "additionalProperties": False,
}

REVIEW_LINE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "variant_title": {"type": "string"},
        "quantity": {"type": "integer", "minimum": 1},
        "unit_amount": {"type": "integer"},
        "total": {"type": "integer"},
    },
    "required": ["title", "quantity", "unit_amount", "total"],
    "additionalProperties": False,
}

ORDER_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "form_handle": {"type": "string", "minLength": 1},
        "items": {"type": "array", "minItems": 1, "items": REVIEW_LINE_SCHEMA},
        "currency_code": {"type": "string", "minLength": 3, "maxLength": 3},
        "subtotal": {"type": "integer"},
        "shipping_total": {"type": "integer"},
        "tax_total": {"type": "integer"},
        "discount_total": {"type": "integer"},
        "total": {"type": "integer"},
        "shipping_label": {"type": "string", "minLength": 1},
        "payment_label": {"type": "string", "minLength": 1},
        "contact_complete": {"type": "boolean"},
        "billing_complete": {"type": "boolean"},
    },
    "required": [
        "form_handle",
        "items",
        "currency_code",
        "subtotal",
        "shipping_total",
        "tax_total",
        "discount_total",
        "total",
        "shipping_label",
        "payment_label",
        "contact_complete",
        "billing_complete",
    ],
    "additionalProperties": False,
}

_REVIEW_PENDING_VALUES_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {"type": "string", "const": "pending"},
        "review_id": {"type": "string", "minLength": 1},
        "expires_at": {"type": "string", "minLength": 1},
    },
    "required": ["state", "review_id", "expires_at"],
    "additionalProperties": False,
}

REVIEW_PENDING_SCHEMA = {
    **_REVIEW_PENDING_VALUES_SCHEMA,
    "required": [],
}

_RECOVERY_VALUES_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {"type": "string", "const": "external_outcome_unknown"},
        "message": {"type": "string", "minLength": 1},
        "correlation_id": {"type": "string", "minLength": 1},
        "order_ref": {"type": "string", "minLength": 1},
    },
    "required": ["state", "message", "correlation_id"],
    "additionalProperties": False,
}

RECOVERY_SCHEMA = {
    **_RECOVERY_VALUES_SCHEMA,
    "required": [],
}

SHIPPING_PROVIDER_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {
            "type": "string",
            "enum": [state.value for state in ShippingProviderState],
        },
        "projection": SHIPPING_OPTIONS_SCHEMA,
        "bindings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "public_handle": {"type": "string", "minLength": 1},
                    "private_id": {"type": "string", "minLength": 1},
                },
                "required": ["public_handle", "private_id"],
                "additionalProperties": False,
            },
        },
        "delivery_phase": {
            "type": "string",
            "enum": [phase.value for phase in DeliveryPhase],
        },
        "failure_kind": {
            "type": "string",
            "enum": [kind.value for kind in MedusaClientFailureKind],
        },
        "failure_code": {"type": "string", "minLength": 1},
    },
    "required": ["state", "projection", "bindings"],
    "additionalProperties": False,
}

__all__ = [
    "CHECKOUT_FACTS_PROVIDER_SCHEMA",
    "CHECKOUT_STARTED_SCHEMA",
    "CONTACT_FORM_SCHEMA",
    "CONTACT_SAVED_SCHEMA",
    "ORDER_REVIEW_SCHEMA",
    "PAYMENT_METHOD_SCHEMA",
    "PAYMENT_PROVIDER_SCHEMA",
    "PAYMENT_SELECTED_SCHEMA",
    "RECOVERY_SCHEMA",
    "REVIEW_LINE_SCHEMA",
    "REVIEW_PENDING_SCHEMA",
    "SHIPPING_OPTIONS_SCHEMA",
    "SHIPPING_PROVIDER_SCHEMA",
    "SHIPPING_SELECTED_SCHEMA",
]
