import asyncio
import json
import os
import random
import subprocess
import tempfile

import aiohttp
from aiohttp import web
from aiohttp_socks import ProxyConnector, ProxyType


class SimpleProxyServer:
    def __init__(self):
        self.socket_path = "/tmp/my_socket_for_server.sock"
        self.proxy_pool = []  # HTTP/SOCKS5 прокси (строка URL)
        self.advanced_pool = []  # Shadowsocks/Trojan/VLESS/VMess (словари)
        self.current_index = 0

    # ============================================
    # 1. Получение пула от Мозгов
    # ============================================

    async def fetch_pool_from_mozgi(self):
        """Запросить все прокси у Мозгов через LDS"""
        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
            writer.write(b"proxy:shadowsocks")
            await writer.drain()

            chunks = []
            while True:
                chunk = await reader.read(8192)
                if not chunk:
                    break
                chunks.append(chunk)

            data = json.loads(b"".join(chunks).decode())
            writer.close()
            await writer.wait_closed()

            # Разбираем HTTP/SOCKS5
            for protocol in ["http", "https", "socks5"]:
                pool = data.get(protocol, {})
                for order in ["5", "4", "3", "2", "1"]:
                    for item in pool.get(order, []):
                        proxy_url = item.get("proxy", "")
                        if proxy_url:
                            if protocol == "socks5":
                                proxy_url = proxy_url.replace("http://", "socks5://")
                            self.proxy_pool.append(proxy_url)

            # Разбираем Shadowsocks/Trojan/VLESS/VMess
            for protocol in ["shadowsocks", "trojan", "vless", "vmess"]:
                pool = data.get(protocol, {})
                for order in ["5", "4", "3", "2", "1"]:
                    for item in pool.get(order, []):
                        item["protocol"] = protocol
                        self.advanced_pool.append(item)

            print(
                f"📥 Получено: {len(self.proxy_pool)} HTTP/SOCKS5, {len(self.advanced_pool)} Advanced"
            )
            return True

        except Exception as e:
            print(f"❌ Ошибка получения пула: {e}")
            return False

    # ============================================
    # 2. Валидация прокси
    # ============================================

    async def validate_proxy(self, proxy_url):
        """Проверить, жив ли прокси"""
        try:
            connector = ProxyConnector.from_url(proxy_url)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    "http://httpbin.org/ip",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "origin" in data:
                            return True
        except:
            pass
        return False

    async def filter_live_proxies(self):
        """Оставить только живые HTTP/SOCKS5 прокси"""
        if not self.proxy_pool:
            return

        print(f"🔍 Проверяю {len(self.proxy_pool)} прокси...")

        tasks = [self.validate_proxy(p) for p in self.proxy_pool]
        results = await asyncio.gather(*tasks)

        self.proxy_pool = [p for p, ok in zip(self.proxy_pool, results) if ok]
        print(f"✅ Живых: {len(self.proxy_pool)}")

    # ============================================
    # 3. Получение следующего прокси
    # ============================================

    def get_next_proxy(self):
        """Вернуть следующий HTTP/SOCKS5 прокси"""
        if not self.proxy_pool:
            return None
        proxy = self.proxy_pool[self.current_index % len(self.proxy_pool)]
        self.current_index += 1
        return proxy

    def get_random_advanced(self):
        """Вернуть случайный Advanced прокси"""
        if not self.advanced_pool:
            return None
        return random.choice(self.advanced_pool)

    # ============================================
    # 4. Локальный туннель для Shadowsocks/Trojan
    # ============================================

    async def start_sslocal(self, host, port, method, password):
        """Запустить sslocal и вернуть локальный SOCKS5-порт"""
        local_port = random.randint(20000, 40000)
        cmd = [
            "sslocal",
            "-s",
            host,
            "-p",
            str(port),
            "-m",
            method,
            "-k",
            password,
            "-l",
            str(local_port),
            "-v",
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        await asyncio.sleep(1)
        return process, local_port

    async def start_trojan(self, host, port, password, sni):
        """Запустить trojan и вернуть локальный SOCKS5-порт"""
        local_port = random.randint(20000, 40000)
        config = {
            "run_type": "client",
            "local_addr": "127.0.0.1",
            "local_port": local_port,
            "remote_addr": host,
            "remote_port": int(port),
            "password": [password],
            "ssl": {"sni": sni or host, "verify": False, "verify_hostname": False},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            config_path = f.name

        cmd = ["trojan", "-c", config_path]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        await asyncio.sleep(1)
        return process, local_port, config_path

    # ============================================
    # 5. Выполнение HTTP-запроса через прокси
    # ============================================

    async def _try_http_socks5(self, target_url, headers):
        """Пробует HTTP/SOCKS5 прокси"""
        proxy = self.get_next_proxy()
        if not proxy:
            return None

        try:
            connector = ProxyConnector.from_url(proxy)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    target_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    body = await resp.read()
                    if len(body) > 100:
                        print(f"✅ {proxy} → {resp.status}")
                        return web.Response(body=body, status=resp.status)
        except Exception as e:
            print(f"❌ {proxy}: {str(e)[:60]}")
        return None

    async def _try_shadowsocks(self, target_url, headers):
        """Пробует Shadowsocks прокси"""
        ss = None
        for item in self.advanced_pool:
            if item.get("protocol") == "shadowsocks" and "host" in item:
                ss = item
                break
        if not ss:
            return None

        process = None
        try:
            process, local_port = await self.start_sslocal(
                ss["host"],
                ss["port"],
                ss.get("method", "aes-256-cfb"),
                ss.get("password", ""),
            )
            connector = ProxyConnector.from_url(f"socks5://127.0.0.1:{local_port}")
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    target_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    body = await resp.read()
                    if len(body) > 100:
                        print(f"✅ SS {ss['host']}:{ss['port']} → {resp.status}")
                        return web.Response(body=body, status=resp.status)
        except Exception as e:
            print(f"❌ SS: {str(e)[:60]}")
        finally:
            if process:
                process.terminate()
        return None

    async def _try_trojan(self, target_url, headers):
        """Пробует Trojan прокси"""
        tr = None
        for item in self.advanced_pool:
            if item.get("protocol") == "trojan" and "host" in item:
                tr = item
                break
        if not tr:
            return None

        process = None
        config_path = None
        try:
            process, local_port, config_path = await self.start_trojan(
                tr["host"],
                tr["port"],
                tr.get("password", ""),
                tr.get("sni", tr["host"]),
            )
            connector = ProxyConnector.from_url(f"socks5://127.0.0.1:{local_port}")
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    target_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    body = await resp.read()
                    if len(body) > 100:
                        print(f"✅ Trojan {tr['host']}:{tr['port']} → {resp.status}")
                        return web.Response(body=body, status=resp.status)
        except Exception as e:
            print(f"❌ Trojan: {str(e)[:60]}")
        finally:
            if process:
                process.terminate()
            if config_path:
                try:
                    os.unlink(config_path)
                except:
                    pass
        return None

    # ============================================
    # 6. Обработчик запросов
    # ============================================

    async def handle_request(self, request):
        target_url = str(request.url)
        print(f"📥 Запрос: {target_url}")

        # Копируем заголовки от клиента
        headers = {}
        for name, value in request.headers.items():
            if name.lower() in ("host", "user-agent", "accept", "accept-language"):
                headers[name] = value

        # Пробуем HTTP/SOCKS5
        for _ in range(5):
            resp = await self._try_http_socks5(target_url, headers)
            if resp:
                return resp

        # Пробуем Shadowsocks
        resp = await self._try_shadowsocks(target_url, headers)
        if resp:
            return resp

        # Пробуем Trojan
        resp = await self._try_trojan(target_url, headers)
        if resp:
            return resp

        return web.Response(text="Не удалось выполнить запрос", status=502)

    async def router(self, request):
        if request.method == "CONNECT":
            return web.Response(text="HTTPS не поддерживается", status=501)
        return await self.handle_request(request)

    # ============================================
    # 7. Старт
    # ============================================

    async def start(self, host="0.0.0.0", port=9000):
        ok = await self.fetch_pool_from_mozgi()
        if not ok:
            print("❌ Не удалось получить пул")
            return

        # Фильтруем мёртвые прокси
        await self.filter_live_proxies()

        if not self.proxy_pool and not self.advanced_pool:
            print("❌ Нет рабочих прокси")
            return

        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", self.router)

        print(f"🚀 Сервер: http://{host}:{port}")
        print(f"   HTTP/SOCKS5: {len(self.proxy_pool)} шт")
        print(f"   Shadowsocks/Trojan/VLESS/VMess: {len(self.advanced_pool)} шт")

        await web._run_app(app, host=host, port=port)


if __name__ == "__main__":
    server = SimpleProxyServer()
    asyncio.run(server.start())

# import asyncio
# import json
# import os
# import random
# import subprocess
# import tempfile
#
# import aiohttp
# from aiohttp import web
# from aiohttp_socks import ProxyConnector, ProxyType
#
#
# class SimpleProxyServer:
#     def __init__(self):
#         self.socket_path = "/tmp/my_socket_for_server.sock"
#         self.proxy_pool = []  # HTTP/SOCKS5 прокси (строка URL)
#         self.advanced_pool = []  # Shadowsocks/Trojan/VLESS/VMess (словари)
#         self.current_index = 0
#
#     # ============================================
#     # 1. Получение пула от Мозгов
#     # ============================================
#
#     async def fetch_pool_from_mozgi(self):
#         """Запросить все прокси у Мозгов через LDS"""
#         try:
#             reader, writer = await asyncio.open_unix_connection(self.socket_path)
#             writer.write(b"all")  # Запрашиваем все протоколы
#             await writer.drain()
#
#             chunks = []
#             while True:
#                 chunk = await reader.read(8192)
#                 if not chunk:
#                     break
#                 chunks.append(chunk)
#
#             data = json.loads(b"".join(chunks).decode())
#             writer.close()
#             await writer.wait_closed()
#
#             # Разбираем HTTP/SOCKS5
#             for protocol in ["http", "https", "socks5"]:
#                 pool = data.get(protocol, {})
#                 for order in ["5", "4", "3", "2", "1"]:
#                     for item in pool.get(order, []):
#                         proxy_url = item.get("proxy", "")
#                         if proxy_url:
#                             # SOCKS5 от Мозгов приходят как http://IP:PORT — исправляем
#                             if protocol == "socks5":
#                                 proxy_url = proxy_url.replace("http://", "socks5://")
#                             self.proxy_pool.append(proxy_url)
#
#             # Разбираем Shadowsocks/Trojan/VLESS/VMess
#             for protocol in ["shadowsocks", "trojan", "vless", "vmess"]:
#                 pool = data.get(protocol, {})
#                 for order in ["5", "4", "3", "2", "1"]:
#                     for item in pool.get(order, []):
#                         item["protocol"] = protocol
#                         self.advanced_pool.append(item)
#
#             print(
#                 f"📥 Получено: {len(self.proxy_pool)} HTTP/SOCKS5, {len(self.advanced_pool)} Advanced"
#             )
#             return True
#
#         except Exception as e:
#             print(f"❌ Ошибка получения пула: {e}")
#             return False
#
#     # ============================================
#     # 2. Получение следующего прокси
#     # ============================================
#
#     def get_next_proxy(self):
#         """Вернуть следующий HTTP/SOCKS5 прокси"""
#         if not self.proxy_pool:
#             return None
#         proxy = self.proxy_pool[self.current_index % len(self.proxy_pool)]
#         self.current_index += 1
#         return proxy
#
#     def get_random_advanced(self):
#         """Вернуть случайный Advanced прокси (SS/Trojan/VLESS/VMess)"""
#         if not self.advanced_pool:
#             return None
#         return random.choice(self.advanced_pool)
#
#     # ============================================
#     # 3. Локальный туннель для Shadowsocks/Trojan
#     # ============================================
#
#     async def start_sslocal(self, host, port, method, password):
#         """Запустить sslocal и вернуть локальный SOCKS5-порт"""
#         local_port = random.randint(20000, 40000)
#         cmd = [
#             "sslocal",
#             "-s",
#             host,
#             "-p",
#             str(port),
#             "-m",
#             method,
#             "-k",
#             password,
#             "-l",
#             str(local_port),
#             "-v",
#         ]
#         process = await asyncio.create_subprocess_exec(
#             *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
#         )
#         await asyncio.sleep(1)
#         return process, local_port
#
#     async def start_trojan(self, host, port, password, sni):
#         """Запустить trojan и вернуть локальный SOCKS5-порт"""
#         local_port = random.randint(20000, 40000)
#         config = {
#             "run_type": "client",
#             "local_addr": "127.0.0.1",
#             "local_port": local_port,
#             "remote_addr": host,
#             "remote_port": int(port),
#             "password": [password],
#             "ssl": {"sni": sni or host, "verify": False, "verify_hostname": False},
#         }
#         with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
#             json.dump(config, f)
#             config_path = f.name
#
#         cmd = ["trojan", "-c", config_path]
#         process = await asyncio.create_subprocess_exec(
#             *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
#         )
#         await asyncio.sleep(1)
#         return process, local_port, config_path
#
#     # ============================================
#     # 4. Выполнение HTTP-запроса через разные типы прокси
#     # ============================================
#
#     async def _try_http_socks5(self, target_url):
#         """Пробует HTTP/SOCKS5 прокси"""
#         proxy = self.get_next_proxy()
#         if not proxy:
#             return None
#
#         try:
#             connector = ProxyConnector.from_url(proxy)
#             async with aiohttp.ClientSession(connector=connector) as session:
#                 async with session.get(
#                     target_url, timeout=aiohttp.ClientTimeout(total=10)
#                 ) as resp:
#                     body = await resp.read()
#                     if len(body) > 100:
#                         print(f"✅ {proxy} → {resp.status}")
#                         return web.Response(body=body, status=resp.status)
#         except Exception as e:
#             print(f"❌ {proxy}: {str(e)[:60]}")
#         return None
#
#     # async def _try_shadowsocks(self, target_url):
#     #     """Пробует Shadowsocks прокси"""
#     #     ss = self.get_random_advanced()
#     #     if not ss or ss["protocol"] != "shadowsocks":
#     #         return None
#     #
#     #     process = None
#     #     try:
#     #         process, local_port = await self.start_sslocal(
#     #             ss["host"],
#     #             ss["port"],
#     #             ss.get("method", "aes-256-cfb"),
#     #             ss.get("password", ""),
#     #         )
#     #         connector = ProxyConnector.from_url(f"socks5://127.0.0.1:{local_port}")
#     #         async with aiohttp.ClientSession(connector=connector) as session:
#     #             async with session.get(
#     #                 target_url, timeout=aiohttp.ClientTimeout(total=10)
#     #             ) as resp:
#     #                 body = await resp.read()
#     #                 if len(body) > 100:
#     #                     print(f"✅ SS {ss['host']}:{ss['port']} → {resp.status}")
#     #                     return web.Response(body=body, status=resp.status)
#     #     except Exception as e:
#     #         print(f"❌ SS {ss.get('host')}: {str(e)[:60]}")
#     #     finally:
#     #         if process:
#     #             process.terminate()
#     #     return None
#     #
#     # async def _try_trojan(self, target_url):
#     #     """Пробует Trojan прокси"""
#     #     tr = self.get_random_advanced()
#     #     if not tr or tr["protocol"] != "trojan":
#     #         return None
#     #
#     #     process = None
#     #     config_path = None
#     #     try:
#     #         process, local_port, config_path = await self.start_trojan(
#     #             tr["host"],
#     #             tr["port"],
#     #             tr.get("password", ""),
#     #             tr.get("sni", tr["host"]),
#     #         )
#     #         connector = ProxyConnector.from_url(f"socks5://127.0.0.1:{local_port}")
#     #         async with aiohttp.ClientSession(connector=connector) as session:
#     #             async with session.get(
#     #                 target_url, timeout=aiohttp.ClientTimeout(total=10)
#     #             ) as resp:
#     #                 body = await resp.read()
#     #                 if len(body) > 100:
#     #                     print(f"✅ Trojan {tr['host']}:{tr['port']} → {resp.status}")
#     #                     return web.Response(body=body, status=resp.status)
#     #     except Exception as e:
#     #         print(f"❌ Trojan {tr.get('host')}: {str(e)[:60]}")
#     #     finally:
#     #         if process:
#     #             process.terminate()
#     #         if config_path:
#     #             try:
#     #                 os.unlink(config_path)
#     #             except:
#     #                 pass
#     #     return None
#     #
#     # # ============================================
#     # # 5. Обработчик запросов
#     # # ============================================
#     #
#     # async def handle_request(self, request):
#     #     target_url = str(request.url)
#     #     print(f"📥 Запрос: {target_url}")
#     #
#     #     # Пробуем 5 HTTP/SOCKS5 прокси
#     #     for _ in range(5):
#     #         resp = await self._try_http_socks5(target_url)
#     #         if resp:
#     #             return resp
#     #
#     #     # Пробуем Shadowsocks
#     #     resp = await self._try_shadowsocks(target_url)
#     #     if resp:
#     #         return resp
#     #
#     #     # Пробуем Trojan
#     #     resp = await self._try_trojan(target_url)
#     #     if resp:
#     #         return resp
#     #
#     #     return web.Response(text="Не удалось выполнить запрос", status=502)
#     async def handle_request(self, request):
#         target_url = str(request.url)
#         print(f"📥 Запрос: {target_url}")
#
#         # Копируем заголовки от клиента, особенно Host
#         headers = {}
#         for name, value in request.headers.items():
#             if name.lower() in ("host", "user-agent", "accept", "accept-language"):
#                 headers[name] = value
#
#         # Пробуем HTTP/SOCKS5
#         for _ in range(5):
#             resp = await self._try_http_socks5(target_url, headers)
#             if resp:
#                 return resp
#
#         # Пробуем Shadowsocks
#         resp = await self._try_shadowsocks(target_url, headers)
#         if resp:
#             return resp
#
#         # Пробуем Trojan
#         resp = await self._try_trojan(target_url, headers)
#         if resp:
#             return resp
#
#         return web.Response(text="Не удалось выполнить запрос", status=502)
#
#     async def _try_http_socks5(self, target_url, headers):
#         proxy = self.get_next_proxy()
#         if not proxy:
#             return None
#
#         try:
#             connector = ProxyConnector.from_url(proxy)
#             async with aiohttp.ClientSession(connector=connector) as session:
#                 async with session.get(
#                     target_url,
#                     headers=headers,
#                     timeout=aiohttp.ClientTimeout(total=10),
#                 ) as resp:
#                     body = await resp.read()
#                     if len(body) > 100:
#                         print(f"✅ {proxy} → {resp.status}")
#                         return web.Response(body=body, status=resp.status)
#         except Exception as e:
#             print(f"❌ {proxy}: {str(e)[:60]}")
#         return None
#
#     async def _try_shadowsocks(self, target_url, headers):
#         # Ищем SS в пуле
#         ss = None
#         for item in self.advanced_pool:
#             if item.get("protocol") == "shadowsocks" and "host" in item:
#                 ss = item
#                 break
#         if not ss:
#             return None
#
#         process = None
#         try:
#             process, local_port = await self.start_sslocal(
#                 ss["host"],
#                 ss["port"],
#                 ss.get("method", "aes-256-cfb"),
#                 ss.get("password", ""),
#             )
#             connector = ProxyConnector.from_url(f"socks5://127.0.0.1:{local_port}")
#             async with aiohttp.ClientSession(connector=connector) as session:
#                 async with session.get(
#                     target_url,
#                     headers=headers,
#                     timeout=aiohttp.ClientTimeout(total=10),
#                 ) as resp:
#                     body = await resp.read()
#                     if len(body) > 100:
#                         print(f"✅ SS {ss['host']}:{ss['port']} → {resp.status}")
#                         return web.Response(body=body, status=resp.status)
#         except Exception as e:
#             print(f"❌ SS: {str(e)[:60]}")
#         finally:
#             if process:
#                 process.terminate()
#         return None
#
#     async def _try_trojan(self, target_url, headers):
#         tr = None
#         for item in self.advanced_pool:
#             if item.get("protocol") == "trojan" and "host" in item:
#                 tr = item
#                 break
#         if not tr:
#             return None
#
#         process = None
#         config_path = None
#         try:
#             process, local_port, config_path = await self.start_trojan(
#                 tr["host"],
#                 tr["port"],
#                 tr.get("password", ""),
#                 tr.get("sni", tr["host"]),
#             )
#             connector = ProxyConnector.from_url(f"socks5://127.0.0.1:{local_port}")
#             async with aiohttp.ClientSession(connector=connector) as session:
#                 async with session.get(
#                     target_url,
#                     headers=headers,
#                     timeout=aiohttp.ClientTimeout(total=10),
#                 ) as resp:
#                     body = await resp.read()
#                     if len(body) > 100:
#                         print(f"✅ Trojan {tr['host']}:{tr['port']} → {resp.status}")
#                         return web.Response(body=body, status=resp.status)
#         except Exception as e:
#             print(f"❌ Trojan: {str(e)[:60]}")
#         finally:
#             if process:
#                 process.terminate()
#             if config_path:
#                 try:
#                     os.unlink(config_path)
#                 except:
#                     pass
#         return None
#
#     async def router(self, request):
#         if request.method == "CONNECT":
#             return web.Response(text="HTTPS не поддерживается", status=501)
#         return await self.handle_request(request)
#
#     # ============================================
#     # 6. Старт
#     # ============================================
#
#     async def start(self, host="0.0.0.0", port=9000):
#         ok = await self.fetch_pool_from_mozgi()
#         if not ok:
#             print("❌ Не удалось получить пул")
#             return
#
#         app = web.Application()
#         app.router.add_route("*", "/{tail:.*}", self.router)
#
#         print(f"🚀 Сервер: http://{host}:{port}")
#         print(f"   HTTP/SOCKS5: {len(self.proxy_pool)} шт")
#         print(f"   Shadowsocks/Trojan/VLESS/VMess: {len(self.advanced_pool)} шт")
#
#         await web._run_app(app, host=host, port=port)
#
#
# if __name__ == "__main__":
#     server = SimpleProxyServer()
#     asyncio.run(server.start())
