from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, ForeignKey, BIGINT
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.testing.suite.test_reflection import users

from database import Base


class User(Base):
    first_name: Mapped[str]
    last_name: Mapped[str | None]
    username: Mapped[str | None]
    language_code: Mapped[str | None]

    is_banned: Mapped[bool] = mapped_column(default=False)
    is_enabled: Mapped[bool] = mapped_column(default=False)
    privacy_mode: Mapped[bool] = mapped_column(default=False)

    business_connection_id: Mapped[str | None] = mapped_column(default=None)
    subscriber_until: Mapped[datetime] = mapped_column(default=func.now() + timedelta(days=7))


class Persona(Base):
    first_name: Mapped[str]
    last_name: Mapped[str | None]
    username: Mapped[str | None]
    language_code: Mapped[str | None]

    @property
    def full_name(self) -> str:
        return f"{self.first_name}" + (f" {self.last_name}" if self.last_name else "")

    @property
    def hname(self):
        if self.username:
            return f'<a href="https://t.me/{self.username}">{self.full_name}</a>'
        return f'<a href="tg://user?id={self.id}">{self.full_name}</a>'

class SavedMessage(Base):
    # Normal Mode
    connected_user_id: Mapped[int | None] = mapped_column(BIGINT)
    chat_id: Mapped[int | None] = mapped_column(BIGINT)
    message_id: Mapped[int | None] = mapped_column(BIGINT)

    # Privacy Mode
    privacy_key: Mapped[str]

    # Message Data
    outgoing: Mapped[bool]
    text: Mapped[str | None]
    content_type: Mapped[str]
    content: Mapped[str | None]