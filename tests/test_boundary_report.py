from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_boundaries import (
    REQUIRED_CHECK_NAMES,
    build_boundary_report,
    check_browser_network,
    main,
)


def test_boundary_report_computes_all_approved_checks() -> None:
    report = build_boundary_report()

    assert tuple(check["name"] for check in report["checks"]) == REQUIRED_CHECK_NAMES
    assert report["status"] == "pass"
    assert report["violation_count"] == 0
    for check in report["checks"]:
        assert check["status"] == "pass"
        assert check["violations"] == []
        assert isinstance(check["evidence"], dict)
        assert check["evidence"]
    architectural_review = next(
        check for check in report["checks"] if check["name"] == "architectural_review"
    )
    assert architectural_review["evidence"]["invariants"][
        "standalone_medusa_demo_uses_repo_local_pinned_server"
    ]
    assert architectural_review["evidence"]["standalone_medusa_server"][
        "compose_build_contexts"
    ] == ["../medusa", "../medusa"]


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
    assert '"name": "architectural_review"' in rendered
    assert '"violation_count": 0' in rendered
