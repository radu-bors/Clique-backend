from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

class User(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    username: Optional[str] = None
    email: EmailStr
    birthdate: str
    gender: str
    location: str
    profile_photo_url: Optional[str] = None
    description: Optional[str] = None
    last_online: Optional[str] = None
    is_online: bool = False
    social_media_links: Optional[dict] = None
