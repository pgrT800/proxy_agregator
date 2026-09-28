# test_redis.py
import asyncio

import redis.asyncio as redis


async def test_redis():
    """Простой тест подключения к Redis"""

    print("🔍 Тестируем подключение к Redis...")

    # Параметры подключения (по умолчанию)
    host = "localhost"
    port = 6379

    try:
        # 1. Подключаемся
        print(f"📡 Подключаюсь к {host}:{port}...")
        r = await redis.from_url(f"redis://{host}:{port}/0", decode_responses=True)

        # 2. Проверяем пинг
        print("📡 Отправляю PING...")
        response = await r.ping()

        if response:
            print("✅ PONG! Redis работает!")
        else:
            print("❌ Redis не ответил на PING")
            return

        stats_data = {
            "🌐 HTTP": {"1": 150, "2": 300, "3": 100},
            "🔒 HTTPS": {"1": 200, "2": 400, "3": 50},
            "🧦 SOCKS5": {"1": 100, "2": 200, "3": 75},
        }

        # === СОХРАНЕНИЕ КАК ХЭШ ===

        # Способ 1: Каждый протокол - отдельный хэш
        for protocol, orders in stats_data.items():
            await r.hset(f"stats:{protocol}", mapping=orders)
        protocol = "🌐 HTTP"
        data = await r.hgetall(f"stats:{protocol}")
        # Результат: {"1": "150", "2": "300", "3": "100"}

        # Преобразуем строки в числа
        orders = {k: int(v) for k, v in data.items()}
        print(orders)
        # Результат: {"1": 150, "2": 300, "3": 100}

        # # 3. Тестовые операции
        # print("\n📦 Тестовые операции:")
        #
        # # SET
        # await r.set("test_key", "Hello Redis!")
        # print("   ✅ SET test_key = 'Hello Redis!'")
        #
        # # GET
        # value = await r.get("test_key")
        # print(f"   ✅ GET test_key = '{value}'")
        #
        # # DELETE
        # await r.delete("test_key")
        # print("   ✅ DELETE test_key")
        #
        # # Проверяем что удалилось
        # value = await r.get("test_key")
        # print(f"   ✅ Проверка: test_key = {value}")
        #
        # print("\n🎉 Все тесты пройдены успешно!")
        #
        # 4. Закрываем соединение
        await r.aclose()

    except redis.exceptions.ConnectionError as e:
        print(f"\n❌ ОШИБКА: Не удалось подключиться к Redis!")
        print(f"   Детали: {e}")
        print("\n💡 Решение:")
        print("   1. Установи Redis: sudo apt install redis-server  # Ubuntu/Debian")
        print("   2. Или: sudo pacman -S redis  # Arch Linux")
        print("   3. Запусти Redis: sudo systemctl start redis")
        print("   4. Проверь статус: redis-cli ping")

    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")


async def main():
    print("=" * 50)
    print("🧪 ТЕСТОВЫЙ СТЕНД REDIS")
    print("=" * 50)
    await test_redis()


if __name__ == "__main__":
    asyncio.run(main())
