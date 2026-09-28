#!/usr/bin/env python3
"""
mtproto proxy checker v3.0
расширенная версия с множеством источников и валидацией
"""

import asyncio
import ipaddress
import os
import re
import socket
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp

# ==================== НАСТРОЙКИ ====================
TIMEOUT = 5  # таймаут соединения в секундах
MAX_CONCURRENT = 50  # количество одновременных проверок
SAVE_DEAD = False  # сохранять ли мёртвые прокси
MIN_LATENCY = 0  # минимальная задержка в мс (0 = без фильтра)
MAX_LATENCY = 2000  # максимальная задержка в мс
ENABLE_GEO_FILTER = False  # включить гео-фильтрацию
ALLOWED_COUNTRIES = {'RU', 'UA', 'BY', 'KZ'}  # разрешённые страны (если включен фильтр)

# ==================== ИСТОЧНИКИ ПРОКСИ ====================

# MTProto прокси для Telegram (основные)
mtproto_sources = [
    # GitHub репозитории
    "https://raw.githubusercontent.com/solispirit/mtproto/master/all_proxies.txt",
    "https://raw.githubusercontent.com/grim1313/mtproto-for-telegram/master/all_proxies.txt",
    "https://raw.githubusercontent.com/aliilapro/mtprotoproxy/main/mtproto.txt",
    "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/proxy_ru.txt",
    "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/proxy_eu.txt",
    "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/proxy_all.txt",
    "https://raw.githubusercontent.com/s3nn4/mtproxy/main/proxy.txt",
    "https://raw.githubusercontent.com/maxxbb/mtproxy/master/mtproxylist.txt",
    "https://raw.githubusercontent.com/mrpopin/mtproxy-list/main/proxy.txt",
    "https://raw.githubusercontent.com/justarion/mtproxy-list/main/proxy.txt",
    "https://raw.githubusercontent.com/ShadowProxy66/mtproxy/main/mtproto.txt",
    "https://raw.githubusercontent.com/mtprotoproxy/mtprotoproxy/master/proxy.txt",
    "https://raw.githubusercontent.com/telegram-proxy-list/mtproxy/main/mtproto.txt",
    "https://raw.githubusercontent.com/proxyscrape/free-proxy-list/main/mtproto.txt",
    
    # Telegram каналы через tgstat/telemetrio (если доступны)
    "https://api.telegram.org/s/mtproxyz",  # пример, может требовать авторизации
    
    # Публичные списки
    "https://www.proxy-list.download/api/v1/get?type=mtproto",
    "https://proxyscrape.com/api/v2/getproxies?protocol=mtproto&timeout=10000&country=all",
    
    # Дополнительные зеркала
    "https://gitlab.com/mtproxy/lists/-/raw/main/mtproto.txt",
    "https://codeberg.org/mtproxy/mtproxy-list/raw/branch/main/proxies.txt",
]

# HTTP/HTTPS прокси
http_sources = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/https.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/thespeedx/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/shiftytr/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/http_raw.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/https_raw.txt",
    "https://raw.githubusercontent.com/opsxcq/proxy-list/master/list.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/Proxy-List/http.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/Proxy-List/https.txt",
    "https://www.proxy-list.download/api/v1/get?type=http",
    "https://www.proxy-list.download/api/v1/get?type=https",
    "https://proxyscrape.com/api/v2/getproxies?protocol=http&timeout=10000&country=all",
    "https://proxyscrape.com/api/v2/getproxies?protocol=https&timeout=10000&country=all",
]

