#!/usr/bin/env python3
"""
MTProto Proxy Checker v2.0
Расширенная версия с множеством источников
"""

import asyncio
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import aiohttp

# ==================== НАСТРОЙКИ ====================
TIMEOUT = 5  # таймаут в секундах
MAX_CONCURRENT = 50  # количество одновременных проверок
SAVE_DEAD = False  # сохранять ли мёртвые прокси

# ==================== ИСТОЧНИКИ ПРОКСИ ====================

# MTProto прокси для Telegram
MTProto_SOURCES = [
    # Основные источники
    "https://raw.githubusercontent.com/SoliSpirit/mtproto/master/all_proxies.txt",
    "https://raw.githubusercontent.com/Grim1313/mtproto-for-telegram/master/all_proxies.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/MTProtoProxy/main/mtproto.txt",
    # Специализированные для РФ (маскировка под Яндекс/VK/Госуслуги)
    "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/proxy_ru.txt",
    "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/proxy_eu.txt",
    "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/proxy_all.txt",
    # Дополнительные источники
    "https://raw.githubusercontent.com/S3nn4/MTProxy/main/proxy.txt",
    "https://raw.githubusercontent.com/maxxbb/MTProxy/master/MTProxyList.txt",
    "https://raw.githubusercontent.com/MrPopin/MTProxy-List/main/proxy.txt",
    "https://raw.githubusercontent.com/JustArion/mtproxy-list/main/proxy.txt",
]

# HTTP/HTTPS прокси
HTTP_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/opsxcq/proxy-list/master/list.txt",
]

# SOCKS4/SOCKS5 прокси
SOCKS_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/main/socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
]

# Shadowsocks/V2Ray конфиги (для справки)
VPN_SOURCES = [
    "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/1.txt",
    "https://raw.githubusercontent.com/itszees/Free-Proxies/main/shadowsocks.txt",
]

# Все источники в одном списке (с метками)
ALL_SOURCES = {
    "mtproto": MTProto_SOURCES,
    "http": HTTP_SOURCES,
    "socks": SOCKS_SOURCES,
}

# ==================== ПАРСИНГ ПРОКСИ ====================


def parse_proxy(line: str, source_type: str = "mtproto") -> Optional[Dict]:
    """
    Парсит строку прокси из разных форматов
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Формат tg://proxy или https://t.me/proxy
    if "proxy?" in line and ("server=" in line or "port=" in line):
        params = {}
        for m in re.finditer(r"[?&](server|port|secret)=([^&]+)", line):
            params[m.group(1)] = m.group(2)

        if "server" in params and "port" in params:
            try:
                port = int(params["port"])
                secret = params.get("secret")
                if secret:
                    secret = secret.replace("%3D", "=").replace("%3d", "=")
                return {
                    "type": "mtproto",
                    "server": params["server"],
                    "port": port,
                    "secret": secret,
                    "source_type": "mtproto",
                }
            except ValueError:
                pass

    # Формат ip:port или ip:port:secret (MTProto)
    if source_type == "mtproto":
        parts = line.split(":")
        if len(parts) >= 2:
            server = parts[0]
            try:
                port = int(parts[1])
                secret = parts[2] if len(parts) > 2 else None
                # Проверяем, что это не HTTP прокси (порт не 80/8080/3128)
                if port not in [80, 8080, 3128, 8000]:
                    return {
                        "type": "mtproto",
                        "server": server,
                        "port": port,
                        "secret": secret,
                        "source_type": "mtproto",
                    }
            except ValueError:
                pass

    # Формат ip:port (HTTP/SOCKS)
    if source_type in ["http", "socks"]:
        parts = line.split(":")
        if len(parts) == 2:
            server = parts[0]
            try:
                port = int(parts[1])
                return {
                    "type": source_type,
                    "server": server,
                    "port": port,
                    "secret": None,
                    "source_type": source_type,
                }
            except ValueError:
                pass

    return None


async def fetch_proxies(
    session: aiohttp.ClientSession, url: str, source_type: str
) -> List[Dict]:
    """
    Скачивает прокси из указанного URL
    """
    try:
        async with session.get(url, timeout=15) as response:
            if response.status == 200:
                text = await response.text()
                proxies = []
                for line in text.split("\n"):
                    proxy = parse_proxy(line, source_type)
                    if proxy:
                        proxies.append(proxy)

                # Определяем имя файла для вывода
                filename = url.split("/")[-1] if "/" in url else url[:30]
                print(f"  ✅ {source_type.upper()} | {filename}: {len(proxies)} прокси")
                return proxies
            else:
                print(
                    f"  ⚠️ {source_type.upper()} | {url.split('/')[-1]}: статус {response.status}"
                )
                return []
    except asyncio.TimeoutError:
        print(f"  ⏰ {source_type.upper()} | {url.split('/')[-1]}: таймаут")
        return []
    except Exception as e:
        print(f"  ❌ {source_type.upper()} | {url.split('/')[-1]}: {str(e)[:40]}")
        return []


async def fetch_all_proxies() -> List[Dict]:
    """
    Скачивает прокси из всех источников
    """
    print("\n📥 ЗАГРУЗКА ПРОКСИ ИЗ ИСТОЧНИКОВ")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for source_type, urls in ALL_SOURCES.items():
            for url in urls:
                tasks.append(fetch_proxies(session, url, source_type))

        results = await asyncio.gather(*tasks)

    # Объединяем все прокси
    all_proxies = []
    for proxies in results:
        all_proxies.extend(proxies)

    # Удаляем дубликаты (по server:port)
    seen = set()
    unique_proxies = []
    for p in all_proxies:
        key = f"{p['server']}:{p['port']}"
        if key not in seen:
            seen.add(key)
            unique_proxies.append(p)

    # Статистика по типам
    stats = defaultdict(int)
    for p in unique_proxies:
        stats[p["type"]] += 1

    print("\n" + "=" * 60)
    print(f"📊 СТАТИСТИКА ЗАГРУЗКИ")
    print(f"   Всего уникальных: {len(unique_proxies)}")
    for t, count in stats.items():
        print(f"   {t.upper()}: {count}")
    print("=" * 60)

    return unique_proxies


# ==================== ПРОВЕРКА ПРОКСИ ====================


async def check_proxy_simple(proxy: Dict) -> Dict:
    """
    Проверяет прокси через TCP-соединение
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(proxy["server"], proxy["port"]), timeout=TIMEOUT
        )
        writer.close()
        await writer.wait_closed()
        return {"proxy": proxy, "status": "alive", "latency": TIMEOUT}
    except:
        return {"proxy": proxy, "status": "dead", "latency": None}


