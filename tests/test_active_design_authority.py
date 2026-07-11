from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_active_context_authorizes_the_medusa_runtime() -> None:
    context = (ROOT / "context.md").read_text(encoding="utf-8")
    decisions = (ROOT / "decisions" / "README.md").read_text(encoding="utf-8")
    assert "ADR-004-routedeck-medusa-consumer-driven-runtime.md" in context
    assert "ADR-004-routedeck-medusa-consumer-driven-runtime.md" in decisions
    assert "No replacement implementation plan is active" not in context
    assert "ask whether to use local, Mac mini" not in context


def test_retired_gate_is_not_current_authority() -> None:
    prompt = (ROOT / "critical_prompt.md").read_text(encoding="utf-8")
    assert "ADR-004" in prompt
    assert "new SQLite/event/outbox durability" not in prompt
    assert "independent example projects" not in prompt
