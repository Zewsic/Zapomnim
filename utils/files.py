import ssl

import aiohttp
import asyncio

import certifi

ssl_context = ssl.create_default_context(cafile=certifi.where())

async def upload_file(file_data: bytes, name: str) -> str:
    headers = {
        "User-Agent": "Zapomnim Telegram Bot/1.0 (contact: me@zewsic.pro)"
    }

    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field('file', file_data, filename=name)
        async with session.post("https://0x0.st", data=data, ssl=ssl_context, headers=headers) as resp:
            return await resp.text()
