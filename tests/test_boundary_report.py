from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_boundaries import (
    REQUIRED_CHECK_NAMES,
    _check_framework_product_vocabulary,
    _check_product_frontend_assistant_protocol,
    build_boundary_report,
    check_browser_network,
    check_runtime_ownership,
    main,
)


def test_boundary_report_computes_all_approved_checks() -> None:
    report = build_boundary_report()

    assert report["schema_version"] == 4
    assert tuple(check["name"] for check in report["checks"]) == REQUIRED_CHECK_NAMES
    assert report["status"] == "pass"
    assert report["violation_count"] == 0
    for check in report["checks"]:
        assert check["status"] == "pass"
        assert check["violations"] == []
        assert isinstance(check["evidence"], dict)
        assert check["evidence"]
    store_inventory = next(
        check
        for check in report["checks"]
        if check["name"] == "store_endpoint_inventory"
    )
    assert store_inventory["evidence"]["endpoint_owners"] == [
        "examples/medusa-agent/backend/medusa_agent/medusa/client/resources/cart.py",
        "examples/medusa-agent/backend/medusa_agent/medusa/client/resources/catalog.py",
        "examples/medusa-agent/backend/medusa_agent/medusa/client/resources/checkout.py",
        "examples/medusa-agent/backend/medusa_agent/medusa/client/resources/orders.py",
        "examples/medusa-agent/backend/medusa_agent/medusa/client/transport.py",
    ]
    architectural_review = next(
        check for check in report["checks"] if check["name"] == "architectural_review"
    )
    assert architectural_review["evidence"]["invariants"][
        "standalone_medusa_demo_uses_repo_local_pinned_server"
    ]
    assert architectural_review["evidence"]["invariants"][
        "generic_runtime_supplies_all_transport_planes"
    ]
    assert architectural_review["evidence"]["invariants"][
        "product_frontend_does_not_own_assistant_stream_protocol"
    ]
    assert architectural_review["evidence"]["invariants"][
        "framework_production_copy_is_product_neutral"
    ]
    assert architectural_review["evidence"]["standalone_medusa_server"][
        "compose_build_contexts"
    ] == ["../medusa", "../medusa"]


def test_runtime_ownership_proves_core_construction_and_transport_derivation() -> None:
    check = check_runtime_ownership()

    assert check.name == "runtime_ownership"
    assert check.status == "pass"
    assert check.violations == ()
    assert check.evidence["product_constructor_calls"] == []
    assert check.evidence["product_astream_events_calls"] == []
    assert all(check.evidence["invariants"].values())


def test_browser_network_check_lexes_production_source_and_rejects_store_access(
    tmp_path: Path,
) -> None:
    source = tmp_path / "examples" / "medusa-agent" / "frontend" / "src"
    source.mkdir(parents=True)
    (source / "unsafe.ts").write_text(
        "\n".join(
            (
                'import Medusa from "@medusajs/js-sdk";',
                'const endpoint = "http://127.0.0.1:9100/store/products";',
                '// fetch("http://127.0.0.1:9100/store/comment-only")',
            )
        ),
        encoding="utf-8",
    )

    check = check_browser_network(tmp_path)

    assert check.name == "browser_network"
    assert check.status == "fail"
    assert len(check.violations) == 2
    assert all("comment-only" not in violation for violation in check.violations)


def test_boundary_report_fails_loudly_when_production_roots_are_missing(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="production root"):
        build_boundary_report(tmp_path)


def test_boundary_cli_writes_the_computed_report(tmp_path: Path) -> None:
    output = tmp_path / "boundary-report.json"

    assert main(["--json", str(output)]) == 0
    rendered = output.read_text(encoding="utf-8")
    assert '"schema_version": 4' in rendered
    assert '"name": "runtime_ownership"' in rendered
    assert '"name": "architectural_review"' in rendered
    assert '"violation_count": 0' in rendered


def test_architectural_review_names_direct_product_assistant_protocol_ownership(
    tmp_path: Path,
) -> None:
    source = tmp_path / "examples" / "medusa-agent" / "frontend" / "src"
    source.mkdir(parents=True)
    unsafe = source / "unsafe.ts"
    unsafe.write_text(
        "\n".join(
            (
                "const stream = client.streamAssistantTurn(request);",
                "switch (event.type) {",
                '  case "assistant_delta":',
                "    break;",
                "}",
            )
        ),
        encoding="utf-8",
    )

    evidence, violations = _check_product_frontend_assistant_protocol(tmp_path)

    assert evidence["scanned_files"] == [
        "examples/medusa-agent/frontend/src/unsafe.ts"
    ]
    assert violations == [
        "examples/medusa-agent/frontend/src/unsafe.ts:1:product frontend calls streamAssistantTurn directly",
        "examples/medusa-agent/frontend/src/unsafe.ts:3:product frontend switches over generic assistant event:assistant_delta",
    ]


def test_architectural_review_names_product_vocabulary_in_generic_source(
    tmp_path: Path,
) -> None:
    for relative in (
        "packages/core/src",
        "packages/react/src",
        "routedeck_core",
        "routedeck_fastapi",
        "routedeck_langgraph",
        "routedeck_sqlalchemy",
    ):
        (tmp_path / relative).mkdir(parents=True)
    unsafe = tmp_path / "packages" / "core" / "src" / "unsafe.ts"
    unsafe.write_text(
        'export const message = "The buyer-agent stream failed.";\n',
        encoding="utf-8",
    )
    (unsafe.parent / "ignored.test.ts").write_text(
        'export const fixture = "buyer";\n',
        encoding="utf-8",
    )
    (unsafe.parent / "generated.ts").write_text(
        'export const schemaExample = "buyer";\n',
        encoding="utf-8",
    )

    evidence, violations = _check_framework_product_vocabulary(tmp_path)

    assert "packages/core/src/unsafe.ts" in evidence["scanned_files"]
    assert violations == [
        "packages/core/src/unsafe.ts:1:forbidden product vocabulary:buyer-agent"
    ]
