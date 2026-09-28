import asyncio

import aiohttp


class GitHttp:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        """
        max_retries: сколько раз пытаться получить данные (по умолчанию 3)
        base_delay: начальная задержка между попытками в секундах (растёт вдвое)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def get_content(self, source: str, session: aiohttp.ClientSession) -> list:
        """Получить список строк с одного источника с ретраями"""
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with asyncio.timeout(15):
                    async with session.get(source) as response:
                        text = await response.text()
                        proxies = text.strip().split("\n")
                        list_proxis = [line.strip() for line in proxies if line.strip()]

                        print(
                            f"✅ [{attempt}/{self.max_retries}] {source}: {len(list_proxis)} строк"
                        )
                        return list_proxis

            except asyncio.TimeoutError:
                last_error = f"таймаут"
            except aiohttp.ClientError as e:
                last_error = f"сетевая ошибка: {e}"
            except Exception as e:
                last_error = f"ошибка: {e}"

            # Если не последняя попытка — ждём с растущей задержкой
            if attempt < self.max_retries:
                delay = self.base_delay * (2 ** (attempt - 1))  # 1с, 2с, 4с...
                print(
                    f"⏳ [{attempt}/{self.max_retries}] {source}: {last_error}, повтор через {delay:.0f}с..."
                )
                await asyncio.sleep(delay)

        # Все попытки исчерпаны
        print(
            f"❌ [{self.max_retries}/{self.max_retries}] {source}: не удалось после {self.max_retries} попыток ({last_error})"
        )
        return []
