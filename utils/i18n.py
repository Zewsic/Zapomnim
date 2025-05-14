from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, Optional, Set

from aiogram.utils.i18n import SimpleI18nMiddleware
from babel import Locale, UnknownLocaleError
from aiogram import BaseMiddleware, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import TelegramObject, User
from aiogram.utils.i18n.core import I18n
from aiogram.utils.i18n.middleware import I18nMiddleware

class PatchedI18nMiddleware(SimpleI18nMiddleware):
    """
    Simple I18n middleware.

    Chooses language code from the User object received in event
    """

    def __init__(
            self,
            i18n: I18n,
            i18n_key: Optional[str] = "i18n",
            middleware_key: str = "i18n_middleware",
    ) -> None:
        super().__init__(i18n=i18n, i18n_key=i18n_key, middleware_key=middleware_key)

    async def get_locale(self, event: TelegramObject, data: Dict[str, Any]) -> str:
        event_from_user = event.from_user
        if event_from_user is None or event_from_user.language_code is None:
            return self.i18n.default_locale
        try:
            locale = Locale.parse(event_from_user.language_code, sep="-")
        except UnknownLocaleError:
            return self.i18n.default_locale

        if locale.language not in self.i18n.available_locales:
            return self.i18n.default_locale
        return locale.language
