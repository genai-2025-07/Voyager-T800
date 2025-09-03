from ast import List
import boto3
from botocore.exceptions import ClientError
from typing import List, Dict, Optional
from pydantic import BaseModel
import os

import logging
logger = logging.getLogger(__name__)

# region_name=os.getenv("AWS_REGION", 'us-east-2')
#dynamodb= boto3.resource('dynamodb', region_name= region_name)

# dynamodb= boto3.resource('dynamodb', endpoint_url='http://localhost:8000', region_name= region_name) with endpoint for local DynamoDB

# table_name= os.getenv("DYNAMODB_TABLE", "session_metadata")
# table = dynamodb.Table(table_name)

class SessionMetadata(BaseModel):
    user_id: str
    session_id: str
    session_summary: str
    started_at: str
    messages: List[Dict]


class QueryParams(BaseModel):
    key_condition_expression: Optional[str] = None
    filter_expression: Optional[str] = None
    projection_expression: Optional[str] = None
    index_name: Optional[str] = None
    limit: Optional[int] = None


class ScanParams(BaseModel):
    filter_expression: Optional[str] = None
    projection_expression: Optional[str] = None
    limit: Optional[int] = None


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
        if table is None:
            self.region_name =os.getenv("AWS_REGION", 'us-east-2')
            self.table_name = os.getenv("DYNAMODB_TABLE", "session_metadata")
            
            self.dynamodb = boto3.resource('dynamodb', region_name=self.region_name)
            table= self.dynamodb.Table(self.table_name)
        self.table = table 
        
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
                    "user_id": session_metadata.user_id,
                    "session_id": session_metadata.session_id,
                    "session_summary": session_metadata.session_summary,
                    "started_at": session_metadata.started_at,
                    "messages": session_metadata.messages
                }
            )
            return response["ResponseMetadata"]["HTTPStatusCode"]
        except ClientError as e:
            logger.error(f"Error putting item: {e.response['Error']['Message']}")
            raise

    def get_item(self, session_metadata: SessionMetadata) -> Dict:
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
            response = self.table.get_item(
                Key={
                    "user_id": session_metadata.user_id, 
                    "session_id": session_metadata.session_id
                }
            )
            return response['Item']
        except ClientError as e:
            logger.error(f"Error getting item: {e.response['Error']['Message']}")
            raise

    def query_table(self, query_params: QueryParams, **kwargs) -> Dict:
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
            logger.error(f"Error querying table: {e.response['Error']['Message']}")
            raise

    def scan_table(self, scan_params: ScanParams, **kwargs) -> Dict:
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
            logger.error(f"Error scanning table: {e.response['Error']['Message']}")
            raise

    def query_by_user_id(self, user_id: str, limit: Optional[int] = None) -> Dict:
        """
        Convenience method to query items by user_id.
        
        Args:
            user_id: The user ID to query for.
            limit: Optional limit on the number of results.
        
        Returns:
            dict: Dictionary containing the query results.
        """
        return self.query_table(
            query_params=QueryParams(key_condition_expression='user_id = :user_id'),
            ExpressionAttributeValues={':user_id': user_id},
            Limit=limit
        )





            
