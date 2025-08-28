from moto import mock_aws
import boto3
import pytest
from datetime import datetime, timezone
from data_layer.dynamodb_client import put_item, get_item


TABLE_NAME = "session_metadata"

@pytest.fixture
def dynamodb_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "session_id", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName":"user_id", "AttributeType":"S"},
                {"AttributeName":"session_id", "AttributeType":"S"},
            ],
            BillingMode="PAY_PER_REQUEST"
        )
        table.wait_until_exists()
        yield table

@pytest.fixture
def sample_messages():
    return [
            {
            "message_id": "msg_001",
            "sender": "user",
            "timestamp": "2025-08-26T18:25:00+03:00",
            "content": "Plan a trip to Lviv for 1 day",
            "metadata": {
                "language": "en",
                "message_type": "text"}
            },
            {
                "message_id": "msg_002",
                "sender": "assistant",
                "timestamp": "2025-08-26T18:25:01+03:00",
                "trip_data": {
                    "destination": "Amsterdam",
                    "duration_days": 1,
                    "transportation": "public_transit",
                    "itinerary": [
                                {
                                    "day": 1,
                                    "location": "Amsterdam",
                                    "activities": [
                                        "Visit to the Van Gogh Museum",
                                        "Canal Walk",
                                        "Dinner at a Restaurant near Dam Square"],
                                    "accommodation": None,
                                    "budget_estimate": None
                                },],
                    },
                "metadata":{
                    "language": "en",
                    "message_type": "text"}
            }
         ]

@pytest.mark.unit
def test_put_and_get_item(dynamodb_table, sample_messages):
    user_id = "u123"
    session_id = "s456"
    summary = "Test session"
    started = datetime.now(timezone.utc).isoformat()
    messages = sample_messages

    result = put_item(dynamodb_table, user_id, session_id, summary, started, messages)
    assert result is True

    item = get_item(dynamodb_table, user_id, session_id)
    assert item["user_id"] == user_id
    assert item["session_id"] == session_id
    assert item["session_summary"] == summary
    assert item["started_at"] == started
    assert item["messages"] == messages