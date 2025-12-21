from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field

class ConsentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    consent: bool

class DemographicsIn(BaseModel):
    age_band: str
    gender: str
    puzzle_experience: str
