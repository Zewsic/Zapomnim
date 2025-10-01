import asyncio
import json
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import or_f
from aiogram.types import LinkPreviewOptions, Message
from aiogram.utils.i18n import gettext as _
from aiogram.utils.markdown import hlink
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from database import create_session
from database.models import Metric, User
from utils import get_user
from utils.botapi import TelegramDataUtils

logger = logging.getLogger("Zapomnim/VoiceMessagesTranscriber")
client = AsyncOpenAI()

router = Router()

MAKE_SUMMARY_PROMPT = """Задача: Составить краткое summary по транскрипции голосового сообщения.

1. Удалить слова-паразиты, междометия и повторы — оставить только информативные фразы.
2. Сохранить ключевой смысл и последовательность идей.
3. Заменить искажённые технические термины без аналогов в РФ на их канонический английский эквивалент (например: «докер компоуз» → Docker Compose).
4. Для структурирования использовать только нумерацию 1./2./... или маркеры -.
5. Разрешены HTML-теги <b> и <i> для выделения важного.
6. Итоговое summary — не более 1000 символов, без дополнительных комментариев."""

ENHANCE_TRANSCRIBE_PROMPT = """Задача: Исправь и отформатируй транскрипцию голосового сообщения.

Инструкции:
- Приводи текст в соответствие с нормами современного русского литературного языка: исправляй орфографию, пунктуацию и грамматику.
- Переформулируй фразы с оговорками или ошибками, сохраняя исходный смысл.
- Заменяй искажённые технические термины на их каноничный английский эквивалент (например, «докер компоуз» → Docker Compose).
- Удаляй слова-паразиты («ээ», «м-м», «типа») при отсутствии смысловой нагрузки.
- Не цензурируй и не замещай ненормативную лексику и маты — передавай их как в оригинале.
- Если улучшение транскрипции невозможно, не отправляй ничего.
- В результате выводи только итоговый откорректированный текст без дополнительных комментариев.

Не пиши никаких дополнительных комментариев кроме самой улучшенной расшифровки."""


# --- helpers ---------------------------------------------------------------


def _clip_for_tg(text: str, limit: int = 1800) -> str:
    text = text.rstrip()
    if len(text) > limit:
        return text[:limit] + " ... "
    return text


async def _transcribe_only(path: Path) -> str:
    """Только распознаёт речь и возвращает сырую транскрипцию."""
    with path.open("rb") as f:
        tr = await client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=f,
        )
    return tr.text


async def _enhance_text(raw_text: str, context: str | None) -> tuple[str, dict[str, int]]:
    """Улучшаем/саммаризуем уже полученный текст и возвращаем текст + метрики."""
    ln = len(raw_text)

    # Оптимизация токенов: используем более дешевые модели и меньше reasoning effort
    if ln < 512:
        prompt = ENHANCE_TRANSCRIBE_PROMPT
        model = "gpt-5-nano"
        effort = "low"
    elif ln < 1024:
        prompt = MAKE_SUMMARY_PROMPT
        model = "gpt-5-nano"
        effort = "low"
    else:
        prompt = MAKE_SUMMARY_PROMPT
        model = "gpt-5-mini"
        effort = "low"

    ai_chat = [
        {"role": "system", "content": prompt},
    ]

    if context:
        ai_chat.append({"role": "system", "content": f"Немного контекста чата: \n\n{context}"})

    ai_chat.append({"role": "user", "content": f"Расшифровка:\n\n{raw_text}"})

    resp = await client.chat.completions.create(
        model=model,
        messages=ai_chat,
        reasoning_effort=effort,
    )

    text = resp.choices[0].message.content

    # Если OpenAI вернул None или пустой текст, возвращаем исходный
    if not text or not text.strip():
        text = raw_text

    return text, {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "model": model,
    }


# --- ffmpeg ---------------------------------------------------------------


