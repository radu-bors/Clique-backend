from fastapi import FastAPI, Depends, HTTPException, Header

app = FastAPI()

def verify_URL_token(token: str = ""):
    if token != "AreYouThere?":
        raise HTTPException(status_code=403, detail="Invalid access token")
    return token

@app.get("/status_URL_token")
def read_root(token: str = Depends(verify_URL_token)):
    return {"message": "Yep, I'm functional with URL tokens"}

def verify_header_token(token: str = Header(default=None)):
    if token != "AreYouThere?":
        raise HTTPException(status_code=403, detail="Invalid access token")
    return token

@app.get("/status_header_token")
def read_root(token: str = Depends(verify_header_token)):
    return {"message": "Yep, I'm functional with header tokens"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
