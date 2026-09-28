#!/usr/bin/env python3
import asyncio
import os
import random
import re
import sys
from asyncio.timeouts import timeout
from typing import Dict, Optional

import aiohttp
from aiohttp import (
    ClientConnectionError,
    ClientConnectorSSLError,
    ServerDisconnectedError,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.custom_widget import update_task


class Validator:
    def __init__(self, timeout: int = 2):
        self.timeout = timeout
        # Заголовки как у реального браузера (Chrome 124)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
            "DNT": "1",
            "Sec-CH-UA": '"Not.A/Brand";v="8", "Chromium";v="124", "Google Chrome";v="124"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1",
            "Connection": "keep-alive",
        }

    async def check_proxy_target(
        self, host: str, port: str, task_id: str, session: aiohttp.ClientSession
    ) -> Dict:
        # 🔧 КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: для прокси всегда используем http://
        # даже если целевой сайт — https://
        proxy_url = f"http://{host}:{port}"

        # 1️⃣ Проверка IP + анонимности
        ip_result = await self._check_ip(proxy_url, session)
        if not ip_result.get("alive"):
            return self._empty_result(host, port, proxy_url)

        # 2️⃣ Проверка реальных сайтов (все через HTTPS для полной проверки туннеля)
        test_sites = {
            "telegram": "https://web.telegram.org",
            "google": "https://www.google.com/generate_204",
            "cloudflare": "https://1.1.1.1/cdn-cgi/trace",
            "httpbin": "https://httpbin.org/ip",  # для проверки тела ответа
        }

        site_results = {}
        tasks = [
            asyncio.create_task(self._check_site_https(proxy_url, url, session))
            for name, url in test_sites.items()
        ]
        done, _ = await asyncio.wait(tasks)
        for task in done:
            name, ok, status, details = task.result()
            site_results[name] = ok

        working = [name for name, ok in site_results.items() if ok]

        # Формируем результат в вашем формате
        result = {
            "telegram": site_results.get("telegram", False),
            "instagram": False,
            "youtube": False,
            "facebook": False,
            "rutracker": False,
            "zoomeye": False,
            "whatsapp": False,
            "host:port:type": f"https://{host}:{port}",  # для отображения
            "proxy_ip": ip_result.get("ip", ""),
            "is_anonymous": ip_result.get("anonymous", False),
            "tested_sites": len(working),
            "working_services": working,
            # Дополнительные метрики для отладки
            "supports_connect": site_results.get("httpbin", False),
            "ssl_verified": True,
        }
        return result

    async def _check_ip(self, proxy_url: str, session: aiohttp.ClientSession) -> Dict:
        """Проверяет прокси и возвращает внешний IP + уровень анонимности"""
        urls = [
            "https://httpbin.org/ip",
            "https://api.ipify.org?format=json",
            "https://ifconfig.me/ip",
        ]
        for url in urls:
            try:
                async with session.get(
                    url,
                    proxy=proxy_url,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout, sock_connect=3),
                    ssl=True,  # ✅ Проверяем сертификаты
                    allow_redirects=True,
                ) as resp:
                    if resp.status != 200:
                        continue

                    text = await resp.text()
                    # Извлекаем IP из JSON или plain text
                    ip_match = re.search(
                        r"(?:\"origin\":\s*\"|)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})",
                        text,
                    )
                    if ip_match:
                        proxy_ip = ip_match.group(1)
                        # Проверяем заголовки прозрачности
                        headers_dict = {k.lower(): v for k, v in resp.headers.items()}
                        is_anonymous = not any(
                            h in headers_dict
                            for h in ("x-forwarded-for", "via", "proxy-authorization")
                        )
                        return {
                            "alive": True,
                            "ip": proxy_ip,
                            "anonymous": is_anonymous,
                        }
            except (
                ClientConnectorSSLError,
                ServerDisconnectedError,
                asyncio.TimeoutError,
            ):
                continue
            except Exception:
                continue
        return {"alive": False}

    async def _check_site_https(
        self, proxy_url: str, target_url: str, session: aiohttp.ClientSession
    ) -> tuple:
        """
        Проверяет HTTPS-сайт через прокси с полной валидацией туннеля.
        Возвращает: (name, is_ok, status_code, details_dict)
        """
        name = target_url.split("/")[2].replace("www.", "").split(".")[0]

        try:
            async with session.get(
                target_url,
                proxy=proxy_url,  # http://host:port для прокси
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout, sock_connect=3),
                ssl=True,  # ✅ Проверяем реальные сертификаты
                allow_redirects=True,
            ) as resp:
                # Google generate_204 возвращает 204
                if target_url.endswith("generate_204"):
                    return (
                        name,
                        resp.status == 204,
                        resp.status,
                        {"status": resp.status},
                    )

                # Проверка статуса
                if resp.status not in (200, 301, 302):
                    return name, False, resp.status, {"status": resp.status}

                # 🔍 Читаем тело для проверки целостности
                text = await resp.text()

                # Проверка контента: длина, капча, блок
                if (
                    len(text) < 200
                    or "captcha" in text.lower()
                    or "blocked" in text.lower()
                ):
                    return name, False, resp.status, {"content_check": "failed"}

                # 🔍 Проверка Content-Length (если есть)
                headers = resp.headers
                if "content-length" in headers:
                    try:
                        cl = int(headers["content-length"])
                        if cl > 0 and len(text.encode("utf-8")) < cl * 0.5:
                            return (
                                name,
                                False,
                                resp.status,
                                {"content_length": "mismatch"},
                            )
                    except (ValueError, TypeError):
                        pass

                # ✅ Все проверки пройдены
                return name, True, resp.status, {"content_len": len(text)}

        except ClientConnectorSSLError as e:
            # ❌ Ошибка SSL — прокси не поддерживает корректный TLS-туннель
            return name, False, None, {"ssl_error": str(e)[:100]}
        except ServerDisconnectedError:
            # ❌ Прокси разорвал соединение (часто при некорректном CONNECT)
            return name, False, None, {"disconnected": True}
        except ClientConnectionError as e:
            return name, False, None, {"connection_error": str(e)[:100]}
        except asyncio.TimeoutError:
            return name, False, None, {"timeout": True}
        except Exception as e:
            return name, False, None, {"error": f"{type(e).__name__}: {str(e)[:50]}"}

    def _empty_result(self, host: str, port: str, proxy_url: str) -> Dict:
        return {
            "telegram": False,
            "instagram": False,
            "youtube": False,
            "facebook": False,
            "rutracker": False,
            "zoomeye": False,
            "whatsapp": False,
            "host:port:type": proxy_url,
            "proxy_ip": "",
            "is_anonymous": False,
            "tested_sites": 0,
            "working_services": [],
            "supports_connect": False,
            "ssl_verified": False,
        }


