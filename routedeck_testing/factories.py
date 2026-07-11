"""Explicitly test-only invalid contracts and binding doubles."""

from __future__ import annotations

from routedeck_core.app import ApplicationSpec, FeatureBindings, FeatureSpec
from routedeck_core.app.compiled import CompiledRouteDeckApp
from routedeck_core.contracts.application import CapabilitySpec, NodeSpec
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    NodeRef,
    RecoveryPolicySpec,
    RouteSpec,
    TransitionSpec,
)
from routedeck_core.contracts.operations import (
    ContextProviderSpec,
    GuardRef,
    GuardSpec,
    OperationRef,
    OperationSpec,
    ProviderRef,
    ReviewPolicy,
    SafetyClass,
)
from routedeck_core.contracts.surfaces import (
    SurfaceRef,
    SurfaceSlotsSpec,
    SurfaceSpec,
)


_PROVIDER = ContextProviderSpec(
    id="test.context",
    description="Test-only context provider declaration.",
)
_GUARD = GuardSpec(
    id="test.allowed",
    description="Test-only guard declaration.",
)
_ADVANCE = OperationSpec(
    id="test.advance",
    title="Advance",
    description="Advance the test-only graph.",
    safety_class=SafetyClass.NAVIGATION,
    outcomes=("advanced",),
    provider_refs=(_PROVIDER.ref,),
    guard_refs=(_GUARD.ref,),
)
_FINISH = OperationSpec(
    id="test.finish",
    title="Finish",
    description="Finish the test-only graph.",
    safety_class=SafetyClass.WRITE_EXTERNAL,
    review_policy=ReviewPolicy.REQUIRED,
    outcomes=("completed",),
    provider_refs=(_PROVIDER.ref,),
    guard_refs=(_GUARD.ref,),
)
_FRAME = SurfaceSpec(id="test.frame", component="test.frame")
_START_SURFACE = SurfaceSpec(id="test.start", component="test.start")
_MIDDLE_SURFACE = SurfaceSpec(id="test.middle", component="test.middle")
_END_SURFACE = SurfaceSpec(id="test.end", component="test.end")
_ERROR_SURFACE = SurfaceSpec(id="test.error", component="test.error")
_CAPABILITY = CapabilitySpec(
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
_START = NodeSpec(
    id="test.start",
    title="Start",
    kind=NodeKind.WORKFLOW,
    route=RouteSpec(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
    context_providers=(_PROVIDER,),
    guards=(_GUARD,),
    operations=(_ADVANCE,),
    capabilities=(_CAPABILITY,),
    surfaces=SurfaceSlotsSpec(
        active=_START_SURFACE,
        frame=(_FRAME,),
        error=(_ERROR_SURFACE,),
    ),
    recovery=RecoveryPolicySpec(
        directives=("retry",), failure_surface=_ERROR_SURFACE.ref
    ),
)
_MIDDLE = NodeSpec(
    id="test.middle",
    title="Middle",
    kind=NodeKind.WORKFLOW,
    route=RouteSpec(
        template="/middle", deep_link_policy=DeepLinkPolicy.SHAREABLE
    ),
    context_providers=(_PROVIDER,),
    guards=(_GUARD,),
    operations=(_FINISH,),
    capabilities=(_CAPABILITY,),
    surfaces=SurfaceSlotsSpec(
        active=_MIDDLE_SURFACE,
        frame=(_FRAME,),
        error=(_ERROR_SURFACE,),
    ),
)
_END = NodeSpec(
    id="test.end",
    title="End",
    kind=NodeKind.TRANSIENT,
    route=RouteSpec(template="/end", deep_link_policy=DeepLinkPolicy.SHAREABLE),
    capabilities=(_CAPABILITY,),
    surfaces=SurfaceSlotsSpec(
        active=_END_SURFACE,
        frame=(_FRAME,),
        error=(_ERROR_SURFACE,),
    ),
)
_TO_MIDDLE = TransitionSpec(
    source=_START.ref,
    operation=_ADVANCE.ref,
    outcome="advanced",
    target=_MIDDLE.ref,
)
_TO_END = TransitionSpec(
    source=_MIDDLE.ref,
    operation=_FINISH.ref,
    outcome="completed",
    target=_END.ref,
)


def invalid_app(mutation: str) -> ApplicationSpec:
    """Return one deliberately invalid application for compiler tests."""

    nodes = (_START, _MIDDLE, _END)
    transitions = (_TO_MIDDLE, _TO_END)

    if mutation == "duplicate_node":
        nodes = (*nodes, _START)
    elif mutation == "duplicate_route":
        nodes = (
            _START,
            _MIDDLE.model_copy(update={"route": _START.route}),
            _END,
        )
    elif mutation == "dangling_transition":
        transitions = (
            _TO_MIDDLE.model_copy(update={"target": NodeRef(id="test.missing")}),
            _TO_END,
        )
    elif mutation == "missing_surface":
        capability = _CAPABILITY.model_copy(
            update={"surfaces": (*_CAPABILITY.surfaces, SurfaceRef(id="test.missing"))}
        )
        nodes = tuple(
            node.model_copy(update={"capabilities": (capability,)})
            for node in nodes
        )
    elif mutation == "missing_outcome":
        transitions = (
            _TO_MIDDLE.model_copy(update={"outcome": "undeclared"}),
            _TO_END,
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
    elif mutation == "unreachable_node":
        transitions = (_TO_MIDDLE,)
    elif mutation == "hierarchy_cycle":
        nodes = (
            _START.model_copy(update={"parent": _END.ref}),
            _MIDDLE,
            _END.model_copy(update={"parent": _START.ref}),
        )
    elif mutation == "conflicting_operation":
        conflict = _ADVANCE.model_copy(update={"title": "Conflicting advance"})
        nodes = (
            _START,
            _MIDDLE.model_copy(update={"operations": (_FINISH, conflict)}),
            _END,
        )
    elif mutation == "conflicting_provider":
        conflict = _PROVIDER.model_copy(
            update={"description": "Conflicting test-only provider."}
        )
        nodes = (
            _START,
            _MIDDLE.model_copy(
                update={"context_providers": (_PROVIDER, conflict)}
            ),
            _END,
        )
    elif mutation == "conflicting_surface":
        conflict = _START_SURFACE.model_copy(
            update={"component": "test.conflicting_start"}
        )
        nodes = (
            _START,
            _MIDDLE.model_copy(
                update={
                    "surfaces": _MIDDLE.surfaces.model_copy(
                        update={"active": conflict}
                    )
                }
            ),
            _END,
        )
    elif mutation == "unexecutable_path":
        operation = OperationSpec(
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

    return ApplicationSpec(
        name="invalid-test-application",
        entry_node=_START.ref,
        features=(
            FeatureSpec(
                namespace="test",
                nodes=nodes,
                transitions=transitions,
            ),
        ),
    )


def invalid_bindings(
    app: CompiledRouteDeckApp,
    mutation: str,
) -> FeatureBindings:
    """Return one deliberately inexact binding set using test doubles only."""

    handlers = {operation.ref: _test_double for operation in app.operations.values()}
    providers = {provider.ref: _test_double for provider in app.providers.values()}
    guards = {guard.ref: _test_double for guard in app.guards.values()}

    if mutation == "missing_handler":
        handlers.pop(min(handlers, key=lambda ref: ref.id))
    elif mutation == "extra_handler":
        handlers[OperationRef(id="test.extra")] = _test_double
    elif mutation == "missing_provider":
        providers.pop(min(providers, key=lambda ref: ref.id))
    elif mutation == "extra_provider":
        providers[ProviderRef(id="test.extra")] = _test_double
    elif mutation == "missing_guard":
        guards.pop(min(guards, key=lambda ref: ref.id))
    elif mutation == "extra_guard":
        guards[GuardRef(id="test.extra")] = _test_double
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


__all__ = ["invalid_app", "invalid_bindings"]
