# client.py
import asyncio
import socket

SOCKET_PATH = "/tmp/test_socket.sock"


async def connect_to_server(socket_path=SOCKET_PATH):
    """Подключается к Unix domain socket серверу"""
    try:
        reader, writer = await asyncio.open_unix_connection(path=socket_path)
        print("✅ Подключение к серверу установлено")
        return reader, writer
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return None, None


async def send_handshake(writer, handshake_msg="HELLO_FROM_CLIENT"):
    """Отправляет рукопожатие"""
    writer.write(handshake_msg.encode())
    await writer.drain()
    print(f"📤 Отправлено рукопожатие: {handshake_msg}")

    # Ждём ответ
    reader, _ = writer  # нужно передать reader отдельно
    return reader


async def send_message(writer, message):
    """Отправляет сообщение серверу"""
    writer.write(message.encode())
    await writer.drain()
    print(f"📤 Отправлено сообщение: {message}")


async def receive_response(reader):
    """Получает ответ от сервера"""
    response = await reader.read(1024)
    response_msg = response.decode().strip()
    print(f"📥 Получен ответ: {response_msg}")
    return response_msg


async def main():
    # 1. Подключаемся к серверу
    reader, writer = await connect_to_server()
    if not reader or not writer:
        return

    # 2. Отправляем рукопожатие
    handshake_msg = "HELLO_FROM_CLIENT"
    writer.write(handshake_msg.encode())
    await writer.drain()
    print(f"📤 Отправлено рукопожатие: {handshake_msg}")

    # 3. Получаем подтверждение рукопожатия
    response = await reader.read(1024)
    print(f"📥 Получено подтверждение: {response.decode()}")

    # 4. Отправляем несколько сообщений
    messages = ["Hello, Server!", "How are you?", "This is test message 3", "Goodbye!"]

    for msg in messages:
        await send_message(writer, msg)
        await receive_response(reader)
        await asyncio.sleep(0.5)

    # 5. Закрываем соединение
    writer.close()
    await writer.wait_closed()
    print("🔌 Соединение закрыто")


if __name__ == "__main__":
    asyncio.run(main())
