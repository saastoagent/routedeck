"""Explicitly test-only contract factories and binding doubles."""

from __future__ import annotations

from typing import cast

from routedeck_core.app import Application, FeatureBindings, Feature
from routedeck_core.app.bindings import ContextProviderHandler, GuardHandler
from routedeck_core.app.compiled import CompiledApplication
from routedeck_core.contracts.application import Capability, Node
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    NodeRef,
    RecoveryPolicy,
    Route,
    Transition,
)
from routedeck_core.contracts.operations import (
    ContextProvider,
    EntityInput,
    GuardRef,
    Guard,
    OperationRef,
    OperationOutcome,
    Operation,
    ProviderRef,
    ReviewPolicy,
    SafetyClass,
)
from routedeck_core.contracts.surfaces import (
    SurfaceRef,
    SurfaceSlots,
    Surface,
)
from routedeck_core.contracts.projection import PublicEntityHandle
from routedeck_core.contracts.session import (
    Location,
    LocationParameter,
    PrivateDraft,
    PrivateEntityBinding,
    PrivateSessionState,
    PublicSessionState,
    ResumeCapabilityBinding,
    RouteDeckSession,
)
from routedeck_core.ports.executor import OperationHandler
from routedeck_core.state.session import SESSION_SCHEMA_VERSION, navgraph_version


