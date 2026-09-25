"""Conservative read-only adapter for the January AI restaurant endpoint."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib.request import Request, urlopen


JANUARY_AI_RESTAURANTS_URL = "https://partners.january.ai/v1.2/restaurants"


class JanuaryAIConfigurationError(RuntimeError):
    """Raised when the opt-in January AI integration is not safely configured."""


class JanuaryAIResponseError(RuntimeError):
    """Raised when January AI returns a response the adapter cannot safely read."""


Fetcher = Callable[[Request, float], bytes]


def _default_fetcher(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS URL
        return response.read()


@dataclass(frozen=True)
class JanuaryAISettings:
    enabled: bool
    auth_header: str | None
    auth_value: str | None
    timeout_seconds: float = 15.0

    @classmethod
    def from_environment(cls) -> "JanuaryAISettings":
        enabled = os.getenv("TRANCEATABLES_ENABLE_JANUARY_AI", "false").lower() == "true"
        return cls(
            enabled=enabled,
            auth_header=os.getenv("JANUARY_AI_AUTH_HEADER"),
            auth_value=os.getenv("JANUARY_AI_AUTH_VALUE"),
            timeout_seconds=float(os.getenv("JANUARY_AI_TIMEOUT_SECONDS", "15")),
        )


class JanuaryAIRestaurantClient:
    """Fetch restaurant reference data without assuming the provider's JSON schema."""

    def __init__(
        self,
        settings: JanuaryAISettings,
        *,
        fetcher: Fetcher = _default_fetcher,
    ) -> None:
        self.settings = settings
        self.fetcher = fetcher

    def status(self) -> dict[str, Any]:
        configured = bool(self.settings.auth_header and self.settings.auth_value)
        return {
            "provider": "January AI",
            "endpoint": JANUARY_AI_RESTAURANTS_URL,
            "enabled": self.settings.enabled,
            "authorization_configured": configured,
            "mode": "read-only restaurant reference data",
            "farm_to_fork_placement": "between kitchen_received and meal_prepared",
            "order_placement": "restaurant discovery before draft order creation",
            "automatic_state_transition": False,
            "response_schema": "unverified-pass-through",
            "simulation_boundary": (
                "The adapter cannot place orders, dispatch robots, contact restaurants, "
                "or change order/trace state."
            ),
        }

    def list_restaurants(self) -> dict[str, Any]:
        if not self.settings.enabled:
            raise JanuaryAIConfigurationError(
                "January AI is disabled; set TRANCEATABLES_ENABLE_JANUARY_AI=true to opt in"
            )
        if not self.settings.auth_header or not self.settings.auth_value:
            raise JanuaryAIConfigurationError(
                "set JANUARY_AI_AUTH_HEADER and JANUARY_AI_AUTH_VALUE from official partner documentation"
            )
        if self.settings.timeout_seconds <= 0:
            raise JanuaryAIConfigurationError("timeout must be positive")

        request = Request(
            JANUARY_AI_RESTAURANTS_URL,
            headers={
                "Accept": "application/json",
                self.settings.auth_header: self.settings.auth_value,
            },
            method="GET",
        )
        raw = self.fetcher(request, self.settings.timeout_seconds)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise JanuaryAIResponseError("restaurant endpoint did not return valid JSON") from error
        if not isinstance(data, (dict, list)):
            raise JanuaryAIResponseError("restaurant JSON must be an object or array")
        return {
            "provider": "January AI",
            "endpoint": JANUARY_AI_RESTAURANTS_URL,
            "read_only": True,
            "schema_normalized": False,
            "data": data,
        }
