import asyncio
import json


async def send_request(message: str) -> str:
    socket_path = "/tmp/my_socket_for_server.sock"

    try:
        reader, writer = await asyncio.open_unix_connection(socket_path)

        # Отправляем запрос
        writer.write(message.encode())
        await writer.drain()
        print(f"📤 Отправлено: {message}")

        # Читаем ВСЕ данные до закрытия соединения
        chunks = []
        while True:
            chunk = await reader.read(8192)
            if not chunk:
                break
            chunks.append(chunk)

        result = b"".join(chunks).decode()
        print(f"📥 Получено: {len(result)} байт")
        print(result)
        writer.close()
        await writer.wait_closed()

        return result

    except FileNotFoundError:
        print("❌ Сервер не запущен")
        return None
    except ConnectionRefusedError:
        print("❌ Сервер не принимает подключения")
        return None


# async def test_get_proxy():
#     result = await send_request("proxy:socks5")
#     if result:
#         data = json.loads(result)
#         stage_one = data.get("proxi", {})
#         print(f"1-й порядок: {len(stage_one.get('1', []))} прокси")
#         print(f"2-й порядок: {len(stage_one.get('2', []))} прокси")
#
async def test_get_proxy():
    result = await send_request("proxy:http")
    if result:
        data = json.loads(result)  # теперь это сразу {"1": [...], "2": [...], ...}
        print(f"1-й порядок: {len(data.get('1', []))} прокси")
        print(f"2-й порядок: {len(data.get('2', []))} прокси")
        print(f"5-й порядок: {len(data.get('5', []))} прокси")


if __name__ == "__main__":
    asyncio.run(test_get_proxy())
# import asyncio
# import json
#
#
# async def send_request(message: str) -> str:
#     """Подключиться к LDS-серверу, отправить запрос, получить ответ"""
#     socket_path = "/tmp/my_socket_for_server.sock"
#
#     try:
#         reader, writer = await asyncio.open_unix_connection(socket_path)
#
#         # Отправляем запрос
#         writer.write(message.encode())
#         await writer.drain()
#         print(f"📤 Отправлено: {message}")
#
#         # Читаем ответ
#         response = await reader.read(4096)
#         result = response.decode()
#         print(f"📥 Получено: {result}")
#
#         writer.close()
#         await writer.wait_closed()
#
#         return result
#
#     except FileNotFoundError:
#         print("❌ Сервер не запущен — файл сокета не найден")
#         return None
#     except ConnectionRefusedError:
#         print("❌ Сервер не принимает подключения")
#         return None
#
#
# # === Тестовые запросы ===
#
#
# async def test_get_proxy():
#     """Запросить прокси у Мозгов"""
#     result = await send_request("proxy")
#     if result:
#         data = json.loads(result)
#         print(f"Получены прокси: {data.get('proxi')}")
#
#
# async def test_unknown():
#     """Отправить неизвестную команду"""
#     result = await send_request("PING")
#     print(f"Ответ сервера: {result}")
#
#
# # === Запуск ===
#
# if __name__ == "__main__":
#     asyncio.run(test_get_proxy())
#     # asyncio.run(test_unknown())
