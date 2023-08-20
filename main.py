from fastapi import FastAPI, Depends, HTTPException, Header, Body, Query
from databases import Database
from sqlalchemy import create_engine, MetaData, Table, Column, String, Date, Boolean, TIMESTAMP, Text, select, and_, BIGINT, Integer, ARRAY, join, update, JSON, CheckConstraint, DateTime

from sqlalchemy.dialects.postgresql import UUID
from typing import Optional, Dict, List, Union, Any

import logging
import uuid
import hashlib
import os

from functions import *

from classes import *

app = FastAPI()

# create the api object
app = FastAPI(
    title="LetsClique app API",
    description="This is the API for the LetsClique app.",
    version="1.0.1",
)

# creating logger for custom logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# update the databases URLs
APP_DB_DATABASE_URL = "postgresql://user:password@app_db:5432/app_db"
AUTH_DB_DATABASE_URL = "postgresql://user:password@auth_db:5432/auth_db"

# connect to the databases
app_db_database = Database(APP_DB_DATABASE_URL)
auth_db_database = Database(AUTH_DB_DATABASE_URL)

# ========================================
# defining API endpoints
# ========================================
@app.get("/status_URL_token")
def read_root(token: str = Depends(verify_URL_token)):
    """
    Test passing tokens in URL. The correct token is 'AreYouThere?'
    
    Returns:
        dict: '{"message": "Yep, I'm functional with URL tokens"}' if token is correct or '"detail":"Invalid access token"' if not.
    """
    return {"message": "Yep, I'm functional with URL tokens"}


@app.get("/status_header_token")
def read_root(token: str = Depends(verify_header_token)):
    """
    Test passing tokens in header. The correct token is 'AreYouThere?'
    
    Returns:
        dict: '{"message": "Yep, I'm functional with header tokens"}' if token is correct or '"detail":"Invalid access token"' if not.
    """
    return {"message": "Yep, I'm functional with header tokens"}


@app.post("/register_user")
async def add_user(user_data: User, auth_data: dict):
    """
    Register a new user and add their authentication data.

    This endpoint accepts user data and authentication data in the request body. 
    The user data is used to register the user in the `users` table of the `app_db` database, 
    while the authentication data is used to store the hashed password and related authentication 
    details in the `users_auth` table of the `auth_db` database.

    Parameters:
    - user_data (User): A Pydantic model instance containing user information as described before.
    - auth_data (dict): A dictionary containing the password for the user. 
                        Expected format: {"password": "user_password"}

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the newly registered user.
        - 'message': A confirmation message indicating successful registration.

    Example:
    - curl -X POST "https://letsclique.de/register_user" \
        -H "accept: application/json" \
        -H "Content-Type: application/json" \
        -d '{
            "user_data": {
                "first_name": "John",
                "middle_name": "A.",
                "last_name": "Doe",
                "username": "johndoe",
                "email": "johndoe@example.com",
                "birthdate": "2000-01-01",
                "gender": "male",
                "location": [40.7128, -74.0060],
                "profile_photo_url": "http://example.com/johndoe.jpg",
                "description": "Hello, I am John.",
                "social_media_links": {"twitter": "johndoe"}
            },
            "auth_data": {
                "password": "strong_password_123"
                        }
            }'

    
    Errors:
    - 422 Unprocessable Entity: If the provided data doesn't meet the validation criteria.
    - 500 Internal Server Error: If there's an issue inserting the data into either database.
    """
    
    # Generate the UUID, set the last_online timestamp, and hash the password
    user_data.user_id = uuid.uuid4()
    user_data.last_online = datetime.now()
    hashed_data = hash_input_with_salt(auth_data['password'])
    
    # Insert user data into app_db
    await insert_user(app_db_database, user_data.dict())
    
    # Insert user authentication data into auth_db
    await insert_user_auth(auth_db_database, 
                        user_data.user_id, 
                        user_data.username, 
                        user_data.email, 
                        hashed_data['hash'], 
                        hashed_data['salt'])
    
    return {"user_id": user_data.user_id, "message": "User and authentication data successfully added!"}


@app.get("/login_user")
async def login_user(email: Optional[str] = Header(None), password: Optional[str] = Header(None)):
    """
    Endpoint to authenticate a user and provide a session token.

    Parameters:
    - email (str): The email of the user provided in the header.
    - password (str): The plaintext password of the user provided in the header.

    Returns:
    - dict: A dictionary containing the user_id, session token, and a confirmation message.
    """

    logger.debug("Entering login_user endpoint.")

    if not email or not password:
        logger.warning("Email or password header missing.")
        raise HTTPException(status_code=400, detail="Email and password headers are required.")
    
    try:
        logger.debug(f"Attempting to generate session token for email: {email}.")
        user_id, token = await generate_session_token(auth_db_database, email, password)
        logger.debug("Session token generated successfully.")
        return {
            "user_id": user_id,
            "token": token,
            "message": "Login successful!"
        }
    except ValueError as ve:
        logger.error(f"ValueError encountered: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")


