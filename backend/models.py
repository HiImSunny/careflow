"""
SQLAlchemy ORM models for CareFlow Orchestrator.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.sqlite import TEXT as SQLITE_TEXT

from backend.database import Base


class Case(Base):
    """Represents a submitted clinical case and its generated care plan."""

    __tablename__ = "cases"

    id: str = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
    input_text: str | None = Column(Text, nullable=True)
    image_ref: str | None = Column(String(512), nullable=True)
    created_at: datetime = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    care_plan_json: str | None = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Case id={self.id} created_at={self.created_at}>"


class Guideline(Base):
    """Represents a clinical guideline associated with a medical specialty."""

    __tablename__ = "guidelines"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    specialty: str = Column(String(64), nullable=False)
    content: str = Column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<Guideline id={self.id} specialty={self.specialty}>"
