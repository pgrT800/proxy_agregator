import asyncio
import json
import os
import random
import subprocess
import tempfile

import aiohttp
from aiohttp_socks import ProxyConnector

from core.TaskRegisterMainInit.TaskRegister import taskregister


class ValidatorVless:
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
        """Проверяет VLESS прокси через XRay"""
        async with semaphore:
            host = proxy_dict["host"]
            port = proxy_dict["port"]
            uuid = proxy_dict.get("uuid", "")

            if not uuid:
                return await self._validate_via_direct(host, port)

            return await self._validate_via_xray(proxy_dict)

    async def _validate_via_direct(self, host: str, port: int) -> dict:
        """Проверяет как обычный SOCKS5 прокси"""
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
                return (name, False)

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

    async def _validate_via_xray(self, proxy_dict: dict) -> dict:
        """Запускает XRay и проверяет все сервисы параллельно"""
        local_port = random.randint(10000, 60000)
        host = proxy_dict["host"]
        port = proxy_dict["port"]
        uuid = proxy_dict["uuid"]

        config = {
            "log": {"loglevel": "warning"},
            "inbounds": [
                {
                    "port": local_port,
                    "protocol": "socks",
                    "settings": {"udp": True},
                    "tag": "socks-inbound",
                }
            ],
            "outbounds": [
                {
                    "protocol": "vless",
                    "settings": {
                        "vnext": [
                            {
                                "address": host,
                                "port": port,
                                "users": [{"id": uuid, "encryption": "none"}],
                            }
                        ]
                    },
                    "streamSettings": self._build_stream_settings(proxy_dict),
                    "tag": "proxy",
                }
            ],
        }

        if proxy_dict.get("security") == "reality":
            config["outbounds"][0]["streamSettings"]["realitySettings"] = {
                "serverName": proxy_dict.get("sni", host),
                "fingerprint": proxy_dict.get("fingerprint", "chrome"),
                "publicKey": proxy_dict.get("pbk", ""),
                "shortId": proxy_dict.get("sid", ""),
            }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            config_path = f.name

        process = None
        results = {}

        try:
            cmd = ["xray", "run", "-c", config_path]

            await asyncio.sleep(random.uniform(0.01, 0.5))
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            if not await self._wait_for_port(local_port):
                return self._empty_result(host, port, uuid)

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
            results["uuid"] = uuid
            results["type"] = "vless"
            results["proxy_url"] = f"socks5://{host}:{port}"
            return results

        except FileNotFoundError:
            print("❌ xray не установлен! Установи: sudo pacman -S xray")
            return self._empty_result(host, port, uuid)
        except Exception as e:
            print(f"❌ Ошибка VLESS валидации: {e}")
            return self._empty_result(host, port, uuid)
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

    def _build_stream_settings(self, proxy_dict: dict) -> dict:
        """Строит streamSettings для XRay"""
        security = proxy_dict.get("security", "tls")
        settings = {"network": proxy_dict.get("type_protocol", "tcp")}

        if settings["network"] == "ws":
            settings["wsSettings"] = {}
            if proxy_dict.get("path"):
                settings["wsSettings"]["path"] = proxy_dict["path"]
            if proxy_dict.get("host_header"):
                settings["wsSettings"]["headers"] = {"Host": proxy_dict["host_header"]}

        if security == "tls":
            settings["security"] = "tls"
            settings["tlsSettings"] = {
                "serverName": proxy_dict.get("sni", proxy_dict["host"]),
                "allowInsecure": True,
            }
        elif security == "reality":
            settings["security"] = "reality"

        return settings

    def _empty_result(self, host: str, port: int, uuid: str = "") -> dict:
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
            "uuid": uuid,
            "type": "vless",
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
