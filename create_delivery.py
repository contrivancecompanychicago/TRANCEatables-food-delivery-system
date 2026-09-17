import os
import requests

DOORDASH_TOKEN = os.environ["DOORDASH_TOKEN"]

endpoint = "https://openapi.doordash.com/drive/v2/deliveries/"

headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {DOORDASH_TOKEN}",
    "Content-Type": "application/json",
}

request_body = {
    "external_delivery_id": "D-12345",
    "pickup_address": "901 Market Street 6th Floor San Francisco, CA 94103",
    "pickup_business_name": "Wells Fargo SF Downtown",
    "pickup_phone_number": "+16505555555",
    "pickup_instructions": "Enter gate code 1234 on the callbox.",
    "dropoff_address": "901 Market Street 6th Floor San Francisco, CA 94103",
    "dropoff_business_name": "Wells Fargo SF Downtown",
    "dropoff_phone_number": "+16505555555",
    "dropoff_instructions": "Enter gate code 1234 on the callbox.",
    "order_value": 1999,
}

try:
    response = requests.post(
        endpoint,
        headers=headers,
        json=request_body,
        timeout=30,
    )

    print(f"HTTP status: {response.status_code}")
    print(response.text)

    response.raise_for_status()

except requests.RequestException as error:
    print(f"DoorDash request failed: {error}")
    raise
