import asyncio
import json
import os
import random
import re
import socket
import ssl
import sys
import time
from collections import deque
from datetime import datetime
from urllib.parse import urlparse

import aiohttp
from aiohttp import web
from aiohttp_socks import ProxyConnector

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
# 2. Менеджер пула прокси
# ============================================

class ProxyPool:
    def __init__(self, min_proxies=30, max_proxies=300):
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
        """Получить следующий прокси"""
        async with self.lock:
            if not self.proxies:
                return None
            
            # Ротация
            proxy = self.proxies.popleft()
            self.proxies.append(proxy)
            
            if proxy in self.stats:
                self.stats[proxy]["last_used"] = datetime.now().isoformat()
                self.stats[proxy]["success_count"] += 1
            
            return proxy

    async def report_failure(self, proxy):
        """Сообщить о неудаче"""
        async with self.lock:
            if proxy in self.stats:
                self.stats[proxy]["fail_count"] += 1
                if self.stats[proxy]["fail_count"] > 3:
                    if proxy in self.proxies:
                        self.proxies.remove(proxy)
                    del self.stats[proxy]
                    self.bad_proxies.add(proxy)
                    print(f"🗑️ Удален {proxy}")

    async def refresh(self):
        """Обновить пул"""
        print("\n📡 Сбор прокси...")
        
        async with aiohttp.ClientSession() as session:
            http = await self._fetch_proxies(session, HTTP_SOURCES)
            socks = await self._fetch_proxies(session, SOCKS5_SOURCES)
        
        all_proxies = list(set(http + socks))
        print(f"📦 Собрано {len(all_proxies)} прокси")
        
        if not all_proxies:
            return
        
        working = await self._check_proxies(all_proxies[:500])
        
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
            
            print(f"✅ Пул: {len(working)} прокси")
            for info in working[:5]:
                print(f"   {info['proxy']} - {info.get('response_time', 0)}ms")
        else:
            print("❌ Нет рабочих прокси")

    async def _fetch_proxies(self, session, sources):
        proxies = set()
        for source in sources:
            try:
                async with session.get(source, timeout=10) as resp:
                    text = await resp.text()
                    for line in text.strip().split("\n"):
                        match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3}:\d{1,5})", line.strip())
                        if match:
                            proxies.add(match.group(1))
            except:
                pass
        return list(proxies)

    async def _check_proxies(self, proxies, max_workers=50):
        semaphore = asyncio.Semaphore(max_workers)
        connector = aiohttp.TCPConnector(limit=max_workers, ssl=self.ssl_context)
        
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
                    timeout=5,
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
                    try:
                        async with session.get(
                            "https://httpbin.org/ip",
                            proxy=proxy_url,
                            timeout=3,
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
                await asyncio.sleep(180)
                async with self.lock:
                    count = len(self.proxies)
                
                if count < self.min_proxies:
                    await self.refresh()
                else:
                    await self._cleanup()
                    
                    if count < self.max_proxies:
                        await self._add_new()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Обновление: {e}")
                await asyncio.sleep(10)

    async def _cleanup(self):
        async with self.lock:
            proxies = list(self.proxies)[:20]
        
        if not proxies:
            return
        
        connector = aiohttp.TCPConnector(limit=10, ssl=self.ssl_context)
        semaphore = asyncio.Semaphore(10)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self._check_one(session, p, semaphore) for p in proxies]
            results = await asyncio.gather(*tasks)
        
        dead = []
        for proxy, result in zip(proxies, results):
            if not result:
                dead.append(proxy)
        
        if dead:
            async with self.lock:
                for proxy in dead:
                    if proxy in self.proxies:
                        self.proxies.remove(proxy)
                        self.bad_proxies.add(proxy)
                    if proxy in self.stats:
                        del self.stats[proxy]
            print(f"🗑️ Удалено {len(dead)}")

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
        
        working = await self._check_proxies(new[:50], max_workers=20)
        
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
            print(f"✅ Добавлено {len(working)}")

    def get_stats(self):
        return {
            "total": len(self.proxies),
            "bad": len(self.bad_proxies),
            "top": list(self.proxies)[:5] if self.proxies else []
        }

