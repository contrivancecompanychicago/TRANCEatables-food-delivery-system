import json

import pytest

from tranceatables.january_ai import (
    JANUARY_AI_RESTAURANTS_URL,
    JanuaryAIConfigurationError,
    JanuaryAIResponseError,
    JanuaryAIRestaurantClient,
    JanuaryAISettings,
)


def test_status_maps_integration_without_exposing_secret() -> None:
    client = JanuaryAIRestaurantClient(
        JanuaryAISettings(True, "X-Partner-Key", "secret-value")
    )
    status = client.status()
    assert status["farm_to_fork_placement"] == "between kitchen_received and meal_prepared"
    assert status["automatic_state_transition"] is False
    assert "secret-value" not in json.dumps(status)


def test_live_fetch_is_disabled_by_default() -> None:
    client = JanuaryAIRestaurantClient(JanuaryAISettings(False, None, None))
    with pytest.raises(JanuaryAIConfigurationError, match="disabled"):
        client.list_restaurants()


def test_auth_configuration_is_required_when_enabled() -> None:
    client = JanuaryAIRestaurantClient(JanuaryAISettings(True, None, None))
    with pytest.raises(JanuaryAIConfigurationError, match="JANUARY_AI_AUTH_HEADER"):
        client.list_restaurants()


def test_read_only_fetch_passes_json_through_without_schema_guessing() -> None:
    captured = {}

    def fake_fetcher(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["auth"] = request.headers["X-partner-key"]
        captured["timeout"] = timeout
        return b'{"restaurants":[{"provider_field":"unchanged"}]}'

    client = JanuaryAIRestaurantClient(
        JanuaryAISettings(True, "X-Partner-Key", "test-key", 8),
        fetcher=fake_fetcher,
    )
    result = client.list_restaurants()
    assert captured == {
        "url": JANUARY_AI_RESTAURANTS_URL,
        "method": "GET",
        "auth": "test-key",
        "timeout": 8,
    }
    assert result["schema_normalized"] is False
    assert result["data"]["restaurants"][0]["provider_field"] == "unchanged"


def test_invalid_json_is_rejected() -> None:
    client = JanuaryAIRestaurantClient(
        JanuaryAISettings(True, "X-Partner-Key", "test-key"),
        fetcher=lambda request, timeout: b"not-json",
    )
    with pytest.raises(JanuaryAIResponseError):
        client.list_restaurants()
