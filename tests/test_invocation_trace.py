from routedeck_langgraph.invocation_trace import _sanitize


def test_trace_sanitization_preserves_usage_but_redacts_credentials() -> None:
    assert _sanitize(
        {
            "input_tokens": 2117,
            "output_tokens": 3,
            "access_token": "private",
            "api_key": "private",
        }
    ) == {
        "input_tokens": 2117,
        "output_tokens": 3,
        "access_token": "[redacted]",
        "api_key": "[redacted]",
    }