async def check_proxies_parallel(proxies: List[Dict]) -> tuple[List[Dict], List[Dict]]:
    """
    Параллельная проверка всех прокси
    """
    print(f"\n🔍 ПРОВЕРКА {len(proxies)} ПРОКСИ (таймаут {TIMEOUT} сек)...")
    start_time = time.time()

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def check_with_limit(proxy):
        async with semaphore:
            return await check_proxy_simple(proxy)

    tasks = [check_with_limit(proxy) for proxy in proxies]
    results = await asyncio.gather(*tasks)

    elapsed = time.time() - start_time

    alive = [r for r in results if r["status"] == "alive"]
    dead = [r for r in results if r["status"] == "dead"]

    print(f"\n📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ")
    print(f"   ✅ Живые: {len(alive)}")
    print(f"   ❌ Мёртвые: {len(dead)}")
    print(f"   ⏱️  Время: {elapsed:.2f} сек")
    print("=" * 60)

    return alive, dead


# ==================== СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ====================


def save_proxies(proxies: List[Dict], source_type: str = None):
    """
    Сохраняет прокси в файлы
    """
    if not proxies:
        return

    # Фильтруем по типу если нужно
    mtproto = [p for p in proxies if p.get("type") == "mtproto"]
    http = [p for p in proxies if p.get("type") == "http"]
    socks = [p for p in proxies if p.get("type") == "socks"]

    # Формат tg:// для Telegram
    if mtproto:
        with open("alive_proxies_tg.txt", "w") as f:
            for p in mtproto:
                if p.get("secret"):
                    f.write(
                        f"tg://proxy?server={p['server']}&port={p['port']}&secret={p['secret']}\n"
                    )
                else:
                    f.write(f"tg://proxy?server={p['server']}&port={p['port']}\n")
        print(f"💾 alive_proxies_tg.txt — {len(mtproto)} MTProto прокси")

    # Простой формат ip:port[:secret]
    with open("alive_proxies_simple.txt", "w") as f:
        for p in proxies:
            if p.get("secret"):
                f.write(f"{p['server']}:{p['port']}:{p['secret']}\n")
            else:
                f.write(f"{p['server']}:{p['port']}\n")
    print(f"💾 alive_proxies_simple.txt — {len(proxies)} прокси (все типы)")

    # HTTP прокси отдельно
    if http:
        with open("alive_proxies_http.txt", "w") as f:
            for p in http:
                f.write(f"{p['server']}:{p['port']}\n")
        print(f"💾 alive_proxies_http.txt — {len(http)} HTTP прокси")

    # SOCKS прокси отдельно
    if socks:
        with open("alive_proxies_socks.txt", "w") as f:
            for p in socks:
                f.write(f"{p['server']}:{p['port']}\n")
        print(f"💾 alive_proxies_socks.txt — {len(socks)} SOCKS прокси")


# ==================== ГЛАВНАЯ ФУНКЦИЯ ====================


async def main():
    print("=" * 60)
    print(f"🔄 MTProto Proxy Checker v2.0")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Таймаут: {TIMEOUT} сек")
    print(f"🚀 Макс. параллельных проверок: {MAX_CONCURRENT}")

    # Подсчёт источников
    total_sources = sum(len(urls) for urls in ALL_SOURCES.values())
    print(f"📡 Источников: {total_sources}")
    print("=" * 60)

    # Шаг 1: Загружаем прокси
    all_proxies = await fetch_all_proxies()

    if not all_proxies:
        print("❌ Не найдено ни одного прокси!")
        print("\n💡 Возможные причины:")
        print("   - Нет интернета")
        print("   - GitHub временно недоступен")
        return

    # Шаг 2: Проверяем прокси
    alive, dead = await check_proxies_parallel(all_proxies)

    # Шаг 3: Сохраняем результаты
    if alive:
        print("\n💾 СОХРАНЕНИЕ РЕЗУЛЬТАТОВ")
        print("-" * 40)
        save_proxies([p["proxy"] for p in alive])

        # Выводим примеры
        print("\n📋 ПРИМЕРЫ ЖИВЫХ ПРОКСИ (первые 5):")
        for i, item in enumerate(alive[:5]):
            p = item["proxy"]
            print(f"   {i+1}. {p['type'].upper()} | {p['server']}:{p['port']}")
    else:
        print("\n❌ Нет живых прокси!")
        print("💡 Попробуйте:")
        print("   - Увеличить TIMEOUT (например, до 10 секунд)")
        print("   - Запустить позже (списки обновляются каждые 4-12 часов)")

    print("\n" + "=" * 60)
    print("✅ Готово!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Прервано пользователем")
        sys.exit(0)
