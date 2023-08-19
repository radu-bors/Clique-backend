from fastapi import FastAPI, Depends, HTTPException, Header, Body
from databases import Database
from sqlalchemy import create_engine, MetaData, Table, Column, String, Date, Boolean, TIMESTAMP, Text, select, and_
from sqlalchemy.dialects.postgresql import UUID
from typing import Optional

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
async def update_user_location_endpoint(user_id: uuid.UUID = Header(...), sessiontoken: str = Header(...), location: str = Header(...)):
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
    is_authenticated = await authenticate_session_token(app_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")
    
    # Update the user's location
    new_location_list = [float(coord) for coord in location.split(",")]
    await update_user_location(app_db_database, user_id, new_location_list)
    logger.debug(f"Updated location for user with ID: {user_id}.")
    
    # Fetch events initiated by the user where is_open is True
    events = Table(
        "events",
        metadata,
        extend_existing=True
    )
    query = events.select().where(and_(events.c.initiated_by == user_id, events.c.is_open == True))
    open_events = await app_db_database.fetch_all(query)
    
    # Update location for each open event
    for event in open_events:
        await update_event_location(app_db_database, event["event_id"], new_location_list)
        logger.debug(f"Updated location for event with ID: {event['event_id']}.")
    
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
    is_authenticated = await authenticate_session_token(app_db_database, user_id, sessiontoken)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user with ID: {user_id}.")
        raise HTTPException(status_code=401, detail="Authentication failed.")
    
    # Define the structure of the users table for reference
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("first_name", Text, nullable=False),
        Column("last_name", Text, nullable=False),
        Column("middle_name", Text),
        Column("username", Text),
        Column("email", Text, unique=True, nullable=False),
        Column("birthdate", DATE, nullable=False),
        Column("gender", Text, nullable=False),
        Column("location", Text, nullable=False),
        Column("profile_photo_url", Text),
        Column("description", Text),
        Column("last_online", TIMESTAMP),
        Column("is_online", Boolean, default=False),
        Column("social_media_links", JSONB),
        extend_existing=True
    )

    # Update user profile
    query = update(users).where(users.c.user_id == user_id).values(**user_data.dict(exclude_unset=True))
    await app_db_database.execute(query)

    logger.debug(f"Profile updated successfully for user with ID: {user_id}.")
    
    return {"message": "Profile updated successfully for the user."}


@app.post("/create_event")
async def create_event_endpoint(
        event_dict: dict,  # Change this to receive a dictionary
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
          "location": [40.7128, -74.0060],
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
    
    # Authenticate the user using the provided user_id and sessiontoken.
    if not await authenticate_user(user_id, sessiontoken):
        raise HTTPException(status_code=401, detail="User authentication failed.")
    
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
    event_data: dict,
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
    is_authenticated = await authenticate_session_token(app_db_database, user_id, sessiontoken)
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