_PROVIDER = ContextProvider(
    id="test.context",
    description="Test-only context provider declaration.",
)
_GUARD = Guard(
    id="test.allowed",
    description="Test-only guard declaration.",
)
_ADVANCE = Operation(
    id="test.advance",
    title="Advance",
    description="Advance the test-only graph.",
    safety_class=SafetyClass.NAVIGATION,
    outcomes=("advanced",),
    provider_refs=(_PROVIDER.ref,),
    guard_refs=(_GUARD.ref,),
)
_FINISH = Operation(
    id="test.finish",
    title="Finish",
    description="Finish the test-only graph.",
    safety_class=SafetyClass.WRITE_EXTERNAL,
    review_policy=ReviewPolicy.REQUIRED,
    unknown_recovery_directive="reconcile_finish",
    outcomes=("completed",),
    provider_refs=(_PROVIDER.ref,),
    guard_refs=(_GUARD.ref,),
)
_FRAME = Surface(id="test.frame", component="test.frame")
_START_SURFACE = Surface(id="test.start", component="test.start")
_MIDDLE_SURFACE = Surface(id="test.middle", component="test.middle")
_END_SURFACE = Surface(id="test.end", component="test.end")
_ERROR_SURFACE = Surface(id="test.error", component="test.error")
_CAPABILITY = Capability(
    id="test.flow",
    title="Test-only flow",
    operations=(_ADVANCE.ref, _FINISH.ref),
    surfaces=(
        _START_SURFACE.ref,
        _MIDDLE_SURFACE.ref,
        _END_SURFACE.ref,
        _ERROR_SURFACE.ref,
    ),
)
_START = Node(
    id="test.start",
    title="Start",
    kind=NodeKind.WORKFLOW,
    route=Route(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
    context_providers=(_PROVIDER,),
    guards=(_GUARD,),
    operations=(_ADVANCE,),
    capabilities=(_CAPABILITY,),
    surfaces=SurfaceSlots(
        active=_START_SURFACE,
        frame=(_FRAME,),
        error=(_ERROR_SURFACE,),
    ),
    recovery=RecoveryPolicy(
        directives=("retry",), failure_surface=_ERROR_SURFACE.ref
    ),
)
_MIDDLE = Node(
    id="test.middle",
    title="Middle",
    kind=NodeKind.WORKFLOW,
    route=Route(template="/middle", deep_link_policy=DeepLinkPolicy.SHAREABLE),
    context_providers=(_PROVIDER,),
    guards=(_GUARD,),
    operations=(_FINISH,),
    capabilities=(_CAPABILITY,),
    surfaces=SurfaceSlots(
        active=_MIDDLE_SURFACE,
        frame=(_FRAME,),
        error=(_ERROR_SURFACE,),
    ),
    recovery=RecoveryPolicy(
        directives=("reconcile_finish",), failure_surface=_ERROR_SURFACE.ref
    ),
)
_END = Node(
    id="test.end",
    title="End",
    kind=NodeKind.TRANSIENT,
    route=Route(template="/end", deep_link_policy=DeepLinkPolicy.SHAREABLE),
    capabilities=(_CAPABILITY,),
    surfaces=SurfaceSlots(
        active=_END_SURFACE,
        frame=(_FRAME,),
        error=(_ERROR_SURFACE,),
    ),
)
_TO_MIDDLE = Transition(
    operation=_ADVANCE.ref,
    outcome="advanced",
    target=_MIDDLE.ref,
)
_TO_END = Transition(
    operation=_FINISH.ref,
    outcome="completed",
    target=_END.ref,
)
_START = _START.model_copy(update={"outgoing": (_TO_MIDDLE,)})
_MIDDLE = _MIDDLE.model_copy(update={"outgoing": (_TO_END,)})


def invalid_app(mutation: str) -> Application:
    """Return one deliberately invalid application for compiler tests."""

    nodes: tuple[Node, ...] = (_START, _MIDDLE, _END)

    if mutation == "duplicate_node":
        nodes = (*nodes, _START)
    elif mutation == "duplicate_route":
        nodes = (
            _START,
            _MIDDLE.model_copy(update={"route": _START.route}),
            _END,
        )
    elif mutation == "ambiguous_route":
        nodes = (
            _START,
            _MIDDLE.model_copy(
                update={
                    "route": Route(
                        template="/products/new",
                        deep_link_policy=DeepLinkPolicy.SHAREABLE,
                    )
                }
            ),
            _END.model_copy(
                update={
                    "route": Route(
                        template="/products/{product_handle}",
                        deep_link_policy=DeepLinkPolicy.SHAREABLE,
                    )
                }
            ),
        )
    elif mutation == "ambiguous_transition":
        nodes = (
            _START.model_copy(
                update={
                    "outgoing": (
                        _TO_MIDDLE,
                        _TO_MIDDLE.model_copy(update={"target": _END.ref}),
                    )
                }
            ),
            _MIDDLE,
            _END,
        )
    elif mutation == "dangling_transition":
        nodes = (
            _START.model_copy(
                update={
                    "outgoing": (
                        _TO_MIDDLE.model_copy(
                            update={"target": NodeRef(id="test.missing")}
                        ),
                    )
                }
            ),
            _MIDDLE,
            _END,
        )
    elif mutation == "missing_surface":
        capability = _CAPABILITY.model_copy(
            update={"surfaces": (*_CAPABILITY.surfaces, SurfaceRef(id="test.missing"))}
        )
        nodes = tuple(
            node.model_copy(update={"capabilities": (capability,)}) for node in nodes
        )
    elif mutation == "missing_outcome":
        nodes = (
            _START.model_copy(
                update={
                    "outgoing": (
                        _TO_MIDDLE.model_copy(update={"outcome": "undeclared"}),
                    )
                }
            ),
            _MIDDLE,
            _END,
        )
    elif mutation == "missing_provider":
        operation = _ADVANCE.model_copy(
            update={
                "provider_refs": (
                    *_ADVANCE.provider_refs,
                    ProviderRef(id="test.missing"),
                )
            }
        )
        nodes = (_START.model_copy(update={"operations": (operation,)}), _MIDDLE, _END)
    elif mutation == "missing_entity_provider":
        operation = _ADVANCE.model_copy(
            update={
                "input_schema": _ADVANCE.input_schema.__class__(
                    {
                        "type": "object",
                        "properties": {"item_ref": {"type": "string"}},
                        "required": ["item_ref"],
                        "additionalProperties": False,
                    }
                ),
                "entity_inputs": (
                    EntityInput(
                        argument_name="item_ref",
                        entity_kind="item",
                    ),
                ),
            }
        )
        nodes = (_START.model_copy(update={"operations": (operation,)}), _MIDDLE, _END)
    elif mutation == "provider_not_on_node":
        middle_only_provider = ContextProvider(
            id="test.middle_only",
            description="Provider deliberately scoped to another test node.",
        )
        operation = _ADVANCE.model_copy(
            update={
                "provider_refs": (
                    *_ADVANCE.provider_refs,
                    middle_only_provider.ref,
                )
            }
        )
        nodes = (
            _START.model_copy(update={"operations": (operation,)}),
            _MIDDLE.model_copy(
                update={
                    "context_providers": (
                        *_MIDDLE.context_providers,
                        middle_only_provider,
                    )
                }
            ),
            _END,
        )
    elif mutation == "guard_not_on_node":
        middle_only_guard = Guard(
            id="test.middle_only",
            description="GuardHandler deliberately scoped to another test node.",
        )
        operation = _ADVANCE.model_copy(
            update={
                "guard_refs": (
                    *_ADVANCE.guard_refs,
                    middle_only_guard.ref,
                )
            }
        )
        nodes = (
            _START.model_copy(update={"operations": (operation,)}),
            _MIDDLE.model_copy(update={"guards": (*_MIDDLE.guards, middle_only_guard)}),
            _END,
        )
    elif mutation == "unreachable_node":
        nodes = (_START, _MIDDLE.model_copy(update={"outgoing": ()}), _END)
    elif mutation == "hierarchy_cycle":
        nodes = (
            _START.model_copy(update={"parent": _END.ref}),
            _MIDDLE,
            _END.model_copy(update={"parent": _START.ref}),
        )
    elif mutation == "parameterized_cancel_target":
        parameterized_middle = _MIDDLE.model_copy(
            update={
                "route": Route(
                    template="/middle/{item_handle}",
                    deep_link_policy=DeepLinkPolicy.SHAREABLE,
                )
            }
        )
        nodes = (
            _START.model_copy(
                update={
                    "navigation": _START.navigation.model_copy(
                        update={"cancel_target": parameterized_middle.ref}
                    )
                }
            ),
            parameterized_middle,
            _END,
        )
    elif mutation == "conflicting_operation":
        operation_conflict = _ADVANCE.model_copy(
            update={"title": "Conflicting advance"}
        )
        nodes = (
            _START,
            _MIDDLE.model_copy(update={"operations": (_FINISH, operation_conflict)}),
            _END,
        )
    elif mutation == "conflicting_provider":
        provider_conflict = _PROVIDER.model_copy(
            update={"description": "Conflicting test-only provider."}
        )
        nodes = (
            _START,
            _MIDDLE.model_copy(
                update={"context_providers": (_PROVIDER, provider_conflict)}
            ),
            _END,
        )
    elif mutation == "conflicting_surface":
        surface_conflict = _START_SURFACE.model_copy(
            update={"component": "test.conflicting_start"}
        )
        nodes = (
            _START,
            _MIDDLE.model_copy(
                update={
                    "surfaces": _MIDDLE.surfaces.model_copy(
                        update={"active": surface_conflict}
                    )
                }
            ),
            _END,
        )
    elif mutation == "unexecutable_path":
        operation = Operation.model_construct(
            id="test.unexecutable",
            title="Unexecutable",
            description="Test-only operation without an executable outcome.",
            safety_class=SafetyClass.READ_EXTERNAL,
            outcomes=(),
        )
        nodes = (
            _START,
            _MIDDLE,
            _END.model_copy(update={"operations": (operation,)}),
        )
    else:
        raise ValueError(f"Unknown invalid application mutation: {mutation}")

    return Application(
        name="invalid-test-application",
        entry_node=_START.ref,
        features=(
            Feature(
                namespace="test",
                nodes=nodes,
            ),
        ),
    )


def invalid_bindings(
    app: CompiledApplication,
    mutation: str,
) -> FeatureBindings:
    """Return one deliberately inexact binding set using test doubles only."""

    handlers: dict[OperationRef, OperationHandler] = {
        operation.ref: cast(OperationHandler, _async_handler_test_double)
        for operation in app.operations.values()
    }
    providers: dict[ProviderRef, ContextProviderHandler] = {
        provider.ref: cast(ContextProviderHandler, _async_provider_test_double)
        for provider in app.providers.values()
    }
    guards: dict[GuardRef, GuardHandler] = {
        guard.ref: cast(GuardHandler, _async_guard_test_double)
        for guard in app.guards.values()
    }

    if mutation == "missing_handler":
        handlers.pop(min(handlers, key=lambda ref: ref.id))
    elif mutation == "extra_handler":
        handlers[OperationRef(id="test.extra")] = cast(OperationHandler, _test_double)
    elif mutation == "missing_provider":
        providers.pop(min(providers, key=lambda ref: ref.id))
    elif mutation == "extra_provider":
        providers[ProviderRef(id="test.extra")] = cast(ContextProviderHandler, _test_double)
    elif mutation == "missing_guard":
        guards.pop(min(guards, key=lambda ref: ref.id))
    elif mutation == "extra_guard":
        guards[GuardRef(id="test.extra")] = cast(GuardHandler, _test_double)
    elif mutation == "sync_handler":
        handlers[min(handlers, key=lambda ref: ref.id)] = cast(
            OperationHandler, _test_double
        )
    elif mutation == "sync_provider":
        providers[min(providers, key=lambda ref: ref.id)] = cast(
            ContextProviderHandler, _test_double
        )
    elif mutation == "sync_guard":
        guards[min(guards, key=lambda ref: ref.id)] = cast(GuardHandler, _test_double)
    elif mutation == "wrong_handler_signature":
        handlers[min(handlers, key=lambda ref: ref.id)] = cast(
            OperationHandler, _wrong_handler_signature
        )
    elif mutation == "wrong_handler_return":
        handlers[min(handlers, key=lambda ref: ref.id)] = cast(
            OperationHandler, _wrong_handler_return
        )
    else:
        raise ValueError(f"Unknown invalid binding mutation: {mutation}")
    return FeatureBindings(
        handlers=handlers,
        providers=providers,
        guards=guards,
    )


def _test_double(*args: object, **kwargs: object) -> object:
    del args, kwargs
    return object()


async def _async_handler_test_double(
    arguments: object,
    context: object,
) -> OperationOutcome:
    del arguments, context
    raise AssertionError("test-only handler must not execute")


async def _async_provider_test_double(context: object) -> object:
    del context
    raise AssertionError("test-only provider must not execute")


async def _async_guard_test_double(context: object) -> object:
    del context
    raise AssertionError("test-only guard must not execute")


async def _wrong_handler_signature(payload: object) -> object:
    del payload
    raise AssertionError("invalid test-only handler must not execute")


async def _wrong_handler_return(
    arguments: object,
    context: object,
) -> str:
    del arguments, context
    return "invalid"


def session_factory(
    *,
    app: CompiledApplication | None = None,
    session_id: str = "session-1",
    node_id: str = "buyer.home",
    route_params: tuple[LocationParameter, ...] = (),
    contact_email: str | None = None,
    private_entity_id: str | None = None,
    public_entity_handle: str | None = None,
    entity_kind: str = "test.entity",
    allowed_operation_ids: tuple[str, ...] = (),
    private_drafts: tuple[PrivateDraft, ...] = (),
    resume_capabilities: tuple[ResumeCapabilityBinding, ...] = (),
) -> RouteDeckSession:
    """Build isolated canonical state; values here never enter product paths."""

    drafts = private_drafts
    if contact_email is not None:
        contact_draft = PrivateDraft(
            form_id="contact",
            field_names=("email",),
            revision=1,
        )
        drafts = tuple(
            draft for draft in drafts if draft.form_id != contact_draft.form_id
        ) + (contact_draft,)

    if (private_entity_id is None) != (public_entity_handle is None):
        raise ValueError(
            "private_entity_id and public_entity_handle must be supplied together"
        )

    private_bindings: tuple[PrivateEntityBinding, ...] = ()
    public_entities: tuple[PublicEntityHandle, ...] = ()
    if private_entity_id is not None and public_entity_handle is not None:
        private_bindings = (
            PrivateEntityBinding(
                entity_kind=entity_kind,
                public_handle=public_entity_handle,
                private_id=private_entity_id,
                allowed_operation_ids=allowed_operation_ids,
            ),
        )
        public_entities = (
            PublicEntityHandle(
                entity_kind=entity_kind,
                handle=public_entity_handle,
            ),
        )

    capability_bindings = tuple(
        ResumeCapabilityBinding(
            handle=capability.handle,
            session_id=capability.session_id,
            node_id=capability.node_id,
            expires_at=capability.expires_at,
            route_params=capability.route_params,
        )
        for capability in resume_capabilities
    )
    return RouteDeckSession(
        session_id=session_id,
        schema_version=SESSION_SCHEMA_VERSION,
        navgraph_version=(
            navgraph_version(app) if app is not None else "test-navgraph-v1"
        ),
        session_version=1,
        projection_version=1,
        event_cursor=0,
        next_history_entry_id=2,
        current=Location(node_id=node_id, route_params=route_params, entry_id=1),
        private_state=PrivateSessionState(
            drafts=drafts,
            entity_bindings=private_bindings,
            resume_capabilities=capability_bindings,
        ),
        public_state=PublicSessionState(entity_handles=public_entities),
    )


__all__ = ["invalid_app", "invalid_bindings", "session_factory"]
