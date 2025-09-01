from ast import List
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from typing import List, Dict
from pydantic import BaseModel
import os

import logging
logger = logging.getLogger(__name__)

# region_name=os.getenv("AWS_REGION", 'us-east-2')
# dynamodb= boto3.resource('dynamodb', region_name= region_name)

# table_name= os.getenv("DYNAMODB_TABLE", "session_metadata")
# table = dynamodb.Table(table_name)

class SessionMetadata(BaseModel):
    user_id: str
    session_id: str
    session_summary: str
    started_at: str
    messages: List[Dict]

def put_item(db_table, session_metadata:SessionMetadata):
    """
    Adds an item to the table.

    Args:
        db_table: The table to put data in it.
        session_metadata: The session metadata to put in the table.
    """
    try:
        db_table.put_item(
            Item={"user_id":session_metadata.user_id,
            "session_id":session_metadata.session_id,
            "session_summary":session_metadata.session_summary,
            "started_at":session_metadata.started_at,
            "messages":session_metadata.messages}
        )
        return True
    except ClientError as e:
        logger.error (f"Error putting item: {e.response['Error']['Message']}")
        raise


def get_item(db_table, session_metadata:SessionMetadata):
    """
    Returns an item from table, using unique identifier of user and session.

    Args:
        db_table: The table to get data from.
        session_metadata: The session metadata to get from the table.

    Returns:
          dict: Dictionary with the retrieved item under the 'Item' key.  
    """
    try:
        response= db_table.get_item(Key = {"user_id":session_metadata.user_id, "session_id":session_metadata.session_id})

    except ClientError as e:
        logger.error (f"Error getting item: {e.response['Error']['Message']}")
        raise
    else:
        return response['Item']


class QueryParams(BaseModel):
    key_condition_expression: str | None = None
    filter_expression: str | None = None
    projection_expression: str | None = None
    index_name: str | None = None
    limit: int | None = None

def query_table(db_table, query_params:QueryParams, **kwargs):
    """
    Queries items from a DynamoDB table using various query parameters.
    
    Args:
        db_table: The DynamoDB table to query.
        query_params: The query parameters to use.
        **kwargs: Additional query parameters like ExpressionAttributeNames, ExpressionAttributeValues, etc.
    
    Returns:
        dict: Dictionary containing the query results with 'Items', 'Count', 'ScannedCount', etc.
    
    Raises:
        ClientError: If there's an error during the query operation.
    """
    try:
        query_params = query_params.model_dump()
   
        query_params.update(kwargs)
        
        response = db_table.query(**query_params)
        return response
        
    except ClientError as e:
        logger.error(f"Error querying table: {e.response['Error']['Message']}")
        raise


class ScanParams(BaseModel):
    filter_expression: str | None = None
    projection_expression: str | None = None
    limit: int | None = None

def scan_table(db_table, scan_params:ScanParams, **kwargs):
    """
    Scans items from a DynamoDB table using various scan parameters.
    
    Args:
        db_table: The DynamoDB table to scan.
        scan_params: The scan parameters to use.
        **kwargs: Additional scan parameters like ExpressionAttributeNames, ExpressionAttributeValues, etc.
    
    Returns:
        dict: Dictionary containing the scan results with 'Items', 'Count', 'ScannedCount', etc.
    
    Raises:
        ClientError: If there's an error during the scan operation.
    """
    try:
        scan_params = scan_params.model_dump()
        
        scan_params.update(kwargs)
        
        response = db_table.scan(**scan_params)
        return response
        
    except ClientError as e:
        logger.error(f"Error scanning table: {e.response['Error']['Message']}")
        raise


def query_by_user_id(db_table, user_id, limit=None):
    """
    Convenience function to query items by user_id.
    
    Args:
        db_table: The DynamoDB table to query.
        user_id: The user ID to query for.
        limit: Optional limit on the number of results.
    
    Returns:
        dict: Dictionary containing the query results.
    """
    return query_table(
        db_table=db_table,
        query_params=QueryParams(key_condition_expression='user_id = :user_id'),
        ExpressionAttributeValues={':user_id': user_id},
        Limit=limit
    )





            
