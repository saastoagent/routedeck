from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

from scripts.check_critical_coverage import (
    CoverageThresholdFailure,
    evaluate_coverage,
    load_coverage_config,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


release_summary = _load_script(
    "routedeck_release_summary",
    ROOT / "examples" / "medusa-agent" / "scripts" / "release-summary.py",
)
trace_sanitizer = _load_script(
    "routedeck_trace_sanitizer",
    ROOT / "examples" / "medusa-agent" / "scripts" / "sanitize-playwright-trace.py",
)


def test_critical_coverage_groups_are_explicit() -> None:
    config = load_coverage_config()

    assert set(config.groups) == {
        "state",
        "navigation",
        "supervision",
        "projection",
        "persistence",
        "observable_store",
    }
    assert all(group.branch_threshold == 85 for group in config.groups.values())
    assert {group.source for group in config.groups.values()} == {
        "python",
        "typescript",
    }
    assert all(group.include for group in config.groups.values())


def test_critical_coverage_fails_each_group_independently(tmp_path: Path) -> None:
    python_report = tmp_path / "python.json"
    typescript_report = tmp_path / "typescript.json"
    python_report.write_text(
        json.dumps(
            {
                "files": {
                    "routedeck_core/state/aggregate.py": {
                        "summary": {
                            "num_branches": 10,
                            "covered_branches": 8,
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    typescript_report.write_text("{}", encoding="utf-8")
    config_path = tmp_path / ".coveragerc"
    config_path.write_text(
        "\n".join(
            (
                "[routedeck:coverage_group:state]",
                "source = python",
                "include = routedeck_core/state/*.py",
                "branch_threshold = 85",
                "",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(CoverageThresholdFailure, match="state.*80.00%.*85%"):
        evaluate_coverage(
            load_coverage_config(config_path),
            python_json=python_report,
            typescript_json=typescript_report,
        )


def test_release_gate_names_match_the_approved_design() -> None:
    assert release_summary.REQUIRED_GATES == (
        "framework_correctness",
        "boundary_and_adapter_integrity",
        "real_commerce_source_of_truth",
        "browser_agent_and_developer_experience",
    )


def test_release_boundary_fixture_requires_schema_v3_runtime_ownership() -> None:
    assert release_summary.BOUNDARY_REPORT_SCHEMA_VERSION == 3
    assert release_summary.REQUIRED_BOUNDARY_CHECKS == (
        "core_imports",
        "store_endpoint_inventory",
        "handler_client_port",
        "browser_network",
        "product_transport_separation",
        "runtime_ownership",
        "source_policy_scan",
        "architectural_review",
    )

    def report(
        *,
        schema_version: int = 3,
        names: tuple[str, ...] | None = None,
    ) -> dict[str, object]:
        check_names = names or release_summary.REQUIRED_BOUNDARY_CHECKS
        return {
            "schema_version": schema_version,
            "status": "pass",
            "violation_count": 0,
            "checks": [
                {
                    "name": name,
                    "status": "pass",
                    "evidence": {"verified": True},
                    "violations": [],
                }
                for name in check_names
            ],
        }

    release_summary._validate_boundary_report(report())
    with pytest.raises(
        release_summary.IncompleteReleaseEvidence,
        match="schema version 3",
    ):
        release_summary._validate_boundary_report(report(schema_version=2))
    with pytest.raises(
        release_summary.IncompleteReleaseEvidence,
        match="inventory or order drifted",
    ):
        release_summary._validate_boundary_report(
            report(
                names=tuple(
                    "shared_runner" if name == "runtime_ownership" else name
                    for name in release_summary.REQUIRED_BOUNDARY_CHECKS
                )
            )
        )


def test_release_summary_requires_every_gate_to_pass() -> None:
    with pytest.raises(release_summary.IncompleteReleaseEvidence, match="missing"):
        release_summary.build_release_summary(
            gate_results={"framework_correctness": "pass"},
            run_id="20260712T000000Z",
        )

    results = {gate: "pass" for gate in release_summary.REQUIRED_GATES}
    results["real_commerce_source_of_truth"] = "fail"
    with pytest.raises(release_summary.IncompleteReleaseEvidence, match="not passing"):
        release_summary.build_release_summary(
            gate_results=results,
            run_id="20260712T000000Z",
        )


def test_release_bundle_contract_is_exact_and_rejects_sensitive_json(
    tmp_path: Path,
) -> None:
    assert set(release_summary.REQUIRED_BUNDLE_FILES) == {
        "RELEASE_SUMMARY.md",
        "gate-results.json",
        "environment.json",
        "commands.jsonl",
        "contracts/compiled-navgraph.json",
        "contracts/frontend-contract.json",
        "contracts/executable-test-paths.json",
        "contracts/schema-parity.json",
        "contracts/conformance-results.json",
        "contracts/boundary-report.json",
        "medusa/seed-before.json",
        "medusa/store-api-trace.ndjson",
        "medusa/order-proof.json",
        "medusa/seed-after-reset.json",
        "runtime/supervision-trace.ndjson",
        "runtime/sse-trace.ndjson",
        "runtime/persistence-restart.json",
        "browser/full-flow-trace.zip",
        "browser/network-events.ndjson",
        "browser/browse.png",
        "browser/cart.png",
        "browser/review-pending.png",
        "browser/confirmation.png",
        "browser/network-boundary.json",
        "browser/playwright-report/scripted.json",
        "browser/playwright-report/persistence.json",
        "browser/playwright-report/live-model.json",
        "docs/clean-install.txt",
        "docs/quickstart-smoke.txt",
    }

    unsafe = tmp_path / "unsafe.json"
    unsafe.write_text(
        json.dumps({"OPENAI_API_KEY": "should-never-be-recorded"}),
        encoding="utf-8",
    )
    with pytest.raises(release_summary.UnsafeReleaseEvidence, match="sensitive key"):
        release_summary.validate_sanitized_file(unsafe)

    unsafe_trace = tmp_path / "unsafe-trace.zip"
    with zipfile.ZipFile(unsafe_trace, "w") as archive:
        archive.writestr(
            "trace.trace",
            '{"request":{"postData":"{\\"email\\":\\"buyer@example.com\\"}"}}',
        )
    with pytest.raises(release_summary.UnsafeReleaseEvidence, match="PII|email"):
        release_summary.validate_sanitized_file(unsafe_trace)


def test_release_verifier_is_local_fail_loud_and_always_scoped_down() -> None:
    script = (
        ROOT / "examples" / "medusa-agent" / "scripts" / "release-verify.ps1"
    ).read_text(encoding="utf-8")

    assert "OPENAI_API_KEY" in script
    assert "openai_api_key_missing" in script
    assert "finally" in script
    assert '"Down"' in script
    assert "demo-stack.ps1" in script
    assert "ResetProtectedDemo" in script
    assert "macmini" not in script.lower()
    assert "127.0.0.1:5198" in script
    assert "127.0.0.1:8098" in script
    assert "127.0.0.1:9100" in script
    assert "Scripted" not in script or "test-only" in script.lower()
    assert script.index('"Status"') < script.index('"Reset"')
    assert "ROUTEDECK_TEST_ONLY" in script
    assert script.index('"browser.scripted_backend_start"') < script.index(
        '"browser.scripted_test_only"'
    )
    assert script.index('"browser.live_backend_start"') < script.index(
        '"browser.real_model"'
    )
    assert "sanitize-playwright-trace.py" in script
    assert (
        "--ignore=examples/medusa-agent/backend/tests/integration/real_medusa" in script
    )
    assert script.index('"framework.python_tests"') < script.index(
        '"commerce.real_medusa"'
    )
    reset_index = script.index('"stack.protected_reset_before"')
    refresh_index = script.index("$fileValuesAfterReset = Read-EnvironmentFile")
    stack_up_index = script.index('"stack.up"')
    assert reset_index < refresh_index < stack_up_index
    assert "Import-ProtectedEnvironment $fileValuesAfterReset" in script
    assert '"git"' in script
    assert '"ls-files"' in script
    assert '"--exclude-standard"' in script
    assert "robocopy" not in script.lower()
    assert "Remove-ScopedTemporaryDirectory" in script
    assert '"routedeck-clean-$RunId"' in script


def test_protected_demo_uses_the_locked_repo_local_package_manager() -> None:
    script = (
        ROOT / "examples" / "medusa-agent" / "scripts" / "demo-stack.ps1"
    ).read_text(encoding="utf-8")

    assert '"npm", "run", "medusa", "--", "exec"' in script
    assert '"yarn"' not in script


def test_typescript_coverage_uses_explicit_vitest_projects() -> None:
    expected_projects = {
        "packages/core/vitest.config.ts": "node",
        "packages/react/vitest.config.ts": "node",
        "packages/testing/vitest.config.ts": "node",
        "examples/medusa-agent/frontend/vitest.config.ts": "jsdom",
    }
    root_config_path = ROOT / "vitest.config.ts"

    assert root_config_path.is_file()
    root_config = root_config_path.read_text(encoding="utf-8")
    for project_path, environment in expected_projects.items():
        assert project_path in root_config
        project_config = (ROOT / project_path).read_text(encoding="utf-8")
        assert f'environment: "{environment}"' in project_config
    assert "examples/medusa-agent/e2e" not in root_config
    assert "react/tests" not in root_config
    assert not (ROOT / "vitest.workspace.ts").exists()

    script = (
        ROOT / "examples" / "medusa-agent" / "scripts" / "release-verify.ps1"
    ).read_text(encoding="utf-8")
    assert '"--config", "vitest.config.ts"' in script


def test_trace_sanitizer_preserves_measured_actions_and_redacts_private_data(
    tmp_path: Path,
) -> None:
    raw_trace = tmp_path / "raw.zip"
    with zipfile.ZipFile(raw_trace, "w") as archive:
        archive.writestr(
            "trace.trace",
            "\n".join(
                (
                    json.dumps({"type": "context-options"}),
                    json.dumps(
                        {
                            "type": "before",
                            "params": {
                                "value": "buyer@example.test",
                                "url": "/checkout?resume=private-token",
                            },
                        }
                    ),
                    json.dumps({"type": "after"}),
                )
            )
            + "\n",
        )
        archive.writestr(
            "trace.network",
            "order_private_1234567890123456 buyer@example.test",
        )
    sensitive = tmp_path / "sensitive-values.json"
    sensitive.write_text(json.dumps(["buyer@example.test"]), encoding="utf-8")
    network = tmp_path / "network-boundary.json"
    network.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "pending_trace_sanitization",
                "capture_source": "playwright_page_request_and_response_events",
                "request_count": 5,
                "response_count": 4,
                "direct_store_request_count": 0,
                "pii_capture_count": 0,
                "raw_private_id_capture_count": 0,
                "screenshots_sanitized": True,
                "screenshot_measurements": [
                    {
                        "byte_count": 100 + index,
                        "sha256": str(index) * 64,
                    }
                    for index in range(1, 5)
                ],
                "trace_sanitized": False,
                "trace_capture": {
                    "source": "playwright_context_tracing",
                    "raw_archive_byte_count": raw_trace.stat().st_size,
                },
            }
        ),
        encoding="utf-8",
    )
    sanitized = tmp_path / "sanitized.zip"

    metrics = trace_sanitizer.sanitize_trace(
        source=raw_trace,
        destination=sanitized,
        sensitive_values_path=sensitive,
        network_summary_path=network,
    )

    assert metrics["retained_trace_member_count"] == 1
    assert metrics["dropped_member_count"] == 1
    assert metrics["trace_event_count"] == 3
    assert metrics["redaction_count"] >= 2
    with zipfile.ZipFile(sanitized) as archive:
        assert archive.namelist() == ["trace.trace"]
        trace_text = archive.read("trace.trace").decode("utf-8")
    assert "buyer@example.test" not in trace_text
    assert "private-token" not in trace_text
    assert "before" in trace_text
    assert "after" in trace_text
    summary = json.loads(network.read_text(encoding="utf-8"))
    assert summary["status"] == "pass"
    assert summary["trace_sanitized"] is True
    assert summary["trace_capture"]["trace_event_count"] == 3
    release_summary.validate_sanitized_file(sanitized)
