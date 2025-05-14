import asyncio

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile

from aiogram.utils.i18n import gettext as _, lazy_gettext as __
from aiogram.utils.markdown import hbold, hcode, hitalic

router = Router()

@router.business_message(lambda bm: bm.text.startswith('.test'))
async def test(message: Message):
    if message.chat.id == message.from_user.id:
        print('Incoming message, skipping!')
        return

    await message.edit_text("Tested!")


@router.message(Command("start"))
async def test_mirror(message: Message):
    bot = await message.bot.get_me()
    emoji = await message.answer('👋')
    await asyncio.sleep(0.7)
    await message.answer_photo(
        photo=FSInputFile(_("START_IMAGE")),
        caption=f"👋{hbold('Добро пожаловать')}!\n"
                f"{hitalic('У вас остался последний шаг')}.\n\n"
                f"{hbold('🏁 Активируем бизнес-бота')}:\n"
                f"1. Перейдите в {hbold('Настройки')} → {hbold('Telegram для бизнеса')}\n"
                f"2. В пункте {hbold('Чат-Боты')} вставьте username бота ({hcode(bot.username)})\n"
                f"3. Выдайте боту все права на сообщения (это необходимо для работы).\n\n"
                f"{hbold('✅ После этого бот начнет работу.')}",
    )
    await emoji.delete()