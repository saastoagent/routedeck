"""Validate RouteDeck's canonical documentation authority and local links."""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "critical_prompt.md",
    "context.md",
    "docs/route-deck-reference.md",
    "architecture/feature-coverage.md",
    "architecture/code-map.md",
    "architecture/documentation-map.md",
    "SYSTEM_FLOW_INDEX.md",
    "test_index/README.md",
    "structure.md",
)
RETIRED_ACTIVE_TERMS = (
    "ApplicationSpec",
    "FeatureSpec",
    "CompiledRouteDeckApp",
    "MEDUSA_APP_SPEC",
    "RouteDeckApp.compile",
    "Full Flow",
    "Core Integration",
    "docs/superpowers/plans/",
    "routedeck_sqlite",
    "react/tests",
)
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def active_markdown_files() -> list[Path]:
    files: set[Path] = set()
    for relative in (
        "README.md",
        "critical_prompt.md",
        "context.md",
        "context_pipeline.md",
        "instructions.md",
        "work_prompt.md",
        "structure.md",
        "SYSTEM_FLOW_INDEX.md",
        "architecture",
        "decisions",
        "docs",
        "skills",
        "test_index",
        "plans",
        "wiki",
        "examples/hello-world/README.md",
        "examples/medusa-agent/README.md",
    ):
        path = PROJECT_ROOT / relative
        if path.is_file() and path.suffix == ".md":
            files.add(path)
        elif path.is_dir():
            files.update(path.rglob("*.md"))
    return sorted(
        path
        for path in files
        if "archive" not in path.relative_to(PROJECT_ROOT).parts
        and "migration" not in path.relative_to(PROJECT_ROOT).parts
    )


def _link_target(source: Path, raw_target: str) -> Path | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    target = target.split("#", 1)[0].split("?", 1)[0]
    if not target:
        return None
    return (source.parent / target).resolve()


def validate() -> list[str]:
    failures: list[str] = []
    for relative in REQUIRED_FILES:
        if not (PROJECT_ROOT / relative).is_file():
            failures.append(f"missing required canonical file: {relative}")

    active_files = active_markdown_files()
    for path in active_files:
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        if "decisions" not in path.relative_to(PROJECT_ROOT).parts:
            for retired in RETIRED_ACTIVE_TERMS:
                if retired in text:
                    failures.append(f"retired active term {retired!r}: {relative}")
        for match in LINK_PATTERN.finditer(text):
            target = _link_target(path, match.group(1))
            if target is not None and not target.exists():
                failures.append(
                    f"broken local link: {relative} -> {match.group(1)}"
                )

    context = (PROJECT_ROOT / "context.md").read_text(encoding="utf-8")
    for required in ("ADR-006", "feature-coverage.md", "Known Gaps"):
        if required not in context:
            failures.append(f"context.md missing current marker: {required}")

    reference = (PROJECT_ROOT / "docs/route-deck-reference.md").read_text(
        encoding="utf-8"
    )
    for required in ("`Application` and `Feature`", "Session selection"):
        if required not in reference:
            failures.append(f"route-deck-reference.md missing marker: {required}")
    return failures


def main() -> int:
    files = active_markdown_files()
    failures = validate()
    print("RouteDeck context architecture check")
    print(f"Active Markdown files checked: {len(files)}")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        print(f"Result: failed ({len(failures)} issues)")
        return 1
    print("Result: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
