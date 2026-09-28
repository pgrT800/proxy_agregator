import asyncio

import aiohttp


class GitHttp:
    async def get_content(self, source, session, max_retries=4):
        print(f"get {source}")

        for attempt in range(max_retries):
            list_proxis = []
            try:
                async with asyncio.timeout(15):
                    async with session.get(source) as response:
                        if response.status != 200:
                            print(f"⚠️ {source} вернул статус {response.status}")
                            return []  # Не повторяем при ошибке 4xx, 5xx

                        text = await response.text()
                        proxies = text.strip().split("\n")
                        # Фильтруем пустые строки
                        list_proxis = [p for p in proxies if p.strip()]

                        if list_proxis:
                            print(f"✅ {source}: {len(list_proxis)} прокси")
                        return list_proxis

            except asyncio.TimeoutError:
                print(f"⏰ Таймаут: {source} (попытка {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)  # 1, 2 секунды

            except aiohttp.ClientConnectorError as e:
                print(f"🌐 Не могу подключиться: {source} - {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

            except aiohttp.ClientError as e:
                print(f"❌ Ошибка HTTP: {source} - {e}")
                break  # Не повторяем при ошибках клиента

            except Exception as e:
                print(f"❌ Неизвестная ошибка: {source} - {e}")
                break  # Не повторяем при неизвестных ошибках

        print(f"❌ Не удалось загрузить {source} после {max_retries} попыток")
        return []  # Возвращаем пустой список, не падаем
