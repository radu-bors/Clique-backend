from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid
from datetime import datetime

class User(BaseModel):
    user_id: uuid.UUID = uuid.uuid4()
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    username: str
    email: EmailStr
    birthdate: str
    gender: str
    location: List[float]
    profile_photo_url: Optional[str] = None
    description: Optional[str] = None
    last_online: datetime = datetime.now()
    social_media_links: Optional[dict] = None

