from fastapi import FastAPI, Depends, HTTPException, Header
from databases import Database
from sqlalchemy import create_engine, MetaData, Table, Column, String, Date, Boolean, TIMESTAMP, Text, select, and_, BIGINT, Integer, ARRAY, join, update, JSON, CheckConstraint, DateTime, insert, or_

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Union, Any

import uuid
import hashlib
import os
import logging
import math

# Setting up logging
logger = logging.getLogger(__name__)


# creating logger for custom logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

metadata = MetaData()

def verify_URL_token(token: str = ""):
    if token != "AreYouThere?":
        raise HTTPException(status_code=403, detail="Invalid access token")
    return token


def verify_header_token(token: str = Header(default=None)):
    if token != "AreYouThere?":
        raise HTTPException(status_code=403, detail="Invalid access token")
    return token


async def insert_user(db: Database, user_data: Dict):
    """
    Inserts a new user into the users table in the app_db database.

    Parameters:
    - db: The database connection.
    - user_data (dict): A dictionary containing user data with the following keys:
        - user_id (UUID): Unique identifier for the user.
        - first_name (str): User's first name.
        - last_name (str): User's last name.
        - middle_name (str, optional): User's middle name.
        - username (str, optional): User's username.
        - email (str): User's email address.
        - birthdate (date): User's birthdate.
        - gender (str): User's gender ('male', 'female', 'other').
        - location (POINT): Geographical point representing user's location.
        - profile_photo_url (str, optional): URL to the user's profile photo.
        - description (str, optional): Description or bio of the user.
        - last_online (TIMESTAMP, optional): Timestamp of the user's last online activity.
        - is_online (bool, default False): Whether the user is currently online.
        - social_media_links (JSONB, optional): JSON object containing user's social media links.

    Returns:
    - The user_id of the inserted user.
    """
    
    # Convert the birthdate string to a date object
    birthdate_str = user_data["birthdate"]
    birthdate_date = datetime.strptime(birthdate_str, "%Y-%m-%d").date()
    user_data["birthdate"] = birthdate_date
    
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
    
    query = users.insert().values(**user_data)
    
    return await db.execute(query)


def hash_input_with_salt(input_str: str) -> dict:
    """
    Hashes the provided input string using SHA-256 with a randomly generated salt.

    The function generates a random salt, then hashes the input string concatenated 
    with this salt using the SHA-256 algorithm. The resultant hash and the salt 
    are both returned.

    Parameters:
    - input_str (str): The string to be hashed.

    Returns:
    - dict: A dictionary containing:
        - 'salt': The randomly generated salt used in the hashing process.
        - 'hash': The resultant SHA-256 hash of the input string combined with the salt.

    Example:
    >>> hash_input_with_salt("password123")
    {'salt': 'SOME_RANDOM_SALT', 'hash': 'SHA256_HASH_OF_INPUT_AND_SALT'}
    """
    
    # Generate a random salt
    salt = os.urandom(16).hex()
    
    # Concatenate the input string with the salt and then hash using SHA-256
    input_with_salt = (input_str + salt).encode('utf-8')
    hash_result = hashlib.sha256(input_with_salt).hexdigest()
    
    return {'salt': salt, 'hash': hash_result}


async def insert_user_auth(db: Database, user_id: uuid.UUID, username: str, email: str, hashed_password: str, salt: str) -> dict:
    """
    Adds user authentication data to the `users_auth` table in the `auth_db` database.

    This function inserts the provided user authentication data into the `users_auth` table. 
    The `is_active` and `is_superuser` fields are set to their default values as defined in 
    the schema. The `last_login` field is set to the current timestamp.

    Parameters:
    - db (Database): The database connection.
    - user_id (uuid.UUID): Unique identifier for the user.
    - username (str): User's username.
    - email (str): User's email address.
    - hashed_password (str): The SHA-256 hashed password for the user.
    - salt (str): The salt used in the password hashing process.

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful addition.

    Errors:
    - Will raise any database-related errors, such as constraint violations.
    """
    
    # Define the structure of the users_auth table
    users_auth = Table(
        "users_auth",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("username", String, unique=True, nullable=False),
        Column("email", String, unique=True, nullable=False),
        Column("hashed_password", String, nullable=False),
        Column("salt", String, nullable=False),
        Column("is_active", Boolean, default=True),
        Column("is_superuser", Boolean, default=False),
        Column("created_at", TIMESTAMP, default=func.now()),
        Column("updated_at", TIMESTAMP, default=func.now()),
        Column("last_login", TIMESTAMP, default=func.now()),
        extend_existing=True
    )

    
    # Insert the user authentication data into the users_auth table
    query = users_auth.insert().values(
        user_id=user_id,
        username=username,
        email=email,
        hashed_password=hashed_password,
        salt=salt
    )
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User authentication data successfully added!'}


