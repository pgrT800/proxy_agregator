import asyncio
import json
import os
import random
import subprocess
import tempfile

import aiohttp
from aiohttp_socks import ProxyConnector

from core.TaskRegisterMainInit.TaskRegister import taskregister


class ValidatorTrojan:
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.services = [
            ("telegram", "http://t.me"),
            ("instagram", "http://instagram.com"),
            ("youtube", "http://youtube.com"),
            ("facebook", "http://facebook.com"),
            ("rutracker", "http://rutracker.org"),
            ("zoomeye", "https://api.zoomeye.org"),
            ("whatsapp", "http://web.whatsapp.com"),
        ]

    async def validate_proxy(self, proxy_dict: dict, semaphore) -> dict:
        async with semaphore:
            host = proxy_dict["host"]
            port = proxy_dict["port"]
            password = proxy_dict.get("password", "")
            sni = proxy_dict.get("sni", host)

            if password:
                return await self._validate_via_trojan(host, port, password, sni)
            else:
                return await self._validate_via_direct(host, port)

    async def _validate_via_direct(self, host: str, port: int) -> dict:
        results = {}
        proxy_url = f"socks5://{host}:{port}"

        async def check_service(name: str, url: str) -> tuple:
            try:
                connector = ProxyConnector.from_url(proxy_url)
                await asyncio.sleep(random.uniform(0.01, 0.5))
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(
                        url, timeout=self.timeout, ssl=False
                    ) as resp:
                        return (name, resp.status in (200, 301, 302))
            except:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            url, proxy=proxy_url, timeout=self.timeout, ssl=False
                        ) as resp:
                            return (name, resp.status in (200, 301, 302))
                except:
                    return (name, False)

        tasks = [
            asyncio.create_task(check_service(name, url)) for name, url in self.services
        ]
        await taskregister.add_task_list_register(tasks)
        done, pending = await asyncio.wait(tasks)

        for task in done:
            name, status = task.result()
            results[name] = status

        results["host"] = host
        results["port"] = port
        results["type"] = "direct"
        results["proxy_url"] = proxy_url
        return results

    async def _validate_via_trojan(
        self, host: str, port: int, password: str, sni: str = None
    ) -> dict:
        local_port = random.randint(10000, 60000)

        config = {
            "run_type": "client",
            "local_addr": "127.0.0.1",
            "local_port": local_port,
            "remote_addr": host,
            "remote_port": port,
            "password": [password],
            "ssl": {
                "sni": sni if sni else host,
                "verify": False,
                "verify_hostname": False,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            config_path = f.name

        process = None
        results = {}

        try:
            cmd = ["trojan", "-c", config_path]
            await asyncio.sleep(random.uniform(0.01, 0.5))
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            if not await self._wait_for_port(local_port):
                return self._empty_result(host, port, password)
            print(f"🔍 Trojan: порт {local_port} открыт, создаю задачи валидации...")
            connector = ProxyConnector.from_url(f"socks5://127.0.0.1:{local_port}")

            async def check_service(name: str, url: str) -> tuple:
                try:
                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with session.get(
                            url, timeout=self.timeout, ssl=False
                        ) as resp:
                            return (name, resp.status in (200, 301, 302))
                except:
                    return (name, False)

            tasks = [
                asyncio.create_task(check_service(name, url))
                for name, url in self.services
            ]
            done, pending = await asyncio.wait(tasks)

            for task in done:
                name, status = task.result()
                results[name] = status

            results["host"] = host
            results["port"] = port
            results["password"] = password
            results["sni"] = sni if sni else host
            results["type"] = "trojan"
            results["proxy_url"] = f"socks5://{host}:{port}"
            return results

        except FileNotFoundError:
            print("❌ trojan не установлен! Установи: sudo pacman -S trojan")
            return self._empty_result(host, port, password)
        except Exception as e:
            print(f"❌ Ошибка Trojan валидации: {e}")
            return self._empty_result(host, port, password)
        finally:
            if process and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except:
                    process.kill()
            try:
                os.unlink(config_path)
            except:
                pass

    def _empty_result(self, host: str, port: int, password: str = "") -> dict:
        return {
            "telegram": False,
            "instagram": False,
            "youtube": False,
            "facebook": False,
            "rutracker": False,
            "zoomeye": False,
            "whatsapp": False,
            "host": host,
            "port": port,
            "password": password,
            "type": "trojan",
            "proxy_url": f"socks5://{host}:{port}",
        }

    async def _wait_for_port(self, port: int, max_wait: int = 2) -> bool:
        for i in range(max_wait):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", port), timeout=2
                )
                writer.close()
                print(f"✅ Порт {port} запустился за {i+1} сек trojan")
                return True
            except asyncio.CancelledError:
                print(f"🛑 Порт {port}: ожидание отменено trojan")
                raise
            except:
                await asyncio.sleep(1)
        print(f"❌ Порт {port} не запустился за {max_wait} сек trojan")
        return False


# import asyncio
# import json
# import os
# import random
# import subprocess
# import tempfile
#
# import aiohttp
# from aiohttp_socks import ProxyConnector
#
# from core.TaskRegisterMainInit.TaskRegister import taskregister
#
#
# class ValidatorTrojan:
#     def __init__(self, timeout: int = 10):
#         self.timeout = timeout
#         self.services = [
#             ("telegram", "http://t.me"),
#             ("instagram", "http://instagram.com"),
#             ("youtube", "http://youtube.com"),
#             ("facebook", "http://facebook.com"),
#             ("rutracker", "http://rutracker.org"),
#             ("zoomeye", "https://api.zoomeye.org"),
#             ("whatsapp", "http://web.whatsapp.com"),
#         ]
#
#     async def validate_proxy(self, proxy_dict: dict, semaphore) -> dict:
#         """Проверяет доступность сервисов через Trojan прокси"""
#         async with semaphore:
#             host = proxy_dict["host"]
#             port = proxy_dict["port"]
#             password = proxy_dict.get("password", "")
#             sni = proxy_dict.get("sni", host)
#
#             if password:
#                 return await self._validate_via_trojan(host, port, password, sni)
#             else:
#                 return await self._validate_via_direct(host, port)
#
#     async def _validate_via_direct(self, host: str, port: int) -> dict:
#         """Проверяет прокси как обычный SOCKS5 или HTTP"""
#         results = {}
#         proxy_url = f"socks5://{host}:{port}"
#
#         async def check_service(name: str, url: str) -> tuple:
#             try:
#                 connector = ProxyConnector.from_url(proxy_url)
#                 await asyncio.sleep(random.uniform(0.01, 0.5))
#                 async with aiohttp.ClientSession(connector=connector) as session:
#                     async with session.get(
#                         url, timeout=self.timeout, ssl=False
#                     ) as resp:
#                         return (name, resp.status in (200, 301, 302))
#             except:
#                 try:
#                     async with aiohttp.ClientSession() as session:
#                         async with session.get(
#                             url, proxy=proxy_url, timeout=self.timeout, ssl=False
#                         ) as resp:
#                             return (name, resp.status in (200, 301, 302))
#                 except:
#                     return (name, False)
#
#         tasks = [
#             asyncio.create_task(check_service(name, url)) for name, url in self.services
#         ]
#         await taskregister.add_task_list_register(tasks)
#         done, pending = await asyncio.wait(tasks)
#
#         for task in done:
#             name, status = task.result()
#             results[name] = status
#
#         results["host"] = host
#         results["port"] = port
#         results["type"] = "direct"
#         results["proxy_url"] = proxy_url
#         return results
#
#     async def _validate_via_trojan(
#         self, host: str, port: int, password: str, sni: str = None
#     ) -> dict:
#         """Запускает trojan-client и проверяет все сервисы параллельно"""
#         local_port = random.randint(10000, 60000)
#
#         config = {
#             "run_type": "client",
#             "local_addr": "127.0.0.1",
#             "local_port": local_port,
#             "remote_addr": host,
#             "remote_port": port,
#             "password": [password],
#             "ssl": {
#                 "sni": sni if sni else host,
#                 "verify": False,
#                 "verify_hostname": False,
#             },
#         }
#
#         with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
#             json.dump(config, f)
#             config_path = f.name
#
#         process = None
#         results = {}
#
#         try:
#             cmd = ["trojan", "-c", config_path]
#
#             await asyncio.sleep(random.uniform(0.01, 0.5))
#             process = await asyncio.create_subprocess_exec(
#                 *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
#             )
#
#             if not await self._wait_for_port(local_port):
#                 return self._empty_result(host, port, password)
#
#             connector = ProxyConnector.from_url(f"socks5://127.0.0.1:{local_port}")
#
#             async def check_service(name: str, url: str) -> tuple:
#                 try:
#                     async with aiohttp.ClientSession(connector=connector) as session:
#                         async with session.get(
#                             url, timeout=self.timeout, ssl=False
#                         ) as resp:
#                             return (name, resp.status in (200, 301, 302))
#                 except:
#                     return (name, False)
#
#             tasks = [
#                 asyncio.create_task(check_service(name, url))
#                 for name, url in self.services
#             ]
#             await taskregister.add_task_list_register(tasks)
#             done, pending = await asyncio.wait(tasks)
#
#             for task in done:
#                 name, status = task.result()
#                 results[name] = status
#
#             results["host"] = host
#             results["port"] = port
#             results["password"] = password
#             results["sni"] = sni if sni else host
#             results["type"] = "trojan"
#             results["proxy_url"] = f"socks5://{host}:{port}"
#             return results
#
#         except FileNotFoundError:
#             print("❌ trojan не установлен! Установи: sudo pacman -S trojan")
#             return self._empty_result(host, port, password)
#         except Exception as e:
#             print(f"❌ Ошибка Trojan валидации: {e}")
#             return self._empty_result(host, port, password)
#         finally:
#             if process and process.returncode is None:
#                 process.terminate()
#                 try:
#                     await asyncio.wait_for(process.wait(), timeout=2)
#                 except:
#                     process.kill()
#             try:
#                 os.unlink(config_path)
#             except:
#                 pass
#
#     def _empty_result(self, host: str, port: int, password: str = "") -> dict:
#         return {
#             "telegram": False,
#             "instagram": False,
#             "youtube": False,
#             "facebook": False,
#             "rutracker": False,
#             "zoomeye": False,
#             "whatsapp": False,
#             "host": host,
#             "port": port,
#             "password": password,
#             "type": "trojan",
#             "proxy_url": f"socks5://{host}:{port}",
#         }
#
#     async def _wait_for_port(self, port: int, max_wait: int = 2) -> bool:
#         """Ждёт, пока порт начнёт слушать"""
#         for i in range(max_wait):
#             try:
#                 reader, writer = await asyncio.wait_for(
#                     asyncio.open_connection("127.0.0.1", port), timeout=2
#                 )
#                 writer.close()
#                 print(f"✅ Порт {port} запустился за {i+1} сек")
#                 return True
#             except asyncio.CancelledError:
#                 print(f"🛑 Порт {port}: ожидание отменено")
#                 raise
#             except:
#                 await asyncio.sleep(1)
#         print(f"❌ Порт {port} не запустился за {max_wait} сек")
#         return False
