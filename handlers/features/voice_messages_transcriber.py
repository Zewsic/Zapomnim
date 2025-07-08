import asyncio
import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Tuple, Dict

from aiogram import Router, F
from aiogram.filters import or_f
from aiogram.types import Message, LinkPreviewOptions
from aiogram.utils.markdown import hlink
from aiogram.utils.i18n import gettext as _
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import BinaryIO

from database import create_session, RedisSession
from database.models import Metric, User
from utils import get_user
from utils.botapi import TelegramDataUtils

logger = logging.getLogger('Zapomnim/VoiceMessagesTranscriber')
client = AsyncOpenAI()

router = Router()


async def get_text_from_voice(path, enhanced: bool) -> Tuple[str, Dict[str, int]]:
    """Отправляет аудио в OpenAI, возвращает текст и метрики."""
    with path.open('rb') as f:
        transcription = await client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=f
        )

    if not enhanced:
        return transcription.text, {}

    is_short = len(transcription.text) < 512
    prompt = _("VOICE_TRANSCRIBE_ENHANCE_PROMPT") if is_short else _("VOICE_TRANSCRIBE_SUMMARY_PROMPT")
    model = "gpt-4.1-mini" if is_short else "o4-mini"

    enhanced = await client.responses.create(
        model=model,
        input=prompt + transcription.text,
    )

    return enhanced.output_text, {
        "input_tokens": enhanced.usage.input_tokens,
        "output_tokens": enhanced.usage.output_tokens,
        "model": model
    }


async def ffmpeg_convert(src: Path, dst: Path) -> None:
    """Конвертирует аудио в m4a асинхронно."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(src), str(dst),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode:
        logger.error("ffmpeg error: %s", stderr.decode().strip())
        raise RuntimeError("ffmpeg failed")


async def _transcribe_voice_message(message: Message, enhanced: bool, watermark: str, reply_mode: bool) -> None:
    if reply_mode:
        status_message = await message.answer(
            _("VOICE_TRANSCRIBE_IN_PROCESS_TEXT").format(watermark=watermark),
            reply_to_message_id=message.message_id,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    else:
        try:
            status_message = message
            await status_message.edit_text(_("VOICE_TRANSCRIBE_IN_PROCESS_TEXT").format(watermark=watermark))
        except:
            status_message = await message.answer(
                _("VOICE_TRANSCRIBE_IN_PROCESS_TEXT").format(watermark=watermark),
                reply_to_message_id=message.message_id,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )

    # -- загрузка файла TG
    to_transcribe = message.voice or message.video_note
    file_info = await message.bot.get_file(to_transcribe.file_id)
    src = Path(TelegramDataUtils.get_normal_file_path(file_info))
    dst = Path(f"cache/voice_{to_transcribe.file_id}.m4a")

    try:
        await ffmpeg_convert(src, dst)
        text, usage = await get_text_from_voice(dst, enhanced)

        usage['audio_duration'] = to_transcribe.duration
    except Exception:
        logger.exception("Transcription error")
        await status_message.edit_text(
            _("VOICE_TRANSCRIBE_ERROR_TEXT").format(watermark=watermark),
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        return None
    finally:
        for path in (src, dst):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Can't remove %s", path)

    cleaned = text[:-1]
    if len(cleaned) > 1800:
        cleaned = cleaned[:1800] + ' ... '
    await status_message.edit_text(
        f'<blockquote expandable><i>{cleaned}. {watermark}</i></blockquote>',
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )

    return usage


async def transcribe_voice_messages(user: User, message: Message, session: AsyncSession, reply_mode: bool) -> None:
    enabled = await user.get_bool('settings.transcribe_voice_messages.enabled', session, default=True)
    enabled_video = await user.get_bool('settings.transcribe_voice_messages.enabled_video', session, default=True)
    enhanced = await user.get_bool('settings.transcribe_voice_messages.enhanced', session, default=True)
    use_watermark = await user.get_bool('settings.transcribe_voice_messages.watermark', session, default=True)

    if (message.voice and not enabled) or (message.video_note and not enabled_video):
        return

    watermark = hlink("(?)", f"https://t.me/zapomnim_bot?start=ref{message.from_user.id}") if use_watermark else ''

    usage = await _transcribe_voice_message(message, enhanced, watermark, reply_mode)
    if not usage:
        return

    async with create_session() as session:
        user = await get_user(session, id=message.from_user.id)

        metric = Metric(
            connected_user_id=user.id if not user.privacy_mode else None,
            chat_id=message.chat.id if not user.privacy_mode else None,
            message_id=message.message_id if not user.privacy_mode else None,
            name='metrics.transcribe_voice_message',
            value=json.dumps(usage)
        )
        session.add(metric)
        await session.commit()


@router.message(or_f(F.voice, F.video_note))
async def process_process_input_voice_message(message: Message):
    usage = await _transcribe_voice_message(message, True, hlink("(?)", f"https://t.me/zapomnim_bot"), True)
    if not usage:
        return

    metric_name = 'metrics.input.transcribe_voice_message' if message.chat.id == message.from_user.id else 'metrics.chat.transcribe_voice_message'

    async with create_session() as session:
        metric = Metric(
            chat_id=message.chat.id,
            message_id=message.message_id,
            name=metric_name,
            value=json.dumps(usage)
        )
        session.add(metric)
        await session.commit()