async def update_user_location(db: Database, user_id: UUID, coordinates: List[float]):
    """
    Update the location of a user in the users table.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.
    - coordinates (List[float]): A list containing latitude and longitude.

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful update.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("location", Text, nullable=False),
        extend_existing=True
    )

    # Update the location of the user in the users table
    query = update(users).where(users.c.user_id == user_id).values(location=coordinates)
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User location successfully updated!'}


async def update_user_profile_photo_url(db: Database, user_id: UUID, profile_photo_url: str):
    """
    Update the profile_photo_url of a user in the users table.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.
    - profile_photo_url (str): New value for the profile_photo_url field.

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful update.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("profile_photo_url", Text),
        extend_existing=True
    )

    # Update the profile_photo_url of the user in the users table
    query = update(users).where(users.c.user_id == user_id).values(profile_photo_url=profile_photo_url)
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User profile_photo_url successfully updated!'}


async def update_user_description(db: Database, user_id: UUID, description: str):
    """
    Update the description of a user in the users table.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.
    - description (str): New value for the description field.

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful update.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("description", Text),
        extend_existing=True
    )

    # Update the description of the user in the users table
    query = update(users).where(users.c.user_id == user_id).values(description=description)
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User description successfully updated!'}


async def update_user_last_online(db: Database, user_id: UUID):
    """
    Update the last_online timestamp of a user in the users table to the current timestamp.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful update.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("last_online", TIMESTAMP),
        extend_existing=True
    )

    # Update the last_online timestamp of the user in the users table to the current timestamp
    current_timestamp = datetime.now()
    query = update(users).where(users.c.user_id == user_id).values(last_online=current_timestamp)
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User last_online successfully updated!'}


async def update_user_social_media_links(db: Database, user_id: UUID, social_media_links: Dict):
    """
    Update the social_media_links JSONB field of a user in the users table.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.
    - social_media_links (Dict): New JSONB value for the social_media_links field.

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful update.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("social_media_links", JSONB),
        extend_existing=True
    )

    # Update the social_media_links of the user in the users table
    query = update(users).where(users.c.user_id == user_id).values(social_media_links=social_media_links)
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User social_media_links successfully updated!'}


async def update_user_first_name(db: Database, user_id: UUID, first_name: str):
    """
    Update the first_name of a user in the users table.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.
    - first_name (str): New value for the first_name field.

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful update.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("first_name", Text, nullable=False),
        extend_existing=True
    )

    # Update the first_name of the user in the users table
    query = update(users).where(users.c.user_id == user_id).values(first_name=first_name)
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User first_name successfully updated!'}


async def update_user_last_name(db: Database, user_id: UUID, last_name: str):
    """
    Update the last_name of a user in the users table.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.
    - last_name (str): New value for the last_name field.

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful update.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("last_name", Text, nullable=False),
        extend_existing=True
    )

    # Update the last_name of the user in the users table
    query = update(users).where(users.c.user_id == user_id).values(last_name=last_name)
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User last_name successfully updated!'}


async def update_user_middle_name(db: Database, user_id: UUID, middle_name: str):
    """
    Update the middle_name of a user in the users table.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.
    - middle_name (str): New value for the middle_name field.

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful update.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("middle_name", Text),
        extend_existing=True
    )

    # Update the middle_name of the user in the users table
    query = update(users).where(users.c.user_id == user_id).values(middle_name=middle_name)
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User middle_name successfully updated!'}


async def update_user_username(db: Database, user_id: UUID, username: str):
    """
    Update the username of a user in the users table.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.
    - username (str): New value for the username field.

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful update.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("username", Text, nullable=False),
        extend_existing=True
    )

    # Update the username of the user in the users table
    query = update(users).where(users.c.user_id == user_id).values(username=username)
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User username successfully updated!'}


async def update_user_email(db: Database, user_id: UUID, email: str):
    """
    Update the email of a user in the users table.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.
    - email (str): New value for the email field.

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful update.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("email", Text, nullable=False, unique=True),
        extend_existing=True
    )

    # Update the email of the user in the users table
    query = update(users).where(users.c.user_id == user_id).values(email=email)
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User email successfully updated!'}


