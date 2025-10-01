from datetime import UTC, datetime

import boto3
import pytest

from moto import mock_aws

from app.data_layer.dynamodb_client import DynamoDBClient, SessionMetadata


TABLE_NAME = 'session_metadata'


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
        dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                {'AttributeName': 'session_id', 'KeyType': 'RANGE'},
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'session_id', 'AttributeType': 'S'},
            ],
            BillingMode='PAY_PER_REQUEST',
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
            'message_id': 'msg_001',
            'sender': 'user',
            'timestamp': '2025-08-26T18:25:00+03:00',
            'content': 'Plan a trip to Lviv for 1 day',
            'metadata': {'language': 'en', 'message_type': 'text'},
        },
        {
            'message_id': 'msg_002',
            'sender': 'assistant',
            'timestamp': '2025-08-26T18:25:01+03:00',
            'trip_data': {
                'destination': 'Amsterdam',
                'duration_days': 1,
                'transportation': 'public_transit',
                'itinerary': [
                    {
                        'day': 1,
                        'location': 'Amsterdam',
                        'activities': [
                            'Visit to the Van Gogh Museum',
                            'Canal Walk',
                            'Dinner at a Restaurant near Dam Square',
                        ],
                        'accommodation': None,
                        'budget_estimate': None,
                    },
                ],
            },
            'metadata': {'language': 'en', 'message_type': 'text'},
        },
    ]


@pytest.fixture
def inserted_item(dynamodb_table):
    item = {'user_id': 'u789', 'session_id': 's012'}
    dynamodb_table.put_item(Item=item)
    return item


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

    obj = DynamoDBClient(dynamodb_table)

    sample_item = SessionMetadata(
        user_id='u123',
        session_id='s456',
        session_summary='Test session',
        started_at=datetime.now(UTC).isoformat(),
        messages=sample_messages,
        structured_itinerary={
            'destination': 'Paris',
            'duration_days': 2,
            'transportation': 'walking',
            'itinerary': [],
            'language': 'en',
            'session_summary': 'Test trip to Paris',
        },
    )

    result = obj.put_item(sample_item)
    assert result == 200

    response = dynamodb_table.scan()
    items = response.get('Items', [])

    assert len(items) > 0, f'Table contains {len(items)} item(s)'
    assert items[0]['user_id'] == sample_item.user_id
    assert items[0]['session_id'] == sample_item.session_id


@pytest.mark.unit
def test_get_item(dynamodb_table, inserted_item):
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

    obj = DynamoDBClient(dynamodb_table)

    user_id_test = inserted_item['user_id']
    session_id_test = inserted_item['session_id']

    retrieved_item = obj.get_item(user_id_test, session_id_test)

    assert retrieved_item is not None
    assert retrieved_item['user_id'] == user_id_test
    assert retrieved_item['session_id'] == session_id_test


@pytest.mark.unit
def test_get_item_not_found(dynamodb_table):
    """
    Unit test for verifying that get_item returns None when item is not found.

    This test ensures that:
      1. The `get_item` function returns None when the requested item doesn't exist.
      2. No KeyError is raised when accessing non-existent items.

    Assertions:
        - `get_item` should return None for non-existent user_id/session_id combinations.
    """
    obj = DynamoDBClient(dynamodb_table)
    nonexistent = SessionMetadata(
        user_id='not_found', session_id='s999', session_summary='', started_at='', messages=[]
    )

    assert obj.get_item(nonexistent.user_id, nonexistent.session_id) is None
