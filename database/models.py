from datetime import datetime, timedelta

from sqlalchemy import func, ForeignKey, BIGINT, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from database import Base, RedisSession


class UserData(Base):
    user_id: Mapped[int] = mapped_column(BIGINT, ForeignKey('users.id'))
    key: Mapped[str]
    value: Mapped[str]


class User(Base):
    first_name: Mapped[str]
    last_name: Mapped[str | None]
    username: Mapped[str | None]
    language_code: Mapped[str | None]

    is_banned: Mapped[bool] = mapped_column(default=False)
    is_enabled: Mapped[bool] = mapped_column(default=False)
    privacy_mode: Mapped[bool] = mapped_column(default=False)

    business_connection_id: Mapped[str | None] = mapped_column(default=None)
    subscriber_until: Mapped[datetime | None] = mapped_column(default=None)

    referral_id: Mapped[int | None] = mapped_column(BIGINT, ForeignKey('users.id'), default=None)
    referrals_income: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def has_subscription(self) -> bool:
        """Return True if the subscription is still active."""
        return self.subscriber_until > datetime.now()

    @property
    def is_working(self) -> bool:
        return not self.is_banned and self.is_enabled and (self.subscriber_until + timedelta(days=1)) > datetime.now()

    async def set_int(self, key: str, value: int, db: AsyncSession):
        await RedisSession.set(f"user_data:{self.id}:{key}", value)
        await self._set_db_value(key, str(value), db)

    async def set_bool(self, key: str, value: bool, db: AsyncSession):
        await RedisSession.set(f"user_data:{self.id}:{key}", int(value))
        await self._set_db_value(key, str(int(value)), db)

    async def set_string(self, key: str, value: str, db: AsyncSession):
        await RedisSession.set(f"user_data:{self.id}:{key}", value)
        await self._set_db_value(key, value, db)

    async def get_int(self, key: str, db: AsyncSession, default: int = 0) -> int:
        v = await RedisSession.get(f"user_data:{self.id}:{key}")
        if v is not None:
            return int(v)
        db_value = await self._get_db_value(key, db)
        return int(db_value) if db_value is not None else default

    async def get_bool(self, key: str, db: AsyncSession, default: bool = False) -> bool:
        v = await RedisSession.get(f"user_data:{self.id}:{key}")
        if v is not None:
            return bool(int(v))
        db_value = await self._get_db_value(key, db)
        return bool(int(db_value)) if db_value is not None else default

    async def get_string(self, key: str, db: AsyncSession, default: str = "") -> str:
        v = await RedisSession.get(f"user_data:{self.id}:{key}")
        if v is not None:
            return v.decode()
        db_value = await self._get_db_value(key, db)
        return db_value if db_value is not None else default

    async def _set_db_value(self, key: str, value: str, db: AsyncSession):
        from sqlalchemy import select
        stmt = select(UserData).where(UserData.user_id == self.id, UserData.key == key)
        obj = (await db.execute(stmt)).scalar_one_or_none()
        if obj:
            obj.value = value
        else:
            obj = UserData(user_id=self.id, key=key, value=value)
            db.add(obj)
        await db.commit()

    async def _get_db_value(self, key: str, db: AsyncSession):
        from sqlalchemy import select
        stmt = select(UserData.value).where(UserData.user_id == self.id, UserData.key == key)
        res = (await db.execute(stmt)).scalar_one_or_none()
        return res


class Persona(Base):
    first_name: Mapped[str]
    last_name: Mapped[str | None]
    username: Mapped[str | None]
    language_code: Mapped[str | None]

    @property
    def full_name(self) -> str:
        return (f"{self.first_name}" + (f" {self.last_name}" if self.last_name else "")).replace('<', '').replace('>',
                                                                                                                  '')

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


class Metric(Base):
    # Normal Mode
    connected_user_id: Mapped[int | None] = mapped_column(BIGINT)
    chat_id: Mapped[int | None] = mapped_column(BIGINT)
    message_id: Mapped[int | None] = mapped_column(BIGINT)

    name: Mapped[str]
    value: Mapped[str | None]