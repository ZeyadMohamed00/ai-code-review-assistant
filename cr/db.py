import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Integer, Text, JSON, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

engine = create_engine(os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres@localhost/cr"), pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Review(Base):
    __tablename__ = "cr_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(300))
    reviewer: Mapped[str] = mapped_column(String(40))
    findings: Mapped[list] = mapped_column(JSON)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def init():
    Base.metadata.create_all(engine)
