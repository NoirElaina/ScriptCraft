from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, utc_now


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    source_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    owner = relationship("User", back_populates="projects")
    chapters = relationship("Chapter", back_populates="project", cascade="all, delete-orphan")
    story_elements = relationship("StoryElement", back_populates="project", cascade="all, delete-orphan")
    script_versions = relationship("ScriptVersion", back_populates="project", cascade="all, delete-orphan")
    ai_runs = relationship("AIRun", back_populates="project", cascade="all, delete-orphan")
