import asyncio
import json
import os
import re
import sys
import time
import ssl
import random
import socket
from collections import deque
from datetime import datetime
from urllib.parse import urlparse

import aiohttp
from aiohttp import web, ClientTimeout, TCPConnector
from aiohttp.client_exceptions import ClientError

# ============================================
# 1. Конфигурация
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

# ============================================
# 2. ProxyPool с улучшенной обработкой
# ============================================

class ProxyPool:
    def __init__(self, min_proxies=20, max_proxies=200):
        self.min_proxies = min_proxies
        self.max_proxies = max_proxies
        self.proxies = deque()
        self.stats = {}
        self.bad_proxies = set()
        self.lock = asyncio.Lock()
        self.is_running = False
        self.update_task = None
        
        # Оптимизированный SSL
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
        
        print(f"📦 ProxyPool: {min_proxies}-{max_proxies}")

    async def start(self):
        self.is_running = True
        await self.refresh()
        self.update_task = asyncio.create_task(self._background_update())
        print("✅ ProxyPool запущен")

    async def stop(self):
        self.is_running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except:
                pass

    async def get_proxy(self):
        """Получить лучший прокси"""
        async with self.lock:
            if not self.proxies:
                return None
            
            proxy = self.proxies[0]
            
            if proxy in self.stats:
                self.stats[proxy]["last_used"] = datetime.now().isoformat()
                self.stats[proxy]["success_count"] += 1
            
            return proxy

    async def report_failure(self, proxy):
        async with self.lock:
            if proxy in self.stats:
                self.stats[proxy]["fail_count"] += 1
                self.stats[proxy]["response_time"] = min(
                    self.stats[proxy]["response_time"] * 1.5, 9999
                )
                
                if self.stats[proxy]["fail_count"] > 3:
                    if proxy in self.proxies:
                        self.proxies.remove(proxy)
                    del self.stats[proxy]
                    self.bad_proxies.add(proxy)
                    print(f"🗑️ Удален {proxy}")

    async def report_success(self, proxy, response_time):
        async with self.lock:
            if proxy in self.stats:
                current = self.stats[proxy]["response_time"]
                self.stats[proxy]["response_time"] = current * 0.7 + response_time * 0.3
                self.stats[proxy]["success_count"] += 1
                self.stats[proxy]["fail_count"] = 0
                await self._resort()

    async def _resort(self):
        sorted_proxies = sorted(
            [(self.stats[p]["response_time"], p) for p in self.proxies if p in self.stats],
            key=lambda x: x[0]
        )
        self.proxies = deque([p for _, p in sorted_proxies])

    async def refresh(self):
        print("\n📡 Сбор прокси...")
        
        connector = TCPConnector(
            limit=100,
            ssl=self.ssl_context,
            force_close=True,
            enable_cleanup_closed=True
        )
        
        async with aiohttp.ClientSession(connector=connector) as session:
            http = await self._fetch_proxies(session, HTTP_SOURCES)
            socks = await self._fetch_proxies(session, SOCKS5_SOURCES)
        
        all_proxies = list(set(http + socks))
        print(f"📦 Собрано {len(all_proxies)} прокси")
        
        if not all_proxies:
            return
        
        working = await self._check_proxies(all_proxies[:300], max_workers=100)
        
        if working:
            async with self.lock:
                self.proxies = deque()
                self.stats = {}
                for info in working:
                    proxy = info['proxy']
                    self.proxies.append(proxy)
                    self.stats[proxy] = {
                        "response_time": info.get('response_time', 9999),
                        "success_count": 0,
                        "fail_count": 0,
                        "supports_https": info.get('supports_https', False)
                    }
            
            await self._resort()
            
            print(f"✅ Пул: {len(working)} прокси")
            for i, info in enumerate(working[:5]):
                print(f"   {i+1}. {info['proxy']} - {info.get('response_time', 0)}ms")
        else:
            print("❌ Нет рабочих прокси")

    async def _fetch_proxies(self, session, sources):
        proxies = set()
        for source in sources:
            try:
                async with session.get(source, timeout=10) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        for line in text.strip().split("\n"):
                            line = line.strip()
                            match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3}:\d{1,5})", line)
                            if match:
                                proxies.add(match.group(1))
            except:
                pass
        return list(proxies)

    async def _check_proxies(self, proxies, max_workers=100):
        semaphore = asyncio.Semaphore(max_workers)
        connector = TCPConnector(
            limit=max_workers,
            ssl=self.ssl_context,
            force_close=True,
            enable_cleanup_closed=True
        )
        
        print(f"🔍 Проверка {len(proxies)} прокси...")
        
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self._check_one(session, p, semaphore) for p in proxies]
            results = await asyncio.gather(*tasks)
        
        working = [r for r in results if r]
        working.sort(key=lambda x: x['response_time'])
        print(f"✅ Рабочих: {len(working)}")
        return working

    async def _check_one(self, session, proxy, semaphore):
        async with semaphore:
            try:
                proxy_url = f"http://{proxy}"
                start = time.monotonic()
                
                async with session.get(
                    "http://httpbin.org/ip",
                    proxy=proxy_url,
                    timeout=ClientTimeout(total=5, connect=3),
                    ssl=self.ssl_context
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    real_ip = data.get("origin", "").split(",")[0].strip()
                    if not real_ip:
                        return None
                    
                    response_time = round((time.monotonic() - start) * 1000, 1)
                    
                    supports_https = False
                    if response_time < 1000:
                        try:
                            async with session.get(
                                "https://httpbin.org/ip",
                                proxy=proxy_url,
                                timeout=ClientTimeout(total=3, connect=2),
                                ssl=self.ssl_context
                            ) as https_resp:
                                if https_resp.status == 200:
                                    supports_https = True
                        except:
                            pass
                    
                    return {
                        "proxy": proxy,
                        "real_ip": real_ip,
                        "response_time": response_time,
                        "supports_https": supports_https
                    }
            except:
                return None

    async def _background_update(self):
        while self.is_running:
            try:
                await asyncio.sleep(120)
                async with self.lock:
                    count = len(self.proxies)
                
                if count < self.min_proxies:
                    await self.refresh()
                else:
                    await self._add_new()
                
                await asyncio.sleep(180)
                await self._refresh_stats()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Обновление: {e}")
                await asyncio.sleep(10)

    async def _add_new(self):
        async with aiohttp.ClientSession() as session:
            http = await self._fetch_proxies(session, HTTP_SOURCES[:3])
            socks = await self._fetch_proxies(session, SOCKS5_SOURCES[:2])
        
        new = list(set(http + socks))
        
        async with self.lock:
            existing = set(self.proxies)
            new = [p for p in new if p not in existing and p not in self.bad_proxies]
        
        if not new:
            return
        
        working = await self._check_proxies(new[:50], max_workers=30)
        
        if working:
            async with self.lock:
                for info in working:
                    proxy = info['proxy']
                    if len(self.proxies) < self.max_proxies:
                        self.proxies.append(proxy)
                        self.stats[proxy] = {
                            "response_time": info.get('response_time', 9999),
                            "success_count": 0,
                            "fail_count": 0,
                            "supports_https": info.get('supports_https', False)
                        }
                
                await self._resort()
            
            print(f"✅ Добавлено {len(working)}")

    async def _refresh_stats(self):
        async with self.lock:
            if not self.proxies:
                return
            
            check_list = list(self.proxies)[:10]
        
        connector = TCPConnector(limit=10, ssl=self.ssl_context)
        semaphore = asyncio.Semaphore(10)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self._check_one(session, p, semaphore) for p in check_list]
            results = await asyncio.gather(*tasks)
        
        async with self.lock:
            for proxy, result in zip(check_list, results):
                if result:
                    if proxy in self.stats:
                        self.stats[proxy]["response_time"] = result['response_time']
                        self.stats[proxy]["supports_https"] = result.get('supports_https', False)
                else:
                    if proxy in self.proxies:
                        self.proxies.remove(proxy)
                    if proxy in self.stats:
                        del self.stats[proxy]
            
            await self._resort()

    def get_stats(self):
        return {
            "total": len(self.proxies),
            "bad": len(self.bad_proxies),
            "top": list(self.proxies)[:5] if self.proxies else []
        }

