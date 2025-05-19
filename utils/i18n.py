import logging
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, Optional, Set

from aiogram.utils.i18n import SimpleI18nMiddleware
from aiogram import BaseMiddleware, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    TelegramObject,
    User,
    Message,
    CallbackQuery
)
from aiogram.utils.i18n.core import I18n
from aiogram.utils.i18n.middleware import I18nMiddleware
from babel import Locale, UnknownLocaleError

from database import create_session
from utils import get_user


class PatchedI18nMiddleware(SimpleI18nMiddleware):
    """
    Simple I18n middleware.

    Chooses language code from the User object in the event or DB.
    """

    def __init__(
        self,
        i18n: I18n,
        i18n_key: Optional[str] = "i18n",
        middleware_key: str = "i18n_middleware",
    ) -> None:
        super().__init__(i18n=i18n, i18n_key=i18n_key, middleware_key=middleware_key)

    async def get_locale(self, event: TelegramObject, data: Dict[str, Any]) -> str:
        """
        Возвращает локаль (язык), основываясь на данных из БД (поле user_data.language_code).
        Если user_data отсутствует или язык не задан — возвращаем 'en' как fallback.
        """
        user_data = await self._get_user_data_from_event(event)
        if user_data and user_data.language_code:
            return user_data.language_code
        return 'en'

    async def _get_user_data_from_event(self, event: TelegramObject) -> Optional[Any]:
        """
        Универсальный метод, пытается получить user_data из БД,
        основываясь на типе event и полях business_connection_id или from_user.
        """
        async with create_session() as session:
            try:
                if isinstance(event, Message):
                    if event.business_connection_id:
                        return await get_user(
                            business_connection_id=event.business_connection_id,
                            session=session
                        )
                    if event.from_user and event.from_user.id:
                        return await get_user(id=event.from_user.id, session=session)

                elif isinstance(event, CallbackQuery):
                    if event.from_user and event.from_user.id:
                        return await get_user(id=event.from_user.id, session=session)

                else:
                    if hasattr(event, 'business_connection_id'):
                        return await get_user(
                            business_connection_id=event.business_connection_id,
                            session=session
                        )
                    if hasattr(event, 'user') and getattr(event, 'user'):
                        # event.user.id
                        return await get_user(
                            id=getattr(event.user, 'id', None),
                            session=session
                        )
            except Exception as exc:
                logging.exception(f"Error getting user data: {exc}")
                return None

        return None