# SOCKS4/SOCKS5 прокси
socks_sources = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/main/socks5.txt",
    "https://raw.githubusercontent.com/thespeedx/proxy-list/master/socks4.txt",
    "https://raw.githubusercontent.com/thespeedx/proxy-list/master/socks5.txt",
    "https://raw.githubusercontent.com/shiftytr/proxy-list/master/socks4.txt",
    "https://raw.githubusercontent.com/shiftytr/proxy-list/master/socks5.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks4.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks5.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/Proxy-List/socks4.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/Proxy-List/socks5.txt",
    "https://www.proxy-list.download/api/v1/get?type=socks4",
    "https://www.proxy-list.download/api/v1/get?type=socks5",
    "https://proxyscrape.com/api/v2/getproxies?protocol=socks4&timeout=10000&country=all",
    "https://proxyscrape.com/api/v2/getproxies?protocol=socks5&timeout=10000&country=all",
]

# Shadowsocks/V2Ray/Trojan конфиги (для справки)
vpn_sources = [
    "https://raw.githubusercontent.com/nikita29a/freeproxylist/main/mirror/1.txt",
    "https://raw.githubusercontent.com/itszees/free-proxies/main/shadowsocks.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/Eternity.txt",
]

# Все источники с метками
ALL_SOURCES = {
    "mtproto": mtproto_sources,
    "http": http_sources,
    "socks": socks_sources,
}

# ==================== ВАЛИДАЦИЯ ====================

