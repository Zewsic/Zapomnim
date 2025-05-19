import asyncio
import time

from aiogram import Router, F
from aiogram.filters import Command, CommandStart, StateFilter, and_f, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, CallbackQuery, MenuButtonCommands, \
    BusinessConnection
from aiogram.utils.i18n import gettext as _, lazy_gettext as __

from config import StartState, SettingsState
from database import create_session
from keyboards import security_select_keyboard
from utils import TelegramMirrorUtils, update_user, get_user, _UNSET, PatchedI18nMiddleware

router = Router()