@app.post("/update_user_location")
async def update_user_location_endpoint(user_id: uuid.UUID = Header(...),
                                        sessiontoken: str = Header(...),
                                        location: str = Header(...)):
    """
    Endpoint to update the location of a user and their open events.
    
    Parameters:
    - user_id (uuid.UUID, header): The unique identifier of the user.
    - sessiontoken (str, header): The session token of the user.
    - location (str, header): The new location coordinates in "latitude,longitude" format.
    
    Returns:
    - JSON: A success or error message.
    """
    logger.debug(f"Attempting to update location for user with ID: {user_id}.")
    
    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")
    
    # Update the user's location
    new_location_list = [float(coord) for coord in location.split(",")]
    await update_user_location(app_db_database, user_id, new_location_list)
    logger.debug(f"Updated location for user with ID: {user_id}.")
    
    # Define the structure of the events table for reference
    events = Table(
        "events",
        metadata,
        Column("initiated_by", UUID, nullable=False),
        Column("location", Text, nullable=False),
        Column("is_open", Boolean, nullable=False),
        extend_existing=True
    )
    
    #query = events.select().where(and_(events.c.initiated_by == user_id, events.c.is_open == True))
    #open_events = await app_db_database.fetch_all(query)
    
    # Update location for each open event
    #for event in open_events:
    #    await update_event_location(app_db_database, event["event_id"], new_location_list)
    #    logger.debug(f"Updated location for event with ID: {event['event_id']}.")
    
    return {"message": "Location updated successfully for user and their open events."}


@app.post("/update_user_profile")
async def update_user_profile_endpoint(
    user_data: User,
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...)
    ):
    """
    Endpoint to update the profile of a user.
    
    Parameters:
    - user_data (User): A Pydantic model instance containing user information.
    - user_id (uuid.UUID, header): The unique identifier of the user.
    - sessiontoken (str, header): The session token of the user.
    
    Returns:
    - dict: A dictionary containing a confirmation message.
    """
    
    logger.debug(f"Attempting to update profile for user with ID: {user_id}.")
    
    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")
    
    # Convert the birthdate string to a date object
    if user_data.birthdate:
        user_data.birthdate = datetime.strptime(user_data.birthdate, '%Y-%m-%d').date()
    
    # define struncture of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("first_name", String, nullable=False),
        Column("last_name", String, nullable=False),
        Column("middle_name", String),
        Column("username", String),
        Column("email", String, unique=True, nullable=False),
        Column("birthdate", Date, nullable=False),
        Column("gender", String, nullable=False),
        Column("location", Text, nullable=False),
        Column("profile_photo_url", String),
        Column("description", String),
        Column("last_online", TIMESTAMP),
        Column("is_online", Boolean, default=False),
        Column("social_media_links", JSON),
        extend_existing=True
    )

    # Update user profile
    query = update(users).where(users.c.user_id == user_id).values(**user_data.dict(exclude_unset=True))
    await app_db_database.execute(query)

    logger.debug(f"Profile updated successfully for user with ID: {user_id}.")
    
    return {"message": "Profile updated successfully for the user."}


@app.post("/create_event")
async def create_event_endpoint(
        event_dict: dict = Body(...),
        user_id: uuid.UUID = Header(...), 
        sessiontoken: str = Header(...)
    ):
    """
    Create a new event.

    This endpoint accepts event data in the request body and inserts it into 
    the `events` table of the `app_db` database.

    Parameters:
    - event_dict (dict): A dictionary containing event information.
    - user_id (uuid.UUID, header): The unique identifier of the user.
    - sessiontoken (str, header): The session token of the user.

    Returns:
    - dict: A dictionary containing:
        - 'event_id': The UUID of the newly created event.
        - 'message': A confirmation message indicating successful event creation.

    Example:
    - curl -X POST "https://letsclique.de/create_event" \
     -H "user_id: some-uuid" \
     -H "sessiontoken: some-token" \
     -d '{"activity_name": "some name",
          "participant_min_age": 18,
          "participant_max_age": 30,
          "participant_pref_genders": ["male", "female"],
          "description": "Join us for a fun evening of board games!"
         }'

    Errors:
    - 401 Unauthorized: If the authentication fails.
    - 422 Unprocessable Entity: If the provided data doesn't meet the validation criteria.
    - 500 Internal Server Error: If there's an issue inserting the data into the database.
    """
    
    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")
    
    # Extract the activity_name from the dictionary and fetch its corresponding activity_id.
    activity_name = event_dict.pop("activity_name", None)  # Extract and remove activity_name from event_dict
    if not activity_name:
        raise HTTPException(status_code=400, detail="Activity name is required.")
    activity_id = await get_activity_id(app_db_database, activity_name)

    # Add the fetched activity_id to the event_dict
    event_dict["activity_id"] = activity_id

    # Generate event_id for event_dict
    event_dict["event_id"] = uuid.uuid4()

    # Modify the event_dict with other required attributes.
    event_dict["initiated_by"] = user_id
    event_dict["location"] = [0, 0]  # Setting the location coordinates to [0, 0].

    # Validate and convert the modified event_dict to an Event instance
    event = Event(**event_dict)

    # Insert event data into app_db.
    await insert_event(app_db_database, event.dict())
    
    return {"event_id": event.event_id, "message": "Event successfully created!"}