# ============================================
# 3. Прокси-сервер
# ============================================

class ProxyServer:
    def __init__(self, pool, host="0.0.0.0", port=9000):
        self.pool = pool
        self.host = host
        self.port = port
        self.app = None
        self.runner = None
        self.site = None
        
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # Для CONNECT метода (HTTPS)
        self.loop = asyncio.get_event_loop()
        
        print(f"🌐 ProxyServer на {host}:{port}")

    async def start(self):
        """Запуск сервера"""
        self.app = web.Application()
        self.app.router.add_route('*', '/{path:.*}', self._handle_request)
        
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        
        print(f"✅ Прокси-сервер запущен на http://{self.host}:{self.port}")
        print(f"   Используйте: curl -x http://localhost:{self.port} http://httpbin.org/ip")
        print(f"   Браузер: chromium --proxy-server='http://localhost:{self.port}'")
        
        return True

    async def stop(self):
        """Остановка сервера"""
        if self.runner:
            await self.runner.cleanup()

    async def _handle_request(self, request):
        """Обработка всех запросов"""
        try:
            # Получаем прокси из пула
            proxy = await self.pool.get_proxy()
            if not proxy:
                return web.Response(status=503, text="No proxy available")
            
            # Строим URL
            target_url = str(request.url)
            method = request.method
            
            # Получаем тело запроса
            body = await request.read() if request.can_read_body else None
            
            # Создаем сессию с прокси
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            
            # Определяем протокол
            scheme = "https" if request.url.scheme == "https" else "http"
            proxy_url = f"http://{proxy}"
            
            # Формируем заголовки
            headers = dict(request.headers)
            # Удаляем заголовки, которые могут вызвать проблемы
            headers.pop("Proxy-Connection", None)
            headers.pop("Proxy-Authorization", None)
            
            # Отправляем запрос через прокси
            async with aiohttp.ClientSession(connector=connector) as session:
                try:
                    async with session.request(
                        method=method,
                        url=target_url,
                        headers=headers,
                        data=body,
                        proxy=proxy_url,
                        ssl=self.ssl_context,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        # Читаем ответ
                        response_body = await resp.read()
                        
                        # Формируем ответ
                        response_headers = dict(resp.headers)
                        response_headers.pop("Content-Encoding", None)
                        response_headers.pop("Transfer-Encoding", None)
                        
                        return web.Response(
                            status=resp.status,
                            headers=response_headers,
                            body=response_body
                        )
                        
                except asyncio.TimeoutError:
                    await self.pool.report_failure(proxy)
                    return web.Response(status=504, text="Proxy timeout")
                except Exception as e:
                    await self.pool.report_failure(proxy)
                    return web.Response(status=502, text=f"Proxy error: {str(e)}")
                
        except Exception as e:
            return web.Response(status=500, text=f"Server error: {str(e)}")

# ============================================
# 4. HTTP прокси с CONNECT (для HTTPS)
# ============================================

class ConnectProxyServer:
    """Прокси-сервер с поддержкой CONNECT метода (HTTPS)"""
    
    def __init__(self, pool, host="0.0.0.0", port=9000):
        self.pool = pool
        self.host = host
        self.port = port
        self.server = None
        
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        print(f"🔒 HTTPS Proxy на {host}:{port}")

    async def start(self):
        """Запуск сервера"""
        self.server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port
        )
        
        print(f"✅ HTTPS прокси запущен на {self.host}:{self.port}")
        return True

    async def stop(self):
        """Остановка сервера"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _handle_client(self, reader, writer):
        """Обработка клиента"""
        try:
            # Читаем запрос
            data = await reader.readline()
            if not data:
                return
            
            parts = data.decode().split()
            if len(parts) < 2:
                return
            
            method = parts[0].upper()
            target = parts[1]
            version = parts[2] if len(parts) > 2 else "HTTP/1.1"
            
            if method == "CONNECT":
                # Обработка HTTPS через CONNECT
                await self._handle_connect(reader, writer, target)
            else:
                # Обычный HTTP запрос
                await self._handle_http(reader, writer, method, target, version)
                
        except Exception as e:
            print(f"❌ Ошибка клиента: {e}")
            try:
                writer.close()
            except:
                pass

    async def _handle_connect(self, reader, writer, target):
        """Обработка CONNECT метода (HTTPS)"""
        proxy = await self.pool.get_proxy()
        if not proxy:
            writer.write(b"HTTP/1.1 503 No Proxy Available\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        
        try:
            # Получаем прокси
            proxy_parts = proxy.split(":")
            proxy_host = proxy_parts[0]
            proxy_port = int(proxy_parts[1]) if len(proxy_parts) > 1 else 8080
            
            # Подключаемся к прокси
            proxy_reader, proxy_writer = await asyncio.open_connection(
                proxy_host, proxy_port
            )
            
            # Отправляем CONNECT на прокси
            connect_cmd = f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n"
            proxy_writer.write(connect_cmd.encode())
            await proxy_writer.drain()
            
            # Читаем ответ от прокси
            response = await proxy_reader.readline()
            if b"200" not in response:
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await writer.drain()
                proxy_writer.close()
                writer.close()
                return
            
            # Отправляем клиенту успешное соединение
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()
            
            # Туннелируем трафик
            await asyncio.gather(
                self._pipe(reader, proxy_writer),
                self._pipe(proxy_reader, writer)
            )
            
        except Exception as e:
            print(f"❌ CONNECT ошибка: {e}")
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await writer.drain()
        finally:
            try:
                writer.close()
            except:
                pass

    async def _handle_http(self, reader, writer, method, target, version):
        """Обработка HTTP запроса"""
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
                line = await reader.readline()
                if line == b"\r\n" or line == b"\n":
                    break
                if line:
                    parts = line.decode().strip().split(":", 1)
                    if len(parts) == 2:
                        headers[parts[0].strip()] = parts[1].strip()
            
            # Строим URL
            if target.startswith("http://") or target.startswith("https://"):
                url = target
            else:
                host = headers.get("Host", "")
                scheme = "https" if "https" in urlparse(target).scheme else "http"
                url = f"{scheme}://{host}{target}" if host else target
            
            # Отправляем запрос через прокси
            proxy_url = f"http://{proxy}"
            
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    proxy=proxy_url,
                    ssl=self.ssl_context,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    # Отправляем ответ клиенту
                    writer.write(f"HTTP/1.1 {resp.status} {resp.reason}\r\n".encode())
                    for key, value in resp.headers.items():
                        if key.lower() not in ["content-encoding", "transfer-encoding"]:
                            writer.write(f"{key}: {value}\r\n".encode())
                    writer.write(b"\r\n")
                    
                    # Отправляем тело
                    async for chunk in resp.content.iter_chunked(8192):
                        writer.write(chunk)
                        await writer.drain()
                    
        except Exception as e:
            print(f"❌ HTTP ошибка: {e}")
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await writer.drain()
        finally:
            try:
                writer.close()
            except:
                pass

    async def _pipe(self, reader, writer):
        """Передача данных между соединениями"""
        try:
            while True:
                data = await reader.read(8192)
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
# 5. Главная функция
# ============================================

async def main():
    print("=" * 60)
    print("🌐 СОБСТВЕННЫЙ ПРОКСИ-СЕРВЕР")
    print("=" * 60)
    
    # Создаем пул прокси
    pool = ProxyPool(min_proxies=30, max_proxies=300)
    await pool.start()
    
    # Запускаем HTTPS прокси (с поддержкой CONNECT)
    https_proxy = ConnectProxyServer(pool, port=9000)
    await https_proxy.start()
    
    print("\n" + "=" * 60)
    print("✅ Прокси-сервер работает")
    print("   Порт: 9000")
    print("   Тест: curl -x http://localhost:9000 https://httpbin.org/ip")
    print("   Браузер: chromium --proxy-server='http://localhost:9000'")
    print("   Нажми Ctrl+C для остановки")
    print("=" * 60)
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Остановка...")
        await https_proxy.stop()
        await pool.stop()
        print("✅ Остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
