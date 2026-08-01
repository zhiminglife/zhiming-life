"""Typed HTTP contracts shared by the local desktop API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BirthInfo(BaseModel):
    calendar: Literal["solar", "lunar"] = "solar"
    year: int = Field(ge=1900, le=2200)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    hour: int = Field(ge=-1, le=23)
    gender: Literal["male", "female"]
    is_leap_month: bool = False
    birth_place: str = ""


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    relationship: str = Field(default="other", max_length=40)
    birth: BirthInfo | None = None
    notes: str = Field(default="", max_length=1000)


class PersonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    relationship: str | None = Field(default=None, max_length=40)
    birth: BirthInfo | None = None
    notes: str | None = Field(default=None, max_length=1000)


class Person(PersonCreate):
    id: str
    created_at: str
    updated_at: str


class SessionCreate(BaseModel):
    primary_person_id: str
    secondary_person_id: str | None = None
    title: str = Field(default="新开一问", max_length=120)


class Session(SessionCreate):
    id: str
    created_at: str
    updated_at: str


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class Message(BaseModel):
    id: int
    session_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: str
