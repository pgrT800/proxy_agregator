import asyncio
import random

import aiohttp
from aiohttp_socks import ProxyConnectionError, ProxyConnector, SocksError


class CheckerSocks5:
    async def check_proxy(
        self,
        host: str,
        port: int,
        task_id: str = None,
        session=None,
        max_retries: int = 2,
    ):
        """
        Проверяет SOCKS5 прокси через реальное подключение
        """
        from aiohttp_socks import ProxyConnectionError, ProxyConnector, SocksError

        proxy_url = f"socks5://{host}:{port}"

        for attempt in range(max_retries):
            connector = None
            try:
                connector = ProxyConnector.from_url(proxy_url)
                # Если переданная сессия есть, создаём новую с этим коннектором
                # Нельзя использовать переданную сессию с другим коннектором!

                await asyncio.sleep(random.uniform(0.01, 0.5))
                async with aiohttp.ClientSession(connector=connector) as temp_session:
                    async with temp_session.get(
                        "http://httpbin.org/ip",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as response:
                        return response.status == 200

            except ProxyConnectionError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    return False
            except SocksError:
                return False
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    return False
            except aiohttp.ClientError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    return False
            except Exception:
                return False
            finally:
                if connector:
                    await connector.close()

        return False
