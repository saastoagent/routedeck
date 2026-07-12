"""Sanitize a genuine Playwright trace and attach measured release metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "password",
        "secret",
        "email",
        "phone",
        "first_name",
        "last_name",
        "address_1",
        "address_2",
        "postal_code",
    }
)
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_RAW_PRIVATE_ID = re.compile(
    r"(?<![A-Za-z0-9])(?:cart|order|prod|variant|item|line|li|litem|so|reg|sc|pay)_"
    r"[A-Za-z0-9]{16,}"
)


class TraceSanitizationError(RuntimeError):
    """Raised when trace evidence is absent, malformed, or not measurable."""


def sanitize_trace(
    *,
    source: Path,
    destination: Path,
    sensitive_values_path: Path,
    network_summary_path: Path,
) -> dict[str, int]:
    sensitive_values = _load_sensitive_values(sensitive_values_path)
    try:
        archive = zipfile.ZipFile(source)
    except (OSError, zipfile.BadZipFile) as exc:
        raise TraceSanitizationError(
            "Playwright did not produce a valid trace ZIP"
        ) from exc

    retained: list[tuple[str, bytes]] = []
    redaction_count = 0
    event_count = 0
    event_types: set[str] = set()
    source_member_count = 0
    with archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        source_member_count = len(members)
        for member in members:
            if member.flag_bits & 0x1:
                raise TraceSanitizationError(
                    "Encrypted Playwright trace members are unsafe"
                )
            if Path(member.filename).suffix != ".trace":
                continue
            source_text = archive.read(member).decode("utf-8")
            sanitized_lines: list[str] = []
            for line_number, line in enumerate(source_text.splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise TraceSanitizationError(
                        f"Malformed Playwright trace event {member.filename}:{line_number}"
                    ) from exc
                if not isinstance(event, dict):
                    raise TraceSanitizationError(
                        "Playwright trace event must be an object"
                    )
                event_type = event.get("type")
                if isinstance(event_type, str):
                    event_types.add(event_type)
                sanitized, count = _sanitize_value(event, sensitive_values)
                redaction_count += count
                event_count += 1
                sanitized_lines.append(
                    json.dumps(sanitized, sort_keys=True, separators=(",", ":"))
                )
            retained.append(
                (member.filename, ("\n".join(sanitized_lines) + "\n").encode())
            )

    if not retained or event_count == 0:
        raise TraceSanitizationError("Trace archive has no genuine Playwright events")
    if not {"before", "after"}.issubset(event_types):
        raise TraceSanitizationError(
            "Trace archive does not contain measured Playwright before/after actions"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name, content in retained:
            output.writestr(name, content)
    temporary.replace(destination)

    _assert_sanitized_archive(destination, sensitive_values)
    metrics = {
        "source_member_count": source_member_count,
        "retained_trace_member_count": len(retained),
        "dropped_member_count": source_member_count - len(retained),
        "trace_event_count": event_count,
        "redaction_count": redaction_count,
    }
    _complete_network_summary(network_summary_path, destination, metrics)
    return metrics


def _load_sensitive_values(path: Path) -> tuple[str, ...]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TraceSanitizationError(
            "Could not load explicit trace redaction values"
        ) from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TraceSanitizationError(
            "Trace redaction values must be a JSON string list"
        )
    normalized = tuple(item for item in value if item)
    if not normalized:
        raise TraceSanitizationError("Trace redaction values are empty")
    return normalized


def _sanitize_value(value: Any, sensitive_values: tuple[str, ...]) -> tuple[Any, int]:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        count = 0
        for key, child in value.items():
            if str(key).lower() in _SENSITIVE_KEYS and child is not None:
                sanitized[str(key)] = "[redacted]"
                count += 1
            else:
                sanitized_child, child_count = _sanitize_value(child, sensitive_values)
                sanitized[str(key)] = sanitized_child
                count += child_count
        return sanitized, count
    if isinstance(value, list):
        sanitized_list: list[Any] = []
        count = 0
        for child in value:
            sanitized_child, child_count = _sanitize_value(child, sensitive_values)
            sanitized_list.append(sanitized_child)
            count += child_count
        return sanitized_list, count
    if isinstance(value, str):
        return _sanitize_string(value, sensitive_values)
    return value, 0


def _sanitize_string(value: str, sensitive_values: tuple[str, ...]) -> tuple[str, int]:
    sanitized = value
    count = 0
    for sensitive in sensitive_values:
        occurrences = sanitized.count(sensitive)
        if occurrences:
            sanitized = sanitized.replace(sensitive, "[redacted]")
            count += occurrences
    sanitized, email_count = _EMAIL.subn("[redacted-email]", sanitized)
    sanitized, private_count = _RAW_PRIVATE_ID.subn("[redacted-private-id]", sanitized)
    count += email_count + private_count
    sanitized_url, query_count = _redact_query_values(sanitized)
    return sanitized_url, count + query_count


def _redact_query_values(value: str) -> tuple[str, int]:
    if "?" not in value:
        return value, 0
    parsed = urlsplit(value)
    if not parsed.query or (not parsed.scheme and not parsed.path.startswith("/")):
        return value, 0
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if not pairs:
        return value, 0
    redacted_query = urlencode([(name, "[redacted]") for name, _ in pairs])
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, redacted_query, parsed.fragment)
    ), len(pairs)


def _assert_sanitized_archive(path: Path, sensitive_values: tuple[str, ...]) -> None:
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            text = archive.read(member).decode("utf-8")
            if any(value in text for value in sensitive_values):
                raise TraceSanitizationError(
                    "Sanitized trace retains an explicit PII value"
                )
            if _EMAIL.search(text) or _RAW_PRIVATE_ID.search(text):
                raise TraceSanitizationError("Sanitized trace retains private material")


def _complete_network_summary(
    path: Path,
    trace_path: Path,
    metrics: dict[str, int],
) -> None:
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TraceSanitizationError(
            "Browser network summary is missing or malformed"
        ) from exc
    screenshots = summary.get("screenshot_measurements")
    evidence_passes = (
        summary.get("status") == "pending_trace_sanitization"
        and summary.get("capture_source")
        == "playwright_page_request_and_response_events"
        and isinstance(summary.get("request_count"), int)
        and summary["request_count"] > 0
        and isinstance(summary.get("response_count"), int)
        and summary["response_count"] > 0
        and summary.get("direct_store_request_count") == 0
        and summary.get("pii_capture_count") == 0
        and summary.get("raw_private_id_capture_count") == 0
        and summary.get("screenshots_sanitized") is True
        and isinstance(screenshots, list)
        and len(screenshots) == 4
        and all(
            isinstance(item, dict)
            and isinstance(item.get("byte_count"), int)
            and item["byte_count"] > 0
            and isinstance(item.get("sha256"), str)
            and len(item["sha256"]) == 64
            for item in screenshots
        )
    )
    if not evidence_passes:
        raise TraceSanitizationError(
            "Measured browser request/response/screenshot evidence is not clean"
        )
    trace_capture = summary.get("trace_capture")
    if not isinstance(trace_capture, dict):
        raise TraceSanitizationError("Browser summary has no raw trace measurement")
    trace_bytes = trace_path.read_bytes()
    summary["status"] = "pass"
    summary["trace_sanitized"] = True
    summary["trace_capture"] = {
        **trace_capture,
        **metrics,
        "sanitized_archive_byte_count": len(trace_bytes),
        "sanitized_archive_sha256": hashlib.sha256(trace_bytes).hexdigest(),
        "sanitization": "parsed_json_redaction_and_network_resource_omission",
    }
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(f"{json.dumps(summary, indent=2)}\n", encoding="utf-8")
    temporary.replace(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sensitive-values", type=Path, required=True)
    parser.add_argument("--network-summary", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = _parse_args()
    metrics = sanitize_trace(
        source=arguments.input,
        destination=arguments.output,
        sensitive_values_path=arguments.sensitive_values,
        network_summary_path=arguments.network_summary,
    )
    print(json.dumps(metrics, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