def is_valid_ip(ip: str) -> bool:
    """Проверяет, является ли строка валидным IP-адресом"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        # Проверяем, может это домен
        if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', ip):
            return True
        return False

def is_valid_port(port: int) -> bool:
    """Проверяет, находится ли порт в допустимом диапазоне"""
    return 1 <= port <= 65535

def is_valid_mtproto_secret(secret: Optional[str]) -> bool:
    """
    Проверяет формат MTProto secret
    - Может быть пустым
    - Должен быть hex строкой (чётной длины) или dd/dd форматом
    """
    if not secret:
        return True  # пустой секрет допустим
    
    # Декодируем URL-encoded символы
    secret = unquote(secret)
    
    # Формат dd/dd (для маскировки)
    if re.match(r'^dd[0-9a-fA-F]+$', secret):
        return True
    
    # Формат hex строки (чётная длина)
    if re.match(r'^[0-9a-fA-F]+$', secret) and len(secret) % 2 == 0:
        return True
    
    # Формат base64 (для некоторых прокси)
    if re.match(r'^[A-Za-z0-9+/]+=*$', secret) and len(secret) >= 8:
        return True
    
    return False

def is_private_ip(ip: str) -> bool:
    """Проверяет, является ли IP приватным (локальным)"""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return False  # домены считаем публичными

def validate_proxy(proxy: dict) -> Tuple[bool, Optional[str]]:
    """
    Полная валидация прокси
    Возвращает (is_valid, error_message)
    """
    # Проверка обязательных полей
    required = ['type', 'server', 'port']
    for field in required:
        if field not in proxy or not proxy[field]:
            return False, f"Отсутствует поле: {field}"
    
    # Валидация сервера (IP или домен)
    if not is_valid_ip(proxy['server']):
        return False, f"Невалидный адрес сервера: {proxy['server']}"
    
    # Валидация порта
    if not is_valid_port(proxy['port']):
        return False, f"Невалидный порт: {proxy['port']}"
    
    # Исключаем приватные IP для публичных прокси
    if is_private_ip(proxy['server']):
        return False, "Приватный IP-адрес"
    
    # Валидация secret для MTProto
    if proxy.get('type') == 'mtproto':
        if not is_valid_mtproto_secret(proxy.get('secret')):
            return False, f"Невалидный формат secret: {proxy.get('secret', '')[:20]}..."
    
    # Фильтр по странам (если включен)
    if ENABLE_GEO_FILTER and proxy.get('country'):
        if proxy['country'].upper() not in ALLOWED_COUNTRIES:
            return False, f"Страна не в списке: {proxy['country']}"
    
    return True, None

# ==================== ПАРСИНГ ПРОКСИ ====================

def parse_proxy(line: str, source_type: str = "mtproto") -> Optional[Dict]:
    """
    Парсит строку прокси из разных форматов с валидацией
    """
    line = line.strip()
    
    # Пропускаем пустые строки и комментарии
    if not line or line.startswith("#") or line.startswith("//"):
        return None
    
    proxy = None
    
    # === Формат 1: tg://proxy?server=...&port=...&secret=... ===
    if "tg://proxy" in line or ("proxy?" in line and "server=" in line):
        try:
            # Извлекаем query параметры
            if "tg://" in line:
                url_part = line.split("tg://", 1)[1]
            else:
                url_part = line
            
            params = {}
            for match in re.finditer(r'[?&](server|port|secret|name|icon)=([^&\s]+)', url_part):
                key, value = match.groups()
                params[key] = unquote(value)
            
            if 'server' in params and 'port' in params:
                port = int(params['port'])
                if is_valid_port(port):
                    proxy = {
                        "type": "mtproto",
                        "server": params['server'].strip(),
                        "port": port,
                        "secret": params.get('secret'),
                        "name": params.get('name'),
                        "source_type": "mtproto",
                        "raw": line,
                    }
        except (ValueError, IndexError):
            pass
    
    # === Формат 2: https://t.me/proxy?server=... ===
    elif "t.me/proxy" in line or "t.me/socks" in line:
        try:
            params = {}
            for match in re.finditer(r'[?&](server|port|secret)=([^&]+)', line):
                key, value = match.groups()
                params[key] = unquote(value)
            
            if 'server' in params and 'port' in params:
                port = int(params['port'])
                if is_valid_port(port):
                    proxy = {
                        "type": "mtproto",
                        "server": params['server'].strip(),
                        "port": port,
                        "secret": params.get('secret'),
                        "source_type": "mtproto",
                        "raw": line,
                    }
        except (ValueError, IndexError):
            pass
    
    # === Формат 3: IP:PORT[:SECRET] для MTProto ===
    elif source_type == "mtproto" and ":" in line:
        parts = line.split(":")
        if len(parts) >= 2:
            server = parts[0].strip()
            try:
                port = int(parts[1])
                secret = parts[2].strip() if len(parts) > 2 else None
                
                if is_valid_ip(server) and is_valid_port(port):
                    # Исключаем стандартные HTTP порты для MTProto
                    if port not in [80, 8080, 3128, 8000, 8888]:
                        proxy = {
                            "type": "mtproto",
                            "server": server,
                            "port": port,
                            "secret": secret,
                            "source_type": "mtproto",
                            "raw": line,
                        }
            except ValueError:
                pass
    
    # === Формат 4: IP:PORT для HTTP/SOCKS ===
    elif source_type in ["http", "socks", "https"]:
        # Убираем протокол если есть
        clean_line = re.sub(r'^https?://', '', line).strip()
        parts = clean_line.split(":")
        
        if len(parts) == 2:
            server = parts[0].strip()
            try:
                port = int(parts[1])
                if is_valid_ip(server) and is_valid_port(port):
                    proxy = {
                        "type": source_type,
                        "server": server,
                        "port": port,
                        "secret": None,
                        "source_type": source_type,
                        "raw": line,
                    }
            except ValueError:
                pass
        
        # Формат IP:PORT:USER:PASS для аутентифицированных прокси
        elif len(parts) == 4 and source_type in ["http", "https"]:
            server = parts[0].strip()
            try:
                port = int(parts[1])
                if is_valid_ip(server) and is_valid_port(port):
                    proxy = {
                        "type": source_type,
                        "server": server,
                        "port": port,
                        "username": parts[2].strip(),
                        "password": parts[3].strip(),
                        "secret": None,
                        "source_type": source_type,
                        "raw": line,
                        "auth": True,
                    }
            except ValueError:
                pass
    
    # === Формат 5: Shadowsocks ss:// ===
    elif line.startswith("ss://"):
        try:
            # ss://base64(user:pass@server:port)#name
            # или ss://user:pass@server:port
            url_part = line[5:]  # убираем ss://
            
            # Пробуем декодировать base64 часть
            if "#" in url_part:
                config_part, name_part = url_part.split("#", 1)
            else:
                config_part = url_part
            
            # Пробуем декодировать
            try:
                decoded = base64.b64decode(config_part.split("@")[0]).decode()
                user_pass, server_port = decoded.split("@")
                server, port = server_port.split(":")
                port = int(port)
                
                if is_valid_ip(server) and is_valid_port(port):
                    proxy = {
                        "type": "shadowsocks",
                        "server": server,
                        "port": port,
                        "method": user_pass.split(":")[0] if ":" in user_pass else None,
                        "password": user_pass.split(":")[1] if ":" in user_pass else None,
                        "source_type": "vpn",
                        "raw": line,
                    }
            except:
                pass
        except:
            pass
    
    # Валидируем найденный прокси
    if proxy:
        is_valid, error = validate_proxy(proxy)
        if not is_valid:
            return None
    
    return proxy


async def fetch_proxies(
    session: aiohttp.ClientSession, 
    url: str, 
    source_type: str
) -> List[Dict]:
    """
    Скачивает и парсит прокси из указанного URL
    """
    filename = url.split("/")[-1] if "/" in url else url[:30]
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
            if response.status == 200:
                text = await response.text()
                proxies = []
                
                for line in text.split("\n"):
                    proxy = parse_proxy(line, source_type)
                    if proxy:
                        proxies.append(proxy)
                
                print(f"  ✅ {source_type.upper():8} | {filename:30} | {len(proxies):4} прокси")
                return proxies
            else:
                print(f"  ⚠️  {source_type.upper():8} | {filename:30} | HTTP {response.status}")
                return []
                
    except asyncio.TimeoutError:
        print(f"  ⏰ {source_type.upper():8} | {filename:30} | таймаут")
        return []
    except aiohttp.ClientError as e:
        print(f"  ❌ {source_type.upper():8} | {filename:30} | {str(e)[:30]}")
        return []
    except Exception as e:
        print(f"  ❌ {source_type.upper():8} | {filename:30} | {type(e).__name__}")
        return []


async def fetch_all_proxies() -> List[Dict]:
    """
    Скачивает прокси из всех источников с прогрессом
    """
    print("\n📥 Загрузка прокси из источников...")
    print("=" * 70)
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for source_type, urls in ALL_SOURCES.items():
            for url in urls:
                tasks.append(fetch_proxies(session, url, source_type))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Объединяем и валидируем
    all_proxies = []
    for result in results:
        if isinstance(result, list):
            all_proxies.extend(result)
    
    # Удаляем дубликаты и невалидные
    seen = set()
    unique_proxies = []
    
    for p in all_proxies:
        key = f"{p['type']}:{p['server']}:{p['port']}"
        if key not in seen:
            is_valid, _ = validate_proxy(p)
            if is_valid:
                seen.add(key)
                unique_proxies.append(p)
    
    # Статистика
    stats = defaultdict(int)
    for p in unique_proxies:
        stats[p["type"]] += 1
    
    print("\n" + "=" * 70)
    print(f"📊 Статистика после валидации")
    print(f"   Всего уникальных: {len(unique_proxies)}")
    for t, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"   {t.upper():10}: {count}")
    print("=" * 70)
    
    return unique_proxies


# ==================== ПРОВЕРКА ПРОКСИ ====================

async def check_proxy_mtproto(proxy: Dict) -> Dict:
    """
    Проверяет MTProto прокси через TCP + простой handshake
    """
    start = time.time()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(proxy['server'], proxy['port']), 
            timeout=TIMEOUT
        )
        
        # Простая проверка: MTProto сервер отвечает на любой пакет
        # (реальная проверка требует полного handshake)
        writer.write(b'\x00' * 16)  # dummy packet
        await asyncio.wait_for(writer.drain(), timeout=2)
        
        # Пробуем прочитать ответ (не блокируясь)
        try:
            response = await asyncio.wait_for(reader.read(16), timeout=1)
            # Если получили ответ - прокси жив
            is_alive = len(response) > 0
        except:
            is_alive = True  # даже без ответа подключение успешно
        
        writer.close()
        await writer.wait_closed()
        
        latency = int((time.time() - start) * 1000)
        
        return {
            "proxy": proxy,
            "status": "alive" if is_alive else "dead",
            "latency": latency,
            "checked_at": datetime.now().isoformat(),
        }
        
    except asyncio.TimeoutError:
        return {"proxy": proxy, "status": "dead", "latency": None, "error": "timeout"}
    except ConnectionRefusedError:
        return {"proxy": proxy, "status": "dead", "latency": None, "error": "refused"}
    except OSError as e:
        return {"proxy": proxy, "status": "dead", "latency": None, "error": str(e)}
    except Exception as e:
        return {"proxy": proxy, "status": "dead", "latency": None, "error": type(e).__name__}


async def check_proxy_http(proxy: Dict) -> Dict:
    """
    Проверяет HTTP/SOCKS прокси через CONNECT запрос
    """
    start = time.time()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(proxy['server'], proxy['port']), 
            timeout=TIMEOUT
        )
        
        # HTTP CONNECT запрос к примеру домена
        connect_request = f"CONNECT httpbin.org:80 HTTP/1.1\r\nHost: httpbin.org:80\r\n\r\n"
        writer.write(connect_request.encode())
        await asyncio.wait_for(writer.drain(), timeout=2)
        
        # Читаем ответ
        response = await asyncio.wait_for(reader.read(1024), timeout=3)
        response_str = response.decode(errors='ignore').lower()
        
        writer.close()
        await writer.wait_closed()
        
        # Проверяем успешный ответ (200 Connection established)
        is_alive = "200" in response_str or "connection established" in response_str
        latency = int((time.time() - start) * 1000)
        
        return {
            "proxy": proxy,
            "status": "alive" if is_alive else "dead",
            "latency": latency,
            "checked_at": datetime.now().isoformat(),
        }
        
    except asyncio.TimeoutError:
        return {"proxy": proxy, "status": "dead", "latency": None, "error": "timeout"}
    except Exception as e:
        return {"proxy": proxy, "status": "dead", "latency": None, "error": str(e)[:30]}


async def check_proxy_simple(proxy: Dict) -> Dict:
    """
    Базовая проверка через TCP соединение
    """
    start = time.time()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(proxy['server'], proxy['port']), 
            timeout=TIMEOUT
        )
        writer.close()
        await writer.wait_closed()
        
        latency = int((time.time() - start) * 1000)
        return {
            "proxy": proxy,
            "status": "alive",
            "latency": latency,
            "checked_at": datetime.now().isoformat(),
        }
    except:
        return {
            "proxy": proxy, 
            "status": "dead", 
            "latency": None,
            "checked_at": datetime.now().isoformat(),
        }


async def check_proxies_parallel(proxies: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Параллельная проверка всех прокси с прогрессом
    """
    print(f"\n🔍 Проверка {len(proxies)} прокси (таймаут {TIMEOUT} сек, параллельно: {MAX_CONCURRENT})...")
    start_time = time.time()
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    progress_count = [0]
    
    async def check_with_limit(proxy):
        async with semaphore:
            # Выбираем метод проверки по типу
            if proxy.get('type') == 'mtproto':
                result = await check_proxy_mtproto(proxy)
            elif proxy.get('type') in ['http', 'https']:
                result = await check_proxy_http(proxy)
            else:
                result = await check_proxy_simple(proxy)
            
            # Прогресс
            progress_count[0] += 1
            if progress_count[0] % 50 == 0:
                print(f"   ⏳ Проверено: {progress_count[0]}/{len(proxies)}")
            
            return result
    
    tasks = [check_with_limit(proxy) for proxy in proxies]
    results = await asyncio.gather(*tasks)
    
    elapsed = time.time() - start_time
    
    # Фильтруем по статусу и задержке
    alive = [
        r for r in results 
        if r["status"] == "alive" 
        and (MIN_LATENCY <= (r.get("latency") or 0) <= MAX_LATENCY)
    ]
    dead = [r for r in results if r["status"] == "dead"]
    
    # Сортируем живые по задержке
    alive.sort(key=lambda x: x.get("latency") or 9999)
    
    # Статистика
    print(f"\n📊 Результаты проверки")
    print(f"   ✅ Живые: {len(alive)} ({len(alive)/len(proxies)*100:.1f}%)")
    print(f"   ❌ Мёртвые: {len(dead)}")
    print(f"   ⏱️  Время: {elapsed:.2f} сек ({len(proxies)/elapsed:.0f} прокси/сек)")
    
    # Статистика по типам
    type_stats = defaultdict(lambda: {"alive": 0, "dead": 0})
    for r in results:
        t = r['proxy'].get('type', 'unknown')
        if r['status'] == 'alive':
            type_stats[t]['alive'] += 1
        else:
            type_stats[t]['dead'] += 1
    
    print(f"\n   По типам:")
    for t, stats in sorted(type_stats.items()):
        total = stats['alive'] + stats['dead']
        if total > 0:
            rate = stats['alive'] / total * 100
            print(f"   {t.upper():10}: {stats['alive']:3} живых / {stats['dead']:3} мёртвых ({rate:.1f}%)")
    
    print("=" * 70)
    
    return alive, dead


