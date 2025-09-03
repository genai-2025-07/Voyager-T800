from moto import mock_aws
import boto3
import pytest
from datetime import datetime, timezone
from data_layer.dynamodb_client import DynamoDBClient, SessionMetadata


TABLE_NAME = "session_metadata"

@pytest.fixture
def dynamodb_table():
    """
    Pytest fixture that creates a temporary mock DynamoDB table for testing.
    This fixture uses `moto`'s `mock_aws` to simulate DynamoDB behavior
    without requiring access to a real AWS account. It creates a table
    with the following schema:
      - Partition key: `user_id` (String)
      - Sort key: `session_id` (String)

    The table is configured with on-demand billing mode (`PAY_PER_REQUEST`).

    Yields:
        boto3.resources.factory.dynamodb.Table: A reference to the mocked
        DynamoDB table, which can be used in tests to insert, query, and
        retrieve items.
    """
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
    """
    Pytest fixture that creates list of sample messages.
    """
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
def test_put_item(dynamodb_table, sample_messages):
    """
    Unit test for verifying insertion of items in the DynamoDB table.

    This test ensures that:
      1. The `put_item` function successfully stores an item in the table.
      2. The item is properly stored with all the expected fields.

    The test uses a mocked DynamoDB table (via the `dynamodb_table` fixture)
    and a predefined list of sample messages (via the `sample_messages` fixture).

    Assertions:
        - `put_item` should return True after successful insertion.
        - The item should be retrievable from the table with correct data.
    """

    obj= DynamoDBClient(dynamodb_table)

    sample_item=SessionMetadata(user_id="u123", 
                                session_id="s456", 
                                session_summary="Test session", 
                                started_at=datetime.now(timezone.utc).isoformat(), 
                                messages=sample_messages)
    
    result = obj.put_item(sample_item)
    assert result == 200

    response = dynamodb_table.scan()
    items = response.get("Items", [])

    assert len(items) > 0, f"Table contains {len(items)} item(s)"
    assert items[0]['user_id']==sample_item.user_id
    assert items[0]['session_id']==sample_item.session_id
    

@pytest.mark.unit
def test_get_item(dynamodb_table, sample_messages):
    """
    Unit test for verifying retrieval of items from the DynamoDB table.

    This test ensures that:
      1. The `get_item` function successfully retrieves an item from the table.
      2. All retrieved fields match the originally stored data.

    The test first inserts an item using `put_item`, then tests the retrieval
    functionality using `get_item`.

    Assertions:
        - Retrieved item should contain:
            * Matching `user_id` and `session_id`.
            * Correct `session_summary`.
            * Correct `started_at` timestamp.
            * The same `messages` list that was inserted.
    """

    obj= DynamoDBClient(dynamodb_table)

    sample_item = SessionMetadata(
        user_id="u789", 
        session_id="s012", 
        session_summary="Another test session", 
        started_at=datetime.now(timezone.utc).isoformat(), 
        messages=sample_messages
    )

    put_result = obj.put_item(sample_item)
    assert put_result == 200

    item = obj.get_item(sample_item)
    assert item is not None

    assert item["user_id"] == sample_item.user_id
    assert item["session_id"] == sample_item.session_id
    assert item["session_summary"] == sample_item.session_summary
    assert item["started_at"] == sample_item.started_at
    assert item["messages"] == sample_item.messages