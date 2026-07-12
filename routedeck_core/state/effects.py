from __future__ import annotations

from ..contracts.effects import SessionEffects
from ..contracts.projection import ClassifiedValue, DataClassification
from ..contracts.session import (
    PrivateEntityBinding,
    PrivateSessionState,
    PublicSessionState,
    PublicSurfaceState,
    RouteDeckSession,
)


def session_state_with_effects(
    session: RouteDeckSession,
    effects: SessionEffects,
) -> tuple[PrivateSessionState, PublicSessionState]:
    """Apply already-validated replace semantics without revision mutation."""

    removed_form_ids = set(effects.remove_private_form_ids)
    current_form_ids = {draft.form_id for draft in session.private_state.drafts}
    if not removed_form_ids <= current_form_ids:
        raise ValueError("effect can only remove existing private forms")

    replaced_kinds = {effect.entity_kind for effect in effects.replace_entities}
    public_entities = [
        entity
        for entity in session.public_state.entity_handles
        if entity.entity_kind not in replaced_kinds
    ]
    private_entities = [
        binding
        for binding in session.private_state.entity_bindings
        if binding.entity_kind not in replaced_kinds
    ]
    for replacement in effects.replace_entities:
        for binding in replacement.bindings:
            public_entities.append(binding.public)
            private_entities.append(
                PrivateEntityBinding(
                    entity_kind=replacement.entity_kind,
                    public_handle=binding.public.handle,
                    private_id=binding.private_id.get_secret_value(),
                    allowed_operation_ids=binding.allowed_operation_ids,
                )
            )

    surface_updates = {
        update.surface_id: PublicSurfaceState(
            surface_id=update.surface_id,
            values=tuple(
                ClassifiedValue(
                    name=value.name,
                    value=value.value,
                    classification=DataClassification.PUBLIC,
                )
                for value in update.values
            ),
        )
        for update in effects.surface_updates
    }
    surfaces: list[PublicSurfaceState] = []
    seen: set[str] = set()
    for surface in session.public_state.surface_state:
        surface_replacement = surface_updates.get(surface.surface_id)
        surfaces.append(
            surface_replacement if surface_replacement is not None else surface
        )
        seen.add(surface.surface_id)
    surfaces.extend(
        surface
        for surface_id, surface in surface_updates.items()
        if surface_id not in seen
    )

    private_state = PrivateSessionState(
        drafts=tuple(
            draft
            for draft in session.private_state.drafts
            if draft.form_id not in removed_form_ids
        ),
        entity_bindings=tuple(private_entities),
        resume_capabilities=session.private_state.resume_capabilities,
        configurations=session.private_state.configurations,
    )
    public_state = PublicSessionState(
        entity_handles=tuple(public_entities),
        surface_state=tuple(surfaces),
        status_code=session.public_state.status_code,
        status_message=session.public_state.status_message,
        failure=session.public_state.failure,
        disabled_operation_ids=session.public_state.disabled_operation_ids,
    )
    return private_state, public_state


__all__ = ["session_state_with_effects"]
