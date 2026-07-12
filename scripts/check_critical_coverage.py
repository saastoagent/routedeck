"""Enforce RouteDeck's independently measured critical branch-coverage groups."""

from __future__ import annotations

import argparse
import configparser
import fnmatch
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / ".coveragerc"
GROUP_SECTION_PREFIX = "routedeck:coverage_group:"


class CoverageConfigurationError(ValueError):
    """Raised when the version-controlled coverage contract is invalid."""


class CoverageThresholdFailure(RuntimeError):
    """Raised when one or more critical groups do not meet their threshold."""


@dataclass(frozen=True)
class CriticalCoverageGroup:
    name: str
    source: Literal["python", "typescript"]
    include: tuple[str, ...]
    branch_threshold: int


@dataclass(frozen=True)
class CriticalCoverageConfig:
    groups: Mapping[str, CriticalCoverageGroup]


def _split_multiline(value: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in value.splitlines() if line.strip())


def load_coverage_config(path: Path = DEFAULT_CONFIG) -> CriticalCoverageConfig:
    parser = configparser.ConfigParser(interpolation=None)
    loaded = parser.read(path, encoding="utf-8")
    if not loaded:
        raise CoverageConfigurationError(f"Coverage configuration is missing: {path}")

    groups: dict[str, CriticalCoverageGroup] = {}
    for section in parser.sections():
        if not section.startswith(GROUP_SECTION_PREFIX):
            continue
        name = section.removeprefix(GROUP_SECTION_PREFIX).strip()
        if not name:
            raise CoverageConfigurationError(f"Coverage group has no name: {section}")
        source = parser.get(section, "source", fallback="").strip()
        if source not in {"python", "typescript"}:
            raise CoverageConfigurationError(
                f"Coverage group {name!r} has unsupported source {source!r}"
            )
        include = _split_multiline(parser.get(section, "include", fallback=""))
        if not include:
            raise CoverageConfigurationError(
                f"Coverage group {name!r} must declare include globs"
            )
        threshold = parser.getint(section, "branch_threshold", fallback=-1)
        if not 0 <= threshold <= 100:
            raise CoverageConfigurationError(
                f"Coverage group {name!r} has invalid branch threshold {threshold}"
            )
        if name in groups:
            raise CoverageConfigurationError(f"Duplicate coverage group: {name}")
        groups[name] = CriticalCoverageGroup(
            name=name,
            source=source,  # type: ignore[arg-type]
            include=include,
            branch_threshold=threshold,
        )

    if not groups:
        raise CoverageConfigurationError(
            f"No [{GROUP_SECTION_PREFIX}<name>] sections found in {path}"
        )
    return CriticalCoverageConfig(groups=groups)