@app.post("/update_event")
async def update_event_endpoint(
    event_data: dict = Body(...),
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...),
):
    """
    Endpoint to update an event's details.

    This endpoint accepts event data in the request body and updates the corresponding 
    entry in the `events` table of the `app_db` database.

    Parameters:
    - event_data (dict): A dictionary containing updated event information.
    - user_id (uuid.UUID, header): The unique identifier of the user.
    - sessiontoken (str, header): The session token of the user.

    Returns:
    - dict: A dictionary containing a confirmation message.

    Example:
    - curl -X POST "https://letsclique.de/update_event" \
     -H "user_id: some-uuid" \
     -H "sessiontoken: some-token" \
     -d '{"event_id": "some-uuid",
          "activity_name": "some name",
          "participant_min_age": 18,
          "participant_max_age": 30,
          "participant_pref_genders": ["male", "female"],
          "description": "Updated description of the event."
         }'

    Errors:
    - 401 Unauthorized: If the authentication fails.
    - 422 Unprocessable Entity: If the provided data doesn't meet the validation criteria.
    - 500 Internal Server Error: If there's an issue updating the data in the database.
    """
    
    logger.debug(f"Attempting to update event with ID: {event_data['event_id']} by user with ID: {user_id}.")
    
    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")
    
    # Extract the activity_name from the dictionary and fetch its corresponding activity_id.
    activity_name = event_data.pop("activity_name", None)
    if not activity_name:
        raise HTTPException(status_code=400, detail="Activity name is required.")
    activity_id = await get_activity_id(app_db_database, activity_name)

    # Add the fetched activity_id to the event_data dictionary
    event_data["activity_id"] = activity_id

    # Define the structure of the events table for reference
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("activity_id", BIGINT, nullable=False),
        Column("initiated_by", UUID, nullable=False),
        Column("location", Text, nullable=False),
        Column("address", Text),
        Column("participant_min_age", Integer, nullable=False),
        Column("participant_max_age", Integer, nullable=False),
        Column("participant_pref_genders", ARRAY(String), nullable=False),
        Column("description", Text, nullable=False),
        Column("is_open", Boolean, nullable=False),
        Column("initiated_on", TIMESTAMP, nullable=False),
        Column("event_picture_url", Text),
        Column("event_date_time", TIMESTAMP),
        extend_existing=True
    )

    # Update event details
    query = (
        update(events)
        .where(events.c.event_id == event_data['event_id'])
        .values(**event_data)
    )
    await app_db_database.execute(query)

    logger.debug(f"Event details updated successfully for event with ID: {event_data['event_id']} by user with ID: {user_id}.")
    
    return {"message": "Event details updated successfully."}

from sqlalchemy import select, and_, func

@app.post("/delete_event")
async def close_event_endpoint(
    request_data: dict = Body(...),
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...)
):
    """
    Close (soft delete) an event based on the event_id provided in the request body.

    This endpoint accepts an event_id in the request body and sets the event's is_open 
    field to False in the `events` table of the `app_db` database, effectively closing the event.

    Parameters:
    - request_data (dict): A dictionary containing the event_id to be closed.
    - user_id (UUID, header): The unique identifier of the user.
    - sessiontoken (str, header): The session token of the user.

    Returns:
    - dict: A dictionary containing a confirmation message.

    Example:
    - curl -X POST "https://letsclique.de/delete_event" \
     -H "user_id: some-uuid" \
     -H "sessiontoken: some-token" \
     -d '{"event_id": "some-uuid"}'

    Errors:
    - 401 Unauthorized: If the authentication fails.
    - 403 Forbidden: If the event_id provided does not correspond to the user_id.
    - 500 Internal Server Error: If there's an issue updating the data in the database.
    """
    
    logger.debug(f"Attempting to close event with ID: {request_data['event_id']} by user with ID: {user_id}.")
    
    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")
    
    # Check if the event_id corresponds to the user_id in the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("activity_id", BIGINT, nullable=False),
        Column("initiated_by", UUID, nullable=False),
        Column("location", Text, nullable=False),
        Column("address", Text),
        Column("participant_min_age", Integer, nullable=False),
        Column("participant_max_age", Integer, nullable=False),
        Column("participant_pref_genders", ARRAY(String), nullable=False),
        Column("description", Text, nullable=False),
        Column("is_open", Boolean, nullable=False),
        Column("initiated_on", TIMESTAMP, nullable=False),
        Column("event_picture_url", Text),
        Column("event_date_time", TIMESTAMP),
        extend_existing=True
    )
    event_query = select([events.c.initiated_by]).where(events.c.event_id == request_data['event_id'])
    event_initiator = await app_db_database.fetch_one(event_query)

    if not event_initiator or event_initiator['initiated_by'] != user_id:
        logger.warning(f"User with ID: {user_id} is not authorized to close event with ID: {request_data['event_id']}.")
        raise HTTPException(status_code=403, detail="You are not authorized to close this event.")
    
    # Close the event
    await close_event(app_db_database, request_data['event_id'])
    
    return {"message": "Event successfully closed."}


