"""Advisory architecture/test coverage checker for RouteDeck source changes."""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_MAP = PROJECT_ROOT / "architecture" / "code-map.md"
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".mjs", ".js", ".json", ".toml", ".md"}


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


def _run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout


def _git_root() -> Path:
    return Path(_run_git(["rev-parse", "--show-toplevel"]).strip()).resolve()


def _project_relative_git_path(path: str, git_root: Path) -> str | None:
    absolute = (git_root / path.replace("\\", "/").strip('"')).resolve()
    try:
        return absolute.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return None


def changed_files_from_git() -> list[str]:
    git_root = _git_root()
    files: list[str] = []
    commands = (
        ["diff", "--name-only"],
        ["diff", "--cached", "--name-only"],
        ["ls-files", "--others", "--exclude-standard"],
    )
    for command in commands:
        for path_text in _run_git(command).splitlines():
            if not path_text.strip():
                continue
            path = _project_relative_git_path(path_text, git_root)
            if path is not None:
                files.append(path)
    return sorted(set(files))


def normalize_input_path(path: str) -> str:
    absolute = Path(path)
    if absolute.is_absolute():
        try:
            return absolute.resolve().relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            return absolute.as_posix()
    normalized = path.replace("\\", "/")
    return normalized[2:] if normalized.startswith("./") else normalized


def is_source_file(path: str) -> bool:
    return Path(path).suffix in SOURCE_SUFFIXES


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


def touched_anchors(row: CoverageRow, changed_files: list[str]) -> list[str]:
    anchors = row.architecture_anchors + row.test_anchors
    touched: list[str] = []
    for anchor in anchors:
        for changed in changed_files:
            if changed == anchor or fnmatch.fnmatch(changed, anchor):
                touched.append(anchor)
                break
    return sorted(set(touched))


def print_report(files_to_check: list[str], changed_files: list[str]) -> None:
    rows = load_coverage_rows()
    source_files = [path for path in files_to_check if is_source_file(path)]

    print("RouteDeck doc coverage advisory")
    print(f"Code map: {CODE_MAP.relative_to(PROJECT_ROOT).as_posix()}")

    if not source_files:
        print("No changed source files to map.")
        print("Result: advisory only; exit code remains 0.")
        return

    unmapped: list[str] = []
    for path in source_files:
        owned_rows = owners_for(path, rows)
        if not owned_rows:
            unmapped.append(path)
            print(f"\nWARN: {path}")
            print("  No subsystem owner found in architecture/code-map.md.")
            continue

        print(f"\nOK: {path}")
        for row in owned_rows:
            print(f"  Subsystem: {row.subsystem}")
            print(
                "  Architecture anchors: "
                + (", ".join(row.architecture_anchors) or "(none)")
            )
            print("  Test anchors: " + (", ".join(row.test_anchors) or "(none)"))
            touched = touched_anchors(row, changed_files)
            if touched:
                print("  Changed anchors in this worktree: " + ", ".join(touched))
            else:
                print(
                    "  WARN: no related architecture/test anchor is currently changed; "
                    "closeout should state why the documented contract is unchanged."
                )

    if unmapped:
        print("\nUnmapped source files:")
        for path in unmapped:
            print(f"- {path}")
    print("\nResult: advisory only; exit code remains 0.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Map changed RouteDeck source files to architecture/test anchors."
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="Specific project-relative source files to check instead of git status.",
    )
    args = parser.parse_args()

    changed_files = changed_files_from_git()
    files_to_check = (
        [normalize_input_path(path) for path in args.files]
        if args.files
        else changed_files
    )
    print_report(files_to_check, changed_files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
