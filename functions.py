from fastapi import FastAPI, Depends, HTTPException, Header
from databases import Database
from sqlalchemy import create_engine, MetaData, Table, Column, String, Date, Boolean, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from typing import Optional, Dict

import uuid
import hashlib
import os

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
        Column("gender", String, nullable=False, 
               check=CheckConstraint("gender IN ('male', 'female', 'other')")),
        Column("location", Text, nullable=False), # Using Text for simplicity; consider using a specific type for POINT if needed
        Column("profile_photo_url", String),
        Column("description", String, 
               check=CheckConstraint("CHAR_LENGTH(description) <= 1000")),
        Column("last_online", TIMESTAMP),
        Column("is_online", Boolean, default=False),
        Column("social_media_links", JSON)
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
        Column("created_at", TIMESTAMP, default=datetime.now()),
        Column("updated_at", TIMESTAMP, default=datetime.now()),
        Column("last_login", TIMESTAMP, default=datetime.now())
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

