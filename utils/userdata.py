from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import RedisSession
from database.models import User, Persona
from utils import _UNSET, save_to_redis, load_from_redis


async def update_user(
        id: int,
        session: AsyncSession,
        *,
        first_name: str = _UNSET,
        last_name: Optional[str] = _UNSET,
        username: Optional[str] = _UNSET,
        is_banned: bool = _UNSET,
        business_connection_id: Optional[str] = _UNSET,
        subscription_until: datetime = _UNSET,
        is_enabled: bool = _UNSET,
        language: str = _UNSET,
) -> User:
    user = User(id=id)
    if first_name is not _UNSET:
        user.first_name = first_name
    if last_name is not _UNSET:
        user.last_name = last_name
    if username is not _UNSET:
        user.username = username
    if is_banned is not _UNSET:
        user.is_banned = is_banned
    if is_enabled is not _UNSET:
        user.is_enabled = is_enabled
    if business_connection_id is not _UNSET:
        user.business_connection_id = business_connection_id
        await RedisSession.set(f"business_connection_to_user_id:{business_connection_id}", str(id))
    if subscription_until is not _UNSET:
        user.subscription_until = subscription_until
    if language is not _UNSET:
        user.language_code = language

    user = await session.merge(user)
    await save_to_redis(user)

    return user


async def get_user(
        session: AsyncSession,
        *,
        id: int = _UNSET,
        business_connection_id: Optional[str] = _UNSET,
) -> Optional[User]:
    if id is _UNSET:
        if business_connection_id is not _UNSET:
            from_redis = await RedisSession.get(f"business_connection_to_user_id:{business_connection_id}")
            if from_redis:
                id = int(from_redis)
            else:
                r = await session.execute(select(User.id).where(User.business_connection_id == business_connection_id))
                id = r.scalar()
                if id:
                    await RedisSession.set(f"business_connection_to_user_id:{business_connection_id}", str(id))
        else:
            return None
    user = await load_from_redis(User, f"{id}")
    if user is None:
        user = await session.get(User, id)
    return user


async def update_persona(
        id: int,
        session: AsyncSession,
        *,
        first_name: str = _UNSET,
        last_name: Optional[str] = _UNSET,
        username: Optional[str] = _UNSET,
        language: str = _UNSET,
) -> Persona:
    persona = Persona(id=id)
    if first_name is not _UNSET:
        persona.first_name = first_name
    if last_name is not _UNSET:
        persona.last_name = last_name
    if username is not _UNSET:
        persona.username = username
    if language is not _UNSET:
        persona.language_code = language

    persona = await session.merge(persona)
    await save_to_redis(persona)

    return persona


async def get_persona(
        session: AsyncSession,
        id: int = _UNSET,
) -> Optional[Persona]:
    persona = await load_from_redis(Persona, f"{id}")
    if persona is None:
        persona = await session.get(Persona, id)
        if persona:
            await save_to_redis(persona)
    return persona
