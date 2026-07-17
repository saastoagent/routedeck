from pathlib import Path


ROOT = Path(__file__).parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_active_context_uses_the_current_authority_and_coverage_spine() -> None:
    context = _read("context.md")
    decisions = _read("decisions/README.md")

    assert "ADR-006-framework-owned-runtime-and-conversation-boundary.md" in context
    assert "architecture/feature-coverage.md" in context
    assert "Known Gaps" in context
    assert "ADR-004-routedeck-medusa-consumer-driven-runtime.md" in decisions
    assert "docs/superpowers/plans/" not in context
    assert "ApplicationSpec" not in context
    assert "FeatureSpec" not in context


def test_critical_prompt_names_only_the_live_authoring_and_runtime_boundary() -> None:
    prompt = _read("critical_prompt.md")

    for marker in (
        "ADR-006",
        "`Application`/`Feature`",
        "RouteDeckOperationRunner",
        "Session Selection Boundary",
    ):
        assert marker in prompt
    for retired in (
        "ApplicationSpec",
        "FeatureSpec",
        "Full Flow",
        "Core Integration",
        "Corpus",
    ):
        assert retired not in prompt


def test_completed_plans_and_designs_are_archived_not_active() -> None:
    archive = ROOT / "docs" / "archive"
    assert (archive / "README.md").is_file()
    assert (archive / "superpowers" / "plans").is_dir()
    assert (
        archive
        / "superpowers"
        / "plans"
        / "2026-07-15-routedeck-runtime-boundary-refactor.md"
    ).is_file()
    assert not (ROOT / "docs" / "superpowers" / "plans").exists()
    assert (
        archive
        / "superpowers"
        / "specs"
        / "2026-07-17-context-architecture-coverage-design.md"
    ).is_file()


def test_documentation_coverage_checker_does_not_read_git_state() -> None:
    checker = _read("scripts/check_doc_coverage.py")

    assert "subprocess" not in checker
    assert "changed_files_from_git" not in checker
    assert "all_source_files" in checker
    assert '"--files"' in checker
