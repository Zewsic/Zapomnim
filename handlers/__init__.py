from handlers.data_management import router as data_management_router
from handlers.features.delete_messages_handler import router as delete_messages_router
from handlers.features.edit_messages_handler import router as edit_messages_router
from handlers.features.process_message import router as process_message_router
from handlers.features.statistics import router as statistics_router
from handlers.features.static_chat_analyzer import router as STA_router
from handlers.features.chat_export import router as chat_export_router
from handlers.features.voice_messages_transcriber import router as voice_transcribe_router
from handlers.initial_setup import router as initial_setup_router
from handlers.menu import router as menu_router
from handlers.settings import router as settings_router
from handlers.subscription import router as subscription_router

__all__ = [
    "data_management_router",
    "delete_messages_router",
    "edit_messages_router",
    "initial_setup_router",
    "menu_router",
    "process_message_router",
    "settings_router",
    "statistics_router",
    "subscription_router",
    "STA_router",
    "chat_export_router",
    "voice_transcribe_router"
]