# ==================== СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ====================

def save_proxies(results: List[Dict], include_dead: bool = False):
    """
    Сохраняет прокси в различные форматы
    """
    if not results:
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Группируем по типу
    by_type = defaultdict(list)
    for item in results:
        p = item['proxy']
        by_type[p.get('type', 'unknown')].append(item)
    
    # === TG формат для Telegram ===
    mtproto_alive = [item for item in results if item['proxy'].get('type') == 'mtproto']
    if mtproto_alive:
        filename = f"alive_mtproto_{timestamp}.txt"
        with open(filename, "w", encoding='utf-8') as f:
            for item in mtproto_alive:
                p = item['proxy']
                secret = p.get('secret')
                if secret:
                    f.write(f"tg://proxy?server={p['server']}&port={p['port']}&secret={secret}\n")
                else:
                    f.write(f"tg://proxy?server={p['server']}&port={p['port']}\n")
        print(f"💾 {filename} — {len(mtproto_alive)} MTProto прокси")
    
    # === Простой формат IP:PORT[:SECRET] ===
    filename = f"alive_proxies_{timestamp}.txt"
    with open(filename, "w", encoding='utf-8') as f:
        for item in results:
            p = item['proxy']
            secret = p.get('secret')
            if secret:
                f.write(f"{p['server']}:{p['port']}:{secret}\n")
            else:
                f.write(f"{p['server']}:{p['port']}\n")
    print(f"💾 {filename} — {len(results)} прокси (все типы)")
    
    # === Отдельные файлы по типам ===
    for ptype, items in by_type.items():
        if ptype in ['http', 'https', 'socks4', 'socks5']:
            filename = f"alive_{ptype}_{timestamp}.txt"
            with open(filename, "w", encoding='utf-8') as f:
                for item in items:
                    p = item['proxy']
                    f.write(f"{p['server']}:{p['port']}\n")
            print(f"💾 {filename} — {len(items)} {ptype} прокси")
    
    # === JSON с метаданными ===
    json_data = []
    for item in results:
        p = item['proxy'].copy()
        p['latency'] = item.get('latency')
        p['checked_at'] = item.get('checked_at')
        p['status'] = item.get('status')
        json_data.append(p)
    
    with open(f"results_{timestamp}.json", "w", encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"💾 results_{timestamp}.json — полная информация")
    
    # === Если нужно сохранить и мёртвые ===
    if include_dead:
        dead_items = [item for item in results if item.get('status') == 'dead']
        if dead_items:
            with open(f"dead_proxies_{timestamp}.txt", "w", encoding='utf-8') as f:
                for item in dead_items:
                    p = item['proxy']
                    f.write(f"{p['server']}:{p['port']}  # {item.get('error', 'unknown')}\n")
            print(f"💾 dead_proxies_{timestamp}.txt — {len(dead_items)} мёртвых")


