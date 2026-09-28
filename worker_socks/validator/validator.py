import asyncio
import random

import aiohttp
from aiohttp_socks import ProxyConnector

from core.TaskRegisterMainInit.TaskRegister import taskregister


class Validator:

    async def check_proxy_target(self, host, port, session):
        proxy_url = f"socks5://{host}:{port}"  # ← меняем протокол
        list_service = [
            "http://t.me",
            "http://instagram.com",
            "http://youtube.com",
            "http://facebook.com",
            "http://rutracker.org",
            "https://api.zoomeye.org",
            "http://web.whatsapp.com",
        ]

        list_task = []
        for service in list_service:
            task = asyncio.create_task(self._check_url(proxy_url, service, session))
            list_task.append(task)
        results = await asyncio.gather(*list_task)

        return {
            "telegram": results[0],
            "instagram": results[1],
            "youtube": results[2],
            "facebook": results[3],
            "rutracker": results[4],
            "zoomeye": results[5],
            "whatsapp": results[6],
            "host:port:type": proxy_url,
        }

    async def _check_url(self, proxy_url, target_url, session):
        try:
            connector = ProxyConnector.from_url(proxy_url)  # ← SOCKS5 connector
            # async with aiohttp.ClientSession(connector=connector) as session:

            await asyncio.sleep(random.uniform(0.01, 0.5))
            async with session.get(
                target_url,
                timeout=7,
                ssl=False,
                allow_redirects=True,
            ) as resp:
                return resp.status in (200, 301, 302)
        except Exception as e:
            return False
