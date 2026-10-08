import json
from urllib.error import HTTPError

import pytest

from tranceatables.sheety_reference import (
    SheetyReferenceClient,
    SheetyReferenceError,
)


BASE_URL = (
    "https://api.sheety.co/project-id/"
    "makeDeepHumanMealsServicesStage22CleanedReview"
)


def response(payload, status=200):
    body = json.dumps(payload).encode()

    def transport(request, timeout):
        assert request.get_method() == "GET"
        assert request.headers["Authorization"] == "Bearer test-secret"
        assert timeout == 30.0
        return status, body

    return transport


def test_reads_each_reference_collection():
    payloads = {
        "restaurants": {"restaurants": []},
        "groceryItems": {"groceryItems": [{"restaurantId": "R-1"}]},
        "mealReferences": {
            "mealReferences": [{"mealReferenceId": "MEAL-1"}]
        },
    }

    def transport(request, timeout):
        endpoint = request.full_url.rsplit("/", 1)[-1]
        return 200, json.dumps(payloads[endpoint]).encode()

    client = SheetyReferenceClient(
        BASE_URL, "test-secret", transport=transport
    )

    snapshot = client.snapshot()

    assert snapshot.restaurants == ()
    assert snapshot.grocery_items[0]["restaurantId"] == "R-1"
    assert snapshot.meal_references[0]["mealReferenceId"] == "MEAL-1"


def test_rejects_non_sheety_or_insecure_base_url():
    for url in (
        "http://api.sheety.co/project",
        "https://example.com/project",
    ):
        with pytest.raises(SheetyReferenceError):
            SheetyReferenceClient(url, "test-secret")


def test_requires_nonempty_token():
    with pytest.raises(SheetyReferenceError):
        SheetyReferenceClient(BASE_URL, "  ")


def test_rejects_unexpected_schema():
    client = SheetyReferenceClient(
        BASE_URL,
        "test-secret",
        transport=response({"wrongKey": []}),
    )
    with pytest.raises(SheetyReferenceError, match="top-level key"):
        client.get_restaurants()


def test_rejects_non_object_records():
    client = SheetyReferenceClient(
        BASE_URL,
        "test-secret",
        transport=response({"groceryItems": ["not-an-object"]}),
    )
    with pytest.raises(SheetyReferenceError, match="list of objects"):
        client.get_grocery_items()


def test_reports_http_status_without_exposing_token():
    client = SheetyReferenceClient(
        BASE_URL,
        "test-secret",
        transport=response({"error": "unauthorized"}, status=401),
    )
    with pytest.raises(SheetyReferenceError) as captured:
        client.get_restaurants()
    assert "401" in str(captured.value)
    assert "test-secret" not in str(captured.value)


def test_from_environment(monkeypatch):
    monkeypatch.setenv("SHEETY_BASE_URL", BASE_URL)
    monkeypatch.setenv("SHEETY_BEARER_TOKEN", "test-secret")

    client = SheetyReferenceClient.from_environment()

    assert client.base_url == BASE_URL
