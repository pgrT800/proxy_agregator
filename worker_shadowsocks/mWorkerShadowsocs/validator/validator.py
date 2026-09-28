import asyncio
import random
import subprocess

import aiohttp
from aiohttp_socks import ProxyConnectionError, ProxyConnector

from core.custom_widget import register_task, update_task
from core.TaskRegisterMainInit.TaskRegister import taskregister
from core.tui_global_set import write_top


class ValidatorShadowsocks:
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
            method = proxy_dict.get("method", "")
            password = proxy_dict.get("password", "")

            if password and method:
                return await self._validate_via_sslocal(host, port, method, password)
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

        # Запускаем все проверки параллельно
        tasks = [
            asyncio.create_task(check_service(name, url)) for name, url in self.services
        ]
        done, pending = await asyncio.wait(tasks)

        for task in done:
            name, status = task.result()
            results[name] = status

        results["host"] = host
        results["port"] = port
        results["type"] = "direct"
        results["proxy_url"] = proxy_url
        return results

    async def _validate_via_sslocal(
        self, host: str, port: int, method: str, password: str
    ) -> dict:
        local_port = random.randint(10000, 60000)
        process = None
        results = {}

        try:
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

            await asyncio.sleep(random.uniform(0.01, 0.5))
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            if not await self._wait_for_port(local_port):
                return self._empty_result(host, port, method, password)

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

            # Запускаем все проверки параллельно
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
            results["method"] = method
            results["password"] = password
            results["type"] = "ss"
            results["proxy_url"] = f"socks5://{host}:{port}"
            return results

        except Exception:
            return self._empty_result(host, port, method, password)
        finally:
            if process and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except:
                    process.kill()

    def _empty_result(
        self, host: str, port: int, method: str = "", password: str = ""
    ) -> dict:
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
            "method": method,
            "password": password,
            "type": "ss",
            "proxy_url": f"socks5://{host}:{port}",
        }

    async def _wait_for_port(self, port: int, max_wait: int = 2) -> bool:
        """Ждёт, пока порт начнёт слушать"""
        for i in range(max_wait):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", port), timeout=2
                )
                writer.close()
                print(f"✅ Порт {port} запустился за {i+1} сек")
                return True
            except asyncio.CancelledError:
                print(f"🛑 Порт {port}: ожидание отменено")
                raise
            except:
                await asyncio.sleep(1)
        print(f"❌ Порт {port} не запустился за {max_wait} сек")
        return False
