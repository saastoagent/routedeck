from __future__ import annotations

from routedeck_core.contracts.navigation import (
    NodeRef,
)
from routedeck_core.contracts.operations import (
    EntityInput,
    EntityProvider,
    Operation,
    OperationSource,
    SafetyClass,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.surfaces import (
    SurfaceAffordance,
)

from ...identifiers import MedusaOperationType, MedusaOutcomeType

from .models import ORDER_RECOVERY_PROVIDER_SCHEMA


ORDER_PROVIDER = EntityProvider(
    id="orders.confirmed_order",
    entity_kind="order",
    description="Independently verified order facts for the completion result.",
    output_schema=FrozenJsonObject(ORDER_RECOVERY_PROVIDER_SCHEMA),
)
RECONCILE_ORDER = Operation(
    id=MedusaOperationType.ORDERS_RECONCILE,
    title="Verify submitted order",
    description="Re-read an already submitted order without completing the cart again.",
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["order_ref"],
            "properties": {"order_ref": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        }
    ),
    entity_inputs=(EntityInput(argument_name="order_ref", entity_kind="order"),),
    safety_class=SafetyClass.READ_EXTERNAL,
    allowed_sources=frozenset({OperationSource.AGENT, OperationSource.SURFACE}),
    outcomes=(MedusaOutcomeType.VERIFIED,),
    provider_refs=(ORDER_PROVIDER.ref,),
)
RECONCILE_ORDER_AFFORDANCE = SurfaceAffordance(
    id="reconcile_order",
    event="retry",
    operation=RECONCILE_ORDER.ref,
)

ORDER_CONFIRMATION_REF = NodeRef(id="orders.confirmation")