@app.post("/filter_events")
async def filter_events_endpoint(
    filter_criteria: EventFilterCriteria = Body(...),
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...)
) -> Dict[str, Any]:
    """
    Endpoint to filter events based on given criteria.

    This endpoint accepts filter criteria in the request body and returns events from 
    the `events` table of the `app_db` database that match the criteria.

    Parameters:
    - filter_criteria (EventFilterCriteria): A dictionary containing filter parameters.
    - user_id (UUID, header): The unique identifier of the user.
    - sessiontoken (str, header): The session token of the user.

    Returns:
    - dict: A dictionary containing:
        - 'event_ids': A list of event IDs that match the criteria.
        - 'event_locations': A list of locations for the matching events.
        - 'event_activities': A list of activity IDs for the matching events.
        - 'message': A confirmation message.

    Errors:
    - 401 Unauthorized: If the authentication fails.
    """
    
    logger.debug(f"Filtering events for user with ID: {user_id} based on provided criteria.")

    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")

    # Get the user's location
    user_location = await get_user_location(app_db_database, user_id)

    # Convert activity names to activity IDs
    activity_ids = [await get_activity_id(app_db_database, name) for name in filter_criteria.activity_names]

    # Define the structure of the events table for reference
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("activity_id", BIGINT, nullable=False),
        Column("initiated_by", UUID, nullable=False),
        Column("location", Text, nullable=False),
        Column("address", Text),
        Column("participant_min_age", Integer, nullable=False),
        Column("participant_max_age", Integer, nullable=False),
        Column("participant_pref_genders", ARRAY(String), nullable=False),
        Column("description", Text, nullable=False),
        Column("is_open", Boolean, nullable=False),
        Column("initiated_on", TIMESTAMP, nullable=False),
        Column("event_picture_url", Text),
        Column("event_date_time", TIMESTAMP),
        extend_existing=True
    )

    # Query to fetch events based on activity IDs
    query = select([events]).where(
        and_(
            events.c.activity_id.in_(activity_ids),
            events.c.participant_min_age <= filter_criteria.max_age,
            events.c.participant_max_age >= filter_criteria.min_age
        )
    )
    all_relevant_events = await app_db_database.fetch_all(query)

    # Further filter events in Python based on distance and preferred genders
    filtered_events = [
        event for event in all_relevant_events 
        if set(event.participant_pref_genders).intersection(filter_criteria.pref_genders)
        and haversine_distance(user_location, event.location) <= filter_criteria.radius
    ]

    # Extract event details from the filtered results
    event_ids = [event.event_id for event in filtered_events]
    event_locations = [event.location for event in filtered_events]
    event_activities = [event.activity_id for event in filtered_events]

    logger.debug(f"Filtered {len(event_ids)} events for user with ID: {user_id} based on provided criteria.")
    
    return {
        "event_ids": event_ids,
        "event_locations": event_locations,
        "event_activities": event_activities,
        "message": f"Successfully filtered {len(event_ids)} events."
    }


@app.get("/get_event_details")
async def get_event_details_endpoint(
    event_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...)
) -> Dict[str, Union[str, uuid.UUID]]:
    """
    Endpoint to fetch details of a specific event.

    This endpoint retrieves the details of an event specified by its `event_id`.

    Parameters:
    - event_id (UUID, path): The unique identifier of the event.
    - user_id (UUID, header): The unique identifier of the user.
    - sessiontoken (str, header): The session token of the user.

    Returns:
    - dict: A dictionary containing:
        - 'activity_name': The name of the activity associated with the event.
        - 'initiator_id': The user ID of the event initiator.
        - 'event_description': The description of the event.
        - 'message': A confirmation message.

    Errors:
    - 401 Unauthorized: If the authentication fails.
    - 404 Not Found: If the event with the specified ID does not exist.
    """
    
    logger.debug(f"Fetching details for event with ID: {event_id} requested by user with ID: {user_id}.")

    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")

    # Define the structure of the events and activities tables for reference
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("activity_id", BIGINT, nullable=False),
        Column("initiated_by", UUID, nullable=False),
        Column("description", Text, nullable=False),
        extend_existing=True
    )

    activities = Table(
        "activities",
        metadata,
        Column("activity_id", BIGINT, primary_key=True),
        Column("activity_name", Text, nullable=False),
        extend_existing=True
    )

    # Join the tables on the activity_id and fetch event details
    query = (
        select([activities.c.activity_name, events.c.initiated_by, events.c.description])
        .select_from(events.join(activities, events.c.activity_id == activities.c.activity_id))
        .where(events.c.event_id == event_id)
    )

    result = await app_db_database.fetch_one(query)

    # Check if the event was found
    if not result:
        logger.warning(f"Event with ID: {event_id} not found.")
        raise HTTPException(status_code=404, detail="Event not found.")

    logger.debug(f"Successfully fetched details for event with ID: {event_id}.")

    return {
        "activity_name": result.activity_name,
        "initiator_id": result.initiated_by,
        "event_description": result.description,
        "message": "Event details fetched successfully."
    }
    
    