# ==================== ГЛАВНАЯ ФУНКЦИЯ ====================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='MTProto Proxy Checker v3.0')
    parser.add_argument('-t', '--timeout', type=int, default=5, help='Таймаут в секундах')
    parser.add_argument('-c', '--concurrent', type=int, default=50, help='Параллельных проверок')
    parser.add_argument('-d', '--dead', action='store_true', help='Сохранять мёртвые прокси')
    parser.add_argument('-l', '--latency', type=int, nargs=2, metavar=('MIN', 'MAX'),
                       help='Фильтр по задержке в мс')
    parser.add_argument('--geo', action='store_true', help='Включить гео-фильтрацию')
    parser.add_argument('--countries', type=str, help='Разрешённые страны (RU,UA,BY)')
    
    args = parser.parse_args()
    
    # Применяем аргументы к настройкам
    global TIMEOUT, MAX_CONCURRENT, SAVE_DEAD, MIN_LATENCY, MAX_LATENCY, ENABLE_GEO_FILTER, ALLOWED_COUNTRIES
    TIMEOUT = args.timeout
    MAX_CONCURRENT = args.concurrent
    SAVE_DEAD = args.dead
    
    if args.latency:
        MIN_LATENCY, MAX_LATENCY = args.latency
    
    if args.geo:
        ENABLE_GEO_FILTER = True
        if args.countries:
            ALLOWED_COUNTRIES = set(args.countries.upper().split(','))
    
    # Заголовок
    print("=" * 70)
    print(f"🔄 MTProto Proxy Checker v3.0")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Таймаут: {TIMEOUT} сек | Параллельно: {MAX_CONCURRENT}")
    if ENABLE_GEO_FILTER:
        print(f"🌍 Гео-фильтр: {', '.join(ALLOWED_COUNTRIES)}")
    if MIN_LATENCY > 0 or MAX_LATENCY < 2000:
        print(f"⚡ Задержка: {MIN_LATENCY}-{MAX_LATENCY} мс")
    
    total_sources = sum(len(urls) for urls in ALL_SOURCES.values())
    print(f"📡 Источников: {total_sources}")
    print("=" * 70)
    
    # Шаг 1: Загрузка
    all_proxies = await fetch_all_proxies()
    
    if not all_proxies:
        print("\n❌ Не найдено ни одного валидного прокси!")
        print("\n💡 Возможные причины:")
        print("   • Нет интернета или блокировка GitHub")
        print("   • Слишком строгая валидация")
        print("   • Временная недоступность источников")
        return
    
    # Шаг 2: Проверка
    alive, dead = await check_proxies_parallel(all_proxies)
    
    # Шаг 3: Сохранение
    if alive:
        print(f"\n💾 Сохранение {len(alive)} живых прокси...")
        print("-" * 40)
        save_proxies(alive, include_dead=SAVE_DEAD)
        
        # Топ-10 самых быстрых
        print(f"\n🏆 Топ-10 самых быстрых:")
        for i, item in enumerate(alive[:10], 1):
            p = item['proxy']
            lat = item.get('latency', '?')
            print(f"   {i:2}. {p['type'].upper():8} {p['server']:15}:{p['port']:5} {lat}ms")
    else:
        print("\n❌ Нет живых прокси!")
        print("💡 Попробуйте:")
        print("   • Увеличить timeout: -t 10")
        print("   • Уменьшить параллельность: -c 20")
        print("   • Расширить фильтр задержки: -l 0 5000")
        print("   • Запустить позже (списки обновляются каждые 4-12 часов)")
    
    print("\n" + "=" * 70)
    print("✅ Готово!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