async def update_user_birthdate(db: Database, user_id: UUID, birthdate: str):
    """
    Update the birthdate of a user in the users table.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.
    - birthdate (str): New value for the birthdate field (formatted as 'YYYY-MM-DD').

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful update.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("birthdate", DATE, nullable=False),
        extend_existing=True
    )

    # Update the birthdate of the user in the users table
    query = update(users).where(users.c.user_id == user_id).values(birthdate=birthdate)
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User birthdate successfully updated!'}


async def update_user_gender(db: Database, user_id: UUID, gender: str):
    """
    Update the gender of a user in the users table.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.
    - gender (str): New value for the gender field. Valid values are 'male', 'female', or 'other'.

    Returns:
    - dict: A dictionary containing:
        - 'user_id': The UUID of the user.
        - 'message': A confirmation message indicating successful update.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("gender", Text, nullable=False),
        extend_existing=True
    )

    # Ensure the gender value is valid
    if gender not in ['male', 'female', 'other']:
        raise ValueError("Invalid gender value. Must be 'male', 'female', or 'other'.")

    # Update the gender of the user in the users table
    query = update(users).where(users.c.user_id == user_id).values(gender=gender)
    
    await db.execute(query)

    return {'user_id': user_id, 'message': 'User gender successfully updated!'}


