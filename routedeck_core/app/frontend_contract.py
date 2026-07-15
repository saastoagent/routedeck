from __future__ import annotations

from collections.abc import Mapping

from ..contracts.application import NodeSpec
from ..contracts.navigation import TransitionSpec
from ..contracts.surfaces import SurfaceSlotsSpec
from .compiled import (
    FrontendContract,
    FrontendNodeContract,
    FrontendSurfaceContract,
    FrontendSurfaceSlots,
    FrontendTransitionContract,
)
from .feature import ApplicationSpec


def _build_frontend_contract(
    *,
    source_spec: ApplicationSpec,
    nodes: tuple[NodeSpec, ...],
    transitions: tuple[TransitionSpec, ...],
    surfaces: Mapping[str, FrontendSurfaceContract],
) -> FrontendContract:
    return FrontendContract(
        name=source_spec.name,
        entry_node_id=source_spec.entry_node.id,
        nodes={
            node.id: FrontendNodeContract(
                id=node.id,
                title=node.title,
                route_template=node.route.template,
                deep_link_policy=node.route.deep_link_policy,
                surfaces=_frontend_surface_slots(node.surfaces),
                operation_ids=tuple(operation.id for operation in node.operations),
            )
            for node in nodes
        },
        transitions=tuple(
            FrontendTransitionContract(
                source=transition.source.id,
                operation_id=transition.operation.id,
                outcome=transition.outcome,
                target=transition.target.id,
            )
            for transition in transitions
        ),
        surfaces=surfaces,
    )


def _frontend_surface_slots(slots: SurfaceSlotsSpec) -> FrontendSurfaceSlots:
    return FrontendSurfaceSlots(
        active=slots.active.id if slots.active is not None else None,
        frame=tuple(surface.id for surface in slots.frame),
        peer=tuple(surface.id for surface in slots.peer),
        detail=tuple(surface.id for surface in slots.detail),
        form=tuple(surface.id for surface in slots.form),
        review=tuple(surface.id for surface in slots.review),
        status=tuple(surface.id for surface in slots.status),
        error=tuple(surface.id for surface in slots.error),
        diagnostic=tuple(surface.id for surface in slots.diagnostic),
    )
