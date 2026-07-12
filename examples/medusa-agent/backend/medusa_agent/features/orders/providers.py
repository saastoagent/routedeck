from __future__ import annotations

from dataclasses import dataclass

from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.supervision.guards import ProviderInvocationContext, ProviderResult

from .models import OrderRecoveryContext


@dataclass(frozen=True)
class BoundOrderProvider:
    """Expose only the safe verification fingerprint for one bound order."""

    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        order_ref = context.request.arguments.to_dict().get("order_ref")
        if not isinstance(order_ref, str) or not order_ref:
            raise ValueError("orders provider requires one order_ref")
        public_matches = tuple(
            entity
            for entity in context.session.public_state.entity_handles
            if entity.entity_kind == "order" and entity.handle == order_ref
        )
        private_matches = tuple(
            binding
            for binding in context.session.private_state.entity_bindings
            if binding.entity_kind == "order" and binding.public_handle == order_ref
        )
        if len(public_matches) != 1 or len(private_matches) != 1:
            raise RuntimeError("order recovery binding is unavailable")
        values = {
            value.name: value.value.to_python() for value in public_matches[0].values
        }
        fingerprint = values.get("verification_fingerprint")
        if not isinstance(fingerprint, str):
            raise RuntimeError("order recovery fingerprint is unavailable")
        contact_form_handle = values.get("contact_form_handle")
        if not isinstance(contact_form_handle, str) or not contact_form_handle:
            raise RuntimeError("order recovery private form handle is unavailable")
        recovery = OrderRecoveryContext(
            order_ref=order_ref,
            verification_fingerprint=fingerprint,
            contact_form_handle=contact_form_handle,
        )
        return ProviderResult(values=FrozenJsonObject(recovery.to_provider_values()))


__all__ = ["BoundOrderProvider"]