# import asyncio
# import os
# import sys
# from asyncio.timeouts import timeout
#
# import aiohttp
#
# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
#
# import asyncio
# import random
# import re
# from typing import Dict, Optional
#
# import aiohttp
#
# from core.custom_widget import update_task
#
#
# class Validator:
#     def __init__(self, timeout: int = 7):
#         self.timeout = timeout
#         self.headers = {
#             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
#             "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
#             "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
#             "DNT": "1",
#             "Sec-CH-UA": '"Not.A/Brand";v="8", "Chromium";v="124", "Google Chrome";v="124"',
#             "Sec-CH-UA-Mobile": "?0",
#             "Sec-CH-UA-Platform": '"Windows"',
#             "Upgrade-Insecure-Requests": "1",
#         }
#
#     async def check_proxy_target(
#         self, host: str, port: str, task_id: str, session: aiohttp.ClientSession
#     ) -> Dict:
#         proxy_url = f"https://{host}:{port}"
#
#         # 1️⃣ Быстрая проверка маршрутизации + определение IP прокси
#         ip_result = await self._check_ip(proxy_url, session)
#         if not ip_result.get("alive"):
#             return self._empty_result(host, port, proxy_url)
#
#         # 2️⃣ Проверка реальных сайтов с заголовками браузера
#         test_sites = {
#             "telegram": "https://web.telegram.org",
#             "google": "https://www.google.com/generate_204",
#             "cloudflare": "https://1.1.1.1/cdn-cgi/trace",
#         }
#
#         site_results = {}
#         tasks = [
#             asyncio.create_task(self._check_site(proxy_url, url, session))
#             for name, url in test_sites.items()
#         ]
#         done, _ = await asyncio.wait(tasks)
#         for task in done:
#             name, ok, status = task.result()
#             site_results[name] = ok
#
#         # 3️⃣ Считаем рабочие сервисы
#         working = [name for name, ok in site_results.items() if ok]
#         count = len(working)
#
#         # Формируем ответ в вашем формате
#         result = {
#             "telegram": site_results.get("telegram", False),
#             "instagram": False,  # можно оставить, если не тестируете
#             "youtube": False,
#             "facebook": False,
#             "rutracker": False,
#             "zoomeye": False,
#             "whatsapp": False,
#             "host:port:type": proxy_url,
#             "proxy_ip": ip_result.get("ip", ""),
#             "is_anonymous": ip_result.get("anonymous", False),
#             "tested_sites": count,
#             "working_services": working,
#         }
#         return result
#
#     async def _check_ip(self, proxy_url: str, session: aiohttp.ClientSession) -> Dict:
#         """Проверяет, проксирует ли запрос, и возвращает IP + уровень анонимности"""
#         urls = [
#             "https://httpbin.org/ip",
#             "https://api.ipify.org?format=json",
#             "https://ifconfig.me/ip",
#         ]
#         for url in urls:
#             try:
#                 async with session.get(
#                     url,
#                     proxy=proxy_url,
#                     headers=self.headers,
#                     timeout=self.timeout,
#                     allow_redirects=True,
#                 ) as resp:
#                     if resp.status != 200:
#                         continue
#
#                     text = await resp.text()
#                     # Извлекаем IP из JSON или plain text
#                     ip_match = re.search(
#                         r"(?:\"origin\":\s*\"|)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})",
#                         text,
#                     )
#                     if ip_match:
#                         proxy_ip = ip_match.group(1)
#                         # Проверяем заголовки прозрачности
#                         headers_dict = {k.lower(): v for k, v in resp.headers.items()}
#                         is_anonymous = not any(
#                             h in headers_dict
#                             for h in ("x-forwarded-for", "via", "proxy-authorization")
#                         )
#
#                         return {
#                             "alive": True,
#                             "ip": proxy_ip,
#                             "anonymous": is_anonymous,
#                         }
#             except:
#                 continue
#         return {"alive": False}
#
#     async def _check_site(
#         self, proxy_url: str, target_url: str, session: aiohttp.ClientSession
#     ) -> tuple:
#         """Проверяет доступность одного сайта через прокси"""
#         name = target_url.split("/")[2].replace("www.", "").split(".")[0]
#         try:
#             async with session.get(
#                 target_url,
#                 proxy=proxy_url,
#                 headers=self.headers,
#                 timeout=self.timeout,
#                 allow_redirects=True,
#             ) as resp:
#                 # Google generate_204 возвращает 204
#                 if target_url.endswith("generate_204"):
#                     return name, resp.status == 204, resp.status
#
#                 # Остальные: 200 или корректный редирект на HTTPS
#                 if resp.status in (200,):
#                     text = await resp.text()
#                     # Проверяем, что это не страница-заглушка/капча
#                     if (
#                         len(text) > 200
#                         and "captcha" not in text.lower()
#                         and "blocked" not in text.lower()
#                     ):
#                         return name, True, resp.status
#                 return name, False, resp.status
#         except:
#             return name, False, None
#
#     def _empty_result(self, host: str, port: str, proxy_url: str) -> Dict:
#         return {
#             "telegram": False,
#             "instagram": False,
#             "youtube": False,
#             "facebook": False,
#             "rutracker": False,
#             "zoomeye": False,
#             "whatsapp": False,
#             "host:port:type": proxy_url,
#             "proxy_ip": "",
#             "is_anonymous": False,
#             "tested_sites": 0,
#             "working_services": [],
#         }
#
# old my validator---------------------
#
# class Validator:
#
#     async def check_proxy_target(self, host, port, task_id, session):
#         proxy_url = f"https://{host}:{port}"
#         list_service = [
#             "http://t.me",
#             "http://instagram.com",  # Исправил опечатку: было instagramm.com
#             "http://youtube.com",
#             "http://facebook.com",
#             "http://rutracker.org",
#             "https://api.zoomeye.org",
#             "http://web.whatsapp.com",
#         ]
#
#         list_task = []
#         # Добавляем задачу для проверки t.me, как и для всех остальных
#         for service in list_service:
#             task = asyncio.create_task(self._check_url(proxy_url, service, session))
#             list_task.append(task)
#
#         # Ждём выполнения всех задач
#         results = await asyncio.gather(*list_task)
#
#         # Формируем и возвращаем словарь
#         data = {
#             "telegram": results[0],
#             "instagram": results[1],
#             "youtube": results[2],
#             "facebook": results[3],
#             "rutracker": results[4],
#             "zoomeye": results[5],
#             "whatsapp": results[6],
#             "host:port:type": proxy_url,
#         }
#         # update_task(task_id, add=1)
#         return data
#
#     async def _check_url(self, proxy_url, target_url, session):
#         try:
#
#             await asyncio.sleep(random.uniform(0.01, 0.5))
#             async with session.get(
#                 target_url,
#                 proxy=proxy_url,
#                 timeout=5,
#                 ssl=False,
#                 allow_redirects=True,
#             ) as resp:
#                 # 200 — OK
#                 # 301/302 — редирект, тоже OK
#                 # 400/405 — прокси не поддерживает этот тип запроса
#                 return resp.status in (200, 301, 302)
#         except Exception as e:
#             # print(f"except is {e}")
#             return False
