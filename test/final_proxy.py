import asyncio
import json
import re

import aiohttp
from aiohttp import web
from proxy_checker import ProxyChecker

# ============================================
# 1. Источники прокси
# ============================================

HTTP_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
]

SOCKS5_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
]

# API для проверки прокси
API_PROXY_CHECKER = "http://api.proxy-checker.net/api/proxy-checker/"
API_PROXYSCRAPE = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all"
API_PUBPROXY = "http://pubproxy.com/api/proxy?format=json&type=http"


# ============================================
# 2. Сбор прокси
# ============================================


async def fetch_proxies(session, sources, label):
    """Скачать прокси из списка источников"""
    all_proxies = set()

    for source in sources:
        try:
            async with session.get(
                source,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                text = await resp.text()
                lines = text.strip().split("\n")

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3}:\d{1,5})", line)
                    if match:
                        all_proxies.add(match.group(1))

                print(f"  ✅ {source}: +{len(lines)} строк")

        except Exception as e:
            print(f"  ❌ {source}: {str(e)[:60]}")

    print(f"📥 Собрано {len(all_proxies)} уникальных {label}-прокси")
    return list(all_proxies)


# ============================================
# 3. Проверка прокси (4 метода)
# ============================================


def check_via_library(proxy):
    """
    Метод 1: Проверка через библиотеку proxy-checker
    """
    try:
        checker = ProxyChecker()
        result = checker.check_proxy(proxy)

        if result and result.get("status") == "alive":
            print(f"  ✅ [library] {proxy} — жив (country: {result.get('country')})")
            return True
        else:
            print(f"  ❌ [library] {proxy} — мёртв")
            return False
    except Exception as e:
        print(f"  ⚠️ [library] {proxy}: {str(e)[:40]}")
        return False