@app.get("/get_user_details")
async def get_user_details_endpoint(
    target_user_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...)
):
    """
    Retrieve the details of a user.

    This endpoint fetches and returns selected details of a user specified by `target_user_id`.

    Parameters:
    - target_user_id (UUID, path): The ID of the user whose details are to be retrieved.
    - user_id (UUID, header): The unique identifier of the user making the request.
    - sessiontoken (str, header): The session token of the user making the request.

    Returns:
    - dict: A dictionary containing the user's details.

    Errors:
    - 401 Unauthorized: If the authentication fails.
    - 404 Not Found: If the `target_user_id` does not correspond to any user in the database.
    """
    
    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")
    
    # Convert the birthdate string to a date object
    if user_data.birthdate:
        user_data.birthdate = datetime.strptime(user_data.birthdate, '%Y-%m-%d').date()
    
    # Partial definition of the `users` table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("first_name", Text, nullable=False),
        Column("last_name", Text, nullable=False),
        Column("middle_name", Text),
        Column("birthdate", Date, nullable=False),
        Column("location", Text, nullable=False),
        Column("profile_photo_url", Text),
        Column("last_online", TIMESTAMP),
        extend_existing=True
    )

    # Fetch the user details
    query = select(users).where(users.c.user_id == target_user_id)
    user_record = await app_db_database.fetch_one(query)
    
    # If no user found with the given `target_user_id`
    if not user_record:
        logger.error(f"User details not found for user with ID: {target_user_id}.")
        raise HTTPException(status_code=404, detail="User not found.")
    
    # Calculate age from birthdate
    today = datetime.today()
    age = today.year - user_record.birthdate.year - ((today.month, today.day) < (user_record.birthdate.month, user_record.birthdate.day))

    # Construct the response dictionary
    user_details = {
        "first_name": user_record.first_name,
        "last_name": user_record.last_name,
        "middle_name": user_record.middle_name,
        "age": age,
        "location": user_record.location,
        "profile_photo_url": user_record.profile_photo_url,
        "last_online": user_record.last_online
    }
    
    logger.debug(f"Successfully fetched details for user with ID: {target_user_id}.")

    return user_details


@app.get("/is_participant")
async def is_participant_endpoint(
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...),
    event_id: uuid.UUID = Header(...),
    participant_id: uuid.UUID = Header(...)
):
    """
    Determine if a user is a participant of a given event.

    Parameters:
    - user_id (UUID, header): The unique identifier of the user making the request.
    - sessiontoken (str, header): The session token of the user making the request.
    - event_id (UUID, header): The ID of the event in question.
    - participant_id (UUID, header): The ID of the participant in question.

    Returns:
    - dict: A dictionary indicating whether the user is a participant and a confirmation message.

    Errors:
    - 401 Unauthorized: If the authentication fails.
    """
    
    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")
    
    # Define the structure of the participation_requests table
    participation_requests = Table(
        "participation_requests",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("event_creator", UUID),
        Column("request_participant", UUID),
        Column("accepted_status", Boolean),
        Column("chat_id", UUID),
        Column("chat_block", Text),
        extend_existing=True
    )
    
    # Query to check if the participant_id is a participant of the event_id
    query = (
        select(participation_requests.c.accepted_status)
        .where(participation_requests.c.event_id == event_id)
        .where(participation_requests.c.request_participant == participant_id)
    )
    record = await app_db_database.fetch_one(query)

    # Determine the participation status
    if record:
        is_participant = record.accepted_status
        message = "User is a participant of the event." if is_participant else "User is not a participant of the event."
    else:
        is_participant = False
        message = "No participation request found for the user for this event."

    logger.debug(f"Checked participation status for user {participant_id} in event {event_id}: {is_participant}")
    
    return {"is_participant": is_participant, "message": message}


