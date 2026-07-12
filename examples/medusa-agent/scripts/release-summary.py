"""Validate and summarize a complete, sanitized RouteDeck release proof bundle."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


REQUIRED_GATES = (
    "framework_correctness",
    "boundary_and_adapter_integrity",
    "real_commerce_source_of_truth",
    "browser_agent_and_developer_experience",
)

REQUIRED_BUNDLE_FILES = (
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
)

REQUIRED_NONEMPTY_DIRECTORIES = (
    "junit",
    "coverage",
    "browser/playwright-report",
)

REQUIRED_BOUNDARY_CHECKS = (
    "core_imports",
    "store_endpoint_inventory",
    "handler_client_port",
    "browser_network",
    "product_transport_separation",
    "shared_runner",
    "source_policy_scan",
    "architectural_review",
)

_SENSITIVE_KEYS = frozenset(
    {
        "openai_api_key",
        "api_key",
        "authorization",
        "cookie",
        "set-cookie",
        "password",
        "secret",
        "encryption_key",
        "publishable_key",
        "email",
        "phone",
        "first_name",
        "last_name",
        "address_1",
        "address_2",
        "postal_code",
        "medusa_cart_id",
        "medusa_order_id",
        "private_id",
        "raw_private_id",
    }
)
_REDACTED_VALUES = frozenset({"[redacted]", "<redacted>", "redacted"})
_TEXT_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?im)\b(?:OPENAI_API_KEY|authorization|password|secret|encryption_key)"
    r"\s*[=:]\s*(?!\[?redacted\b)\S+"
)
_EMAIL_VALUE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_SENSITIVE_STRING_FIELD = re.compile(
    r"""(?i)["'](?:authorization|cookie|set-cookie|password|secret|encryption_key|"""
    r"""email|phone|first_name|last_name|address_1|address_2|postal_code)["']"""
    r"""\s*:\s*["'](?!\[?redacted\b)[^"']+["']"""
)
_RAW_MEDUSA_ID = re.compile(
    r"(?<![A-Za-z0-9])(?:cart|order|prod|variant|item|line|li|litem|so|reg|sc|pay)_"
    r"[A-Za-z0-9]{16,}"
)


class IncompleteReleaseEvidence(RuntimeError):
    """Raised when any mandatory release gate or proof artifact is absent."""


class UnsafeReleaseEvidence(RuntimeError):
    """Raised when a release artifact contains raw secret, PII, or private ID data."""


def _gate_status(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("status"), str):
        return value["status"]
    return None


def validate_gate_results(
    gate_results: Mapping[str, Any],
    *,
    require_detailed_evidence: bool = False,
) -> None:
    missing = [gate for gate in REQUIRED_GATES if gate not in gate_results]
    unexpected = sorted(set(gate_results).difference(REQUIRED_GATES))
    if missing:
        raise IncompleteReleaseEvidence(
            "Release gate results are missing: " + ", ".join(missing)
        )
    if unexpected:
        raise IncompleteReleaseEvidence(
            "Release gate results contain unexpected gates: " + ", ".join(unexpected)
        )
    not_passing = [
        gate for gate in REQUIRED_GATES if _gate_status(gate_results[gate]) != "pass"
    ]
    if not_passing:
        raise IncompleteReleaseEvidence(
            "Release gates are not passing: " + ", ".join(not_passing)
        )

    if require_detailed_evidence:
        browser_gate = gate_results["browser_agent_and_developer_experience"]
        if not isinstance(browser_gate, dict):
            raise IncompleteReleaseEvidence(
                "Browser/agent gate must include detailed live-model evidence"
            )
        evidence = browser_gate.get("evidence")
        if not isinstance(evidence, dict):
            raise IncompleteReleaseEvidence("Browser/agent gate has no evidence object")
        if evidence.get("live_model_smoke") != "pass":
            raise IncompleteReleaseEvidence("Real-model smoke evidence is not passing")
        if evidence.get("model_execution") != "real_openai_api_key":
            raise IncompleteReleaseEvidence(
                "Real-model gate may not use a scripted or fallback model"
            )


