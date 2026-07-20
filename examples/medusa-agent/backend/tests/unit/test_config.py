from __future__ import annotations

from pydantic import SecretStr

from medusa_agent.config import Settings


def test_runtime_and_http_policy_are_explicit_configuration() -> None:
    settings = Settings(
        medusa_base_url="http://127.0.0.1:9100",
        medusa_publishable_key=SecretStr("pk_test"),
        medusa_region_id="region-test",
        medusa_country_code="dk",
        medusa_sales_channel_id="channel-test",
        medusa_payment_provider_id="pp_system_default",
        routedeck_database_url="sqlite+pysqlite:///runtime.sqlite",
        routedeck_state_encryption_key=SecretStr("state-key"),
        openai_api_key=None,
        openai_buyer_model="model-buyer",
        openai_entry_model="model-entry",
        medusa_timeout_seconds=15,
        routedeck_instance_id="medusa-agent-local",
        routedeck_review_ttl_seconds=900,
        routedeck_resume_capability_ttl_seconds=86400,
        routedeck_worker_count=1,
        routedeck_guest_cookie_name="routedeck_guest",
        routedeck_guest_cookie_secure=False,
        routedeck_guest_cookie_path="/",
        routedeck_browser_origins=(
            "http://127.0.0.1:5198",
            "http://localhost:5198",
        ),
    )

    assert settings.routedeck_instance_id == "medusa-agent-local"
    assert settings.routedeck_review_ttl_seconds == 900
    assert settings.routedeck_resume_capability_ttl_seconds == 86400
    assert settings.routedeck_worker_count == 1
    assert settings.routedeck_guest_cookie_secure is False
    assert tuple(str(item).rstrip("/") for item in settings.routedeck_browser_origins) == (
        "http://127.0.0.1:5198",
        "http://localhost:5198",
    )
