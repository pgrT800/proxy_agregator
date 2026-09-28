import asyncio
import random
import sys
from collections import deque

# ============================================
# 1. Сбор прокси (упрощенно)
# ============================================


async def collect_proxies():
    """Собираем прокси из интернета"""
    import re

    import aiohttp

    sources = [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    ]

    proxies = set()
    async with aiohttp.ClientSession() as session:
        for source in sources:
            try:
                async with session.get(source, timeout=10) as resp:
                    text = await resp.text()
                    for line in text.split("\n"):
                        match = re.search(
                            r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+)", line
                        )
                        if match:
                            proxies.add(match.group(1))
            except:
                pass

    return list(proxies)


# ============================================
# 2. Проверка прокси (быстрая)
# ============================================


async def check_proxy(proxy):
    """Проверяем, работает ли прокси"""
    import aiohttp

    try:
        proxy_url = f"http://{proxy}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://httpbin.org/ip", proxy=proxy_url, timeout=5
            ) as resp:
                if resp.status == 200:
                    return True
    except:
        pass
    return False


# ============================================
# 3. ПРОСТОЙ ТУННЕЛЬНЫЙ ПРОКСИ-СЕРВЕР
# ============================================


class TunnelProxy:
    def __init__(self, proxies, host="0.0.0.0", port=9000):
        self.proxies = deque(proxies)  # Очередь прокси
        self.host = host
        self.port = port
        self.server = None
        self.bad_proxies = set()

        print(f"🌐 Загружено {len(proxies)} прокси")

    async def start(self):
        """Запуск сервера"""
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )

        print(f"✅ Туннельный прокси на {self.host}:{self.port}")
        print(f"   Используй: chromium --proxy-server='http://localhost:{self.port}'")
        print("   Нажми Ctrl+C для остановки")

        async with self.server:
            await self.server.serve_forever()

    def get_next_proxy(self):
        """Берем следующий прокси из очереди"""
        # Ищем рабочий прокси (не в bad)
        for _ in range(len(self.proxies)):
            proxy = self.proxies[0]
            self.proxies.rotate(-1)
            if proxy not in self.bad_proxies:
                return proxy

        # Если все плохие - сброс
        self.bad_proxies.clear()
        return self.proxies[0] if self.proxies else None

    async def handle_client(self, reader, writer):
        """Обработка клиента - ПРОСТО ТУННЕЛЬ"""
        try:
            # Читаем первую строку запроса
            data = await reader.readline()
            if not data:
                writer.close()
                return

            # Разбираем метод и цель
            parts = data.decode().split()
            if len(parts) < 2:
                writer.close()
                return

            method = parts[0].upper()
            target = parts[1]

            if method == "CONNECT":
                # HTTPS - через туннель
                await self.handle_connect(reader, writer, target)
            else:
                # HTTP - просто прокси
                await self.handle_http(reader, writer, data)

        except Exception as e:
            print(f"❌ Ошибка клиента: {e}")
        finally:
            try:
                writer.close()
            except:
                pass

    async def handle_connect(self, reader, writer, target):
        """CONNECT - создаем туннель через внешний прокси"""

        # Пробуем разные прокси пока не найдем рабочий
        max_attempts = 5
        for attempt in range(max_attempts):
            proxy = self.get_next_proxy()
            if not proxy:
                writer.write(b"HTTP/1.1 503 No Proxy\r\n\r\n")
                await writer.drain()
                return

            try:
                # Разбираем цель
                host, port = target.split(":")
                port = int(port)

                # Разбираем прокси
                proxy_host, proxy_port = proxy.split(":")
                proxy_port = int(proxy_port)

                # Подключаемся к внешнему прокси
                proxy_reader, proxy_writer = await asyncio.open_connection(
                    proxy_host, proxy_port
                )

                # Отправляем CONNECT на внешний прокси
                connect_cmd = f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n"
                proxy_writer.write(connect_cmd.encode())
                await proxy_writer.drain()

                # Ждем ответ от прокси
                response = await proxy_reader.readline()

                if b"200" not in response:
                    # Прокси не работает - помечаем и пробуем следующий
                    self.bad_proxies.add(proxy)
                    proxy_writer.close()
                    continue

                # Отправляем клиенту успех
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()

                print(f"🔒 Туннель: {target} через {proxy}")

                # ТУННЕЛЬ - просто пересылаем данные
                await asyncio.gather(
                    self.pipe(reader, proxy_writer), self.pipe(proxy_reader, writer)
                )
                return  # Успешно завершили

            except Exception as e:
                self.bad_proxies.add(proxy)
                print(f"⚠️ Ошибка {proxy}: {e}")
                continue

        # Если все прокси не работают
        writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        await writer.drain()

    async def handle_http(self, reader, writer, first_line):
        """HTTP запрос - просто проксируем"""
        proxy = self.get_next_proxy()
        if not proxy:
            writer.write(b"HTTP/1.1 503 No Proxy\r\n\r\n")
            await writer.drain()
            return

        try:
            # Читаем остальные заголовки
            headers = b""
            while True:
                line = await reader.readline()
                headers += line
                if line == b"\r\n" or line == b"\n":
                    break

            # Парсим хост
            host = None
            for line in (first_line + headers).split(b"\r\n"):
                if line.lower().startswith(b"host:"):
                    host = line.decode().split(":", 1)[1].strip()
                    break

            if not host:
                writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                await writer.drain()
                return

            # Строим полный URL
            parts = first_line.decode().split()
            if len(parts) < 2:
                return

            method = parts[0]
            target = parts[1]

            if target.startswith(("http://", "https://")):
                url = target
            else:
                scheme = "https" if ":443" in host else "http"
                url = f"{scheme}://{host}{target}"

            # Подключаемся к внешнему прокси
            proxy_host, proxy_port = proxy.split(":")
            proxy_port = int(proxy_port)

            proxy_reader, proxy_writer = await asyncio.open_connection(
                proxy_host, proxy_port
            )

            # Отправляем запрос
            request = f"{method} {url} HTTP/1.1\r\n".encode()
            request += headers
            proxy_writer.write(request)
            await proxy_writer.drain()

            print(f"🌐 {method} {url} через {proxy}")

            # Проксируем ответ
            await self.pipe(proxy_reader, writer)

        except Exception as e:
            self.bad_proxies.add(proxy)
            print(f"❌ HTTP ошибка: {e}")
            try:
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await writer.drain()
            except:
                pass

    async def pipe(self, reader, writer, buffer_size=8192):
        """ПРОСТАЯ ПЕРЕДАЧА ДАННЫХ"""
        try:
            while True:
                data = await reader.read(buffer_size)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except:
            pass


# ============================================
# 4. ЗАПУСК
# ============================================


async def main():
    print("=" * 60)
    print("🚀 ПРОСТОЙ ТУННЕЛЬНЫЙ ПРОКСИ")
    print("=" * 60)

    # Собираем прокси
    print("\n📡 Сбор прокси...")
    proxies = await collect_proxies()
    print(f"📦 Найдено {len(proxies)} прокси")

    if not proxies:
        print("❌ Нет прокси. Добавьте вручную в список.")
        # Добавляем тестовый прокси (если есть)
        proxies = ["212.58.132.5:8888"]  # Пример

    # Запускаем туннель
    proxy_server = TunnelProxy(proxies, port=9000)
    await proxy_server.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Пока!")
