import logging

import boto3

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from pydantic import BaseModel

from app.config.config import settings


logger = logging.getLogger(__name__)

# region_name=os.getenv("AWS_REGION", 'us-east-2')
# dynamodb= boto3.resource('dynamodb', region_name= region_name)

# dynamodb= boto3.resource('dynamodb', endpoint_url='http://localhost:8000', region_name= region_name) with endpoint for local DynamoDB

# table_name= os.getenv("DYNAMODB_TABLE", "session_metadata")
# table = dynamodb.Table(table_name)


class SessionMetadata(BaseModel):
    user_id: str
    session_id: str
    session_summary: str
    started_at: str
    messages: list[dict]


class QueryParams(BaseModel):
    key_condition_expression: str | None = None
    filter_expression: str | None = None
    projection_expression: str | None = None
    index_name: str | None = None
    limit: int | None = None


class ScanParams(BaseModel):
    filter_expression: str | None = None
    projection_expression: str | None = None
    limit: int | None = None


class DynamoDBClient:
    """
    A class to handle DynamoDB operations for session metadata.
    """

    def __init__(self, table=None):
        """
        Initialize the DynamoDB client.

        Args:
            table_name: The DynamoDB table name. Defaults to environment variable DYNAMODB_TABLE.
            region_name: The AWS region. Defaults to environment variable AWS_REGION.
        """
        if table is not None:
            self.table = table
        else:
            self.region_name = settings.aws_region
            self.table_name = settings.dynamodb_table

            use_local_dynamodb = settings.use_local_dynamodb

            if use_local_dynamodb:
                endpoint_url = settings.dynamodb_endpoint_url
                self.dynamodb = boto3.resource(
                    'dynamodb',
                    region_name=self.region_name,
                    endpoint_url=endpoint_url,
                    aws_access_key_id='dummy',
                    aws_secret_access_key='dummy',
                )
                logger.info(f'Using local DynamoDB at {endpoint_url}')
            else:
                self.dynamodb = boto3.resource('dynamodb', region_name=self.region_name)
                logger.info(f'Using AWS DynamoDB in region {self.region_name}')

            self.table = self.dynamodb.Table(self.table_name)

    def put_item(self, session_metadata: SessionMetadata) -> int:
        """
        Adds an item to the table.

        Args:
            session_metadata: The session metadata to put in the table.

        Returns:
            int: HTTP status code of the response.

        Raises:
            ClientError: If there's an error during the put operation.
        """
        try:
            response = self.table.put_item(
                Item={
                    'user_id': session_metadata.user_id,
                    'session_id': session_metadata.session_id,
                    'session_summary': session_metadata.session_summary,
                    'started_at': session_metadata.started_at,
                    'messages': session_metadata.messages,
                }
            )
            return response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
        except ClientError:
            logger.error('Failed to put item into DynamoDB')
            raise

    def get_item(self, user_id: str, session_id: str) -> dict:
        """
        Returns an item from table, using unique identifier of user and session.

        Args:
            session_metadata: The session metadata to get from the table.

        Returns:
            dict: Dictionary with the retrieved item under the 'Item' key.

        Raises:
            ClientError: If there's an error during the get operation.
        """
        try:
            response = self.table.get_item(Key={'user_id': user_id, 'session_id': session_id})
            item = response.get('Item')
            if item is not None:
                return item
            else:
                return None
        except ClientError as e:
            logger.error(f'Error getting item: {e.response["Error"]["Message"]}')
            raise

    def query_table(self, query_params: QueryParams, **kwargs) -> dict:
        """
        Queries items from a DynamoDB table using various query parameters.

        Args:
            query_params: The query parameters to use.
            **kwargs: Additional query parameters like ExpressionAttributeNames, ExpressionAttributeValues, etc.

        Returns:
            dict: Dictionary containing the query results with 'Items', 'Count', 'ScannedCount', etc.

        Raises:
            ClientError: If there's an error during the query operation.
        """
        try:
            query_params_dict = query_params.model_dump(exclude_none=True)
            query_params_dict.update(kwargs)

            response = self.table.query(**query_params_dict)
            return response

        except ClientError as e:
            logger.error(f'Error querying table: {e.response["Error"]["Message"]}')
            raise

    def scan_table(self, scan_params: ScanParams, **kwargs) -> dict:
        """
        Scans items from a DynamoDB table using various scan parameters.

        Args:
            scan_params: The scan parameters to use.
            **kwargs: Additional scan parameters like ExpressionAttributeNames, ExpressionAttributeValues, etc.

        Returns:
            dict: Dictionary containing the scan results with 'Items', 'Count', 'ScannedCount', etc.

        Raises:
            ClientError: If there's an error during the scan operation.
        """
        try:
            scan_params_dict = scan_params.model_dump(exclude_none=True)
            scan_params_dict.update(kwargs)

            response = self.table.scan(**scan_params_dict)
            return response

        except ClientError as e:
            logger.error(f'Error scanning table: {e.response["Error"]["Message"]}')
            raise

    def query_by_user_id(self, user_id: str, limit: int | None = None) -> dict:
        """
        Convenience method to query items by user_id.

        Args:
            user_id: The user ID to query for.
            limit: Optional limit on the number of results.

        Returns:
            dict: Dictionary containing the query results.
        """
        params = {
            'KeyConditionExpression': Key('user_id').eq(user_id),
        }
        if limit is not None:
            params['Limit'] = limit
        return self.table.query(**params)

    def delete_item(self, user_id: str, session_id: str) -> int:
        """
        Delete a specific item identified by user_id and session_id.

        Returns:
            int: HTTP status code of the response.
        """
        try:
            response = self.table.delete_item(Key={'user_id': user_id, 'session_id': session_id})
            return response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
        except ClientError as e:
            logger.error(f'Error deleting item: {e.response["Error"]["Message"]}')
            raise

    def list_sessions(self, user_id: str) -> list[dict]:
        """
        List all sessions for a given user_id.
        """
        try:
            response = self.table.query(KeyConditionExpression=Key('user_id').eq(user_id))
            return response.get('Items', [])
        except ClientError as e:
            logger.error(f'Error listing sessions: {e.response["Error"]["Message"]}')
            raise