@app.post("/request_to_join_event")
async def request_to_join_event_endpoint(
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...),
    event_id: uuid.UUID = Header(...)
):
    """
    Request to join a specific event.

    Parameters:
    - user_id (UUID, header): The unique identifier of the user making the request.
    - sessiontoken (str, header): The session token of the user making the request.
    - event_id (UUID, header): The ID of the event the user wants to join.

    Returns:
    - dict: A dictionary containing a confirmation message.

    Errors:
    - 401 Unauthorized: If the authentication fails.
    """
    
    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")
    
    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("initiated_by", UUID),
        extend_existing=True
    )

    # Define the structure of the participation_requests table
    participation_requests = Table(
        "participation_requests",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("event_creator", UUID),
        Column("request_participant", UUID),
        Column("accepted_status", Boolean),
        Column("chat_id", UUID),
        Column("chat_block", Text),
        extend_existing=True
    )
    
    # Search for the event's creator
    query = select(events.c.initiated_by).where(events.c.event_id == event_id)
    event_creator = await app_db_database.fetch_val(query)

    if not event_creator:
        logger.warning(f"No event found for event ID: {event_id}.")
        raise HTTPException(status_code=404, detail="Event not found.")
    
    # Generate a new chat_id
    chat_id = uuid.uuid4()

    # Insert request to join event into the participation_requests table
    query = (
        insert(participation_requests)
        .values(
            event_id=event_id,
            event_creator=event_creator,
            request_participant=user_id,
            chat_id=chat_id
        )
    )
    await app_db_database.execute(query)

    logger.debug(f"User {user_id} requested to join event {event_id}. Chat ID generated: {chat_id}.")
    
    return {"message": "Your request to join the event has been successfully submitted."}


@app.get("/get_incoming_requests")
async def get_incoming_requests_endpoint(
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...),
    event_id: uuid.UUID = Header(...)
) -> Dict[str, List]:
    """
    Endpoint to fetch the list of users who have requested to join a specific event.

    Parameters:
    - user_id (UUID, header): The unique identifier of the user (event creator).
    - sessiontoken (str, header): The session token of the user.
    - event_id (UUID, header): The unique identifier of the event.

    Returns:
    - dict: A dictionary containing:
        - 'user_ids': A list of user IDs who have requested to join the event.
        - 'locations': A list of locations corresponding to each user in 'user_ids'.

    Errors:
    - 401 Unauthorized: If the authentication fails.
    - 404 Not Found: If no requests are found for the specified event.
    """
    
    logger.debug(f"Fetching incoming join requests for event with ID: {event_id} for user with ID: {user_id}.")

    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")

    # Define the structure of the participation_requests table for reference
    participation_requests = Table(
        "participation_requests",
        metadata,
        Column("event_id", uuid.UUID, nullable=False),
        Column("event_creator", uuid.UUID, nullable=False),
        Column("request_participant", uuid.UUID, nullable=False),
        extend_existing=True
    )

    # Query to fetch all participation requests for the given event_id and user_id (event creator)
    query = (
        select([participation_requests.c.request_participant])
        .where(participation_requests.c.event_id == event_id)
        .where(participation_requests.c.event_creator == user_id)
    )

    result = await app_db_database.fetch_all(query)

    # Check if any requests were found
    if not result:
        logger.warning(f"No incoming join requests found for event with ID: {event_id}.")
        raise HTTPException(status_code=404, detail="No incoming join requests found for the specified event.")

    # Fetch the location for each request participant
    user_ids = [r["request_participant"] for r in result]
    locations = [await get_user_location(app_db_database, uid) for uid in user_ids]

    logger.debug(f"Successfully fetched incoming join requests for event with ID: {event_id}.")

    return {
        "user_ids": user_ids,
        "locations": locations
    }


@app.post("/accept_participant")
async def accept_participant_endpoint(
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...),
    participant_id: uuid.UUID = Header(...),
    event_id: uuid.UUID = Header(...)
) -> Dict[str, Union[uuid.UUID, str]]:
    """
    Endpoint to accept a participant for a specific event.

    Parameters:
    - user_id (UUID, header): The unique identifier of the user (event creator).
    - sessiontoken (str, header): The session token of the user.
    - participant_id (UUID, header): The unique identifier of the participant.
    - event_id (UUID, header): The unique identifier of the event.

    Returns:
    - dict: A dictionary containing:
        - 'chat_id': The chat ID for the participant.
        - 'message': A confirmation message.

    Errors:
    - 401 Unauthorized: If the authentication fails.
    - 404 Not Found: If no participation request is found for the specified event and participant.
    """
    
    logger.debug(f"Accepting participant with ID: {participant_id} for event with ID: {event_id} by user with ID: {user_id}.")

    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")

    # Define the structure of the participation_requests table for reference
    participation_requests = Table(
        "participation_requests",
        metadata,
        Column("event_id", uuid.UUID, nullable=False),
        Column("event_creator", uuid.UUID, nullable=False),
        Column("request_participant", uuid.UUID, nullable=False),
        Column("accepted_status", Boolean),
        Column("chat_id", uuid.UUID),
        extend_existing=True
    )

    # Update the accepted_status for the given participant_id and event_id
    query = (
        update(participation_requests)
        .where(participation_requests.c.event_id == event_id)
        .where(participation_requests.c.event_creator == user_id)
        .where(participation_requests.c.request_participant == participant_id)
        .values(accepted_status=True)
        .returning(participation_requests.c.chat_id)
    )

    result = await app_db_database.fetch_one(query)

    # Check if the participation request was found and updated
    if not result:
        logger.warning(f"No participation request found for participant with ID: {participant_id} for event with ID: {event_id}.")
        raise HTTPException(status_code=404, detail="Participation request not found.")

    chat_id = result["chat_id"]
    await close_event(app_db_database, event_id)

    logger.debug(f"Successfully accepted participant with ID: {participant_id} for event with ID: {event_id}.")

    return {
        "chat_id": chat_id,
        "message": "Participant successfully accepted for the event."
    }
    