def _normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    project_prefix = PROJECT_ROOT.as_posix().rstrip("/") + "/"
    return (
        normalized[len(project_prefix) :]
        if normalized.lower().startswith(project_prefix.lower())
        else normalized.lstrip("./")
    )


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    normalized = _normalize_path(path)
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def _load_json(path: Path, label: str) -> Mapping[str, Any]:
    if not path.is_file():
        raise CoverageConfigurationError(f"{label} coverage JSON is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageConfigurationError(
            f"Could not read {label} coverage JSON: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise CoverageConfigurationError(f"{label} coverage JSON must be an object")
    return payload


def _python_branch_counts(document: Mapping[str, Any]) -> dict[str, tuple[int, int]]:
    files = document.get("files")
    if not isinstance(files, dict):
        raise CoverageConfigurationError("Python coverage JSON has no files object")
    result: dict[str, tuple[int, int]] = {}
    for path, record in files.items():
        if not isinstance(path, str) or not isinstance(record, dict):
            raise CoverageConfigurationError("Python coverage file record is malformed")
        summary = record.get("summary")
        if not isinstance(summary, dict):
            raise CoverageConfigurationError(
                f"Python coverage summary is missing for {path}"
            )
        try:
            total = int(summary["num_branches"])
            covered = int(summary["covered_branches"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CoverageConfigurationError(
                f"Python branch counts are missing for {path}"
            ) from exc
        result[_normalize_path(path)] = (covered, total)
    return result


def _typescript_branch_counts(
    document: Mapping[str, Any],
) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for path, record in document.items():
        if path == "total":
            continue
        if not isinstance(path, str) or not isinstance(record, dict):
            raise CoverageConfigurationError(
                "TypeScript coverage file record is malformed"
            )

        branch_summary = record.get("branches")
        if isinstance(branch_summary, dict) and {
            "covered",
            "total",
        }.issubset(branch_summary):
            try:
                result[_normalize_path(path)] = (
                    int(branch_summary["covered"]),
                    int(branch_summary["total"]),
                )
            except (TypeError, ValueError) as exc:
                raise CoverageConfigurationError(
                    f"TypeScript branch summary is malformed for {path}"
                ) from exc
            continue

        branch_hits = record.get("b")
        if not isinstance(branch_hits, dict):
            raise CoverageConfigurationError(
                f"TypeScript branch counts are missing for {path}"
            )
        covered = 0
        total = 0
        for counts in branch_hits.values():
            if not isinstance(counts, list) or any(
                not isinstance(count, int) for count in counts
            ):
                raise CoverageConfigurationError(
                    f"TypeScript branch hit record is malformed for {path}"
                )
            total += len(counts)
            covered += sum(count > 0 for count in counts)
        result[_normalize_path(path)] = (covered, total)
    return result


def evaluate_coverage(
    config: CriticalCoverageConfig,
    *,
    python_json: Path,
    typescript_json: Path,
) -> Mapping[str, Mapping[str, Any]]:
    counts = {
        "python": _python_branch_counts(_load_json(python_json, "Python")),
        "typescript": _typescript_branch_counts(
            _load_json(typescript_json, "TypeScript")
        ),
    }
    report: dict[str, Mapping[str, Any]] = {}
    failures: list[str] = []
    for name, group in config.groups.items():
        matched = {
            path: branch_counts
            for path, branch_counts in counts[group.source].items()
            if _matches(path, group.include)
        }
        if not matched:
            failures.append(f"{name}: no coverage files matched {group.include!r}")
            report[name] = {
                "status": "fail",
                "source": group.source,
                "branch_threshold": group.branch_threshold,
                "matched_files": [],
                "covered_branches": 0,
                "total_branches": 0,
                "branch_percent": 0.0,
            }
            continue
        covered = sum(value[0] for value in matched.values())
        total = sum(value[1] for value in matched.values())
        if total <= 0:
            percent = 0.0
            failures.append(f"{name}: matched files contain no measured branches")
        else:
            percent = covered * 100.0 / total
            if percent < group.branch_threshold:
                failures.append(
                    f"{name}: {percent:.2f}% branch coverage is below "
                    f"{group.branch_threshold}%"
                )
        report[name] = {
            "status": "pass"
            if total > 0 and percent >= group.branch_threshold
            else "fail",
            "source": group.source,
            "branch_threshold": group.branch_threshold,
            "matched_files": sorted(matched),
            "covered_branches": covered,
            "total_branches": total,
            "branch_percent": round(percent, 2),
        }
    if failures:
        raise CoverageThresholdFailure("; ".join(failures))
    return report


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enforce every RouteDeck critical branch-coverage group."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--python-json", type=Path, required=True)
    parser.add_argument("--typescript-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        report = evaluate_coverage(
            load_coverage_config(args.config),
            python_json=args.python_json,
            typescript_json=args.typescript_json,
        )
    except (CoverageConfigurationError, CoverageThresholdFailure) as exc:
        print(f"Critical coverage failed: {exc}")
        return 1
    payload = {
        "schema_version": 1,
        "status": "pass",
        "groups": report,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
