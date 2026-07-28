"""Advisory source-to-architecture coverage checker for RouteDeck."""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_MAP = PROJECT_ROOT / "architecture" / "code-map.md"
SOURCE_SUFFIXES = {
    ".css",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".ps1",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
SOURCE_NAMES = {"Dockerfile"}
EXCLUDED_PART_NAMES = {
    ".agents",
    ".cache",
    ".codex",
    ".codex-run",
    ".demo-data",
    ".git",
    ".mypy_cache",
    ".pnpm-store",
    ".pytest_cache",
    ".ruff_cache",
    ".superpowers",
    ".venv",
    ".worktrees",
    "__pycache__",
    "artifacts",
    "codex_chats_and_memories",
    "context_checkpoints",
    "context_history",
    "dist",
    "graphify-out",
    "logs",
    "node_modules",
    "playwright-report",
    "test-results",
}
EXCLUDED_PREFIXES = {"docs/archive"}


@dataclass(frozen=True)
class CoverageRow:
    subsystem: str
    source_globs: tuple[str, ...]
    architecture_anchors: tuple[str, ...]
    test_anchors: tuple[str, ...]


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _extract_code_items(cell: str) -> tuple[str, ...]:
    return tuple(match.strip() for match in re.findall(r"`([^`]+)`", cell))


def load_coverage_rows() -> list[CoverageRow]:
    if not CODE_MAP.exists():
        raise FileNotFoundError(f"Missing code map: {CODE_MAP}")

    rows: list[CoverageRow] = []
    for line in CODE_MAP.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        if line.startswith("| Subsystem ") or line.startswith("| --- "):
            continue
        cells = _split_table_row(line)
        if len(cells) < 7:
            continue
        rows.append(
            CoverageRow(
                subsystem=cells[0],
                source_globs=_extract_code_items(cells[2]),
                architecture_anchors=_extract_code_items(cells[4]),
                test_anchors=_extract_code_items(cells[5]),
            )
        )

    if not rows:
        raise ValueError(f"No coverage rows parsed from {CODE_MAP}")
    return rows


def normalize_input_path(path: str) -> str:
    absolute = Path(path)
    if absolute.is_absolute():
        try:
            return absolute.resolve().relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            return absolute.as_posix()
    normalized = path.replace("\\", "/")
    return normalized[2:] if normalized.startswith("./") else normalized


def _excluded(path: Path) -> bool:
    relative = path.relative_to(PROJECT_ROOT).as_posix()
    if any(part in EXCLUDED_PART_NAMES for part in Path(relative).parts):
        return True
    return any(
        relative == excluded or relative.startswith(f"{excluded}/")
        for excluded in EXCLUDED_PREFIXES
    )


def is_source_file(path: str) -> bool:
    candidate = Path(path)
    return candidate.suffix in SOURCE_SUFFIXES or candidate.name in SOURCE_NAMES


def all_source_files() -> list[str]:
    source_files: list[str] = []
    for directory, directory_names, file_names in os.walk(PROJECT_ROOT):
        current = Path(directory)
        directory_names[:] = [
            name for name in directory_names if not _excluded(current / name)
        ]
        for file_name in file_names:
            path = current / file_name
            if not _excluded(path) and is_source_file(path.as_posix()):
                source_files.append(path.relative_to(PROJECT_ROOT).as_posix())
    return sorted(source_files)


def matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        clean_pattern = pattern.replace("\\", "/")
        variants = [clean_pattern]
        if "/**/" in clean_pattern:
            variants.append(clean_pattern.replace("/**/", "/"))
        if any(fnmatch.fnmatch(normalized, variant) for variant in variants):
            return True
    return False


def owners_for(path: str, rows: list[CoverageRow]) -> list[CoverageRow]:
    return [row for row in rows if matches_any(path, row.source_globs)]


def touched_anchors(row: CoverageRow, files_to_check: list[str]) -> list[str]:
    anchors = row.architecture_anchors + row.test_anchors
    return sorted(
        {
            anchor
            for anchor in anchors
            for changed in files_to_check
            if changed == anchor or fnmatch.fnmatch(changed, anchor)
        }
    )


def print_report(files_to_check: list[str], *, verbose: bool) -> None:
    rows = load_coverage_rows()
    source_files = sorted({path for path in files_to_check if is_source_file(path)})

    print("RouteDeck documentation coverage advisory")
    print(f"Code map: {CODE_MAP.relative_to(PROJECT_ROOT).as_posix()}")
    print(f"Live source files checked: {len(source_files)}")

    unmapped: list[str] = []
    counts = {row.subsystem: 0 for row in rows}
    for path in source_files:
        owned_rows = owners_for(path, rows)
        if not owned_rows:
            unmapped.append(path)
            print(f"WARN unmapped: {path}")
            continue
        for row in owned_rows:
            counts[row.subsystem] += 1
        if verbose:
            print(f"\nOK: {path}")
            for row in owned_rows:
                print(f"  Subsystem: {row.subsystem}")
                print(
                    "  Architecture anchors: "
                    + (", ".join(row.architecture_anchors) or "(none)")
                )
                print(
                    "  Test anchors: "
                    + (", ".join(row.test_anchors) or "(none)")
                )
                touched = touched_anchors(row, source_files)
                if touched:
                    print("  Anchors in selected set: " + ", ".join(touched))

    print("\nSubsystem coverage:")
    for subsystem, count in counts.items():
        print(f"- {subsystem}: {count} files")
    print(f"\nMapped: {len(source_files) - len(unmapped)}")
    print(f"Unmapped: {len(unmapped)}")
    print("Result: advisory only; exit code remains 0.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Map RouteDeck live source files to architecture/code-map.md "
            "without reading Git state."
        )
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--all",
        action="store_true",
        help="Scan maintained live source (the default).",
    )
    selection.add_argument(
        "--files",
        nargs="+",
        help="Check only the specified project-relative files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print owner and anchor detail for every mapped file.",
    )
    args = parser.parse_args()
    files_to_check = (
        [normalize_input_path(path) for path in args.files]
        if args.files
        else all_source_files()
    )
    print_report(files_to_check, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
