from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, utc_now


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("project_id", "chapter_index", name="uq_chapters_project_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(index=True)
    chapter_key: Mapped[str] = mapped_column(String(80))
    heading: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    project = relationship("Project", back_populates="chapters")
    analysis = relationship("ChapterAnalysis", back_populates="chapter", cascade="all, delete-orphan", uselist=False)
