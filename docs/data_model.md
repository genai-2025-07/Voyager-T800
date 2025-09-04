# Data model 

This document describes the data model used in the project. The application stores session-related information in an Amazon DynamoDB table.

**Table**: session_metadata
**Primary Key**:
- _Partition Key_: user_id (String) – unique identifier of the user.
- _Sort Key_: session_id (String) – unique identifier of the session.

Each combination (user_id, session_id) is unique and represents one session record.

**Attributes**:

|**Attribute**  |**Type**                  |**Description**                                              | 
|---------------|--------------------------|-------------------------------------------------------------|
|user_id        |String                    |Unique identifier for the user                               |
|session_id     |String                    |Unique identifier for the session                            |
|session_summary|String                    |Short description of the session context                     |
|started_at     |String (ISO 8601 datetime)|Session start timestamp                                      |
|messages       |List of Dict              |Each message is stored as a dict with details described below|


**_messages_ structure**

Items in _messages_ contain the following fields:

|**Field**      |**Type**                  |**Description**                                                                  | 
|---------------|--------------------------|---------------------------------------------------------------------------------|
|message_id     |String                    |Unique identifier for the message                                                |
|sender         |String                    |Specify who sent this message (user or AI assistant)                             |
|timestamp      |String (ISO 8601 datetime)|Time when particular message was sent                                            |
|trip_data      |Dict                      |Dictionary with such data (destination, duration days, transportation, itinerary)|
|metadata       |Dict                      |Dictionary with such data (language, message type)                               |

Depends on who has sent specific message, there are different fields in it:
- if sender is user: "message_id","sender", "timestamp", "content", "metadata".
- if sender is AI assistant: "message_id","sender", "timestamp", "trip_data", "metadata". 

**Example item**

{
    "user_id" : "u123",
    "session_id : "s456",
    "session_summary : "Test session",
    "started_at" : "2025-08-28T12:34:56Z",
    "messages": [
        {
            "message_id": "msg_001",
            "sender": "user",
            "timestamp": "2025-08-28T12:34:56Z",
            "content": "Plan a trip to Lviv for 1 day",
            "metadata": {
                "language": "en",
                "message_type": "text"}
            },
            {
                "message_id": "msg_002",
                "sender": "assistant",
                "timestamp": "2025-08-28T12:35:12Z",
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
}


## Notes
- The table is schemaless except for the keys (user_id, session_id).
- Attributes like messages.metadata and messages.trip_data are flexible and may contain additional fields.
- Timestamps are stored as ISO 8601 strings for readability and sorting.

