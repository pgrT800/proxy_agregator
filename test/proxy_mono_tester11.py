import asyncio
import json
import os
import re
import sys
import time
import ssl
import random
import socket
import base64
from collections import deque
from datetime import datetime
from urllib.parse import urlparse, urlunparse, quote

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
# 2. ProxyPool - только рабочие прокси
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
        
        # SSL контекст для тестирования
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
        
        # Разделение по типам
        self.connect_proxies = set()  # Поддерживают CONNECT
        self.working_proxies = set()  # Проверенные рабочие
        
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
        """Получить прокси - только проверенные"""
        async with self.lock:
            if not self.proxies:
                return None
            
            # Ищем прокси с поддержкой CONNECT если нужно
            if require_connect:
                for proxy in self.proxies:
                    if proxy in self.connect_proxies and proxy in self.working_proxies:
                        self.proxies.remove(proxy)
                        self.proxies.append(proxy)
                        return proxy
                
                # Если нет, берем любой рабочий
                for proxy in self.proxies:
                    if proxy in self.working_proxies:
                        self.proxies.remove(proxy)
                        self.proxies.append(proxy)
                        return proxy
                
                return None
            
            # Обычная ротация только среди рабочих
            for _ in range(len(self.proxies)):
                proxy = self.proxies[0]
                self.proxies.rotate(-1)
                if proxy in self.working_proxies:
                    return proxy
            
            return None

    async def report_failure(self, proxy):
        async with self.lock:
            if proxy in self.stats:
                self.stats[proxy]["fail_count"] += 1
                if self.stats[proxy]["fail_count"] > 2:
                    # Удаляем из всех списков
                    if proxy in self.proxies:
                        self.proxies.remove(proxy)
                    if proxy in self.connect_proxies:
                        self.connect_proxies.remove(proxy)
                    if proxy in self.working_proxies:
                        self.working_proxies.remove(proxy)
                    if proxy in self.stats:
                        del self.stats[proxy]
                    self.bad_proxies.add(proxy)
                    print(f"🗑️ Удален {proxy}")

    async def report_success(self, proxy):
        async with self.lock:
            if proxy in self.stats:
                self.working_proxies.add(proxy)
                self.stats[proxy]["success_count"] += 1
                self.stats[proxy]["fail_count"] = 0

    async def refresh(self):
        print("\n📡 Сбор и проверка прокси...")
        
        connector = TCPConnector(limit=50, ssl=self.ssl_context)
        
        async with ClientSession(connector=connector) as session:
            http = await self._fetch_proxies(session, HTTP_SOURCES)
            https = await self._fetch_proxies(session, HTTPS_SOURCES)
        
        all_proxies = list(set(http + https))
        print(f"📦 Собрано {len(all_proxies)} прокси")
        
        if not all_proxies:
            return
        
        # Проверяем все прокси на работоспособность
        working = await self._check_proxies_thorough(all_proxies[:200])
        
        if working:
            async with self.lock:
                self.proxies = deque()
                self.stats = {}
                self.connect_proxies = set()
                self.working_proxies = set()
                
                for info in working:
                    proxy = info['proxy']
                    self.proxies.append(proxy)
                    self.working_proxies.add(proxy)
                    self.stats[proxy] = {
                        "response_time": info.get('response_time', 9999),
                        "success_count": 0,
                        "fail_count": 0,
                        "supports_connect": info.get('supports_connect', False)
                    }
                    if info.get('supports_connect', False):
                        self.connect_proxies.add(proxy)
            
            print(f"✅ Пул: {len(working)} рабочих прокси")
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

    async def _check_proxies_thorough(self, proxies, max_workers=20):
        """Тщательная проверка прокси с тестом TLS"""
        semaphore = asyncio.Semaphore(max_workers)
        connector = TCPConnector(limit=max_workers, ssl=self.ssl_context)
        
        print(f"🔍 Проверка {len(proxies)} прокси (тест TLS)...")
        
        async with ClientSession(connector=connector) as session:
            tasks = [self._check_one_thorough(session, p, semaphore) for p in proxies]
            results = await asyncio.gather(*tasks)
        
        working = [r for r in results if r]
        working.sort(key=lambda x: x['response_time'])
        print(f"✅ Рабочих: {len(working)}")
        return working

    async def _check_one_thorough(self, session, proxy, semaphore):
        """Проверка одного прокси с тестом TLS"""
        async with semaphore:
            try:
                proxy_url = f"http://{proxy}"
                start = time.monotonic()
                
                # 1. Проверка HTTP
                try:
                    async with session.get(
                        "http://httpbin.org/ip",
                        proxy=proxy_url,
                        timeout=ClientTimeout(total=5, connect=3),
                        ssl=self.ssl_context
                    ) as resp:
                        if resp.status != 200:
                            return None
                        await resp.json()
                except:
                    return None
                
                # 2. Проверка TLS (HTTPS) - самый важный тест
                supports_connect = False
                try:
                    async with session.get(
                        "https://httpbin.org/ip",
                        proxy=proxy_url,
                        timeout=ClientTimeout(total=8, connect=5),
                        ssl=self.ssl_context
                    ) as https_resp:
                        if https_resp.status == 200:
                            supports_connect = True
                            await https_resp.json()
                except Exception as e:
                    # Если ошибка TLS - прокси не подходит
                    if "SSL" in str(e) or "TLS" in str(e) or "handshake" in str(e).lower():
                        return None
                    # Другие ошибки тоже отсеиваем
                    return None
                
                # Если прокси не поддерживает HTTPS - не используем
                if not supports_connect:
                    return None
                
                response_time = round((time.monotonic() - start) * 1000, 1)
                
                if response_time > 3000:
                    return None
                
                return {
                    "proxy": proxy,
                    "response_time": response_time,
                    "supports_connect": True  # Только прокси с CONNECT
                }
            except:
                return None

    async def _background_update(self):
        while self.is_running:
            try:
                await asyncio.sleep(180)
                async with self.lock:
                    count = len(self.working_proxies)
                
                if count < self.min_proxies:
                    print(f"⚠️ Мало прокси ({count}), обновление...")
                    await self.refresh()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Обновление: {e}")
                await asyncio.sleep(10)

    def get_stats(self):
        return {
            "total": len(self.working_proxies),
            "connect": len(self.connect_proxies),
            "bad": len(self.bad_proxies)
        }

