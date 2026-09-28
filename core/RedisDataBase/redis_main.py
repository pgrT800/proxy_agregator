import asyncio
import json
from typing import Dict, List, Optional, Union

import redis.asyncio as redis

from core.tui_global_set import write_top


class RedisStorage:
    def __init__(self, host="localhost", port=6379, db=1):
        self.redis = None
        self.host = host
        self.port = port
        self.db = db

    async def connect(self):
        try:
            self.redis = await redis.from_url(
                f"redis://{self.host}:{self.port}/{self.db}", decode_responses=True
            )
            if await self.redis.ping():
                write_top("✅ Redis подключен")
                return self.redis
        except Exception as e:
            write_top(f"❌ Ошибка подключения к Redis: {e}")
            self.redis = None
            return None

    async def save_list(self, key: str, data: list):
        """Сохраняет список как JSON строку"""
        if self.redis is None:
            return
        await self.redis.set(key, json.dumps(data))
        write_top(f"📊 Сохранён список {key} в Redis")

    async def get_list(self, key: str) -> Optional[list]:
        """Получает список из Redis"""
        if self.redis is None:
            return None
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def save_dict(self, key: str, data: dict):
        """Сохраняет словарь как хэш"""
        if self.redis is None:
            return
        await self.redis.hset(key, mapping=data)
        write_top(f"📊 Сохранён хэш {key} в Redis")

    async def get_dict(self, key: str) -> Optional[dict]:
        """Получает хэш из Redis"""
        if self.redis is None:
            return None
        data = await self.redis.hgetall(key)
        return {k: int(v) for k, v in data.items()} if data else None

    async def get(self, key: str) -> Optional[str]:
        """Получает строковое значение по ключу"""
        if self.redis is not None:
            return await self.redis.get(key)
        return None

    async def set(self, key: str, new_orders: dict):
        """
        Специально для формата {"1": [...], "2": [...], ...}
        Объединяет списки прокси по каждому порядку
        """
        if self.redis is None:
            return

        # Если data - строка, пробуем распарсить JSON
        if isinstance(key, str):
            try:
                data = json.loads(key)
                write_top(f"📦 Распарсена строка в JSON для {key}")
            except json.JSONDecodeError:
                write_top(f"❌ Ошибка: не удалось распарсить строку для {key}")
                return

        # Если data - не словарь после парсинга, ошибка
        if not isinstance(data, dict):
            write_top(f"❌ Ошибка: ожидался словарь, получен {type(data)}")
            return

        # Получаем старые данные
        old_raw = await self.redis.get(key)

        # Если данных нет, создаём пустой словарь
        if old_raw is None:
            old_orders = {}
            write_top(f"📊 Первая запись для {key}")
        else:
            try:
                old_orders = json.loads(old_raw)
                if not isinstance(old_orders, dict):
                    old_orders = {}
                write_top(
                    f"📊 Обновление {key} (было {sum(len(v) for v in old_orders.values() if isinstance(v, list))} прокси)"
                )
            except json.JSONDecodeError:
                write_top(f"⚠️ Ошибка парсинга JSON для {key}, создаём новую запись")
                old_orders = {}

        # Объединяем
        added_count = 0
        for order, new_proxies in new_orders.items():
            # Проверяем, что new_proxies - список
            if not isinstance(new_proxies, list):
                write_top(f"⚠️ {order} не является списком, пропускаем")
                continue

            if order in old_orders and isinstance(old_orders[order], list):
                old_orders[order].extend(new_proxies)
            else:
                old_orders[order] = new_proxies
            added_count += len(new_proxies)

        # Сохраняем
        try:
            await self.redis.set(key, json.dumps(old_orders))
            total_count = sum(
                len(v) for v in old_orders.values() if isinstance(v, list)
            )
            write_top(
                f"📊 Обновлён {key} в Redis (добавлено {added_count} прокси, всего {total_count})"
            )
        except Exception as e:
            write_top(f"❌ Ошибка сохранения {key}: {e}")

    async def flush_all(self):
        """Полностью очищает текущую базу данных Redis"""
        if self.redis is None:
            write_top("❌ Redis не подключён — нечего очищать")
            return False

        try:
            await self.redis.flushdb()
            write_top("🗑️ База данных Redis полностью очищена")
            return True
        except Exception as e:
            write_top(f"❌ Ошибка очистки Redis: {e}")
            return False
