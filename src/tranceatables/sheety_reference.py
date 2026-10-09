"""Read-only Sheety reference-data adapter for Stages 2.2 and 2.3.

This module reads curated restaurant, grocery-item, and meal-reference rows.
It deliberately exposes no write methods and has no dependency on robot mission
services.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class SheetyReferenceError(RuntimeError):
    """Raised when Sheety configuration, transport, or data is invalid."""


Transport = Callable[[Request, float], tuple[int, bytes]]


@dataclass(frozen=True)
class RestaurantReference:
    restaurant_id: str
    restaurant_name: str
    pickup_zone: str
    source: str
    sheety_row_id: int | None = None


@dataclass(frozen=True)
class SheetyReferenceSnapshot:
    restaurants: tuple[Mapping[str, Any], ...]
    grocery_items: tuple[Mapping[str, Any], ...]
    meal_references: tuple[Mapping[str, Any], ...]


def _default_transport(request: Request, timeout: float) -> tuple[int, bytes]:
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def _is_true(value: Any) -> bool:
    return value is True or (
        isinstance(value, str) and value.strip().lower() == "true"
    )


class SheetyReferenceClient:
    """Minimal GET-only client for the curated Sheety project."""

    ENDPOINTS = {
        "restaurants": "restaurants",
        "grocery_items": "groceryItems",
        "meal_references": "mealReferences",
    }

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        *,
        timeout: float = 30.0,
        transport: Transport | None = None,
    ) -> None:
        normalized = base_url.rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme != "https" or parsed.netloc != "api.sheety.co":
            raise SheetyReferenceError(
                "SHEETY_BASE_URL must use https://api.sheety.co"
            )
        if not bearer_token.strip():
            raise SheetyReferenceError("SHEETY_BEARER_TOKEN is required")
        if timeout <= 0:
            raise SheetyReferenceError("timeout must be positive")

        self.base_url = normalized
        self._bearer_token = bearer_token
        self.timeout = timeout
        self._transport = transport or _default_transport

    @classmethod
    def from_environment(cls) -> "SheetyReferenceClient":
        try:
            base_url = os.environ["SHEETY_BASE_URL"]
            bearer_token = os.environ["SHEETY_BEARER_TOKEN"]
        except KeyError as error:
            raise SheetyReferenceError(
                f"Missing required environment variable: {error.args[0]}"
            ) from error
        return cls(base_url, bearer_token)

    def _get_collection(self, key: str) -> tuple[Mapping[str, Any], ...]:
        endpoint = self.ENDPOINTS[key]
        request = Request(
            f"{self.base_url}/{endpoint}",
            method="GET",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._bearer_token}",
            },
        )
        try:
            status, body = self._transport(request, self.timeout)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise SheetyReferenceError(
                f"Sheety HTTP {error.code} for {endpoint}: {detail}"
            ) from error
        except URLError as error:
            raise SheetyReferenceError(
                f"Sheety request failed for {endpoint}: {error.reason}"
            ) from error

        if status != 200:
            raise SheetyReferenceError(
                f"Sheety returned HTTP {status} for {endpoint}"
            )
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SheetyReferenceError(
                f"Sheety returned invalid JSON for {endpoint}"
            ) from error

        if not isinstance(payload, dict) or set(payload) != {endpoint}:
            raise SheetyReferenceError(
                f"Expected one top-level key named {endpoint}"
            )
        records = payload[endpoint]
        if not isinstance(records, list) or not all(
            isinstance(record, dict) for record in records
        ):
            raise SheetyReferenceError(
                f"Expected {endpoint} to contain a list of objects"
            )
        return tuple(records)

    def get_restaurants(self) -> tuple[Mapping[str, Any], ...]:
        return self._get_collection("restaurants")

    def get_active_restaurant(self, restaurant_id: str) -> RestaurantReference:
        requested = restaurant_id.strip()
        if not requested:
            raise SheetyReferenceError("restaurant_id cannot be blank")
        matches = [
            record
            for record in self.get_restaurants()
            if str(record.get("restaurantId", "")).strip() == requested
        ]
        if len(matches) != 1:
            raise SheetyReferenceError(
                f"Expected exactly one restaurant named {requested}; found {len(matches)}"
            )
        record = matches[0]
        if not _is_true(record.get("active")):
            raise SheetyReferenceError(f"Restaurant is not active: {requested}")

        name = str(record.get("restaurantName", "")).strip()
        pickup_zone = str(record.get("pickupZone", "")).strip()
        source = str(record.get("source", "")).strip()
        if not name or not pickup_zone or not source:
            raise SheetyReferenceError(
                "Restaurant requires restaurantName, pickupZone, and source"
            )
        row_id = record.get("id")
        return RestaurantReference(
            restaurant_id=requested,
            restaurant_name=name,
            pickup_zone=pickup_zone,
            source=source,
            sheety_row_id=row_id if isinstance(row_id, int) else None,
        )

    def get_grocery_items(self) -> tuple[Mapping[str, Any], ...]:
        return self._get_collection("grocery_items")

    def get_meal_references(self) -> tuple[Mapping[str, Any], ...]:
        return self._get_collection("meal_references")

    def snapshot(self) -> SheetyReferenceSnapshot:
        return SheetyReferenceSnapshot(
            restaurants=self.get_restaurants(),
            grocery_items=self.get_grocery_items(),
            meal_references=self.get_meal_references(),
        )
