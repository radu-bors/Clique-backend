from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, List
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

class Event(BaseModel):
    event_id: uuid.UUID = uuid.uuid4()
    activity_id: int
    initiated_by: uuid.UUID
    location: List[float]
    address: Optional[str] = None
    participant_min_age: int
    participant_max_age: int
    participant_pref_genders: List[str]
    description: str
    event_picture_url: Optional[str] = None
    event_date_time: Optional[datetime] = None

class EventFilterCriteria(BaseModel):
    activity_names: List[str]
    pref_genders: List[str]
    min_age: int
    max_age: int
    radius: float