async def check_via_api_proxy_checker(session, proxy, semaphore):
    """
    Метод 2: Проверка через proxy-checker.net (POST)
    """
    async with semaphore:
        try:
            data = {"proxy_list": proxy}
            async with session.post(
                API_PROXY_CHECKER,
                data=data,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                result = await resp.text()

                if "alive" in result.lower() or "ok" in result.lower():
                    print(f"  ✅ [proxy-checker.net] {proxy} — жив")
                    return True
                else:
                    print(f"  ❌ [proxy-checker.net] {proxy} — мёртв")
                    return False

        except Exception as e:
            print(f"  ⚠️ [proxy-checker.net] {proxy}: {str(e)[:40]}")
            return False


async def fetch_via_proxyscrape(session, semaphore):
    """
    Метод 3: Получить живые прокси через proxyscrape.com
    """
    async with semaphore:
        try:
            async with session.get(
                API_PROXYSCRAPE,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                text = await resp.text()
                proxies = text.strip().split("\r\n")
                proxies = [p.strip() for p in proxies if p.strip()]

                print(f"  ✅ [proxyscrape] Получено {len(proxies)} живых прокси")
                return proxies

        except Exception as e:
            print(f"  ⚠️ [proxyscrape] Ошибка: {str(e)[:60]}")
            return []


async def fetch_via_pubproxy(session, semaphore):
    """
    Метод 4: Получить живые прокси через pubproxy.com
    """
    async with semaphore:
        try:
            async with session.get(
                API_PUBPROXY,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                proxies = []

                for item in data.get("data", []):
                    ip = item.get("ip")
                    port = item.get("port")
                    if ip and port:
                        proxies.append(f"{ip}:{port}")

                print(f"  ✅ [pubproxy] Получено {len(proxies)} живых прокси")
                return proxies

        except Exception as e:
            print(f"  ⚠️ [pubproxy] Ошибка: {str(e)[:60]}")
            return []


# ============================================
# 4. Комплексная фильтрация (все 4 метода)
# ============================================


async def filter_proxies_comprehensive(all_proxies, max_workers=50):
    """
    Проверка прокси через все доступные методы:
    1. Библиотека proxy-checker
    2. API proxy-checker.net
    3. API proxyscrape.com
    4. API pubproxy.com
    """
    semaphore = asyncio.Semaphore(max_workers)
    connector = aiohttp.TCPConnector(limit=max_workers)

    working = set()

    async with aiohttp.ClientSession(connector=connector) as session:
        # Этап 1: Библиотека proxy-checker
        print(f"\n🔍 Этап 1: Проверка через библиотеку proxy-checker...")
        for i, proxy in enumerate(all_proxies[:50]):  # Ограничим 50 для скорости
            if check_via_library(proxy):
                working.add(proxy)
            if (i + 1) % 10 == 0:
                print(f"   Прогресс: {i+1}/{min(50, len(all_proxies))}")

        print(f"   После библиотеки: {len(working)} живых")

        # Этап 2: API proxy-checker.net
        print(f"\n🔍 Этап 2: Проверка через proxy-checker.net...")
        sample = all_proxies[:100]  # Ограничим 100 для скорости

        tasks = [check_via_api_proxy_checker(session, p, semaphore) for p in sample]
        results = await asyncio.gather(*tasks)

        for proxy, is_alive in zip(sample, results):
            if is_alive:
                working.add(proxy)

        print(f"   После proxy-checker.net: {len(working)} живых")

        # Этап 3: proxyscrape.com
        print(f"\n🔍 Этап 3: Получение через proxyscrape.com...")
        for _ in range(3):
            proxies = await fetch_via_proxyscrape(session, asyncio.Semaphore(1))
            working.update(proxies)
            await asyncio.sleep(1)

        print(f"   После proxyscrape.com: {len(working)} живых")

        # Этап 4: pubproxy.com
        print(f"\n🔍 Этап 4: Получение через pubproxy.com...")
        for _ in range(5):
            proxies = await fetch_via_pubproxy(session, asyncio.Semaphore(1))
            working.update(proxies)
            await asyncio.sleep(1)

        print(f"   После pubproxy.com: {len(working)} живых")

    return list(working)


# ============================================
# 5. Прокси-сервер
# ============================================


class SimpleProxyServer:
    def __init__(self, proxies):
        self.proxies = proxies
        self.index = 0

    def get_next_proxy(self):
        if not self.proxies:
            return None
        proxy = self.proxies[self.index % len(self.proxies)]
        self.index += 1
        return proxy

    async def handle(self, request):
        target_url = str(request.url)
        proxy = self.get_next_proxy()

        if not proxy:
            return web.Response(text="Нет доступных прокси", status=502)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    target_url,
                    proxy=f"http://{proxy}",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    body = await resp.read()
                    print(f"✅ {proxy} → {resp.status} | {target_url}")
                    return web.Response(
                        body=body,
                        status=resp.status,
                        headers=dict(resp.headers),
                    )
        except Exception as e:
            print(f"❌ {proxy}: {str(e)[:60]}")

            proxy2 = self.get_next_proxy()
            if proxy2:
                try:
                    async with aiohttp.ClientSession() as s2:
                        async with s2.get(
                            target_url,
                            proxy=f"http://{proxy2}",
                            timeout=aiohttp.ClientTimeout(total=10),
                        ) as r2:
                            body2 = await r2.read()
                            print(f"✅ {proxy2} → {r2.status} (retry)")
                            return web.Response(
                                body=body2,
                                status=r2.status,
                                headers=dict(r2.headers),
                            )
                except Exception:
                    pass

        return web.Response(text="Не удалось выполнить запрос", status=502)

    async def start(self, host="0.0.0.0", port=9000):
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", self.handle)

        print(f"\n{'='*50}")
        print(f"🚀 Прокси-сервер запущен на http://{host}:{port}")
        print(f"   Живых прокси в пуле: {len(self.proxies)}")
        print(f"   Тест: curl -x http://localhost:{port} http://httpbin.org/ip")
        print(f"   Браузер: chromium --proxy-server='http://localhost:{port}'")
        print(f"{'='*50}")

        await web._run_app(app, host=host, port=port)


# ============================================
# 6. Главный поток
# ============================================


async def main():
    print("=" * 50)
    print("📡 СБОР ПРОКСИ ИЗ ОТКРЫТЫХ ИСТОЧНИКОВ")
    print("=" * 50)

    connector = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=connector) as session:
        http_proxies = await fetch_proxies(session, HTTP_SOURCES, "HTTP")
        socks_proxies = await fetch_proxies(session, SOCKS5_SOURCES, "SOCKS5")

    all_proxies = list(set(http_proxies + socks_proxies))
    print(f"\n📦 Всего уникальных прокси: {len(all_proxies)}")

    if not all_proxies:
        print("❌ Не удалось собрать ни одного прокси")
        return

    # Комплексная проверка через все 4 метода
    working = await filter_proxies_comprehensive(all_proxies, max_workers=50)

    if not working:
        print("\n❌ Нет рабочих прокси. Попробуйте позже.")
        return

    # Сохраняем в файл
    with open("live_proxies.txt", "w") as f:
        for p in working:
            f.write(f"http://{p}\n")
    print(f"\n💾 Сохранено {len(working)} прокси в live_proxies.txt")

    # Запускаем сервер
    server = SimpleProxyServer(working)
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
