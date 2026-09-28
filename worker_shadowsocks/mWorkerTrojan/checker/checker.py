import asyncio
import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.custom_widget import update_task


class CheckerTrojan:
    def __init__(self, timeout: int = 8):
        self.timeout = timeout

    async def checker(self, proxy_dict: dict, semaphore, task_id) -> tuple:
        async with semaphore:
            result = await self._check_proxy(proxy_dict)
            # update_task(task_id, add=1)

            return (proxy_dict, result)

    async def _check_proxy(self, proxy_dict: dict) -> bool:
        """TCP проверка для Trojan"""
        host = proxy_dict["host"]
        port = proxy_dict["port"]

        try:

            await asyncio.sleep(random.uniform(0.01, 0.5))
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=self.timeout
            )
            writer.close()
            return True
        except:
            return False
