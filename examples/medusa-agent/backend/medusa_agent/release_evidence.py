from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .medusa.client.http import StoreCallEvidence
from .medusa.client.models import (
    CartCompletionRejected,
    CartCompletionUnknown,
    CompleteCartResult,
    Order,
    OrderPlaced,
    OrderResult,
)


class ReleaseMedusaEvidenceRecorder:
    """Consume typed adapter evidence and write a sanitized release proof."""

    def __init__(
        self,
        bundle_root: Path,
        configured_provider_id: str,
    ) -> None:
        if not bundle_root.is_absolute():
            raise ValueError("ROUTEDECK_RELEASE_BUNDLE must be an absolute path")
        if not configured_provider_id:
            raise ValueError("configured provider ID must be non-empty")
        self._bundle_root = bundle_root
        self._configured_provider_id = configured_provider_id
        self._complete_cart_call_count = 0
        self._independent_reread_count = 0
        self._completed_order: Order | None = None
        self._trace: list[dict[str, object]] = []
        self._all_calls_are_network = True
        self._evidence_lock = asyncio.Lock()

    async def record_complete_cart(
        self,
        call: StoreCallEvidence,
        result: CompleteCartResult,
    ) -> None:
        async with self._evidence_lock:
            self._all_calls_are_network = (
                self._all_calls_are_network and call.transport_kind == "network"
            )
            self._complete_cart_call_count += 1
            if isinstance(result, OrderPlaced):
                self._completed_order = result.order
                result_kind = "order"
            elif isinstance(result, CartCompletionRejected):
                result_kind = "cart_rejected"
            elif isinstance(result, CartCompletionUnknown):
                result_kind = "unknown"
            else:
                raise TypeError("Unexpected complete_cart result while recording proof")
            self._trace.append(
                {
                    "schema_version": 1,
                    "sequence": len(self._trace) + 1,
                    "source": "http_medusa_store_client",
                    "actual_call": True,
                    "operation": call.operation,
                    "method": call.method,
                    "path_template": call.path_template,
                    "transport_kind": call.transport_kind,
                    "result": result_kind,
                }
            )
            self._write_trace()
            self._write_proof(None)

    async def record_get_order(
        self,
        call: StoreCallEvidence,
        order_id: str,
        result: OrderResult,
    ) -> None:
        async with self._evidence_lock:
            self._all_calls_are_network = (
                self._all_calls_are_network and call.transport_kind == "network"
            )
            completed = self._completed_order
            is_independent_reread = (
                completed is not None and completed.id.get_secret_value() == order_id
            )
            if is_independent_reread:
                self._independent_reread_count += 1
            self._trace.append(
                {
                    "schema_version": 1,
                    "sequence": len(self._trace) + 1,
                    "source": "http_medusa_store_client",
                    "actual_call": True,
                    "operation": call.operation,
                    "method": call.method,
                    "path_template": call.path_template,
                    "transport_kind": call.transport_kind,
                    "result": "success" if result.failure is None else "failure",
                    "independent_reread": is_independent_reread,
                }
            )
            self._write_trace()
            reread = result.value if result.failure is None else None
            self._write_proof(reread if is_independent_reread else None)

    def _write_trace(self) -> None:
        destination = self._bundle_root / "medusa" / "store-api-trace.ndjson"
        destination.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(
            destination,
            "".join(
                f"{json.dumps(row, sort_keys=True, separators=(',', ':'))}\n"
                for row in self._trace
            ),
        )

    def _write_proof(self, reread: Order | None) -> None:
        completed = self._completed_order
        comparisons = _order_comparisons(
            completed,
            reread,
            configured_provider_id=self._configured_provider_id,
        )
        independent = reread is not None and self._independent_reread_count == 1
        passing = (
            self._complete_cart_call_count == 1
            and self._independent_reread_count == 1
            and self._all_calls_are_network
            and independent
            and all(comparisons.values())
        )
        document: dict[str, object] = {
            "schema_version": 1,
            "status": "pass" if passing else "fail",
            "source": "measured_typed_medusa_store_calls",
            "transport_kind": (
                "network" if self._all_calls_are_network else "injected"
            ),
            "completion_type": "order" if completed is not None else "unresolved",
            "complete_cart_call_count": self._complete_cart_call_count,
            "get_order_call_count_after_completion": self._independent_reread_count,
            "independent_order_reread": independent,
            **comparisons,
        }
        destination = self._bundle_root / "medusa" / "order-proof.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(destination, f"{json.dumps(document, indent=2)}\n")


def _order_comparisons(
    completed: Order | None,
    reread: Order | None,
    *,
    configured_provider_id: str,
) -> dict[str, bool]:
    if completed is None or reread is None:
        return {
            "order_identity_match": False,
            "items_match": False,
            "quantities_match": False,
            "totals_match": False,
            "email_match": False,
            "shipping_method_match": False,
            "payment_provider_match": False,
        }
    completed_items = sorted(
        (item.title, item.quantity, item.unit_price, item.total)
        for item in completed.items
    )
    reread_items = sorted(
        (item.title, item.quantity, item.unit_price, item.total)
        for item in reread.items
    )
    completed_quantities = sorted(item.quantity for item in completed.items)
    reread_quantities = sorted(item.quantity for item in reread.items)
    completed_shipping = sorted(
        (method.name, method.amount) for method in completed.shipping_methods
    )
    reread_shipping = sorted(
        (method.name, method.amount) for method in reread.shipping_methods
    )
    completed_providers = sorted(
        session.provider_id
        for collection in completed.payment_collections
        for session in collection.payment_sessions
    )
    reread_providers = sorted(
        session.provider_id
        for collection in reread.payment_collections
        for session in collection.payment_sessions
    )
    return {
        "order_identity_match": (
            completed.id.get_secret_value() == reread.id.get_secret_value()
        ),
        "items_match": completed_items == reread_items,
        "quantities_match": completed_quantities == reread_quantities,
        "totals_match": _totals(completed) == _totals(reread),
        "email_match": completed.email == reread.email,
        "shipping_method_match": completed_shipping == reread_shipping,
        "payment_provider_match": (
            completed_providers == reread_providers
            and reread_providers.count(configured_provider_id) == 1
        ),
    }


def _totals(order: Order) -> tuple[int, int, int, int, int, int]:
    return (
        order.total,
        order.subtotal,
        order.item_subtotal,
        order.tax_total,
        order.discount_total,
        order.shipping_total,
    )


def _atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


__all__ = ["ReleaseMedusaEvidenceRecorder"]