@app.post("/remove_participant")
async def remove_participant_endpoint(
    remove_data: Dict[uuid.UUID, uuid.UUID] = Body(...),
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...)
) -> Dict[str, str]:
    """
    Endpoint to remove a participant from a specific event.

    Parameters:
    - remove_data (dict, body): A dictionary containing:
        - 'event_id' (UUID): The unique identifier of the event.
        - 'participant_id' (UUID): The unique identifier of the participant.
    - user_id (UUID, header): The unique identifier of the user (event creator).
    - sessiontoken (str, header): The session token of the user.

    Returns:
    - dict: A dictionary containing:
        - 'message': A confirmation message.

    Errors:
    - 401 Unauthorized: If the authentication fails.
    - 404 Not Found: If no participation request is found for the specified event and participant.
    """
    
    logger.debug(f"Removing participant with ID: {remove_data['participant_id']} from event with ID: {remove_data['event_id']} by user with ID: {user_id}.")

    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")

    # Define the structure of the participation_requests table for reference
    participation_requests = Table(
        "participation_requests",
        metadata,
        Column("event_id", uuid.UUID, nullable=False),
        Column("event_creator", uuid.UUID, nullable=False),
        Column("request_participant", uuid.UUID, nullable=False),
        Column("accepted_status", Boolean),
        Column("chat_id", uuid.UUID),
        extend_existing=True
    )

    # Update the accepted_status for the given participant_id and event_id to False
    query = (
        update(participation_requests)
        .where(participation_requests.c.event_id == remove_data['event_id'])
        .where(participation_requests.c.event_creator == user_id)
        .where(participation_requests.c.request_participant == remove_data['participant_id'])
        .values(accepted_status=False)
    )

    result = await app_db_database.execute(query)

    if not result:
        logger.warning(f"No participation request found for participant with ID: {remove_data['participant_id']} for event with ID: {remove_data['event_id']}.")
        raise HTTPException(status_code=404, detail="Participation request not found.")

    logger.debug(f"Successfully removed participant with ID: {remove_data['participant_id']} from event with ID: {remove_data['event_id']}.")

    return {
        "message": "Participant successfully removed from the event."
    }
    

@app.get("/read_chatblock")
async def read_chatblock_endpoint(
    chat_data: Dict[str, uuid.UUID] = Body(...),
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...)
) -> Dict[str, str]:
    """
    Endpoint to read the chat block associated with a given chat_id.

    Parameters:
    - chat_data (dict, body): A dictionary containing:
        - 'chat_id' (UUID): The unique identifier of the chat.
    - user_id (UUID, header): The unique identifier of the user (event creator or participant).
    - sessiontoken (str, header): The session token of the user.

    Returns:
    - dict: A dictionary containing:
        - 'chatblock': The chat block associated with the given chat_id.

    Errors:
    - 401 Unauthorized: If the authentication fails.
    - 404 Not Found: If no chatblock is found for the specified chat_id and user_id.
    """
    
    logger.debug(f"Fetching chat block for chat with ID: {chat_data['chat_id']} requested by user with ID: {user_id}.")

    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")

    # Define the structure of the participation_requests table for reference
    participation_requests = Table(
        "participation_requests",
        metadata,
        Column("event_id", uuid.UUID, nullable=False),
        Column("event_creator", uuid.UUID, nullable=False),
        Column("request_participant", uuid.UUID, nullable=False),
        Column("accepted_status", Boolean),
        Column("chat_id", uuid.UUID),
        Column("chat_block", String),
        extend_existing=True
    )

    # Construct the select query
    query = (
        select([participation_requests.c.chat_block])
        .where(
            and_(
                participation_requests.c.chat_id == chat_data['chat_id'],
                or_(
                    participation_requests.c.event_creator == user_id,
                    participation_requests.c.request_participant == user_id
                )
            )
        )
    )

    result = await app_db_database.fetch_one(query)

    if not result:
        logger.warning(f"No chatblock found for chat with ID: {chat_data['chat_id']}.")
        raise HTTPException(status_code=404, detail="Chatblock not found.")

    logger.debug(f"Successfully fetched chat block for chat with ID: {chat_data['chat_id']}.")

    return {
        "chatblock": result["chat_block"]
    }
    