# ============================================
# 3. Прокси-сервер - только с поддержкой TLS
# ============================================

class ProxyServer:
    def __init__(self, pool, host="0.0.0.0", port=9000):
        self.pool = pool
        self.host = host
        self.port = port
        self.server = None
        
        # SSL контекст для клиента - игнорируем ошибки
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
        
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
        print(f"   🔒 TLS: игнорирование сертификатов включено")
        print(f"   ⚠️ Используются только прокси с поддержкой CONNECT")
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
                # Проксируем HTTP
                await self._handle_http(reader, writer, method, target, data)
                
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
        """Обработка CONNECT - только с проверенными прокси"""
        # Берем только прокси с CONNECT
        proxy = await self.pool.get_proxy(require_connect=True)
        
        if not proxy:
            print(f"⚠️ Нет доступных прокси для {target}")
            writer.write(b"HTTP/1.1 503 No Proxy Available\r\n\r\n")
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
            
            # Ждем ответ
            response = await asyncio.wait_for(proxy_reader.readline(), timeout=5)
            
            if response and b"200" in response:
                # Успех
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                
                print(f"🔒 TLS туннель для {target} через {proxy}")
                
                # Туннелируем
                await asyncio.gather(
                    self._pipe_data(reader, proxy_writer),
                    self._pipe_data(proxy_reader, writer)
                )
            else:
                # Прокси не поддерживает CONNECT
                await self.pool.report_failure(proxy)
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await writer.drain()
                writer.close()
                
        except asyncio.TimeoutError:
            await self.pool.report_failure(proxy)
            writer.write(b"HTTP/1.1 504 Gateway Timeout\r\n\r\n")
            await writer.drain()
        except Exception as e:
            await self.pool.report_failure(proxy)
            print(f"⚠️ CONNECT ошибка для {proxy}: {e}")
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await writer.drain()
        finally:
            try:
                writer.close()
            except:
                pass

    async def _handle_http(self, reader, writer, method, target, first_line):
        """Обработка HTTP запросов"""
        proxy = await self.pool.get_proxy(require_connect=False)
        if not proxy:
            writer.write(b"HTTP/1.1 503 No Proxy Available\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        
        try:
            # Читаем запрос
            request_data = first_line
            content_length = 0
            
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5)
                request_data += line
                if line == b"\r\n" or line == b"\n":
                    break
                if line:
                    parts = line.decode().strip().split(":", 1)
                    if len(parts) == 2 and parts[0].strip().lower() == "content-length":
                        content_length = int(parts[1].strip())
            
            if content_length > 0:
                body = await asyncio.wait_for(reader.read(content_length), timeout=10)
                request_data += body
            
            # Строим URL
            if target.startswith(("http://", "https://")):
                url = target
            else:
                host = None
                for line in request_data.split(b"\r\n"):
                    if line.lower().startswith(b"host:"):
                        host = line.decode().split(":", 1)[1].strip()
                        break
                
                if not host:
                    writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                    await writer.drain()
                    writer.close()
                    return
                
                # Определяем протокол
                if "://" not in target:
                    scheme = "https" if ":443" in host else "http"
                    url = f"{scheme}://{host}{target}" if target.startswith("/") else f"{scheme}://{host}/{target}"
                else:
                    url = target
            
            # Подключаемся к прокси
            proxy_parts = proxy.split(":")
            proxy_host = proxy_parts[0]
            proxy_port = int(proxy_parts[1]) if len(proxy_parts) > 1 else 8080
            
            proxy_reader, proxy_writer = await asyncio.wait_for(
                asyncio.open_connection(proxy_host, proxy_port),
                timeout=5
            )
            
            # Модифицируем запрос
            lines = request_data.split(b"\r\n")
            first_line_parts = lines[0].split(b" ")
            if len(first_line_parts) >= 2:
                lines[0] = b" ".join([first_line_parts[0], url.encode(), first_line_parts[2] if len(first_line_parts) > 2 else b"HTTP/1.1"])
            
            modified_request = b"\r\n".join(lines)
            
            # Отправляем
            proxy_writer.write(modified_request)
            await proxy_writer.drain()
            
            # Проксируем ответ
            await self._pipe_data(proxy_reader, writer)
            
            # Отмечаем успех
            await self.pool.report_success(proxy)
            
        except asyncio.TimeoutError:
            await self.pool.report_failure(proxy)
            try:
                writer.write(b"HTTP/1.1 504 Gateway Timeout\r\n\r\n")
                await writer.drain()
            except:
                pass
        except Exception as e:
            await self.pool.report_failure(proxy)
            print(f"❌ HTTP ошибка: {e}")
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
        """Передача данных"""
        try:
            while True:
                data = await reader.read(buffer_size)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError, ssl.SSLError):
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
    print("🌐 ПРОКСИ-СЕРВЕР - ТОЛЬКО TLS")
    print("=" * 60)
    print("🔒 Используются только прокси с поддержкой TLS/CONNECT")
    print("🔒 Игнорирование ошибок сертификатов включено")
    print("=" * 60)
    
    pool = ProxyPool(min_proxies=5, max_proxies=50)
    await pool.start()
    
    server = ProxyServer(pool, port=9000)
    await server.start()
    
    print("\n" + "=" * 60)
    print("✅ Сервер готов")
    print("   curl -x http://localhost:9000 https://httpbin.org/ip -k")
    print("   chromium --proxy-server='http://localhost:9000' --ignore-certificate-errors")
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
