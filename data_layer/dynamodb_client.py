from ast import List
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from typing import List, Dict
import os

import logging
logger = logging.getLogger(__name__)

# region_name=os.getenv("AWS_REGION", 'us-east-2')
# dynamodb= boto3.resource('dynamodb', region_name= region_name)

# table_name= os.getenv("DYNAMODB_TABLE", "session_metadata")
# table = dynamodb.Table(table_name)

def put_item(db_table, user_id:str, session_id:str, session_summary:str, started_at:datetime, messages:List[Dict[str, any]]):
    """
    Adds an item to the table.

        :param user_id: The user unique identifier (Partition Key).
        :param session_id: The unique session identifier (Sort Key).
        :param session_summary: The short description of session context.
        :param started_at: The starting time of session.
        :param messages: The list of each message information (message id, sender type, sending time, content, metadata (language, message type), trip data (destination, duration days, transportation, itinerary)). 
    """
    try:
        db_table.put_item(
            Item={"user_id":user_id,
            "session_id":session_id,
            "session_summary":session_summary,
            "started_at":started_at,
            "messages":messages}
        )
        return True
    except ClientError as e:
        logger.error (f"Error putting item: {e.response['Error']['Message']}")
        raise


def get_item(db_table, user_id, session_id ):
    try:
        response= db_table.get_item(Key = {"user_id":user_id, "session_id":session_id})

    except ClientError as e:
        logger.error (f"Error getting item: {e.response['Error']['Message']}")
        raise
    else:
        return response['Item']




            
