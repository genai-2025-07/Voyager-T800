"""
DynamoDB-backed checkpointer for LangGraph agent state persistence.

Simple implementation that stores one checkpoint per user session.
When a user resumes a session, they continue from where they left off.
"""

import logging
from decimal import Decimal
from typing import Any, Optional, Sequence

from app.memory.utils import filter_conversation_messages
import boto3
from boto3.dynamodb.types import Binary
from botocore.exceptions import ClientError
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.checkpoint.base import Checkpoint

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)

logger = logging.getLogger(__name__)


def deserialize_dynamodb_item(obj: Any) -> Any:
    """
    Recursively convert DynamoDB Decimal types to Python int/float.
    
    DynamoDB returns numbers as Decimal to preserve precision, but we need
    regular Python types for compatibility with LangGraph.
    """
    if isinstance(obj, list):
        return [deserialize_dynamodb_item(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: deserialize_dynamodb_item(value) for key, value in obj.items()}
    elif isinstance(obj, Decimal):
        # Convert Decimal to int if it's a whole number, otherwise float
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj


class DynamoDBSaver(BaseCheckpointSaver):
    """
    Simple checkpointer that stores LangGraph checkpoints in DynamoDB.
    
    Each user session gets one checkpoint stored in DynamoDB.
    When the session is resumed, the agent continues from that checkpoint.
    
    Table Schema:
    - Partition Key: user_id (String)
    - Sort Key: session_id (String)
    
    Args:
        table_name: Name of the DynamoDB table
        region_name: AWS region (default: "us-east-1")
        endpoint_url: For local DynamoDB (e.g., "http://localhost:8003")
        aws_access_key_id: AWS access key (optional, for local DynamoDB use "dummy")
        aws_secret_access_key: AWS secret key (optional, for local DynamoDB use "dummy")
    """

    def __init__(
        self,
        table_name: str = "session_metadata",
        region_name: str = "us-east-1",
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ) -> None:
        super().__init__()
        
        # Initialize DynamoDB
        dynamodb_kwargs = {"region_name": region_name}
        if endpoint_url:
            dynamodb_kwargs["endpoint_url"] = endpoint_url
        if aws_access_key_id:
            dynamodb_kwargs["aws_access_key_id"] = aws_access_key_id
        if aws_secret_access_key:
            dynamodb_kwargs["aws_secret_access_key"] = aws_secret_access_key
            
        self.dynamodb = boto3.resource("dynamodb", **dynamodb_kwargs)
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name
        
        logger.info(f"DynamoDB checkpointer initialized with table: {table_name}")

    
    def _parse_thread_id(self, thread_id: str) -> tuple[str, str]:
        """
        Parse thread_id into user_id and session_id.
        
        Expected format: "user_id-session_id"
        If no dash, uses the whole string as both user_id and session_id.
        """
        if "-" in thread_id:
            parts = thread_id.split("-", 1)
            return parts[0], parts[1]
        return thread_id, thread_id

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Get the checkpoint for a thread (user session)."""
        try:
            thread_id = config["configurable"]["thread_id"]
            user_id, session_id = self._parse_thread_id(thread_id)
            
            # Get from DynamoDB
            response = self.table.get_item(
                Key={"user_id": user_id, "session_id": session_id}
            )
            
            item = response.get("Item")
            if not item or "checkpoint" not in item:
                logger.debug(f"No checkpoint found for thread_id: {thread_id}")
                return None
            
            # Deserialize the checkpoint
            checkpoint_data = item["checkpoint"]
            
            # Handle both Binary type and raw bytes
            if hasattr(checkpoint_data, 'value'):
                checkpoint_bytes = checkpoint_data.value
            elif isinstance(checkpoint_data, bytes):
                checkpoint_bytes = checkpoint_data
            else:
                checkpoint_bytes = bytes(checkpoint_data)
            
            checkpoint = self.serde.loads_typed(
                (item["checkpoint_type"], checkpoint_bytes)
            )
            
            # Load metadata and convert Decimal types to Python types
            metadata = deserialize_dynamodb_item(item.get("metadata", {}))
            
            # Create the checkpoint tuple
            checkpoint_tuple = CheckpointTuple(
                config=config,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=None,
                pending_writes=[],
            )
            
            logger.debug(f"Retrieved checkpoint for thread_id: {thread_id}")
            return checkpoint_tuple
            
        except KeyError as e:
            logger.warning(f"Missing thread_id in config: {e}")
            return None
        except ClientError as e:
            logger.error(f"DynamoDB error retrieving checkpoint: {e}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving checkpoint: {e}", exc_info=True)
            return None

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save a checkpoint to the database."""

        # Filter messages in the checkpoint
        if 'messages' in checkpoint.get('channel_values', {}):
            original_messages = checkpoint['channel_values']['messages']
            filtered_messages = filter_conversation_messages(original_messages)
            checkpoint['channel_values']['messages'] = filtered_messages

        try:
            thread_id = config["configurable"]["thread_id"]
            user_id, session_id = self._parse_thread_id(thread_id)
            
            # Serialize the checkpoint
            checkpoint_type, serialized_checkpoint = self.serde.dumps_typed(checkpoint)
            
            # Store in DynamoDB
            # Wrap bytes in Binary type for proper DynamoDB storage
            self.table.put_item(
                Item={
                    "user_id": user_id,
                    "session_id": session_id,
                    "checkpoint": Binary(serialized_checkpoint),
                    "checkpoint_type": checkpoint_type,
                    "metadata": metadata,  # DynamoDB will convert numbers to Decimal
                }
            )
            
            logger.debug(f"Saved checkpoint for thread_id: {thread_id}")
            return config
            
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}", exc_info=True)
            raise

    def put_writes(
        self,
        config: RunnableConfig,
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        """
        Store intermediate writes (not implemented in simple version).
        
        The simple checkpointer doesn't track intermediate writes.
        The full checkpoint contains all the state we need.
        """
        pass  # Not needed for simple use case

    def delete_checkpoint(self, thread_id: str) -> None:
        """
        Delete the checkpoint for a specific thread.
        
        Args:
            thread_id: The thread ID in format "user_id-session_id"
        """
        try:
            user_id, session_id = self._parse_thread_id(thread_id)
            
            self.table.delete_item(
                Key={"user_id": user_id, "session_id": session_id}
            )
            
            logger.info(f"Deleted checkpoint for thread_id: {thread_id}")
            
        except ClientError as e:
            logger.error(f"DynamoDB error deleting checkpoint: {e}")
            raise
        except Exception as e:
            logger.error(f"Error deleting checkpoint: {e}", exc_info=True)
            raise