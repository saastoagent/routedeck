from __future__ import annotations

from pathlib import Path

from mypy import api as mypy_api


def test_session_provisioner_accepts_the_runtime_keyword_only_signature(
    tmp_path: Path,
) -> None:
    source = tmp_path / "valid_session_provisioner.py"
    source.write_text(
        """
from typing import assert_type

from routedeck_core.contracts.session import SessionSnapshot
from routedeck_fastapi.dependencies import SessionProvisioner

async def provision(
    *,
    session_id: str,
    request_id: str,
) -> SessionSnapshot:
    raise RuntimeError

provisioner: SessionProvisioner = provision

async def use() -> None:
    snapshot = await provisioner(session_id="session-1", request_id="request-1")
    assert_type(snapshot, SessionSnapshot)
""".lstrip(),
        encoding="utf-8",
    )

    stdout, _, status = mypy_api.run(
        [
            "--strict",
            "--no-incremental",
            "--explicit-package-bases",
            str(source),
        ]
    )

    assert status == 0, stdout


def test_session_provisioner_rejects_positional_signature_and_calls(
    tmp_path: Path,
) -> None:
    source = tmp_path / "invalid_session_provisioner.py"
    source.write_text(
        """
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_fastapi.dependencies import SessionProvisioner

async def positional(
    session_id: str,
    request_id: str,
    /,
) -> SessionSnapshot:
    raise RuntimeError

provisioner: SessionProvisioner = positional

async def use() -> None:
    await provisioner("session-1", "request-1")
""".lstrip(),
        encoding="utf-8",
    )

    stdout, _, status = mypy_api.run(
        [
            "--strict",
            "--no-incremental",
            "--explicit-package-bases",
            str(source),
        ]
    )

    assert status == 1
    assert 'Incompatible types in assignment' in stdout
    assert 'Too many positional arguments for "__call__" of "SessionProvisioner"' in stdout
