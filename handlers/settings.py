
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _

from database import create_session
from database.models import User
from keyboards.settings import settings_keyboard, messages_settings_keyboard, bot_mode_keyboard, confirm_mode_keyboard
from utils import update_user, get_user
from utils.messages import make_all_messages_private, anonymize_metrics
from utils.widgets import settings_widget, SettingsOption

router = Router()


async def send_settings(bot: Bot, chat_id: int, user: User):
    await bot.send_message(
        chat_id,
        text=_("SETTINGS_TEXT"),
        reply_markup=settings_keyboard()
    )


@router.callback_query(F.data == 'settings')
async def settings(callback_query: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=callback_query.from_user.id)
    await send_settings(callback_query.bot, callback_query.message.chat.id, user)
    await callback_query.message.delete()


# Messages Settings

@router.callback_query(F.data == 'messages_settings')
async def messages_settings(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        text=_("MESSAGES_SETTINGS_TEXT"),
        reply_markup=messages_settings_keyboard())

@router.callback_query(lambda c: c.data.startswith('bot_mode_settings'))
async def bot_mode_settings(callback_query: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=callback_query.from_user.id)

        parts = callback_query.data.split(":")
        action = parts[1] if len(parts) > 1 else None

        if action == 'standard':
            if not user.privacy_mode:
                await callback_query.answer('👍')
                return
            await callback_query.message.edit_text(
                text=_("CONFIRM_STANDARD_BOT_TYPE"),
                reply_markup=confirm_mode_keyboard('standard')
            )
        elif action == 'standard-confirm':
            await update_user(id=user.id, session=session, privacy_mode=False)
            await callback_query.answer(_("BOT_CHANGE_OK"), show_alert=True)
            await settings(callback_query, state)
        elif action == 'privacy':
            if user.privacy_mode:
                await callback_query.answer('👍')
                return
            await callback_query.message.edit_text(
                text=_("CONFIRM_PRIVACY_BOT_TYPE"),
                reply_markup=confirm_mode_keyboard('privacy')
            )
        elif action == 'privacy-confirm':
            await update_user(id=user.id, session=session, privacy_mode=True)

            await make_all_messages_private(user.id, session)
            await anonymize_metrics(user.id, session)

            await callback_query.answer(_("BOT_CHANGE_OK"), show_alert=True)
            await settings(callback_query, state)
        else:
            await callback_query.message.edit_text(
                text=_("SELECT_BOT_TYPE").format(
                    selected_mode=_("BOT_MODE_PRIVACY" if user.privacy_mode else "BOT_MODE_STANDARD")
                ),
                reply_markup=bot_mode_keyboard())

        await session.commit()