@app.post("/write_chatblock")
async def write_chatblock_endpoint(
    chat_data: Dict[uuid.UUID, str] = Body(...),
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...)
) -> Dict[str, str]:
    """
    Endpoint to write to the chat block associated with a given chat_id.

    Parameters:
    - chat_data (dict, body): A dictionary containing:
        - 'chat_id' (UUID, key): The unique identifier of the chat.
        - 'chat_block' (str, value): The content to be written to the chat block.
    - user_id (UUID, header): The unique identifier of the user (event creator or participant).
    - sessiontoken (str, header): The session token of the user.

    Returns:
    - dict: A dictionary containing a confirmation message.

    Errors:
    - 401 Unauthorized: If the authentication fails.
    - 404 Not Found: If no chatblock is found for the specified chat_id and user_id.
    """
    
    logger.debug(f"Writing to chat block for chat with ID: {list(chat_data.keys())[0]} requested by user with ID: {user_id}.")

    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")

    # Define the structure of the participation_requests table for reference
    participation_requests = Table(
        "participation_requests",
        metadata,
        Column("event_id", uuid.UUID, nullable=False),
        Column("event_creator", uuid.UUID, nullable=False),
        Column("request_participant", uuid.UUID, nullable=False),
        Column("accepted_status", Boolean),
        Column("chat_id", uuid.UUID),
        Column("chat_block", String),
        extend_existing=True
    )

    # Construct the update query
    chat_id = list(chat_data.keys())[0]
    chat_block = chat_data[chat_id]
    query = (
        update(participation_requests)
        .where(
            and_(
                participation_requests.c.chat_id == chat_id,
                or_(
                    participation_requests.c.event_creator == user_id,
                    participation_requests.c.request_participant == user_id
                )
            )
        )
        .values(chat_block=chat_block)
    )

    result = await app_db_database.execute(query)

    if not result:
        logger.warning(f"Failed to write to chat block for chat with ID: {chat_id}.")
        raise HTTPException(status_code=404, detail="Chatblock update failed.")

    logger.debug(f"Successfully wrote to chat block for chat with ID: {chat_id}.")

    return {
        "message": "Chat block updated successfully."
    }
    
    
@app.get("/did_I_match")
async def did_I_match_endpoint(
    user_id: uuid.UUID = Header(...),
    sessiontoken: str = Header(...)
) -> Dict[str, List[uuid.UUID]]:
    """
    Endpoint to check if the user matched with any event.

    Parameters:
    - user_id (UUID, header): The unique identifier of the user.
    - sessiontoken (str, header): The session token of the user.

    Returns:
    - dict: A dictionary containing lists of:
        - 'event_id': Event IDs the user matched with.
        - 'chat_id': Chat IDs associated with the matched events.
        - 'event_creator': User IDs of the event creators of the matched events.

    Errors:
    - 401 Unauthorized: If the authentication fails.
    """
    
    logger.debug(f"Checking matches for user with ID: {user_id}.")

    # Authenticate the user's session token
    is_authenticated = await authenticate_session_token(auth_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")

    # Define the structure of the events and participation_requests tables for reference
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("activity_id", Integer, nullable=False),
        Column("initiated_by", UUID, nullable=False),
        Column("is_open", Boolean, nullable=False),
        extend_existing=True
    )

    participation_requests = Table(
        "participation_requests",
        metadata,
        Column("event_id", UUID, nullable=False),
        Column("event_creator", UUID, nullable=False),
        Column("request_participant", UUID, nullable=False),
        Column("chat_id", UUID),
        Column("chat_block", String),
        extend_existing=True
    )

    # Construct the select query to retrieve the matched events
    query = (
        select([
            participation_requests.c.event_id, 
            participation_requests.c.chat_id, 
            participation_requests.c.event_creator
        ])
        .select_from(
            participation_requests.join(
                events, 
                participation_requests.c.event_id == events.c.event_id
            )
        )
        .where(
            and_(
                participation_requests.c.request_participant == user_id,
                events.c.is_open == True
            )
        )
    )

    results = await app_db_database.fetch_all(query)
    
    if not results:
        logger.debug(f"No matches found for user with ID: {user_id}.")
        return {
            "event_id": [],
            "chat_id": [],
            "event_creator": [],
        }

    event_ids = [result["event_id"] for result in results]
    chat_ids = [result["chat_id"] for result in results]
    event_creators = [result["event_creator"] for result in results]

    logger.debug(f"Successfully retrieved matches for user with ID: {user_id}.")

    return {
        "event_id": event_ids,
        "chat_id": chat_ids,
        "event_creator": event_creators
    }

# ========================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ========================================
# establish and close database connections
@app.on_event("startup")
async def startup():
    await app_db_database.connect()
    await auth_db_database.connect()
@app.on_event("shutdown")
async def shutdown():
    await app_db_database.disconnect()
    await auth_db_database.disconnect()