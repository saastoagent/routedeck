from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_hello_world_example_runs_from_the_current_checkout() -> None:
    environment = dict(os.environ)
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(ROOT), existing_pythonpath) if part
    )

    result = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "hello-world" / "hello_world.py")],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        check=True,
        text=True,
    )

    assert result.stdout.splitlines() == [
        "RouteDeck application: hello-world",
        "Entry node: hello.home",
        "Route: /",
        "Nodes: hello.home",
    ]