@router.callback_query(lambda c: c.data.startswith("deleted_messages_settings"))
async def deleted_messages_settings(callback: CallbackQuery):
    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)

        parts = callback.data.split(":")
        toggle_id = parts[2] if len(parts) > 2 and parts[1] == "toggle" else None

        options = [
            SettingsOption(
                option_id="enabled",
                name=_("ENABLE_BUTTON"),
                description=_("DELETED_MESSAGES_SETTINGS_ENABLE_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="enabled_for_outgoing",
                name=_("ENABLE_FOR_OUTGOING"),
                description=_("DELETED_MESSAGES_SETTINGS_ENABLE_FOR_OUTGOING_DESCRIPTION"),
                default=False
            ),
            SettingsOption(
                option_id="save_text",
                name=_("DELETED_MESSAGES_SETTINGS_SAVE_TEXT"),
                description=_("DELETED_MESSAGES_SETTINGS_SAVE_TEXT_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="save_media",
                name=_("DELETED_MESSAGES_SETTINGS_SAVE_MEDIA"),
                description=_("DELETED_MESSAGES_SETTINGS_SAVE_MEDIA_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="save_other",
                name=_("DELETED_MESSAGES_SETTINGS_SAVE_OTHER"),
                description=_("DELETED_MESSAGES_SETTINGS_SAVE_OTHER_DESCRIPTION"),
                default=False
            ),
            SettingsOption(
                option_id="silent_mode",
                name=_("DELETED_MESSAGES_SETTINGS_SILENT_MODE"),
                description=_("DELETED_MESSAGES_SETTINGS_SILENT_MODE_DESCRIPTION"),
                default=True
            ),
        ]

        title = _("DELETED_MESSAGES_SETTINGS_BUTTON")
        description = _("DELETED_MESSAGES_SETTINGS_DESCRIPTION")

        text, reply_markup = await settings_widget(
            user=user,
            session=session,
            options=options,
            message_callback="deleted_messages_settings",
            settings_id="deleted_messages",
            back_id="messages_settings",
            title=title,
            description=description,
            toggle=toggle_id
        )

        await callback.message.edit_text(text, reply_markup=reply_markup)
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edited_messages_settings"))
async def edited_messages_settings(callback: CallbackQuery):
    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)

        parts = callback.data.split(":")
        toggle_id = parts[2] if len(parts) > 2 and parts[1] == "toggle" else None

        options = [
            SettingsOption(
                option_id="enabled",
                name=_("ENABLE_BUTTON"),
                description=_("EDITED_MESSAGES_SETTINGS_ENABLE_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="enabled_for_outgoing",
                name=_("ENABLE_FOR_OUTGOING"),
                description=_("EDITED_MESSAGES_SETTINGS_ENABLE_FOR_OUTGOING_DESCRIPTION"),
                default=False
            ),
            SettingsOption(
                option_id="save_text",
                name=_("DELETED_MESSAGES_SETTINGS_SAVE_TEXT"),
                description=_("EDITED_MESSAGES_SETTINGS_SAVE_TEXT_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="save_media",
                name=_("DELETED_MESSAGES_SETTINGS_SAVE_MEDIA"),
                description=_("DELETED_MESSAGES_SETTINGS_SAVE_MEDIA_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="save_other",
                name=_("DELETED_MESSAGES_SETTINGS_SAVE_OTHER"),
                description=_("DELETED_MESSAGES_SETTINGS_SAVE_OTHER_DESCRIPTION"),
                default=False
            ),
            SettingsOption(
                option_id="silent_mode",
                name=_("DELETED_MESSAGES_SETTINGS_SILENT_MODE"),
                description=_("EDITED_MESSAGES_SETTINGS_SILENT_MODE_DESCRIPTION"),
                default=True
            ),
        ]

        title = _("EDITED_MESSAGES_SETTINGS_BUTTON")
        description = _("EDITED_MESSAGES_SETTINGS_DESCRIPTION")

        text, reply_markup = await settings_widget(
            user=user,
            session=session,
            options=options,
            message_callback="edited_messages_settings",
            settings_id="edited_messages",
            back_id="messages_settings",
            title=title,
            description=description,
            toggle=toggle_id
        )

        await callback.message.edit_text(text, reply_markup=reply_markup)
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("protected_messages_settings"))
async def protected_messages_settings(callback: CallbackQuery) -> None:  # noqa: D103
    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)

        parts = callback.data.split(":")
        toggle_id = parts[2] if len(parts) > 2 and parts[1] == "toggle" else None

        options = [
            SettingsOption(
                option_id="enabled",
                name=_("ENABLE_BUTTON"),
                description=_("PROTECTED_MESSAGES_SETTINGS_ENABLE_DESCRIPTION"),
                default=True
            ),
        ]

        title = _("PROTECTED_MESSAGES_SETTINGS_BUTTON")
        description = _("PROTECTED_MESSAGES_SETTINGS_DESCRIPTION")

        text, reply_markup = await settings_widget(
            user=user,
            session=session,
            options=options,
            message_callback="protected_messages_settings",
            settings_id="protected_messages",
            back_id="messages_settings",
            title=title,
            description=description,
            toggle=toggle_id
        )

        await callback.message.edit_text(text, reply_markup=reply_markup)
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("transcribe_voice_messages_settings"))
async def transcribe_voice_messages_settings(callback: CallbackQuery) -> None:  # noqa: D103
    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)
        if user.privacy_mode:
            await callback.answer(_("UNAVAILABLE_IN_PRIVACY_MODE"), show_alert=True)
            return

        parts = callback.data.split(":")
        toggle_id = parts[2] if len(parts) > 2 and parts[1] == "toggle" else None

        options = [
            SettingsOption(
                option_id="enabled",
                name=_("TRANSCRIBE_VOICE_MESSAGES_SETTINGS_ENABLED_NAME"),
                description=_("TRANSCRIBE_VOICE_MESSAGES_SETTINGS_ENABLE_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="enabled_video",
                name=_("TRANSCRIBE_VIDEO_MESSAGES_SETTINGS_ENABLED_NAME"),
                description=_("TRANSCRIBE_VIDEO_MESSAGES_SETTINGS_ENABLE_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="enhanced",
                name=_("TRANSCRIBE_VOICE_MESSAGES_SETTINGS_ENHANCED_NAME"),
                description=_("TRANSCRIBE_VOICE_MESSAGES_SETTINGS_ENHANCED_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="context_awareness",
                name=_("CONTEXT_AWARENESS"),
                description=_("TRANSCRIBE_VOICE_MESSAGES_SETTINGS_CONTEXT_AWARENESS_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="watermark",
                name=_("TRANSCRIBE_VOICE_MESSAGES_SETTINGS_WATERMARK_NAME"),
                description=_("TRANSCRIBE_VOICE_MESSAGES_SETTINGS_WATERMARK_DESCRIPTION"),
                default=True
            ),
        ]

        title = _("TRANSCRIBE_VOICE_MESSAGES_SETTINGS_BUTTON")
        description = _("TRANSCRIBE_VOICE_MESSAGES_SETTINGS_DESCRIPTION")

        text, reply_markup = await settings_widget(
            user=user,
            session=session,
            options=options,
            message_callback="transcribe_voice_messages_settings",
            settings_id="transcribe_voice_messages",
            back_id="messages_settings",
            title=title,
            description=description,
            toggle=toggle_id
        )

        await callback.message.edit_text(text, reply_markup=reply_markup)
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("enhance_messages_settings"))
async def enhance_messages_settings(callback: CallbackQuery) -> None:  # noqa: D103
    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)
        if user.privacy_mode:
            await callback.answer(_("UNAVAILABLE_IN_PRIVACY_MODE"), show_alert=True)
            return

        parts = callback.data.split(":")
        toggle_id = parts[2] if len(parts) > 2 and parts[1] == "toggle" else None

        options = [
            SettingsOption(
                option_id="correct_grammars",
                name=_("ENABLE_GRAMMAR_CORRECTION_BUTTON"),
                description=_("ENABLE_GRAMMAR_CORRECTION_DESCRIPTION"),
                default=True
            ),
            # SettingsOption(
            #     option_id="blur_adult_content",
            #     name=_("ENABLE_BLUR_ADULT_CONTENT_BUTTON"),
            #     description=_("ENABLE_BLUR_ADULT_CONTENT_DESCRIPTION"),
            #     default=False
            # ),
            SettingsOption(
                option_id="context_awareness",
                name=_("CONTEXT_AWARENESS"),
                description=_("GRAMMAR_CORRECTION_CONTEXT_AWARENESS_DESCRIPTION"),
                default=True
            ),
        ]

        title = _("ENHANCE_MESSAGES_SETTINGS_BUTTON")
        description = _("ENHANCE_MESSAGES_SETTINGS_DESCRIPTION")

        text, reply_markup = await settings_widget(
            user=user,
            session=session,
            options=options,
            message_callback="enhance_messages_settings",
            settings_id="enhance_messages",
            back_id="messages_settings",
            title=title,
            description=description,
            toggle=toggle_id
        )

        await callback.message.edit_text(text, reply_markup=reply_markup)
        await callback.answer()