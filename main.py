from fastapi import FastAPI, Depends, HTTPException, Header
from databases import Database

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