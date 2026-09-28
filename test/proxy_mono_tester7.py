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
from urllib.parse import urlparse, urlunparse

import aiohttp
from aiohttp import ClientTimeout, TCPConnector, ClientSession, hdrs
from aiohttp.client_exceptions import ClientError, ServerTimeoutError

# ============================================
# 1. Конфигурация
# ============================================

HTTP_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
]

HTTPS_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/https.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/https.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
]

# ============================================
# 2. ProxyPool
# ============================================

class ProxyPool:
    def __init__(self, min_proxies=10, max_proxies=100):
        self.min_proxies = min_proxies
        self.max_proxies = max_proxies
        self.proxies = deque()
        self.stats = {}
        self.bad_proxies = set()
        self.lock = asyncio.Lock()
        self.is_running = False
        self.update_task = None
        
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        self.connect_proxies = set()
        
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

    async def get_proxy(self, require_connect=False):
        async with self.lock:
            if not self.proxies:
                return None
            
            if require_connect:
                for proxy in self.proxies:
                    if proxy in self.connect_proxies:
                        self.proxies.remove(proxy)
                        self.proxies.append(proxy)
                        return proxy
                # Если нет с CONNECT, возвращаем любой
                proxy = self.proxies[0]
                self.proxies.rotate(-1)
                return proxy
            
            proxy = self.proxies[0]
            self.proxies.rotate(-1)
            return proxy

    async def report_failure(self, proxy):
        async with self.lock:
            if proxy in self.stats:
                self.stats[proxy]["fail_count"] += 1
                if self.stats[proxy]["fail_count"] > 2:
                    if proxy in self.proxies:
                        self.proxies.remove(proxy)
                    if proxy in self.connect_proxies:
                        self.connect_proxies.remove(proxy)
                    del self.stats[proxy]
                    self.bad_proxies.add(proxy)

    async def report_connect_success(self, proxy):
        async with self.lock:
            if proxy in self.stats:
                self.connect_proxies.add(proxy)

    async def refresh(self):
        print("\n📡 Сбор прокси...")
        
        connector = TCPConnector(limit=50, ssl=self.ssl_context)
        
        async with ClientSession(connector=connector) as session:
            http = await self._fetch_proxies(session, HTTP_SOURCES)
            https = await self._fetch_proxies(session, HTTPS_SOURCES)
        
        all_proxies = list(set(http + https))
        print(f"📦 Собрано {len(all_proxies)} прокси")
        
        if not all_proxies:
            return
        
        working = await self._check_proxies_with_connect(all_proxies[:200])
        
        if working:
            async with self.lock:
                self.proxies = deque()
                self.stats = {}
                self.connect_proxies = set()
                
                for info in working:
                    proxy = info['proxy']
                    self.proxies.append(proxy)
                    self.stats[proxy] = {
                        "response_time": info.get('response_time', 9999),
                        "success_count": 0,
                        "fail_count": 0,
                        "supports_connect": info.get('supports_connect', False)
                    }
                    if info.get('supports_connect', False):
                        self.connect_proxies.add(proxy)
            
            print(f"✅ Пул: {len(working)} прокси")
            print(f"   CONNECT поддерживают: {len(self.connect_proxies)}")
            
            for i, info in enumerate(working[:5]):
                connect_status = "✅" if info.get('supports_connect') else "❌"
                print(f"   {i+1}. {info['proxy']} - {info.get('response_time', 0)}ms {connect_status}")
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

    async def _check_proxies_with_connect(self, proxies, max_workers=30):
        semaphore = asyncio.Semaphore(max_workers)
        connector = TCPConnector(limit=max_workers, ssl=self.ssl_context)
        
        print(f"🔍 Проверка {len(proxies)} прокси...")
        
        async with ClientSession(connector=connector) as session:
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
                    
                    supports_connect = False
                    try:
                        async with session.get(
                            "https://httpbin.org/ip",
                            proxy=proxy_url,
                            timeout=ClientTimeout(total=5, connect=3),
                            ssl=self.ssl_context
                        ) as https_resp:
                            if https_resp.status == 200:
                                supports_connect = True
                    except:
                        pass
                    
                    if response_time > 3000:
                        return None
                    
                    return {
                        "proxy": proxy,
                        "real_ip": real_ip,
                        "response_time": response_time,
                        "supports_connect": supports_connect
                    }
            except:
                return None

    async def _background_update(self):
        while self.is_running:
            try:
                await asyncio.sleep(180)
                async with self.lock:
                    count = len(self.proxies)
                
                if count < self.min_proxies:
                    await self.refresh()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Обновление: {e}")
                await asyncio.sleep(10)

    def get_stats(self):
        return {
            "total": len(self.proxies),
            "connect": len(self.connect_proxies),
            "bad": len(self.bad_proxies)
        }

