import asyncio
import json
import os
from typing import Dict, List, Optional, Union

import redis
import redis.asyncio as redis

from core.PiplineLDS.linuxDomainSocket import linuxdomainsocket
from core.tui_global_set import update_table, update_widget_right, write_left, write_top


class MainSortiring:
    def __init__(
        self,
        queue_http,
        queue_https,
        queue_socks,
        queue_shadowsocks,
        queue_trojan,
        queue_vless,
        queue_vmess,
        log_left=None,
        log_right=None,
    ):
        self.path_socket = "/tmp/my_socket_for_server.sock"
        self.data_http = []
        self.data_https = []
        self.data_socks = []
        self.data_shadowsocks = []
        self.data_trojan = []
        self.data_vless = []
        self.data_vmess = []
        self.queue_http = queue_http
        self.queue_https = queue_https
        self.queue_socks = queue_socks
        self.queue_shadowsocks = queue_shadowsocks
        self.queue_trojan = queue_trojan
        self.queue_vless = queue_vless
        self.queue_vmess = queue_vmess
        self.redis = None
        # сохраняем виджет

    def count_orders(self, data_list):
        """Подсчитывает количество прокси по каждому порядку"""
        orders = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0}
        for item in data_list:
            if isinstance(item, dict):
                for key in ["1", "2", "3", "4", "5", "6"]:
                    if key in item:
                        orders[key] += len(item[key])
        return orders

    async def _get_redis(self):
        """Ленивое подключение к Redis (один раз)"""
        if self.redis is None:
            self.redis = await redis.from_url(
                "redis://localhost:6379/1", decode_responses=True
            )
            await self.redis.ping()
            write_top("✅ Redis подключен")
        return self.redis

    async def save_json(self, key: str, data: dict):
        """Сохраняет любой словарь как JSON строку (ПЕРЕЗАПИСЫВАЕТ)"""
        redis_client = await self._get_redis()
        await redis_client.set(key, json.dumps(data))
        write_top(f"📊 Сохранён JSON {key} в Redis (перезапись)")

    async def save_json_merge(self, key: str, new_data: dict):
        """
        Сохраняет данные, ОБЪЕДИНЯЯ с существующими (не перезаписывает)
        Специально для формата {"1": [...], "2": [...], ...}
        """
        redis_client = await self._get_redis()

        # Получаем старые данные
        old_raw = await redis_client.get(key)

        if old_raw is None:
            old_data = {}
            write_top(f"📊 Первая запись для {key}")
        else:
            try:
                old_data = json.loads(old_raw)
                write_top(
                    f"📊 Обновление {key} (было {sum(len(v) for v in old_data.values() if isinstance(v, list))} прокси)"
                )
            except json.JSONDecodeError:
                write_top(f"⚠️ Ошибка парсинга для {key}, создаём новую запись")
                old_data = {}

        # Объединяем данные
        added_count = 0
        for order, new_proxies in new_data.items():
            if not isinstance(new_proxies, list):
                write_top(f"⚠️ {order} не является списком, пропускаем")
                continue

            if order in old_data and isinstance(old_data[order], list):
                old_data[order].extend(new_proxies)
            else:
                old_data[order] = new_proxies
            added_count += len(new_proxies)

        # Сохраняем
        await redis_client.set(key, json.dumps(old_data))
        total_count = sum(len(v) for v in old_data.values() if isinstance(v, list))
        write_top(
            f"📊 Обновлён {key} в Redis (добавлено {added_count} прокси, всего {total_count})"
        )

    async def get_json(self, key: str) -> Optional[dict]:
        """Получает JSON строку и преобразует обратно в словарь"""
        redis_client = await self._get_redis()
        data = await redis_client.get(key)
        return json.loads(data) if data else None

    async def main_sortiring(self, data):
        """Основная сортировка данных"""
        # Подключаемся к Redis (один раз)
        await self._get_redis()

        # Сохраняем новые данные (НЕ перезаписываем, а дополняем)
        if "http" in data and data["http"] is not None:
            await self.save_json_merge("stats:http", data["http"])

        if "https" in data and data["https"] is not None:
            await self.save_json_merge("stats:https", data["https"])

        if "socks" in data and data["socks"] is not None:
            await self.save_json_merge("stats:socks", data["socks"])

        if "trojan" in data and data["trojan"] is not None:
            await self.save_json_merge("stats:trojan", data["trojan"])

        if "shadowsocks" in data and data["shadowsocks"] is not None:
            await self.save_json_merge("stats:shadowsocks", data["shadowsocks"])

        if "vless" in data and data["vless"] is not None:
            await self.save_json_merge("stats:vless", data["vless"])

        if "vmess" in data and data["vmess"] is not None:
            await self.save_json_merge("stats:vmess", data["vmess"])

        # Загружаем ВСЕ данные из Redis
        http_data = await self.get_json("stats:http") or {}
        https_data = await self.get_json("stats:https") or {}
        socks_data = await self.get_json("stats:socks") or {}
        trojan_data = await self.get_json("stats:trojan") or {}
        shadowsocks_data = await self.get_json("stats:shadowsocks") or {}
        vless_data = await self.get_json("stats:vless") or {}
        vmess_data = await self.get_json("stats:vmess") or {}

        await linuxdomainsocket.server_data("http", http_data)
        await linuxdomainsocket.server_data("https", https_data)
        await linuxdomainsocket.server_data("socks5", socks_data)
        await linuxdomainsocket.server_data("shadowsocks", shadowsocks_data)
        await linuxdomainsocket.server_data("trojan", trojan_data)
        await linuxdomainsocket.server_data("vless", vless_data)
        await linuxdomainsocket.server_data("vmess", vmess_data)

        # cortage_data = [
        #     http_data,
        #     https_data,
        #     socks_data,
        #     shadowsocks_data,
        #     trojan_data,
        #     vless_data,
        #     vmess_data,
        # ]
        # await linuxdomainsocket.server_data(cortage_data)
        # # await self.server_data(http_data)

        # Собираем статистику для таблицы (только длины)
        def get_counts(data_dict):
            return {
                "1": len(data_dict.get("1", [])),
                "2": len(data_dict.get("2", [])),
                "3": len(data_dict.get("3", [])),
                "4": len(data_dict.get("4", [])),
                "5": len(data_dict.get("5", [])),
                "6": len(data_dict.get("6", [])),
            }

        stats_data = {
            "🌐 HTTP": get_counts(http_data),
            "🔒 HTTPS": get_counts(https_data),
            "🧦 SOCKS5": get_counts(socks_data),
            "🦠 Trojan": get_counts(trojan_data),
            "🛡️ Shadowsocks": get_counts(shadowsocks_data),
            "⚡ VLESS": get_counts(vless_data),
            "🚀 VMess": get_counts(vmess_data),
        }

        update_table(stats_data)

    #
    # async def server_data(self, data):
    #     """Отправляет данные через Unix socket"""
    #     # Проверяем существование сокета
    #     if not os.path.exists(self.path_socket):
    #         write_top("Socket LDS not created")
    #         return None
    #
    #     reader = None
    #     writer = None
    #     try:
    #         # Подключаемся к сокету
    #         reader, writer = await asyncio.open_unix_connection(path=self.path_socket)
    #         write_top("✅ Подключение к сокету установлено")
    #
    #         # Преобразуем данные в JSON строку и отправляем
    #         message = json.dumps(data).encode()
    #         writer.write(message)
    #         await writer.drain()
    #         write_top(f"📤 Отправлено {len(message)} байт")
    #
    #         # Получаем ответ (с таймаутом)
    #         try:
    #             response = await asyncio.wait_for(reader.read(1024), timeout=5.0)
    #             write_top(f"📥 Получен ответ: {response.decode()}")
    #             return response.decode()
    #         except asyncio.TimeoutError:
    #             write_top("⚠️ Таймаут ожидания ответа от сервера")
    #             return None
    #
    #     except ConnectionRefusedError:
    #         write_top("❌ Сервер не запущен")
    #         return None
    #     except Exception as e:
    #         write_top(f"❌ Ошибка при отправке данных: {e}")
    #         return None
    #     finally:
    #         # Закрываем соединение
    #         if writer:
    #             writer.close()
    #             await writer.wait_closed()
    #             write_top("🔌 Соединение закрыто")