async def ffmpeg_convert(src: Path, dst: Path) -> None:
    """Конвертирует аудио в m4a асинхронно."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        str(dst),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode:
        logger.error("ffmpeg error: %s", stderr.decode().strip())
        raise RuntimeError("ffmpeg failed")


# --- main flow ------------------------------------------------------------


async def _transcribe_voice_message(
    message: Message, enhanced: bool, watermark: str, context: str | None, reply_mode: bool,
) -> dict[str, int] | None:
    """Новый порядок.
    
    1) показать «расшифровка…»
    2) показать сырую расшифровку
    3) если enhanced=True — заменить на улучшенную версию
    """
    # 1) стартовое «расшифровка…»
    progress_text = _("VOICE_TRANSCRIBE_IN_PROCESS_TEXT").format(watermark=watermark)  # или своя строка
    if reply_mode:
        status_message = await message.answer(
            progress_text,
            reply_to_message_id=message.message_id,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    else:
        try:
            status_message = message
            await status_message.edit_text(progress_text)
        except:  # noqa
            status_message = await message.answer(
                progress_text,
                reply_to_message_id=message.message_id,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )

    # -- загрузка файла TG
    to_transcribe = message.voice or message.video_note
    file_info = await message.bot.get_file(to_transcribe.file_id)
    src = Path(TelegramDataUtils.get_normal_file_path(file_info))
    dst = Path(f"cache/voice_{to_transcribe.file_id}.m4a")

    usage: dict[str, int] = {}

    try:
        await ffmpeg_convert(src, dst)

        # 2) получаем сырую транскрипцию и показываем её
        raw_text = await _transcribe_only(dst)
        cleaned_raw = _clip_for_tg(raw_text)

        # 3) если нужно — улучшаем и заменяем текст
        if enhanced:
            await status_message.edit_text(
                f"🎤 Enhancing... <blockquote expandable><i>{cleaned_raw} {watermark}</i></blockquote>",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            try:
                improved_text, metrics = await _enhance_text(raw_text, context=context)
                usage.update(metrics)
                cleaned_improved = _clip_for_tg(improved_text)

                # Проверяем, что улучшенный текст отличается от исходного
                if cleaned_improved.strip() and cleaned_improved != cleaned_raw:
                    await status_message.edit_text(
                        f"<blockquote expandable><i>{cleaned_improved} {watermark}</i></blockquote>",
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    )
                    logger.info("Enhanced text updated successfully")
                else:
                    # Если улучшенный текст не отличается, показываем исходный
                    await status_message.edit_text(
                        f"<blockquote expandable><i>{cleaned_raw} {watermark}</i></blockquote>",
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    )
                    logger.warning("Enhanced text is empty or same as original, showing raw text")
            except Exception:
                logger.exception("Enhancement failed")
                await status_message.edit_text(
                    f"<blockquote expandable><i>{cleaned_raw} {watermark}</i></blockquote>",
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
        else:
            await status_message.edit_text(
                f"<blockquote expandable><i>{cleaned_raw} {watermark}</i></blockquote>",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )

        usage["audio_duration"] = to_transcribe.duration

    except Exception:
        logger.exception("Transcription error")
        await status_message.edit_text(
            _("VOICE_TRANSCRIBE_ERROR_TEXT").format(watermark=watermark),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return None
    finally:
        for path in (src, dst):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Can't remove %s", path)

    return usage


async def transcribe_voice_messages(user: User, message: Message, session: AsyncSession, reply_mode: bool) -> None:
    enabled = await user.get_bool("settings.transcribe_voice_messages.enabled", session, default=True)
    enabled_video = await user.get_bool("settings.transcribe_voice_messages.enabled_video", session, default=True)
    enhanced = await user.get_bool("settings.transcribe_voice_messages.enhanced", session, default=True)
    use_watermark = await user.get_bool("settings.transcribe_voice_messages.watermark", session, default=True)

    if (message.voice and not enabled) or (message.video_note and not enabled_video):
        return

    watermark = hlink("(?)", f"https://t.me/zapomnim_bot?start=ref{message.from_user.id}") if use_watermark else ""
    context = None  # Context awareness убран как юзелесс

    usage = await _transcribe_voice_message(message=message, enhanced=enhanced, watermark=watermark, reply_mode=reply_mode, context=context)
    if not usage:
        return

    async with create_session() as session:
        user = await get_user(session, id=message.from_user.id)
        metric = Metric(
            connected_user_id=user.id if not user.privacy_mode else None,
            chat_id=message.chat.id if not user.privacy_mode else None,
            message_id=message.message_id if not user.privacy_mode else None,
            name="metrics.transcribe_voice_message",
            value=json.dumps(usage),
        )
        session.add(metric)
        await session.commit()


@router.message(or_f(F.voice, F.video_note))
async def process_process_input_voice_message(message: Message):
    # В публичном/дефолтном хендлере тоже показываем 3 стадии
    usage = await _transcribe_voice_message(
        message,
        enhanced=True,
        watermark=hlink("(?)", "https://t.me/zapomnim_bot"),
        context=None,
        reply_mode=True,
    )
    if not usage:
        return

    metric_name = (
        "metrics.input.transcribe_voice_message" if message.chat.id == message.from_user.id else "metrics.chat.transcribe_voice_message"
    )

    async with create_session() as session:
        metric = Metric(
            chat_id=message.chat.id,
            message_id=message.message_id,
            name=metric_name,
            value=json.dumps(usage),
        )
        session.add(metric)
        await session.commit()
