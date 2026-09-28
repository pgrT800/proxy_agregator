import asyncio
import random
import subprocess

import aiohttp
from aiohttp_socks import ProxyConnectionError, ProxyConnector

from core.custom_widget import register_task, update_task
from core.tui_global_set import write_top


class CheckerShadowsocks:
    def __init__(self, timeout: int = 8):
        self.timeout = timeout
        self._processes = []

    async def checker(self, proxy_dict: dict, semaphore, task_id: str = None):
        """Обёртка для потоковой обработки"""
        try:
            result = await self.check_proxy(proxy_dict, semaphore, task_id)
            return (proxy_dict, result)
        except Exception as e:
            # write_top(f"❌ Ошибка проверки {proxy_dict.get('host')}:{proxy_dict.get('port')} - {e}")
            return (proxy_dict, False)

    async def check_proxy(
        self, proxy_dict: dict, semaphore, task_id: str = None
    ) -> bool:
        host = proxy_dict.get("host")
        port = proxy_dict.get("port")

        if not host or not port:
            return False

        method = proxy_dict.get("method", "aes-256-gcm")
        password = proxy_dict.get("password", "")

        async with semaphore:
            if not password:
                result = await self._tcp_check(host, port)
            else:
                result = await self._full_check(host, port, method, password)

            # if task_id and result:
            # update_task(task_id, add=1)

            return result

    async def _tcp_check(self, host: str, port: int) -> bool:
        try:

            await asyncio.sleep(random.uniform(0.01, 0.5))
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=self.timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return False
        except Exception:
            return False

    async def _full_check(
        self, host: str, port: int, method: str, password: str
    ) -> bool:
        local_port = random.randint(10000, 60000)

        process = None
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
            self._processes.append(process)

            if not await self._wait_for_port(local_port, max_wait=5):
                return False

            result = await self._check_via_socks(local_port)
            return result

        except FileNotFoundError:
            # write_top("❌ sslocal не установлен. Установите shadowsocks-libev")
            return False
        except Exception as e:
            # write_top(f"❌ Ошибка full_check {host}:{port} - {type(e).__name__}")
            return False
        finally:
            if process and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except (asyncio.TimeoutError, ProcessLookupError):
                    process.kill()
            if process in self._processes:
                self._processes.remove(process)

    async def _wait_for_port(self, port: int, max_wait: int = 5) -> bool:
        for _ in range(max_wait):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", port), timeout=1
                )
                writer.close()
                return True
            except (ConnectionRefusedError, asyncio.TimeoutError):
                await asyncio.sleep(1)
        return False

    async def _check_via_socks(self, local_port: int) -> bool:
        test_urls = ["http://httpbin.org/ip", "http://ip-api.com/json"]

        connector = None
        session = None
        try:
            connector = ProxyConnector.from_url(f"socks5://127.0.0.1:{local_port}")
            session = aiohttp.ClientSession(connector=connector)

            for test_url in test_urls:
                try:
                    async with session.get(
                        test_url, timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as resp:
                        if resp.status == 200:
                            return True
                except:
                    continue
            return False
        except:
            return False
        finally:
            if session:
                await session.close()
            if connector:
                await connector.close()

    async def cleanup(self):
        for process in self._processes[:]:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except (asyncio.TimeoutError, ProcessLookupError):
                    process.kill()
        self._processes.clear()
