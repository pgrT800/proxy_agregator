import asyncio
import re

import aiohttp


class GitHttp:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        """
        max_retries: сколько раз пытаться получить данные (по умолчанию 3)
        base_delay: начальная задержка между попытками в секундах (будет расти)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def get_content(self, source: str, session: aiohttp.ClientSession) -> list:
        """Получить список прокси с одного источника с ретраями"""
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with asyncio.timeout(15):
                    async with session.get(source) as response:
                        text = await response.text()
                        list_proxis = self._parse_lines(text)

                        print(
                            f"✅ [{attempt}/{self.max_retries}] {source}: {len(list_proxis)} прокси"
                        )
                        return list_proxis

            except asyncio.TimeoutError:
                last_error = f"таймаут"
            except aiohttp.ClientError as e:
                last_error = f"сетевая ошибка: {e}"
            except Exception as e:
                last_error = f"ошибка: {e}"

            # Если это не последняя попытка — ждём с растущей задержкой
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

    def _parse_lines(self, text: str) -> list:
        """Разобрать текст ответа в список IP:PORT"""
        list_proxis = []
        lines = text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            proxy = self._extract_ip_port(line)
            if proxy:
                list_proxis.append(proxy)

        return list_proxis

    def _extract_ip_port(self, line: str) -> str | None:
        """
        Извлекает IP:PORT из строки по шаблону.
        Поддерживает форматы:
        - 192.168.1.1:8080
        - 192.168.1.1:8080#comment
        - http://192.168.1.1:8080
        - socks5://192.168.1.1:1080
        - 192.168.1.1:8080 extra text
        """
        ip_pattern = r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
        port_pattern = r":([1-9][0-9]{0,4}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])"

        # Ищем IP:PORT в строке
        match = re.search(f"{ip_pattern}{port_pattern}", line)
        if match:
            return match.group(0)

        # Ищем с протоколом (http://..., socks5://...)
        protocol_pattern = r"(?:https?|socks5?)://"
        match_with_protocol = re.search(
            f"{protocol_pattern}?{ip_pattern}{port_pattern}", line
        )
        if match_with_protocol:
            result = match_with_protocol.group(0)
            result = re.sub(protocol_pattern, "", result)
            return result

        return None
