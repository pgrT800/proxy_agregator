import json
import asyncio
import redis.asyncio as redis


async def export_proxies_to_file():
    r = await redis.from_url("redis://localhost:6379/1", decode_responses=True)

    all_proxies = []

    # Пройти по всем протоколам и порядкам
    for protocol in ["http", "https", "socks"]:
        key = f"stats:{protocol}"
        data = await r.get(key)
        if data:
            pool = json.loads(data)
            for order in ["5", "4", "3", "2", "1"]:
                for item in pool.get(order, []):
                    proxy_url = item.get("proxy", "")
                    if proxy_url:
                        # Для SOCKS5 меняем http:// на socks5://
                        if protocol == "socks":
                            proxy_url = proxy_url.replace("http://", "socks5://")
                        all_proxies.append(proxy_url)

    # Записать в файл
    with open("live_proxies.txt", "w") as f:
        for proxy in all_proxies:
            f.write(proxy + "\n")

    print(f"✅ Экспортировано {len(all_proxies)} прокси в live_proxies.txt")


asyncio.run(export_proxies_to_file())
