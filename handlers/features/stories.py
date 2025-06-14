import asyncio

from aiogram import Bot
from aiogram.types import InputStoryContentPhoto, StoryArea, InputFile


async def save_views():
    bot = Bot("7650673156:AAGE0XFuC4kxImobAGfmh4rH3-1UVOu-QlI")

    story = await bot.post_story(
        business_connection_id="5343690076507370511",
        content=InputStoryContentPhoto(InputFile("5467643988472361372")),
        active_period=6*3600
    )
    print(story)

if __name__ == '__main__':
    asyncio.run(save_views())