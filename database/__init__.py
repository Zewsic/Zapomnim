import logging
import os
import re
from datetime import datetime

import redis.asyncio as aioredis
from dotenv import load_dotenv
from sqlalchemy import BIGINT, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs, AsyncSession
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, declared_attr

from os import environ

load_dotenv('.env')


logger = logging.getLogger('Zapomnim/Database')
engine = create_async_engine(
    os.getenv('DATABASE_CONNECTION_STRING'),
    echo=environ.get('BUILD_TYPE') == 'test',
    pool_pre_ping=True
)
create_session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False
)
RedisSession = aioredis.Redis(host=os.getenv("REDIS_HOST"))


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True

    id: Mapped[BIGINT] = mapped_column(BIGINT, primary_key=True, autoincrement=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    @declared_attr.directive
    def __tablename__(cls) -> str:
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        db_name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower() + 's'
        return db_name


async def create_tables():
    global Session, engine

    logger.info("Initializing database...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()

async def get_db() -> AsyncSession:
    async with Session() as session:
        return session