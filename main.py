from fastapi import FastAPI, Depends, HTTPException, Header
from databases import Database
from sqlalchemy import create_engine, MetaData, Table, Column, String, Date, Boolean, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID

from functions import *

from classes import User

# create the api object
app = FastAPI(
    title="LetsClique app API",
    description="This is the API for the LetsClique app."
)

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