async def get_user_first_name(db: Database, user_id: UUID) -> str:
    """
    Retrieve the first_name of a user based on user ID.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.

    Returns:
    - str: The first_name of the user.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("first_name", Text, nullable=False),
        extend_existing=True
    )

    # Query to get the first_name of the user based on user ID
    query = select([users.c.first_name]).where(users.c.user_id == user_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No user found with user_id {user_id}")

    return result["first_name"]


async def get_user_last_name(db: Database, user_id: UUID) -> str:
    """
    Retrieve the last_name of a user based on user ID.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.

    Returns:
    - str: The last_name of the user.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("last_name", Text, nullable=False),
        extend_existing=True
    )

    # Query to get the last_name of the user based on user ID
    query = select([users.c.last_name]).where(users.c.user_id == user_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No user found with user_id {user_id}")

    return result["last_name"]


async def get_user_middle_name(db: Database, user_id: UUID) -> Optional[str]:
    """
    Retrieve the middle_name of a user based on user ID.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.

    Returns:
    - str: The middle_name of the user, or None if the user does not have a middle name.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("middle_name", Text),
        extend_existing=True
    )

    # Query to get the middle_name of the user based on user ID
    query = select([users.c.middle_name]).where(users.c.user_id == user_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No user found with user_id {user_id}")

    return result["middle_name"]


async def get_user_username(db: Database, user_id: UUID) -> str:
    """
    Retrieve the username of a user based on user ID.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.

    Returns:
    - str: The username of the user.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("username", Text, nullable=False),
        extend_existing=True
    )

    # Query to get the username of the user based on user ID
    query = select([users.c.username]).where(users.c.user_id == user_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No user found with user_id {user_id}")

    return result["username"]


async def get_user_email(db: Database, user_id: UUID) -> str:
    """
    Retrieve the email of a user based on user ID.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.

    Returns:
    - str: The email of the user.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("email", Text, nullable=False, unique=True),
        extend_existing=True
    )

    # Query to get the email of the user based on user ID
    query = select([users.c.email]).where(users.c.user_id == user_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No user found with user_id {user_id}")

    return result["email"]


async def get_user_birthdate(db: Database, user_id: UUID) -> str:
    """
    Retrieve the birthdate of a user based on user ID.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.

    Returns:
    - str: The birthdate of the user, formatted as 'YYYY-MM-DD'.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("birthdate", DATE, nullable=False),
        extend_existing=True
    )

    # Query to get the birthdate of the user based on user ID
    query = select([users.c.birthdate]).where(users.c.user_id == user_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No user found with user_id {user_id}")

    # Convert the date object to string format
    return str(result["birthdate"])


async def get_user_gender(db: Database, user_id: UUID) -> str:
    """
    Retrieve the gender of a user based on user ID.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.

    Returns:
    - str: The gender of the user. Valid values are 'male', 'female', or 'other'.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("gender", Text, nullable=False),
        extend_existing=True
    )

    # Query to get the gender of the user based on user ID
    query = select([users.c.gender]).where(users.c.user_id == user_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No user found with user_id {user_id}")

    return result["gender"]


async def get_user_profile_photo_url(db: Database, user_id: UUID) -> Optional[str]:
    """
    Retrieve the profile_photo_url of a user based on user ID.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.

    Returns:
    - str: The profile_photo_url of the user, or None if the user does not have a profile photo URL.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("profile_photo_url", Text),
        extend_existing=True
    )

    # Query to get the profile_photo_url of the user based on user ID
    query = select([users.c.profile_photo_url]).where(users.c.user_id == user_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No user found with user_id {user_id}")

    return result["profile_photo_url"]


async def get_user_description(db: Database, user_id: UUID) -> Optional[str]:
    """
    Retrieve the description of a user based on user ID.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.

    Returns:
    - str: The description of the user, or None if the user does not have a description.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("description", Text),
        extend_existing=True
    )

    # Query to get the description of the user based on user ID
    query = select([users.c.description]).where(users.c.user_id == user_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No user found with user_id {user_id}")

    return result["description"]


async def get_user_last_online(db: Database, user_id: UUID) -> str:
    """
    Retrieve the last_online timestamp of a user based on user ID.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.

    Returns:
    - str: The last_online timestamp of the user, formatted as 'YYYY-MM-DD HH:MM:SS'.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("last_online", TIMESTAMP),
        extend_existing=True
    )

    # Query to get the last_online timestamp of the user based on user ID
    query = select([users.c.last_online]).where(users.c.user_id == user_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No user found with user_id {user_id}")

    # Convert the timestamp object to string format
    return str(result["last_online"])


async def get_user_social_media_links(db: Database, user_id: UUID) -> dict:
    """
    Retrieve the social_media_links JSONB field of a user based on user ID.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): Unique identifier for the user.

    Returns:
    - dict: The social_media_links of the user.
    """

    # Define the structure of the users table
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("social_media_links", JSONB),
        extend_existing=True
    )

    # Query to get the social_media_links of the user based on user ID
    query = select([users.c.social_media_links]).where(users.c.user_id == user_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No user found with user_id {user_id}")

    return result["social_media_links"]


async def insert_event(db: Database, event_data: Dict):
    """
    Inserts a new event into the events table in the app_db database.

    Parameters:
    - db: The database connection.
    - event_data (dict): A dictionary containing event data with the following keys:
        - event_id (UUID): Unique identifier for the event.
        - activity_id (BIGINT): Identifier for the activity.
        - initiated_by (UUID): Identifier for the user initiating the event.
        - location (POINT): Geographical point representing event's location.
        - address (Text, optional): Address where the event is taking place.
        - participant_min_age (INT): Minimum age for participants.
        - participant_max_age (INT): Maximum age for participants.
        - participant_pref_genders (TEXT[]): Preferred genders for participants.
        - description (TEXT): Description of the event.
        - event_picture_url (Text, optional): URL to the event's picture.
        - event_date_time (TIMESTAMP, optional): Timestamp of when the event will take place.

    Returns:
    - The event_id of the inserted event.
    """
    
    # Auto-generate the initiated_on timestamp
    initiated_on_timestamp = datetime.now()
    event_data["initiated_on"] = initiated_on_timestamp
    
    # Open event
    event_data["is_open"] = True
    
    # Define structure of the events table
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
    
    query = events.insert().values(**event_data)
    
    logger.debug(f"Inserting event with ID: {event_data['event_id']}.")
    result = await db.execute(query)
    logger.info(f"Successfully inserted event with ID: {event_data['event_id']}.")
    
    return result


async def get_event_activity_id(db: Database, event_id: UUID) -> int:
    """
    Retrieve the activity_id of an event based on event ID.

    Parameters:
    - db (Database): The database connection.
    - event_id (UUID): Unique identifier for the event.

    Returns:
    - int: The activity_id of the event.
    """

    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("activity_id", BIGINT, nullable=False),
        extend_existing=True
    )

    # Query to get the activity_id of the event based on event ID
    query = select([events.c.activity_id]).where(events.c.event_id == event_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No event found with event_id {event_id}")

    return result["activity_id"]


async def get_event_initiated_by(db: Database, event_id: UUID) -> UUID:
    """
    Retrieve the initiated_by user ID of an event based on event ID.

    Parameters:
    - db (Database): The database connection.
    - event_id (UUID): Unique identifier for the event.

    Returns:
    - UUID: The initiated_by user ID of the event.
    """

    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("initiated_by", UUID, nullable=False),
        extend_existing=True
    )

    # Query to get the initiated_by user ID of the event based on event ID
    query = select([events.c.initiated_by]).where(events.c.event_id == event_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No event found with event_id {event_id}")

    return result["initiated_by"]


async def get_event_location(db: Database, event_id: UUID) -> List[float]:
    """
    Retrieve the location of an event based on event ID.

    Parameters:
    - db (Database): The database connection.
    - event_id (UUID): Unique identifier for the event.

    Returns:
    - List[float]: The geographical POINT representing the location of the event.
    """

    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("location", Text, nullable=False),
        extend_existing=True
    )

    # Query to get the location of the event based on event ID
    query = select([events.c.location]).where(events.c.event_id == event_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No event found with event_id {event_id}")

    # Parse the POINT to a tuple of floats (assuming a format like 'POINT(x y)')
    x, y = map(float, result["location"][6:-1].split())
    return (x, y)


async def get_event_address(db: Database, event_id: UUID) -> Optional[str]:
    """
    Retrieve the address of an event based on event ID.

    Parameters:
    - db (Database): The database connection.
    - event_id (UUID): Unique identifier for the event.

    Returns:
    - str: The address related to the event, or None if the address is not provided.
    """

    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("address", Text),
        extend_existing=True
    )

    # Query to get the address of the event based on event ID
    query = select([events.c.address]).where(events.c.event_id == event_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No event found with event_id {event_id}")

    return result["address"]


async def get_event_participant_min_age(db: Database, event_id: UUID) -> int:
    """
    Retrieve the participant_min_age of an event based on event ID.

    Parameters:
    - db (Database): The database connection.
    - event_id (UUID): Unique identifier for the event.

    Returns:
    - int: The minimum age for participants of the event.
    """

    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("participant_min_age", INT, nullable=False),
        extend_existing=True
    )

    # Query to get the participant_min_age of the event based on event ID
    query = select([events.c.participant_min_age]).where(events.c.event_id == event_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No event found with event_id {event_id}")

    return result["participant_min_age"]


async def get_event_participant_max_age(db: Database, event_id: UUID) -> int:
    """
    Retrieve the participant_max_age of an event based on event ID.

    Parameters:
    - db (Database): The database connection.
    - event_id (UUID): Unique identifier for the event.

    Returns:
    - int: The maximum age for participants of the event.
    """

    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("participant_max_age", INT, nullable=False),
        extend_existing=True
    )

    # Query to get the participant_max_age of the event based on event ID
    query = select([events.c.participant_max_age]).where(events.c.event_id == event_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No event found with event_id {event_id}")

    return result["participant_max_age"]


async def get_event_participant_pref_genders(db: Database, event_id: UUID) -> List[str]:
    """
    Retrieve the participant_pref_genders of an event based on event ID.

    Parameters:
    - db (Database): The database connection.
    - event_id (UUID): Unique identifier for the event.

    Returns:
    - List[str]: List of preferred genders for participants of the event.
    """

    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("participant_pref_genders", ARRAY(Text), nullable=False),
        extend_existing=True
    )

    # Query to get the participant_pref_genders of the event based on event ID
    query = select([events.c.participant_pref_genders]).where(events.c.event_id == event_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No event found with event_id {event_id}")

    return result["participant_pref_genders"]


async def get_event_description(db: Database, event_id: UUID) -> str:
    """
    Retrieve the description of an event based on event ID.

    Parameters:
    - db (Database): The database connection.
    - event_id (UUID): Unique identifier for the event.

    Returns:
    - str: The description of the event.
    """

    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("description", Text, nullable=False),
        extend_existing=True
    )

    # Query to get the description of the event based on event ID
    query = select([events.c.description]).where(events.c.event_id == event_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No event found with event_id {event_id}")

    return result["description"]


async def get_event_is_open(db: Database, event_id: UUID) -> bool:
    """
    Retrieve the is_open status of an event based on event ID.

    Parameters:
    - db (Database): The database connection.
    - event_id (UUID): Unique identifier for the event.

    Returns:
    - bool: Indicates if the event is open for new participants.
    """

    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("is_open", BOOLEAN, nullable=False),
        extend_existing=True
    )

    # Query to get the is_open status of the event based on event ID
    query = select([events.c.is_open]).where(events.c.event_id == event_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No event found with event_id {event_id}")

    return result["is_open"]


async def get_event_initiated_on(db: Database, event_id: UUID) -> str:
    """
    Retrieve the initiated_on timestamp of an event based on event ID.

    Parameters:
    - db (Database): The database connection.
    - event_id (UUID): Unique identifier for the event.

    Returns:
    - str: The initiated_on timestamp of the event, formatted as 'YYYY-MM-DD HH:MM:SS'.
    """

    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("initiated_on", TIMESTAMP, nullable=False),
        extend_existing=True
    )

    # Query to get the initiated_on timestamp of the event based on event ID
    query = select([events.c.initiated_on]).where(events.c.event_id == event_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No event found with event_id {event_id}")

    # Convert the timestamp object to string format
    return str(result["initiated_on"])


async def get_event_picture_url(db: Database, event_id: UUID) -> Optional[str]:
    """
    Retrieve the event_picture_url of an event based on event ID.

    Parameters:
    - db (Database): The database connection.
    - event_id (UUID): Unique identifier for the event.

    Returns:
    - str: The URL for the event picture, or None if the URL is not provided.
    """

    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("event_picture_url", Text),
        extend_existing=True
    )

    # Query to get the event_picture_url of the event based on event ID
    query = select([events.c.event_picture_url]).where(events.c.event_id == event_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No event found with event_id {event_id}")

    return result["event_picture_url"]


async def get_event_date_time(db: Database, event_id: UUID) -> str:
    """
    Retrieve the event_date_time of an event based on event ID.

    Parameters:
    - db (Database): The database connection.
    - event_id (UUID): Unique identifier for the event.

    Returns:
    - str: The event_date_time timestamp of the event, formatted as 'YYYY-MM-DD HH:MM:SS'.
    """

    # Define the structure of the events table
    events = Table(
        "events",
        metadata,
        Column("event_id", UUID, primary_key=True),
        Column("event_date_time", TIMESTAMP),
        extend_existing=True
    )

    # Query to get the event_date_time of the event based on event ID
    query = select([events.c.event_date_time]).where(events.c.event_id == event_id)
    
    result = await db.fetch_one(query)

    if not result:
        raise ValueError(f"No event found with event_id {event_id}")

    # Convert the timestamp object to string format
    return str(result["event_date_time"])


async def authenticate_user(db: Database, email: str, hashed_password: str) -> List[Union[bool, Optional[UUID]]]:
    """
    Authenticate a user based on email and hashed_password.

    Parameters:
    - db (Database): The database connection to auth_db.
    - email (str): User's email address.
    - hashed_password (str): Hashed password of the user.

    Returns:
    - List[bool, Optional[UUID]]: 
      True and the corresponding user_id if a match is found, 
      False and None if no match is found.
    """
    
    logger.debug(f"Entering authenticate_user function for email: {email}.")

    # Define the structure of the users_auth table
    users_auth = Table(
        "users_auth",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("email", String, unique=True, nullable=False),
        Column("hashed_password", String, nullable=False),
        extend_existing=True
    )

    # Query to get the user_id based on email and hashed_password
    query = select([users_auth.c.user_id]).where(
        and_(users_auth.c.email == email, users_auth.c.hashed_password == hashed_password)
    )
    
    result = await db.fetch_one(query)
    
    if not result:
        logger.warning(f"No user found matching email: {email} and provided hashed_password.")
        return False, None

    logger.debug(f"User with email: {email} authenticated successfully.")
    return True, result["user_id"]


async def generate_session_token(db: Database, email: str, password_str: str) -> List[Union[UUID, str]]:
    """
    Generates a session token for a user.

    Parameters:
    - db (Database): The database connection to auth_db.
    - email (str): The user's email.
    - password_str (str): The user's plaintext password.

    Returns:
    - List[UUID, str]: The user_id and the generated session token.
    """

    logger.debug("Entering generate_session_token function.")
    
    # Search for user_id and salt based on email
    users_auth = Table(
        "users_auth",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("email", Text, unique=True, nullable=False),
        Column("salt", Text, nullable=False),
        extend_existing=True
    )

    query = select([users_auth.c.user_id, users_auth.c.salt]).where(users_auth.c.email == email)
    result = await db.fetch_one(query)
    
    if not result:
        logger.warning(f"No user found with email: {email}.")
        raise ValueError("Email not found.")

    user_id, salt = result["user_id"], result["salt"]

    # Generate hashed password
    password_with_salt = (password_str + salt).encode('utf-8')
    hash_result = hashlib.sha256(password_with_salt).hexdigest()

    # Authenticate user using authenticate_user function
    auth_success, auth_user_id = await authenticate_user(db, email, hash_result)
    if not auth_success:
        logger.warning(f"Authentication failed for email: {email}.")
        raise ValueError("Authentication failed.")

    # Generate an entry in the user_sessions table
    expiry_date = datetime.now() + timedelta(days=30)  # 1 month from now
    token = hashlib.sha256((email + str(datetime.now())).encode('utf-8')).hexdigest()

    user_sessions = Table(
        "user_sessions",
        metadata,
        Column("user_id", UUID),
        Column("token", Text, unique=True, nullable=False),
        Column("expiry", TIMESTAMP, nullable=False),
        extend_existing=True
    )

    query = user_sessions.insert().values(user_id=user_id, token=token, expiry=expiry_date)
    await db.execute(query)

    # Return user_id and token
    logger.debug("Exiting generate_session_token function.")
    return user_id, token


async def authenticate_session_token(db: Database, user_id: UUID, token: str) -> bool:
    """
    Authenticate a session token for a user.
    
    Parameters:
    - db (Database): The database connection to auth_db.
    - user_id (UUID): The user's unique identifier.
    - token (str): The session token to be authenticated.

    Returns:
    - bool: True if the token is valid and not expired, False otherwise.
    """
    
    logger.debug(f"Entering authenticate_session_token function for user_id: {user_id}.")
    
    # Define the structure of the user_sessions table
    user_sessions = Table(
        "user_sessions",
        metadata,
        Column("user_id", UUID),
        Column("token", String, unique=True, nullable=False),
        Column("expiry", DateTime, nullable=False),
        extend_existing=True
    )

    # Query to check if the user_id and token exist in the same record and if the token is not expired
    current_time = datetime.now()
    query = select([user_sessions.c.token]).where(
        and_(user_sessions.c.user_id == user_id, user_sessions.c.token == token, user_sessions.c.expiry > current_time)
    )
    
    result = await db.fetch_one(query)
    
    if result:
        logger.debug(f"Token authenticated successfully for user_id: {user_id}.")
        return True
    else:
        logger.warning(f"Token authentication failed for user_id: {user_id}.")
        return False


async def update_event_location(db: Database, event_id: UUID, new_location: List[float]) -> None:
    """
    Updates the location of a specified event in the events table.

    Parameters:
    - db (Database): The database connection to app_db.
    - event_id (UUID): The unique identifier of the event.
    - new_location (List[float]): A list containing the new latitude and longitude coordinates of the event.

    Returns:
    - None: The function will update the event's location in the database.
    """
    
    logger.debug(f"Entering update_event_location function for event_id: {event_id} with new location: {new_location}.")

    try:
        # Define the structure of the events table
        events = Table(
            "events",
            metadata,
            Column("event_id", UUID, primary_key=True),
            Column("location", Text, nullable=False),
            extend_existing=True
        )
        
        # Construct the update query
        query = events.update().where(events.c.event_id == event_id).values(location=str(new_location))
        
        # Execute the update query
        await db.execute(query)
        
        logger.debug(f"Successfully updated location for event with ID: {event_id}.")
        
        return {'event_id': event_id, 'message': 'Event location successfully updated!'}

    
    except Exception as e:
        logger.error(f"Error while updating location for event with ID: {event_id}. Error: {str(e)}")
        raise e  # Re-raise the exception after logging


async def get_activity_id(db: Database, activity_name: str) -> int:
    """
    Fetch the activity_id corresponding to a given activity_name from the activities table.

    Parameters:
    - db (Database): The database connection.
    - activity_name (str): The name of the activity.

    Returns:
    - int: The activity_id corresponding to the provided activity_name.
    """
    
    # Define the SQLAlchemy ORM structure for the activities table.
    activities = Table(
        "activities",
        metadata,
        Column("activity_name", String, unique=True, nullable=False),
        Column("activity_id", BIGINT, primary_key=True),
        extend_existing=True
    )
    
    # Log the attempt to fetch the activity_id.
    logger.info(f"Attempting to fetch activity_id for activity_name: {activity_name}")
    
    # Construct the SQL query to retrieve the activity_id for the given activity_name.
    query = select([activities.c.activity_id]).where(activities.c.activity_name == activity_name)
    
    # Execute the query.
    result = await db.fetch_one(query)

    # Check if the result exists. If not, log an error and raise an exception.
    if not result:
        logger.error(f"No activity found with name: {activity_name}")
        raise ValueError(f"No activity found with name: {activity_name}")
    
    # Log the successful retrieval of the activity_id.
    logger.debug(f"Fetched activity_id {result['activity_id']} for activity_name: {activity_name}")
    
    # Return the retrieved activity_id.
    return result["activity_id"]


async def close_event(db: Database, event_id: uuid.UUID) -> None:
    """
    Close an event by setting its is_open field to False.

    Parameters:
    - db (Database): The database connection.
    - event_id (uuid.UUID): The unique identifier of the event to be closed.

    Raises:
    - ValueError: If no event is found with the provided event_id.

    Returns:
    - None: The function returns nothing but logs the event's closure process.
    """
    
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

    logger.debug(f"Attempting to close event with ID: {event_id}.")
    
    # Update the is_open field of the event
    query = (
        update(events)
        .where(events.c.event_id == event_id)
        .values(is_open=False)
    )
    result = await db.execute(query)

    # Check the number of rows affected
    if result == 0:
        logger.error(f"No event found with ID: {event_id}.")
        raise ValueError(f"No event found with ID: {event_id}.")
    
    logger.info(f"Successfully closed event with ID: {event_id}.")


def haversine_distance(loc1: list, loc2: list) -> int:
    """
    Calculate the Haversine distance between two points on the earth specified by latitude and longitude.

    Parameters:
    - loc1 (list): A list containing the latitude and longitude of the first location.
    - loc2 (list): A list containing the latitude and longitude of the second location.

    Returns:
    - int: The distance between the two locations in kilometers (rounded to the nearest whole number).
    
    Example:
    >>> haversine_distance([40.7128, -74.0060], [34.0522, -118.2437])
    3931
    """
    
    # Check if the locations have the correct format
    if not (len(loc1) == 2 and len(loc2) == 2):
        logger.error("Invalid location format. Each location should be a list with 2 elements.")
        raise ValueError("Each location should be a list with 2 elements: [latitude, longitude].")
    
    logger.debug(f"Calculating distance between {loc1} and {loc2}")
    
    # Radius of the Earth in kilometers
    R = 6371.0
    
    # Convert degrees to radians
    lat1 = math.radians(loc1[0])
    lon1 = math.radians(loc1[1])
    lat2 = math.radians(loc2[0])
    lon2 = math.radians(loc2[1])
    
    # Compute differences between the two sets of lat/longs
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    # Haversine formula
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c

    logger.debug(f"Calculated distance: {distance} km")
    
    return int(round(distance))


async def get_user_location(db, user_id: UUID) -> str:
    """
    Fetch the location of a user based on the provided user_id from the users table.

    Parameters:
    - db (Database): The database connection.
    - user_id (UUID): The unique identifier of the user.

    Returns:
    - str: The location of the user.

    Errors:
    - ValueError: If no user is found with the provided user_id.
    """
    
    # Define the structure of the users table for reference
    users = Table(
        "users",
        metadata,
        Column("user_id", UUID, primary_key=True),
        Column("location", String, nullable=False),
        extend_existing=True
    )
    
    logger.info(f"Attempting to fetch location for user with ID: {user_id}")

    # Construct the select query
    query = select([users.c.location]).where(users.c.user_id == user_id)
    result = await db.fetch_one(query)

    if not result:
        logger.error(f"No user found with ID: {user_id}")
        raise ValueError(f"No user found with ID: {user_id}")

    location = result["location"]
    
    logger.debug(f"Fetched location {location} for user with ID: {user_id}")
    return location


