from scripts import check_doc_coverage


def test_local_worktrees_are_pruned_from_documentation_coverage() -> None:
    worktree_file = (
        check_doc_coverage.PROJECT_ROOT
        / ".worktrees"
        / "local-checkout"
        / "node_modules"
        / "broken-link.ts"
    )

    assert check_doc_coverage._excluded(worktree_file)
    assert not any(
        path.startswith(".worktrees/")
        for path in check_doc_coverage.all_source_files()
    )
