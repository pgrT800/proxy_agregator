#!/usr/bin/env python3
import asyncio
from typing import List, Optional, Tuple

import aiohttp


class ProxyValidator:
    def __init__(self, target_url: str = "http://t.me", timeout: int = 5):
        self.target_url = target_url
        self.timeout = timeout

    async def check_proxy(self, host: str, port: str) -> bool:
        """Проверяет прокси через целевой ресурс"""
        proxy_url = f"http://{host}:{port}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.target_url,
                    proxy=proxy_url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    ssl=False,
                ) as resp:
                    return resp.status in (200, 301, 302, 307, 308)
        except Exception as e:
            # print(f"Ошибка {host}:{port} -> {type(e).__name__}")
            return False

    async def check_batch(
        self, proxies: List[Tuple[str, str]]
    ) -> List[Tuple[str, str, bool]]:
        """Проверяет список прокси параллельно"""
        semaphore = asyncio.Semaphore(50)  # ограничение одновременных проверок

        async def check_one(host, port):
            async with semaphore:
                result = await self.check_proxy(host, port)
                return (host, port, result)

        tasks = [check_one(host, port) for host, port in proxies]
        results = await asyncio.gather(*tasks)
        return results


async def main():
    # Данные прокси (из твоего вывода)
    proxies_data = [
        ("77.76.202.157", "80"),
        ("149.56.12.18", "80"),
        ("216.117.195.93", "80"),
        ("204.57.112.5", "80"),
        ("147.161.210.140", "8800"),
        ("178.212.144.7", "80"),
        ("149.56.35.153", "80"),
        ("20.78.26.206", "8561"),
        ("45.12.151.226", "2829"),
        ("95.213.217.168", "52004"),
        ("185.135.69.34", "80"),
        ("103.125.31.222", "80"),
        ("51.68.124.241", "80"),
        ("13.230.49.39", "8080"),
        ("167.103.31.122", "8800"),
        ("43.200.30.144", "80"),
        ("45.140.147.82", "1082"),
        ("221.132.18.38", "80"),
        ("83.142.126.147", "80"),
        ("180.250.219.58", "53281"),
        ("167.103.144.127", "8800"),
        ("43.252.214.195", "80"),
        ("185.187.92.42", "80"),
        ("43.99.54.236", "5555"),
        ("51.79.135.131", "8080"),
        ("34.96.238.40", "8080"),
        ("191.101.1.116", "80"),
        ("16.163.88.228", "80"),
        ("141.98.153.86", "80"),
        ("160.191.17.64", "8888"),
    ]

    print(f"🔍 Проверка {len(proxies_data)} прокси через {target_url}")
    print("=" * 60)

    validator = ProxyValidator(target_url="http://t.me", timeout=5)
    results = await validator.check_batch(proxies_data)

    alive = []
    dead = []

    for host, port, status in results:
        if status:
            alive.append((host, port))
            print(f"✅ {host}:{port} — ДОСТУПЕН")
        else:
            dead.append((host, port))
            print(f"❌ {host}:{port} — НЕ ДОСТУПЕН")

    print("\n" + "=" * 60)
    print(f"📊 ИТОГО: {len(alive)} живых, {len(dead)} мёртвых")

    # Сохраняем живые прокси
    if alive:
        with open("alive_proxies.txt", "w") as f:
            for host, port in alive:
                f.write(f"{host}:{port}\n")
        print(f"💾 Живые прокси сохранены в alive_proxies.txt")


if __name__ == "__main__":
    target_url = "http://t.me"  # можно заменить на https://t.me, http://httpbin.org/ip
    asyncio.run(main())