def build_release_summary(
    *,
    gate_results: Mapping[str, Any],
    run_id: str,
) -> str:
    validate_gate_results(gate_results)
    rows = [
        "# RouteDeck Release Verification",
        "",
        f"Run: `{run_id}`",
        "",
        "Runtime target: local Windows development machine.",
        "",
        "| Mandatory gate | Result |",
        "| --- | --- |",
    ]
    rows.extend(f"| `{gate}` | pass |" for gate in REQUIRED_GATES)
    rows.extend(
        (
            "",
            "All mandatory gates passed. The bundle validator found no raw secrets, "
            "PII, or private Medusa IDs in text artifacts.",
            "",
        )
    )
    return "\n".join(rows)


def _is_redacted(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in _REDACTED_VALUES


def _validate_json_value(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if (
                key_text.lower() in _SENSITIVE_KEYS
                and child is not None
                and not _is_redacted(child)
            ):
                raise UnsafeReleaseEvidence(
                    f"Artifact contains a sensitive key with an unredacted value: "
                    f"{path}.{key_text}"
                )
            _validate_json_value(child, path=f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_json_value(child, path=f"{path}[{index}]")
    elif isinstance(value, str):
        _validate_text(value, label=path)


def _validate_text(text: str, *, label: str) -> None:
    inspected = text.replace('\\"', '"').replace(
        "pp_system_default", "approved_demo_payment_provider"
    )
    if _TEXT_CREDENTIAL_ASSIGNMENT.search(inspected):
        raise UnsafeReleaseEvidence(f"Artifact contains credential material: {label}")
    if _SENSITIVE_STRING_FIELD.search(inspected):
        raise UnsafeReleaseEvidence(
            f"Artifact contains an unredacted PII field: {label}"
        )
    if _EMAIL_VALUE.search(inspected):
        raise UnsafeReleaseEvidence(f"Artifact contains an email address: {label}")
    match = _RAW_MEDUSA_ID.search(inspected)
    if match is not None:
        raise UnsafeReleaseEvidence(
            f"Artifact contains a raw private Medusa ID at {label}: {match.group(0)}"
        )


def _validate_trace_archive(path: Path) -> None:
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise IncompleteReleaseEvidence(f"Malformed trace archive: {path}") from exc
    with archive:
        total_size = 0
        trace_member_count = 0
        trace_event_count = 0
        trace_event_types: set[str] = set()
        for member in archive.infolist():
            if member.is_dir():
                continue
            if member.flag_bits & 0x1:
                raise UnsafeReleaseEvidence(
                    f"Encrypted trace member cannot be sanitized: {member.filename}"
                )
            total_size += member.file_size
            if member.file_size > 128 * 1024 * 1024 or total_size > 512 * 1024 * 1024:
                raise UnsafeReleaseEvidence(
                    f"Trace archive exceeds sanitization limits: {path}"
                )
            suffix = Path(member.filename).suffix.lower()
            if suffix in {
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
                ".gif",
                ".woff",
                ".woff2",
            }:
                continue
            content = archive.read(member)
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                continue
            _validate_text(text, label=f"{path.as_posix()}!{member.filename}")
            if suffix == ".trace":
                trace_member_count += 1
                for line_number, line in enumerate(text.splitlines(), start=1):
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise IncompleteReleaseEvidence(
                            f"Malformed Playwright trace event: "
                            f"{path}!{member.filename}:{line_number}"
                        ) from exc
                    if not isinstance(event, dict):
                        raise IncompleteReleaseEvidence(
                            "Playwright trace event must be a JSON object"
                        )
                    event_type = event.get("type")
                    if isinstance(event_type, str):
                        trace_event_types.add(event_type)
                    trace_event_count += 1
        if (
            trace_member_count == 0
            or trace_event_count == 0
            or not {"before", "after"}.issubset(trace_event_types)
        ):
            raise IncompleteReleaseEvidence(
                "Trace archive is not a genuine measured Playwright action trace"
            )


def validate_sanitized_file(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".zip":
        _validate_trace_archive(path)
        return
    if suffix == ".png":
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise UnsafeReleaseEvidence(
            f"Unexpected binary release artifact outside approved PNG/ZIP paths: {path}"
        ) from exc
    if suffix == ".json":
        try:
            document = json.loads(text)
        except json.JSONDecodeError as exc:
            raise IncompleteReleaseEvidence(f"Malformed JSON artifact: {path}") from exc
        _validate_json_value(document)
        return
    if suffix in {".jsonl", ".ndjson"}:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                document = json.loads(line)
            except json.JSONDecodeError as exc:
                raise IncompleteReleaseEvidence(
                    f"Malformed JSON line artifact: {path}:{line_number}"
                ) from exc
            _validate_json_value(document, path=f"$line[{line_number}]")
        return
    _validate_text(text, label=path.as_posix())


def _load_json_object(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IncompleteReleaseEvidence(
            f"Could not read JSON evidence: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise IncompleteReleaseEvidence(f"JSON evidence must be an object: {path}")
    return value


def _load_ndjson_objects(path: Path) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise IncompleteReleaseEvidence(
            f"Could not read NDJSON evidence: {path}"
        ) from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IncompleteReleaseEvidence(
                f"Malformed NDJSON evidence: {path}:{line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise IncompleteReleaseEvidence(
                f"NDJSON evidence row must be an object: {path}:{line_number}"
            )
        rows.append(value)
    return rows


def _validate_semantic_evidence(bundle: Path) -> None:
    command_rows = _load_ndjson_objects(bundle / "commands.jsonl")
    required_command_order = (
        "browser.scripted_backend_start",
        "browser.scripted_test_only",
        "browser.sanitize_measured_trace",
        "browser.live_backend_start",
        "browser.persistence_after_restart",
        "browser.real_model",
    )
    command_names = [row.get("name") for row in command_rows]
    try:
        command_indices = [command_names.index(name) for name in required_command_order]
    except ValueError as exc:
        raise IncompleteReleaseEvidence(
            "Release command evidence is missing a measured browser/runtime gate"
        ) from exc
    if command_indices != sorted(command_indices) or any(
        command_rows[index].get("status") != "pass" for index in command_indices
    ):
        raise IncompleteReleaseEvidence(
            "Browser/runtime gate commands did not pass in the required order"
        )

    environment = _load_json_object(bundle / "environment.json")
    if environment.get("runtime_target") != "local":
        raise IncompleteReleaseEvidence(
            "environment.json must record runtime_target=local"
        )
    expected_urls = {
        "frontend": "http://127.0.0.1:5198",
        "agent_api": "http://127.0.0.1:8098",
        "medusa": "http://127.0.0.1:9100",
    }
    if environment.get("smoke_urls") != expected_urls:
        raise IncompleteReleaseEvidence(
            "environment.json does not contain the fixed local smoke URLs"
        )

    boundary = _load_json_object(bundle / "contracts" / "boundary-report.json")
    checks = boundary.get("checks")
    if not isinstance(checks, list):
        raise IncompleteReleaseEvidence("Boundary evidence has no checks list")
    check_names = {check.get("name") for check in checks if isinstance(check, dict)}
    missing_checks = sorted(set(REQUIRED_BOUNDARY_CHECKS).difference(check_names))
    if (
        boundary.get("status") != "pass"
        or boundary.get("violation_count") != 0
        or missing_checks
    ):
        raise IncompleteReleaseEvidence(
            "Boundary evidence is incomplete or failing"
            + (f": missing {', '.join(missing_checks)}" if missing_checks else "")
        )

    network = _load_json_object(bundle / "browser" / "network-boundary.json")
    network_events = _load_ndjson_objects(bundle / "browser" / "network-events.ndjson")
    request_events = [row for row in network_events if row.get("phase") == "request"]
    response_events = [row for row in network_events if row.get("phase") == "response"]
    screenshot_measurements = network.get("screenshot_measurements")
    trace_capture = network.get("trace_capture")
    expected_network_fields = [
        "method",
        "origin",
        "path_template",
        "query_parameter_names",
        "resource_type",
        "status",
    ]
    if (
        network.get("status") != "pass"
        or network.get("capture_source")
        != "playwright_page_request_and_response_events"
        or network.get("captured_network_fields") != expected_network_fields
        or network.get("request_count") != len(request_events)
        or network.get("response_count") != len(response_events)
        or not request_events
        or not response_events
        or network.get("isolated_context_count") != 2
        or {row.get("context") for row in network_events} != {"primary", "anonymous"}
        or [row.get("sequence") for row in network_events]
        != list(range(1, len(network_events) + 1))
        or any(
            row.get("schema_version") != 1
            or not isinstance(row.get("method"), str)
            or not isinstance(row.get("origin"), str)
            or not isinstance(row.get("path_template"), str)
            or "?" in row["path_template"]
            or not isinstance(row.get("query_parameter_names"), list)
            or not isinstance(row.get("resource_type"), str)
            or (
                row.get("phase") == "response"
                and not isinstance(row.get("status"), int)
            )
            for row in network_events
        )
        or network.get("direct_store_request_count") != 0
        or network.get("pii_capture_count") != 0
        or network.get("raw_private_id_capture_count") != 0
        or network.get("screenshots_sanitized") is not True
        or network.get("trace_sanitized") is not True
        or not isinstance(screenshot_measurements, list)
        or len(screenshot_measurements) != 4
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("byte_count"), int)
            or item["byte_count"] <= 0
            or not isinstance(item.get("sha256"), str)
            or len(item["sha256"]) != 64
            for item in screenshot_measurements
        )
        or not isinstance(trace_capture, dict)
        or trace_capture.get("source") != "playwright_context_tracing"
        or not isinstance(trace_capture.get("trace_event_count"), int)
        or trace_capture["trace_event_count"] <= 0
        or not isinstance(trace_capture.get("retained_trace_member_count"), int)
        or trace_capture["retained_trace_member_count"] <= 0
        or trace_capture.get("sanitization")
        != "parsed_json_redaction_and_network_resource_omission"
    ):
        raise IncompleteReleaseEvidence(
            "Browser evidence contains direct Store traffic or unsanitized private data"
        )

    order = _load_json_object(bundle / "medusa" / "order-proof.json")
    required_order_truth = (
        "independent_order_reread",
        "order_identity_match",
        "items_match",
        "quantities_match",
        "totals_match",
        "email_match",
        "shipping_method_match",
        "payment_provider_match",
    )
    if (
        order.get("status") != "pass"
        or order.get("source") != "measured_typed_medusa_store_calls"
        or order.get("transport_kind") != "network"
        or order.get("completion_type") != "order"
        or order.get("complete_cart_call_count") != 1
        or order.get("get_order_call_count_after_completion") != 1
        or any(order.get(key) is not True for key in required_order_truth)
    ):
        raise IncompleteReleaseEvidence(
            "Real Medusa order proof is incomplete or does not match the independent re-read"
        )

    store_trace = _load_ndjson_objects(bundle / "medusa" / "store-api-trace.ndjson")
    if (
        len(store_trace) != 2
        or [row.get("sequence") for row in store_trace] != [1, 2]
        or any(
            row.get("source") != "http_medusa_store_client"
            or row.get("actual_call") is not True
            or row.get("transport_kind") != "network"
            for row in store_trace
        )
        or store_trace[0].get("operation") != "complete_cart"
        or store_trace[0].get("method") != "POST"
        or store_trace[0].get("path_template") != "/store/carts/{cart_id}/complete"
        or store_trace[0].get("result") != "order"
        or store_trace[1].get("operation") != "get_order"
        or store_trace[1].get("method") != "GET"
        or store_trace[1].get("path_template") != "/store/orders/{order_id}"
        or store_trace[1].get("result") != "success"
        or store_trace[1].get("independent_reread") is not True
    ):
        raise IncompleteReleaseEvidence(
            "Store API trace is not the measured complete-cart plus independent re-read"
        )

    supervision = _load_ndjson_objects(bundle / "runtime" / "supervision-trace.ndjson")
    review_dispositions = {
        row.get("disposition")
        for row in supervision
        if row.get("operation_id") == "checkout.place_order"
    }
    if (
        not supervision
        or [row.get("sequence") for row in supervision]
        != list(range(1, len(supervision) + 1))
        or any(
            row.get("source") != "playwright_captured_routedeck_operation_response"
            or row.get("transport_path_template")
            not in {
                "/api/routedeck/dispatch",
                "/api/routedeck/reviews/{review_id}/accept",
            }
            or not isinstance(row.get("operation_id"), str)
            or not isinstance(row.get("disposition"), str)
            or not isinstance(row.get("phases"), list)
            or row.get("failure_present") is not False
            for row in supervision
        )
        or review_dispositions != {"requires_review", "completed"}
    ):
        raise IncompleteReleaseEvidence(
            "Runtime supervision trace is not derived from the measured buyer flow"
        )

    sse = _load_ndjson_objects(bundle / "runtime" / "sse-trace.ndjson")
    sse_event_names = [row.get("event") for row in sse]
    if (
        not sse
        or [row.get("sequence") for row in sse] != list(range(1, len(sse) + 1))
        or any(
            row.get("source") != "playwright_captured_sse_response"
            or not isinstance(row.get("event"), str)
            or not isinstance(row.get("data_fields"), list)
            for row in sse
        )
        or sse_event_names[0] != "stream_start"
        or sse_event_names[-1] != "stream_end"
        or not {"user_message", "assistant_delta", "assistant_end"}.issubset(
            sse_event_names
        )
    ):
        raise IncompleteReleaseEvidence(
            "Runtime SSE trace is not a complete measured agent response"
        )

    persistence = _load_json_object(bundle / "runtime" / "persistence-restart.json")
    if (
        persistence.get("status") != "pass"
        or persistence.get("source")
        != "playwright_confirmation_probe_after_measured_agent_api_restart"
        or persistence.get("route_template")
        != "/orders/{confirmation_handle}/confirmation"
        or persistence.get("pre_restart_confirmation_observed") is not True
        or persistence.get("post_restart_confirmation_observed") is not True
        or persistence.get("session_cookie_restored") is not True
        or persistence.get("confirmation_handle_match") is not True
        or persistence.get("post_restart_health_status") != 200
    ):
        raise IncompleteReleaseEvidence(
            "Persistence restart proof is not a measured confirmation-session probe"
        )

    for gate in ("scripted", "persistence", "live-model"):
        report = _load_json_object(
            bundle / "browser" / "playwright-report" / f"{gate}.json"
        )
        tests = report.get("tests")
        if (
            report.get("status") != "pass"
            or report.get("source") != "playwright_reporter_callbacks"
            or report.get("gate") != gate
            or report.get("full_result_status") != "passed"
            or not isinstance(report.get("test_count"), int)
            or report["test_count"] <= 0
            or not isinstance(report.get("passed_count"), int)
            or report["passed_count"] <= 0
            or report.get("failed_count") != 0
            or not isinstance(tests, list)
            or len(tests) != report["test_count"]
        ):
            raise IncompleteReleaseEvidence(
                f"Measured Playwright report is incomplete or failing: {gate}"
            )

    before = _load_json_object(bundle / "medusa" / "seed-before.json")
    after = _load_json_object(bundle / "medusa" / "seed-after-reset.json")
    before_fingerprint = before.get("normalized_seed_fingerprint")
    if (
        not isinstance(before_fingerprint, str)
        or not before_fingerprint
        or after.get("normalized_seed_fingerprint") != before_fingerprint
        or after.get("test_created_record_count") != 0
    ):
        raise IncompleteReleaseEvidence(
            "Protected reset did not restore the normalized Medusa seed fingerprint"
        )


def validate_release_bundle(bundle: Path) -> None:
    missing_files = [
        relative
        for relative in REQUIRED_BUNDLE_FILES
        if not (bundle / relative).is_file()
    ]
    if missing_files:
        raise IncompleteReleaseEvidence(
            "Release bundle files are missing: " + ", ".join(missing_files)
        )
    empty_directories = []
    for relative in REQUIRED_NONEMPTY_DIRECTORIES:
        directory = bundle / relative
        if not directory.is_dir() or not any(
            path.is_file() for path in directory.rglob("*")
        ):
            empty_directories.append(relative)
    if empty_directories:
        raise IncompleteReleaseEvidence(
            "Release bundle directories are missing or empty: "
            + ", ".join(empty_directories)
        )

    gate_results = _load_json_object(bundle / "gate-results.json")
    validate_gate_results(gate_results, require_detailed_evidence=True)
    _validate_semantic_evidence(bundle)
    for path in sorted(bundle.rglob("*")):
        if path.is_file():
            validate_sanitized_file(path)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a RouteDeck release bundle and write its summary."
    )
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    gate_results = _load_json_object(args.bundle / "gate-results.json")
    summary = build_release_summary(gate_results=gate_results, run_id=args.run_id)
    (args.bundle / "RELEASE_SUMMARY.md").write_text(summary, encoding="utf-8")
    validate_release_bundle(args.bundle)
    print(args.bundle / "RELEASE_SUMMARY.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