# ============================================
# 3. Прокси-сервер с поддержкой YouTube
# ============================================

class ProxyServer:
    def __init__(self, pool, host="0.0.0.0", port=9000):
        self.pool = pool
        self.host = host
        self.port = port
        self.server = None
        
        # SSL контекст для YouTube
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        # Включаем поддержку HTTP/2
        self.ssl_context.set_alpn_protocols(['h2', 'http/1.1'])
        
        # Таймауты для YouTube
        self.connect_timeout = 15
        self.read_timeout = 60
        
        print(f"🌐 ProxyServer на {host}:{port}")

    async def start(self):
        self.server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
            limit=100,
            backlog=100
        )
        
        print(f"✅ Прокси-сервер запущен")
        print(f"   http://{self.host}:{self.port}")
        print(f"   Тест: curl -x http://localhost:{self.port} https://www.youtube.com -k -L")
        return True

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _handle_client(self, reader, writer):
        try:
            data = await asyncio.wait_for(reader.readline(), timeout=10)
            if not data:
                writer.close()
                return
            
            parts = data.decode().split()
            if len(parts) < 2:
                writer.close()
                return
            
            method = parts[0].upper()
            target = parts[1]
            
            if method == "CONNECT":
                await self._handle_connect(reader, writer, target)
            else:
                await self._handle_http(reader, writer, method, target, data)
                
        except asyncio.TimeoutError:
            print("⏱️ Таймаут клиента")
            try:
                writer.close()
            except:
                pass
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            try:
                writer.close()
            except:
                pass

    async def _handle_connect(self, reader, writer, target):
        proxy = await self.pool.get_proxy()
        if not proxy:
            writer.write(b"HTTP/1.1 503 No Proxy\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        
        try:
            proxy_parts = proxy.split(":")
            proxy_host = proxy_parts[0]
            proxy_port = int(proxy_parts[1]) if len(proxy_parts) > 1 else 8080
            
            proxy_reader, proxy_writer = await asyncio.wait_for(
                asyncio.open_connection(proxy_host, proxy_port),
                timeout=5
            )
            
            connect_cmd = f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n"
            proxy_writer.write(connect_cmd.encode())
            await proxy_writer.drain()
            
            response = await asyncio.wait_for(proxy_reader.readline(), timeout=5)
            
            if not response or b"200" not in response:
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await writer.drain()
                proxy_writer.close()
                writer.close()
                return
            
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()
            
            # Туннелирование с большим буфером
            await asyncio.gather(
                self._pipe(reader, proxy_writer),
                self._pipe(proxy_reader, writer)
            )
            
        except asyncio.TimeoutError:
            await self.pool.report_failure(proxy)
            writer.write(b"HTTP/1.1 504 Gateway Timeout\r\n\r\n")
            await writer.drain()
        except Exception as e:
            await self.pool.report_failure(proxy)
            print(f"❌ CONNECT: {e}")
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await writer.drain()
        finally:
            try:
                writer.close()
            except:
                pass

    async def _handle_http(self, reader, writer, method, target, first_line):
        proxy = await self.pool.get_proxy()
        if not proxy:
            writer.write(b"HTTP/1.1 503 No Proxy\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        
        try:
            # Читаем заголовки
            headers = {}
            content_length = 0
            
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5)
                if line == b"\r\n" or line == b"\n":
                    break
                if line:
                    parts = line.decode().strip().split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        headers[key] = value
                        if key.lower() == "content-length":
                            content_length = int(value)
            
            # Читаем тело если есть
            body = b""
            if content_length > 0:
                body = await asyncio.wait_for(reader.read(content_length), timeout=5)
            
            # Строим URL
            if target.startswith(("http://", "https://")):
                url = target
            else:
                host = headers.get("Host", "")
                if not host:
                    writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                    await writer.drain()
                    writer.close()
                    return
                
                # Для YouTube определяем HTTPS
                if ":443" in host or "youtube.com" in host or "googlevideo.com" in host:
                    scheme = "https"
                else:
                    scheme = "http"
                url = f"{scheme}://{host}{target}" if target.startswith("/") else f"{scheme}://{host}/{target}"
            
            # Отправляем через прокси с большими таймаутами
            proxy_url = f"http://{proxy}"
            
            # Создаем connector с большими лимитами
            connector = TCPConnector(
                ssl=self.ssl_context,
                force_close=True,
                enable_cleanup_closed=True,
                limit=0,  # Без ограничений
                ttl_dns_cache=300
            )
            
            async with aiohttp.ClientSession(connector=connector) as session:
                start_req = time.monotonic()
                
                # Добавляем заголовки для YouTube
                headers["Accept-Encoding"] = "gzip, deflate, br"
                headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=body,
                    proxy=proxy_url,
                    ssl=self.ssl_context,
                    timeout=ClientTimeout(
                        total=60,
                        connect=10,
                        sock_read=30
                    ),
                    max_redirects=5
                ) as resp:
                    # Отправляем ответ
                    status_line = f"HTTP/1.1 {resp.status} {resp.reason}\r\n"
                    writer.write(status_line.encode())
                    
                    # Отправляем заголовки (кроме проблемных)
                    for key, value in resp.headers.items():
                        key_lower = key.lower()
                        if key_lower not in ["content-encoding", "transfer-encoding", "content-length"]:
                            writer.write(f"{key}: {value}\r\n".encode())
                    
                    writer.write(b"\r\n")
                    
                    # Отправляем тело с большим буфером
                    chunk_size = 262144  # 256KB для YouTube
                    async for chunk in resp.content.iter_chunked(chunk_size):
                        try:
                            writer.write(chunk)
                            await writer.drain()
                        except:
                            break
                    
                    # Обновляем статистику
                    response_time = round((time.monotonic() - start_req) * 1000, 1)
                    await self.pool.report_success(proxy, response_time)
                    
        except asyncio.TimeoutError:
            await self.pool.report_failure(proxy)
            try:
                writer.write(b"HTTP/1.1 504 Gateway Timeout\r\n\r\n")
                await writer.drain()
            except:
                pass
        except Exception as e:
            await self.pool.report_failure(proxy)
            print(f"❌ HTTP: {e}")
            try:
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await writer.drain()
            except:
                pass
        finally:
            try:
                writer.close()
            except:
                pass

    async def _pipe(self, reader, writer, buffer_size=262144):
        """Передача данных с большим буфером"""
        try:
            while True:
                data = await reader.read(buffer_size)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except:
            pass
        finally:
            try:
                writer.close()
            except:
                pass

# ============================================
# 4. Запуск
# ============================================

async def main():
    print("=" * 60)
    print("🌐 ПРОКСИ-СЕРВЕР ДЛЯ YOUTUBE")
    print("=" * 60)
    
    pool = ProxyPool(min_proxies=20, max_proxies=200)
    await pool.start()
    
    server = ProxyServer(pool, port=9000)
    await server.start()
    
    print("\n" + "=" * 60)
    print("✅ Сервер готов к работе")
    print("   Порт: 9000")
    print("   Тест: curl -x http://localhost:9000 https://www.youtube.com -k -L")
    print("   Браузер: chromium --proxy-server='http://localhost:9000'")
    print("=" * 60)
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Остановка...")
        await server.stop()
        await pool.stop()
        print("✅ Остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
