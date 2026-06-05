from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, utc_now


class ChapterAnalysis(Base):
    __tablename__ = "chapter_analyses"
    __table_args__ = (
        UniqueConstraint("project_id", "chapter_id", name="uq_chapter_analyses_project_chapter"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), index=True)
    chapter_key: Mapped[str] = mapped_column(String(80), index=True)
    chapter_index: Mapped[int] = mapped_column(index=True)
    summary: Mapped[str] = mapped_column(Text)
    analysis: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    project = relationship("Project", back_populates="chapter_analyses")
    chapter = relationship("Chapter", back_populates="analysis")
