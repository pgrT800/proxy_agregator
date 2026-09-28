import asyncio
import json
import os
import random
import re
import subprocess
import sys
import threading
import time

import aiohttp

# ============================================
# 1. Расширенные источники прокси
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
    "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/http.txt",
    "https://raw.githubusercontent.com/GoekhanDev/free-proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/opsxcq/proxy-list/master/list.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
]

SOCKS5_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
    "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/socks5.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/GoekhanDev/free-proxy-list/main/socks5.txt",
    "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/socks5.txt",
]

API_GEOLOCATION = "http://ip-api.com/json/{}"
FINAL_CHECK_URL = "http://httpbin.org/ip"


# ============================================
# 2. Сбор прокси
# ============================================


async def fetch_proxies(session, sources, label):
    all_proxies = set()
    for source in sources:
        try:
            async with session.get(
                source, timeout=aiohttp.ClientTimeout(total=15)
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
# 3. Подробная проверка прокси
# ============================================


async def check_proxy_detailed(session, proxy, semaphore):
    result = {
        "proxy": proxy,
        "alive": False,
        "real_ip": None,
        "response_time": 9999,
        "anonymity": "Unknown",
        "country": None,
        "city": None,
        "isp": None,
        "asn": None,
        "type": "Unknown",
        "static": True,
        "protocol": "HTTP",
    }
    async with semaphore:
        try:
            proxy_url = f"http://{proxy}"
            start = time.monotonic()
            async with session.get(
                FINAL_CHECK_URL, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    return result
                data = await resp.json()
                result["alive"] = True
                result["real_ip"] = data.get("origin", "").split(",")[0].strip()
                result["response_time"] = round((time.monotonic() - start) * 1000, 1)
                headers = {k.lower(): v for k, v in resp.headers.items()}
                if "x-forwarded-for" in headers or "via" in headers:
                    result["anonymity"] = "Transparent"
                elif "proxy-connection" in headers or "proxy-agent" in headers:
                    result["anonymity"] = "Anonymous"
                else:
                    result["anonymity"] = "Elite"
            if result["real_ip"]:
                try:
                    async with session.get(
                        API_GEOLOCATION.format(result["real_ip"]),
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as geo_resp:
                        geo_data = await geo_resp.json()
                        if geo_data.get("status") == "success":
                            result["country"] = geo_data.get("country")
                            result["city"] = geo_data.get("city")
                            result["isp"] = geo_data.get("isp")
                            result["asn"] = (
                                geo_data.get("as", "").split()[0]
                                if geo_data.get("as")
                                else None
                            )
                            isp_lower = (
                                geo_data.get("isp", "") + " " + geo_data.get("org", "")
                            ).lower()
                            mobile_kw = [
                                "mobile",
                                "cellular",
                                "3g",
                                "4g",
                                "5g",
                                "lte",
                                "gsm",
                            ]
                            hosting_kw = [
                                "hosting",
                                "cloud",
                                "vps",
                                "server",
                                "datacenter",
                                "digitalocean",
                                "hetzner",
                                "vultr",
                                "linode",
                                "ovh",
                                "aws",
                                "azure",
                                "google cloud",
                            ]
                            if any(kw in isp_lower for kw in mobile_kw):
                                result["type"] = "Mobile"
                            elif any(kw in isp_lower for kw in hosting_kw):
                                result["type"] = "Datacenter"
                            else:
                                result["type"] = "Residential"
                except:
                    pass
            await asyncio.sleep(0.5)
            try:
                async with session.get(
                    FINAL_CHECK_URL,
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp2:
                    if resp2.status == 200:
                        data2 = await resp2.json()
                        ip2 = data2.get("origin", "").split(",")[0].strip()
                        result["static"] = ip2 == result["real_ip"]
            except:
                result["static"] = True
            rot_icon = "🔒 Static" if result["static"] else "🔄 Rotating"
            print(
                f"  ✅ {proxy} | {result['response_time']}ms | {result['anonymity']} | {result.get('type', '?')} | {result.get('country', '?')} | {rot_icon}"
            )
        except:
            pass
    return result


# ============================================
# 4. Массовая проверка
# ============================================


async def filter_proxies_ultra(all_proxies, max_workers=200):
    semaphore = asyncio.Semaphore(max_workers)
    connector = aiohttp.TCPConnector(limit=max_workers, force_close=True)
    print(f"\n🔍 Проверяю {len(all_proxies)} прокси (потоков: {max_workers})...")
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_proxy_detailed(session, p, semaphore) for p in all_proxies]
        results = await asyncio.gather(*tasks)
    working = [r for r in results if r.get("alive")]
    if working:
        elite = sum(1 for r in working if r.get("anonymity") == "Elite")
        static = sum(1 for r in working if r.get("static"))
        datacenter = sum(1 for r in working if r.get("type") == "Datacenter")
        residential = sum(1 for r in working if r.get("type") == "Residential")
        mobile = sum(1 for r in working if r.get("type") == "Mobile")
        avg_ping = round(
            sum(r.get("response_time", 0) for r in working) / len(working), 1
        )
        print(f"\n{'='*50}")
        print(f"📊 СТАТИСТИКА")
        print(f"   Всего проверено: {len(all_proxies)}")
        print(f"   Живых: {len(working)}")
        print(f"   Средний пинг: {avg_ping}ms")
        print(f"   Elite: {elite} | Anonymous: {len(working) - elite}")
        print(f"   Static: {static} | Rotating: {len(working) - static}")
        print(
            f"   Datacenter: {datacenter} | Residential: {residential} | Mobile: {mobile}"
        )
        print(f"{'='*50}")
        with open("proxy_details.json", "w") as f:
            json.dump(working, f, indent=2, ensure_ascii=False)
        print(f"💾 Подробная информация сохранена в proxy_details.json")
    return working


# ============================================
# 5. Запуск Docker-контейнера mubeng
# ============================================


def start_mubeng_docker(proxy_file="live_proxies.txt", port=9000):
    """Запустить mubeng в Docker с выводом логов"""

    # Получаем абсолютный путь к файлу
    abs_path = os.path.abspath(proxy_file)

    print(f"\n{'='*50}")
    print(f"🐳 Запускаю mubeng в Docker на порту {port}")
    print(f"   Файл прокси: {abs_path}")
    print(f"   Тест: curl -x http://localhost:{port} http://httpbin.org/ip")
    print(f"   Браузер: chromium --proxy-server='http://localhost:{port}'")
    print(f"{'='*50}\n")

    # Удаляем старый контейнер, если есть
    subprocess.run(
        ["docker", "rm", "-f", "mubeng"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Запускаем новый контейнер
    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        "mubeng",
        "--network",
        "host",
        "-v",
        f"{abs_path}:/live_proxies.txt:ro",
        "ghcr.io/mubeng/mubeng:latest",
        "-a",
        f":{port}",
        "-f",
        "/live_proxies.txt",
        "-r",
        "1",
        "-m",
        "random",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        container_id = result.stdout.strip()
        print(f"✅ Контейнер запущен: {container_id[:12]}")

        # Запускаем вывод логов в отдельном потоке
        def show_logs():
            log_cmd = ["docker", "logs", "-f", "mubeng"]
            process = subprocess.Popen(
                log_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in process.stdout:
                print(f"  📋 {line.rstrip()}")

        log_thread = threading.Thread(target=show_logs, daemon=True)
        log_thread.start()

        return container_id
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска Docker: {e.stderr}")
        return None
    except FileNotFoundError:
        print("❌ Docker не установлен или не запущен")
        return None


# ============================================
# 6. Главный поток
# ============================================


async def main():
    print("=" * 50)
    print("📡 СБОР ПРОКСИ ИЗ ОТКРЫТЫХ ИСТОЧНИКОВ")
    print("=" * 50)

    connector = aiohttp.TCPConnector(limit=50)
    async with aiohttp.ClientSession(connector=connector) as session:
        http_proxies = await fetch_proxies(session, HTTP_SOURCES, "HTTP")
        socks_proxies = await fetch_proxies(session, SOCKS5_SOURCES, "SOCKS5")

    all_proxies = list(set(http_proxies + socks_proxies))
    print(f"\n📦 Всего уникальных прокси: {len(all_proxies)}")

    if not all_proxies:
        print("❌ Не удалось собрать ни одного прокси")
        return

    # Проверка
    proxy_details = await filter_proxies_ultra(all_proxies, max_workers=200)

    if not proxy_details:
        print("\n❌ Нет рабочих прокси.")
        return

    # Сохраняем в файл
    with open("live_proxies.txt", "w") as f:
        for d in proxy_details:
            f.write(f"http://{d['proxy']}\n")
    print(f"\n💾 Сохранено {len(proxy_details)} прокси в live_proxies.txt")

    # Запускаем Docker-контейнер с mubeng
    start_mubeng_docker("live_proxies.txt", port=9000)

    print("\n🔄 Сервер работает. Нажми Ctrl+C для остановки.")
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\n🛑 Останавливаю контейнер...")
        subprocess.run(
            ["docker", "rm", "-f", "mubeng"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("✅ Контейнер остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