# ============================================
# 3. Прокси-сервер с потоковой передачей
# ============================================

class ProxyServer:
    def __init__(self, pool, host="0.0.0.0", port=9000):
        self.pool = pool
        self.host = host
        self.port = port
        self.server = None
        
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        print(f"🌐 ProxyServer на {host}:{port}")

    async def start(self):
        self.server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
            limit=50,
            backlog=100
        )
        
        print(f"✅ Прокси-сервер запущен на порту {self.port}")
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
                await self._handle_http_stream(reader, writer, method, target, data)
                
        except asyncio.TimeoutError:
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
        """Обработка CONNECT с потоковой передачей"""
        proxy = await self.pool.get_proxy(require_connect=True)
        if not proxy:
            writer.write(b"HTTP/1.1 503 No Proxy\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        
        try:
            proxy_parts = proxy.split(":")
            proxy_host = proxy_parts[0]
            proxy_port = int(proxy_parts[1]) if len(proxy_parts) > 1 else 8080
            
            # Подключаемся к прокси
            proxy_reader, proxy_writer = await asyncio.wait_for(
                asyncio.open_connection(proxy_host, proxy_port),
                timeout=5
            )
            
            # Отправляем CONNECT
            connect_cmd = f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n"
            proxy_writer.write(connect_cmd.encode())
            await proxy_writer.drain()
            
            # Получаем ответ
            response = await asyncio.wait_for(proxy_reader.readline(), timeout=5)
            
            if response and b"200" in response:
                await self.pool.report_connect_success(proxy)
                
                # Отправляем клиенту успех
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                
                # Туннелируем трафик с большим буфером
                await asyncio.gather(
                    self._pipe_data(reader, proxy_writer),
                    self._pipe_data(proxy_reader, writer)
                )
            else:
                # Если CONNECT не работает, пробуем через HTTP
                proxy_writer.close()
                await self._handle_http_fallback(reader, writer, target, proxy)
                
        except Exception as e:
            print(f"⚠️ CONNECT ошибка: {e}")
            await self.pool.report_failure(proxy)
            await self._handle_http_fallback(reader, writer, target, proxy)

    async def _handle_http_fallback(self, reader, writer, target, proxy):
        """Fallback через HTTP прокси без CONNECT"""
        try:
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()
            
            # Читаем HTTPS трафик
            data = await reader.read(4096)
            if not data:
                writer.close()
                return
            
            proxy_parts = proxy.split(":")
            proxy_host = proxy_parts[0]
            proxy_port = int(proxy_parts[1]) if len(proxy_parts) > 1 else 8080
            
            proxy_reader, proxy_writer = await asyncio.wait_for(
                asyncio.open_connection(proxy_host, proxy_port),
                timeout=5
            )
            
            proxy_writer.write(data)
            await proxy_writer.drain()
            
            await asyncio.gather(
                self._pipe_data(reader, proxy_writer),
                self._pipe_data(proxy_reader, writer)
            )
            
        except Exception as e:
            print(f"⚠️ Fallback ошибка: {e}")
            try:
                writer.close()
            except:
                pass

    async def _handle_http_stream(self, reader, writer, method, target, first_line):
        """Потоковая обработка HTTP запросов без буферизации"""
        proxy = await self.pool.get_proxy()
        if not proxy:
            writer.write(b"HTTP/1.1 503 No Proxy Available\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        
        try:
            # Читаем заголовки
            headers = {}
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5)
                if line == b"\r\n" or line == b"\n":
                    break
                if line:
                    parts = line.decode().strip().split(":", 1)
                    if len(parts) == 2:
                        headers[parts[0].strip()] = parts[1].strip()
            
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
                
                scheme = "https" if "youtube.com" in host or "googlevideo.com" in host else "http"
                url = f"{scheme}://{host}{target}" if target.startswith("/") else f"{scheme}://{host}/{target}"
            
            # Добавляем нужные заголовки
            headers["Accept-Encoding"] = "gzip, deflate, br"
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            
            # Отправляем через прокси с потоковой передачей
            proxy_url = f"http://{proxy}"
            connector = TCPConnector(
                ssl=self.ssl_context,
                force_close=True,
                limit=0,
                enable_cleanup_closed=True
            )
            
            async with ClientSession(connector=connector) as session:
                start_req = time.monotonic()
                
                # Используем stream для больших ответов
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    proxy=proxy_url,
                    ssl=self.ssl_context,
                    timeout=ClientTimeout(total=120, connect=10, sock_read=60)
                ) as resp:
                    # Отправляем статус и заголовки
                    writer.write(f"HTTP/1.1 {resp.status} {resp.reason}\r\n".encode())
                    
                    # Отправляем заголовки (пропускаем проблемные)
                    for key, value in resp.headers.items():
                        key_lower = key.lower()
                        if key_lower not in ["content-encoding", "transfer-encoding", "content-length"]:
                            writer.write(f"{key}: {value}\r\n".encode())
                    
                    # Добавляем свой заголовок для поддержки chunked
                    writer.write(b"Transfer-Encoding: chunked\r\n")
                    writer.write(b"\r\n")
                    
                    # Отправляем тело чанками без буферизации
                    chunk_size = 65536  # 64KB
                    async for chunk in resp.content.iter_chunked(chunk_size):
                        try:
                            # Отправляем chunk в формате hex размер + данные
                            chunk_hex = f"{len(chunk):x}\r\n".encode()
                            writer.write(chunk_hex)
                            writer.write(chunk)
                            writer.write(b"\r\n")
                            await writer.drain()
                        except Exception as e:
                            print(f"⚠️ Ошибка отправки chunk: {e}")
                            break
                    
                    # Отправляем финальный chunk
                    writer.write(b"0\r\n\r\n")
                    await writer.drain()
                    
                    response_time = round((time.monotonic() - start_req) * 1000, 1)
                    
                    # Обновляем статистику при успехе
                    if resp.status < 400:
                        await self.pool.report_success(proxy, response_time)
                    
        except asyncio.TimeoutError:
            await self.pool.report_failure(proxy)
            try:
                writer.write(b"HTTP/1.1 504 Gateway Timeout\r\n\r\n")
                await writer.drain()
            except:
                pass
        except Exception as e:
            print(f"❌ HTTP ошибка: {e}")
            await self.pool.report_failure(proxy)
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

    async def _pipe_data(self, reader, writer, buffer_size=65536):
        """Потоковая передача данных"""
        try:
            while True:
                data = await reader.read(buffer_size)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            print(f"⚠️ Pipe ошибка: {e}")
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
    print("🌐 ПРОКСИ-СЕРВЕР С ПОТОКОВОЙ ПЕРЕДАЧЕЙ")
    print("=" * 60)
    
    pool = ProxyPool(min_proxies=10, max_proxies=100)
    await pool.start()
    
    server = ProxyServer(pool, port=9000)
    await server.start()
    
    print("\n" + "=" * 60)
    print("✅ Сервер готов к работе")
    print("   Порт: 9000")
    print("   Тест: curl -x http://localhost:9000 https://httpbin.org/ip -k")
    print("   YouTube: curl -x http://localhost:9000 https://www.youtube.com -k -L")
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
