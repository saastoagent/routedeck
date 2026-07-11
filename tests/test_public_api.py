from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError


def test_public_packages_import_and_publish_type_markers() -> None:
    import routedeck_core
    import routedeck_fastapi
    import routedeck_langgraph
    import routedeck_sqlite
    import routedeck_testing

    packages = (
        routedeck_core,
        routedeck_fastapi,
        routedeck_langgraph,
        routedeck_sqlite,
        routedeck_testing,
    )

    assert routedeck_core.RouteDeckFailure.__name__ == "RouteDeckFailure"
    for package in packages:
        assert Path(package.__file__).with_name("py.typed").is_file()


def test_target_core_subpackages_are_importable_without_module_collisions() -> None:
    import routedeck_core.context
    import routedeck_core.contracts
    import routedeck_core.ports
    import routedeck_core.projection
    import routedeck_core.state
    import routedeck_core.supervision

    core_root = Path(routedeck_core.__file__).parent
    assert (core_root / "app.py").is_file()
    assert not (core_root / "app").exists()
    assert (core_root / "navigation.py").is_file()
    assert not (core_root / "navigation").exists()


def test_runtime_subclass_remains_compatibility_only() -> None:
    import routedeck_core

    assert "RouteDeckRuntimeBase" not in routedeck_core.__all__
    assert routedeck_core.RouteDeckRuntimeBase.__name__ == "RouteDeckRuntimeBase"


def test_failure_contract_has_one_public_model_definition() -> None:
    import routedeck_core
    from routedeck_core.contracts.failures import (
        FailureKind,
        FailureSafeDetails,
        RouteDeckFailure,
    )
    from routedeck_core.errors import (
        FailureKind as CompatibilityFailureKind,
        FailureSafeDetails as CompatibilityFailureSafeDetails,
        RouteDeckFailure as CompatibilityRouteDeckFailure,
    )

    assert routedeck_core.FailureKind is FailureKind is CompatibilityFailureKind
    assert (
        routedeck_core.FailureSafeDetails
        is FailureSafeDetails
        is CompatibilityFailureSafeDetails
    )
    assert (
        routedeck_core.RouteDeckFailure
        is RouteDeckFailure
        is CompatibilityRouteDeckFailure
    )
    assert RouteDeckFailure.__module__ == "routedeck_core.contracts.failures"


def test_failure_kind_values_are_stable() -> None:
    from routedeck_core.contracts.failures import FailureKind

    assert [kind.value for kind in FailureKind] == [
        "contract",
        "state_conflict",
        "context_provider",
        "guard",
        "review",
        "transport",
        "provider_protocol",
        "business",
        "persistence",
        "external_outcome_unknown",
        "internal",
    ]


def test_failure_details_reject_raw_diagnostics() -> None:
    from routedeck_core.contracts.failures import FailureSafeDetails

    with pytest.raises(ValidationError):
        FailureSafeDetails.model_validate(
            {"response_body": "secret", "exception": "token"}
        )


def test_failure_rejects_unknown_top_level_diagnostics() -> None:
    from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure

    with pytest.raises(ValidationError):
        RouteDeckFailure.model_validate(
            {
                "kind": FailureKind.INTERNAL,
                "code": "unexpected_executor_failure",
                "phase": "execute",
                "correlation_id": "correlation-2",
                "public_message": "The operation could not be completed.",
                "exception": "secret token",
            }
        )


def test_failure_contract_is_typed_and_frozen() -> None:
    from routedeck_core.contracts.failures import (
        FailureKind,
        FailureSafeDetails,
        RouteDeckFailure,
    )

    failure = RouteDeckFailure(
        kind=FailureKind.TRANSPORT,
        code="provider_unavailable",
        phase="execute",
        correlation_id="correlation-1",
        operation_id="catalog.list",
        request_id="request-1",
        public_message="The catalog provider is unavailable.",
        recovery_directive="retry_after_refresh",
        safe_details=FailureSafeDetails(
            affected_capability="catalog",
            provider="medusa",
            provider_code="service_unavailable",
            http_status=503,
            delivery_phase="not_sent",
        ),
    )

    assert failure.kind is FailureKind.TRANSPORT
    assert failure.safe_details.http_status == 503
    with pytest.raises(ValidationError):
        failure.code = "changed"  # type: ignore[misc]
