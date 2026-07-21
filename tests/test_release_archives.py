from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.verify_release_archives import (
    ArchiveVerificationError,
    verify_npm_archive,
    verify_python_wheel,
)


def _write_zip(path: Path, names: tuple[str, ...]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            archive.writestr(name, "content")


def _write_tgz(path: Path, names: tuple[str, ...]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name in names:
            data = b"content"
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


def test_python_wheel_requires_each_advertised_package_and_rejects_tests(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "routedeck_core-0.1.0-py3-none-any.whl"
    expected = (
        "routedeck_core/__init__.py",
        "routedeck_fastapi/__init__.py",
        "routedeck_langgraph/__init__.py",
        "routedeck_sqlalchemy/__init__.py",
        "routedeck_testing/__init__.py",
        "routedeck_core-0.1.0.dist-info/METADATA",
    )
    _write_zip(wheel, expected)

    result = verify_python_wheel(wheel)
    assert result["file_count"] == len(expected)

    _write_zip(wheel, expected + ("tests/test_runtime.py",))
    with pytest.raises(ArchiveVerificationError, match="forbidden"):
        verify_python_wheel(wheel)


def test_npm_archive_requires_runtime_entrypoints_and_rejects_build_debris(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "routedeck-core-0.1.0.tgz"
    expected = (
        "package/package.json",
        "package/README.md",
        "package/LICENSE",
        "package/dist/index.js",
        "package/dist/index.d.ts",
    )
    _write_tgz(archive, expected)

    result = verify_npm_archive(archive)
    assert result["file_count"] == len(expected)

    _write_tgz(archive, expected + ("package/dist/client.test.js",))
    with pytest.raises(ArchiveVerificationError, match="forbidden"):
        verify_npm_archive(archive)
