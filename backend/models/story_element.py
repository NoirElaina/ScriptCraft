from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, utc_now


class StoryElement(Base):
    __tablename__ = "story_elements"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    characters: Mapped[list[dict]] = mapped_column(JSON, default=list)
    locations: Mapped[list[dict]] = mapped_column(JSON, default=list)
    events: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    project = relationship("Project", back_populates="story_elements")
