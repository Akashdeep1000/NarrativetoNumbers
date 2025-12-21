from __future__ import annotations
import secrets
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(8)}"

class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("p"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    participant_no: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255))
    consent: Mapped[bool] = mapped_column(Boolean, default=False)

    sessions: Mapped[list["Session"]] = relationship(back_populates="participant", cascade="all, delete-orphan")
    demographics: Mapped["Demographics"] = relationship(back_populates="participant", uselist=False, cascade="all, delete-orphan")

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("s"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="started")

    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"))
    participant: Mapped["Participant"] = relationship(back_populates="sessions")
    cookie_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)

class Demographics(Base):
    __tablename__ = "demographics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), unique=True)
    participant: Mapped["Participant"] = relationship(back_populates="demographics")
    age_band: Mapped[str] = mapped_column(String(40))
    gender: Mapped[str] = mapped_column(String(40))
    puzzle_experience: Mapped[str] = mapped_column(String(40))

class Level(Base):
    __tablename__ = "levels"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("lvl"))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    session: Mapped["Session"] = relationship(back_populates="levels")

    index: Mapped[int] = mapped_column(Integer) 
    condition: Mapped[str] = mapped_column(String(1), default="A")  
    difficulty: Mapped[str] = mapped_column(String(8))  
    shuffle_steps: Mapped[int] = mapped_column(Integer, default=25)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    moves: Mapped[int] = mapped_column(Integer, default=0)
    time_ms: Mapped[int] = mapped_column(Integer, default=0)

Session.levels = relationship("Level", back_populates="session", cascade="all, delete-orphan")
