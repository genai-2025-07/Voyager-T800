#!/usr/bin/env python3
"""
DynamoDB Table Setup Script for Voyager-T800

This script creates the required DynamoDB table for the application.
It supports both local DynamoDB (development) and AWS DynamoDB (production).

Usage:
    python setup_dynamodb_table.py
"""

import sys

import boto3

from botocore.exceptions import ClientError

from app.config.config import settings


def create_dynamodb_table():
    """Create the session_metadata table in DynamoDB."""

    # Get configuration from settings
    use_local_dynamodb = settings.use_local_dynamodb
    table_name = settings.dynamodb_table
    region_name = settings.aws_region

    print(f'Setting up DynamoDB table: {table_name}')
    print(f'Region: {region_name}')
    print(f'Local DynamoDB: {use_local_dynamodb}')

    # Configure DynamoDB client
    if use_local_dynamodb:
        endpoint_url = settings.dynamodb_endpoint_url
        print(f'Local endpoint: {endpoint_url}')

        dynamodb = boto3.resource(
            'dynamodb',
            region_name=region_name,
            endpoint_url=endpoint_url,
            aws_access_key_id='dummy',
            aws_secret_access_key='dummy',
        )
    else:
        print('Using AWS DynamoDB')
        dynamodb = boto3.resource('dynamodb', region_name=region_name)

    # Table schema based on SessionMetadata model
    table_schema = {
        'TableName': table_name,
        'KeySchema': [
            {
                'AttributeName': 'user_id',
                'KeyType': 'HASH',  # Partition key
            },
            {
                'AttributeName': 'session_id',
                'KeyType': 'RANGE',  # Sort key
            },
        ],
        'AttributeDefinitions': [
            {
                'AttributeName': 'user_id',
                'AttributeType': 'S',  # String
            },
            {
                'AttributeName': 'session_id',
                'AttributeType': 'S',  # String
            },
        ],
        'BillingMode': 'PAY_PER_REQUEST',  # On-demand billing
    }

    try:
        # Check if table already exists
        try:
            existing_table = dynamodb.Table(table_name)
            existing_table.load()
            print(f"Table '{table_name}' already exists!")
            print(f'Table status: {existing_table.table_status}')
            return True
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                raise

        # Create the table
        print(f"Creating table '{table_name}'...")
        table = dynamodb.create_table(**table_schema)

        # Wait for table to be created
        print('Waiting for table to be created...')
        waiter = dynamodb.meta.client.get_waiter('table_exists')
        waiter.wait(TableName=table_name)

        print(f"Table '{table_name}' created successfully!")
        print(f'�� Table status: {table.table_status}')

        return True

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ResourceInUseException':
            print(f" Table '{table_name}' already exists!")
            return True
        else:
            print(f' Error creating table: {e}')
            return False
    except Exception as e:
        print(f' Unexpected error: {e}')
        return False


def main():
    """Main function to set up DynamoDB table."""
    print('=' * 60)
    print('Voyager-T800 DynamoDB Table Setup')
    print('=' * 60)

    success = create_dynamodb_table()

    if success:
        print('\n Setup completed successfully!')
        print('�� You can now run your application:')
        print('   python -m app.main')
    else:
        print('\n Setup failed!')
        print(' Please check the error messages above.')
        sys.exit(1)


if __name__ == '__main__':
    main()
