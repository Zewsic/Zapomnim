from typing import Final, Tuple, Union

import aiofiles
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import File, User
from aiogram.utils.i18n import gettext as _

from config import TELEGRAM_SERVER, TELEGRAM_SERVER_DATA, WEBHOOK_HOST, SUBSCRIPTION_REQUIRED_CHANNEL

WEBHOOK_URL: Final[str] = f"http://{WEBHOOK_HOST}/webhook/%s"


class TelegramMirrorUtils:
    CONNECTED_BOTS: dict[int, Bot] = {}

    @staticmethod
    async def check_token(token: str) -> tuple[Bot, User]:
        mirror_bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                         session=AiohttpSession(api=TELEGRAM_SERVER))

        try:
            bot_info = await mirror_bot.get_me()
        except:  # noqa: E722
            raise KeyError

        return mirror_bot, bot_info

    @staticmethod
    async def check_and_connect(token: str) -> User:
        mirror_bot, bot_info = await TelegramMirrorUtils.check_token(token)

        if not bot_info.can_connect_to_business:
            raise ConnectionError

        await mirror_bot.delete_webhook()
        await mirror_bot.set_webhook(WEBHOOK_URL % bot_info.id)
        TelegramMirrorUtils.CONNECTED_BOTS[bot_info.id] = mirror_bot

        return bot_info

    @staticmethod
    async def disconnect(bot_id):
        bot = TelegramMirrorUtils.CONNECTED_BOTS.get(bot_id)
        if not bot:
            return

        await bot.delete_webhook()
        await bot.close()

        del TelegramMirrorUtils.CONNECTED_BOTS[bot_id]


class TelegramDataUtils:
    BASE_TG_DATA = "/var/lib/telegram-bot-api/"

    @staticmethod
    def get_normal_file_path(file: File) -> str:
        path = file.file_path.replace(TelegramDataUtils.BASE_TG_DATA, TELEGRAM_SERVER_DATA)
        return path

    @staticmethod
    async def get_file(file: File) -> bytes:
        async with aiofiles.open(TelegramDataUtils.get_normal_file_path(file), "rb") as f:
            return await f.read()


# ----------------------------
# Subscription membership utils
# ----------------------------

def _parse_channel_from_link(url: str) -> str | None:
    if not url:
        return None
    # Expecting forms like https://t.me/username or https://t.me/+invite or tg://resolve?domain=username
    try:
        if "t.me/" in url:
            part = url.split("t.me/")[1]
            # cut query/params/fragments
            part = part.split("?")[0].split("#")[0]
            # links with joinchat or +invite are not usable as @username for getChatMember
            if part.startswith("+") or part.startswith("joinchat"):
                return None
            # strip trailing slashes
            part = part.strip("/")
            if part:
                return f"@{part}" if not part.startswith("@") else part
    except Exception:
        return None
    return None


def resolve_required_channel() -> Tuple[Union[int, str], str]:
    """Return (channel_ref, channel_url) for membership checks.

    channel_ref can be an int chat_id (e.g., -100...), or a string @username.
    channel_url is a user-facing https://t.me/... link.
    """
    # Prefer explicit env var
    raw = SUBSCRIPTION_REQUIRED_CHANNEL
    if raw:
        raw = raw.strip()
        # Build url
        url = None
        if raw.startswith("-100") or raw.lstrip("-").isdigit():
            # Cannot build url from numeric id; fallback to localized link
            url = _("CHANNEL_LINK")
        elif raw.startswith("@"):
            url = f"https://t.me/{raw[1:]}"
        else:
            # maybe given as bare username
            url = f"https://t.me/{raw}"
            raw = f"@{raw}" if not raw.startswith("@") else raw

        channel_ref: Union[int, str]
        if raw.lstrip("-").isdigit():
            channel_ref = int(raw)
        else:
            channel_ref = raw
        return channel_ref, url

    # Fallback to localized CHANNEL_LINK
    link = _("CHANNEL_LINK")
    username = _parse_channel_from_link(link)
    url = link if link else "https://t.me"
    if username:
        return username, url
    # As a last resort, return a dummy @ link that will fail membership check gracefully
    return "@invalid_channel", url


async def is_user_member_of_required_channel(bot: Bot, user_id: int) -> Tuple[bool, str]:
    """Check if user is a member of the required channel.

    Returns (is_member, channel_url) where channel_url is for UI.
    """
    channel_ref, channel_url = resolve_required_channel()
    try:
        member = await bot.get_chat_member(chat_id=channel_ref, user_id=user_id)
    except TelegramBadRequest:
        return False, channel_url
    status = getattr(member, "status", None)
    if status in {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR, ChatMemberStatus.RESTRICTED}:
        return True, channel_url
    return False, channel_url
