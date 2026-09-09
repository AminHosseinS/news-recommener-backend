from typing import Optional

from sqlalchemy import String, ARRAY, REAL, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    vector_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vector: Mapped[Optional[list[float]]] = mapped_column(ARRAY(REAL), nullable=True)