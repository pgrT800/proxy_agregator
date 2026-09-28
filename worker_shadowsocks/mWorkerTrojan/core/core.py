# worker_shadowsocks/mWorkerTrojan/worker.py
import asyncio
import base64
import os
import re
import sys
import uuid
import warnings
from urllib.parse import parse_qs, urlparse

import aiohttp

from core.custom_widget import register_task, update_task
from core.StateManager.stateCore.stateCore import (
    StateManager,
    loop_r,
    loop_w,
    statemanager,
)
from core.TaskRegisterMainInit.TaskRegister import taskregister
from core.tui_global_set import write_top
from worker_shadowsocks.getData.datagit import GitHttp
from worker_shadowsocks.mWorkerTrojan.checker.checker import CheckerTrojan
from worker_shadowsocks.mWorkerTrojan.validator.validator import ValidatorTrojan

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def parse_trojan_url(line: str) -> dict | None:
    """
    Парсит trojan:// строку в словарь с host, port, password, sni и т.д.
    Формат: trojan://password@host:port?allowInsecure=1&sni=example.com#name
    """
    line = line.strip()

    # Пропускаем строки с другими протоколами
    if any(x in line for x in ["vmess://", "vless://", "ss://", "ssr://"]):
        return None

    if not line.startswith("trojan://"):
        return None

    # Убираем trojan://
    raw = line[9:]

    # Убираем комментарий после #
    if "#" in raw:
        raw = raw.split("#")[0]

    # Разделяем на часть до ? (основные параметры) и параметры
    if "?" in raw:
        base_part, query_part = raw.split("?", 1)
        params = parse_qs(query_part)
    else:
        base_part = raw
        params = {}

    # Очищаем base_part от лишних символов в конце
    base_part = base_part.rstrip("/")

    # Парсим password@host:port
    password = ""
    host = ""
    port = 443

    if "@" in base_part:
        password, host_port = base_part.split("@", 1)
        if ":" in host_port:
            host, port_str = host_port.rsplit(":", 1)
            port_str = re.sub(r"[^\d]", "", port_str)
            try:
                port = int(port_str)
            except ValueError:
                port = 443
        else:
            host = host_port
    else:
        if ":" in base_part:
            host, port_str = base_part.rsplit(":", 1)
            port_str = re.sub(r"[^\d]", "", port_str)
            try:
                port = int(port_str)
            except ValueError:
                port = 443
        else:
            host = base_part

    # Извлекаем параметры
    sni = params.get("sni", [None])[0]
    allow_insecure = params.get("allowInsecure", [False])[0] == "1"
    security = params.get("security", ["tls"])[0]
    type_ = params.get("type", ["tcp"])[0]

    host = host.rstrip("/").lstrip("/")

    result = {
        "host": host,
        "port": port,
        "password": password,
        "type": "trojan",
    }

    if sni:
        result["sni"] = sni
    if allow_insecure:
        result["allow_insecure"] = allow_insecure
    if security != "tls":
        result["security"] = security
    if type_ != "tcp":
        result["type_protocol"] = type_

    return result


def distribute_by_percent(lst: list, percent: int = 5) -> list:
    if not isinstance(lst, list):
        raise TypeError(f"Ожидался список, получен {type(lst).__name__}")
    if not isinstance(percent, int):
        raise TypeError(
            f"Процент должен быть целым числом, получен {type(percent).__name__}"
        )
    if percent <= 0 or percent > 100:
        raise ValueError(f"Процент должен быть от 1 до 100, получен {percent}")
    if not lst:
        return []
    if len(lst) == 1:
        return [lst]
    if percent == 100:
        return [lst]

    total = len(lst)
    chunk_size = int(total * percent / 100)
    if chunk_size == 0:
        chunk_size = 1
    if chunk_size >= total:
        return [lst]

    parts = []
    start = 0
    while start < total:
        end = min(start + chunk_size, total)
        parts.append(lst[start:end])
        start = end

    if len(parts) > 1 and len(parts[-1]) < chunk_size:
        remainder = parts.pop()
        for i, item in enumerate(remainder):
            parts[i % len(parts)].append(item)
    return parts


# === WRITER: кладёт прокси в очередь чанка ===
async def writer_trojan(chunk: list, queue_dict: dict, task_id: str):
    """Producer: кладёт распарсенные прокси в очередь для reader"""
    queue_writer = queue_dict[f"queue-{task_id}"]

    update_task(
        task_id,
        total=len(chunk),
        stage="📥 Queue",
        progress=0,
        processed=len(chunk),
    )

    for item in chunk:
        if item is not None:
            await queue_writer.put(item)

    await queue_writer.put("Done")  # Сигнал завершения для reader
    write_top(f"✍️ Writer {task_id}: отправлено {len(chunk)} прокси")


# === READER: забирает из очереди, проверяет, валидирует, шлёт в target ===
async def reader_trojan(
    queue_dict: dict,
    task_id: str,
    target_queue: asyncio.Queue,
    semaphore_limit: asyncio.Semaphore,
    queue_name: str = "trojan",
):
    """Consumer: проверяет и валидирует прокси из очереди"""
    checker = CheckerTrojan()
    validator = ValidatorTrojan()
    queue_reader = queue_dict[f"queue-{task_id}"]

    # update_task(task_id, status="running")  # опционально

    while True:
        item = await queue_reader.get()

        if item == "Done":
            write_top(f"🔚 Reader {task_id}: получен сигнал завершения")
            break

        if item is None:
            update_task(task_id, add=1)
            continue

        try:
            # 1️⃣ TCP check (через checker)
            result_checker = await checker.checker(item, semaphore_limit, task_id)
            proxy_dict, is_alive = result_checker

            if is_alive:
                write_top(
                    f"✅ Trojan жив: {proxy_dict.get('host')}:{proxy_dict.get('port')}"
                )
                await asyncio.sleep(0.1)
                # 2️⃣ Protocol validation (через validator)
                result_validate = await validator.validate_proxy(
                    proxy_dict, semaphore_limit
                )

                if result_validate:
                    item_result = {"trojan": result_validate}
                    await target_queue.put(item_result)
                    write_top(f"🎯 Valid Trojan добавлен в результат")

            update_task(task_id, add=1)

        except Exception as e:
            write_top(f"❌ Ошибка обработки {item.get('host', 'unknown')}: {e}")
            update_task(task_id, add=1)
            continue

    update_task(task_id, status="done", stage="✅ Завершён")


# === MAIN WORKER: точная копия архитектуры Shadowsocks ===
async def worker_trojan(
    list_proxis: list,
    target_queue: asyncio.Queue,
    protocol: str = "trojan",
    semaphore_limit: int = 10,
    queue_name: str = "trojan",
):
    """Главная функция Trojan-воркера по шаблону Shadowsocks"""

    # Локальный семафор для ограничения параллельных чанков
    semaphore_local = asyncio.Semaphore(15)
    task_reader_state = asyncio.create_task(loop_r(protocol="trojan"))
    await statemanager.set_reader_task("trojan", task_reader_state)

    list_fitering = await statemanager.filteringData(
        protocol="trojan", list_in=list_proxis
    )
    write_top(f"ОТфильрованно {len(list_proxis)-len(list_fitering)}")
    # Собираем все данные
    if list_fitering is not None:
        list_proxis = list_fitering
    # Парсим прокси
    list_proxis_clean = []
    for line in list_proxis:
        proxy = parse_trojan_url(line)
        if proxy is not None:
            list_proxis_clean.append(proxy)

    total_proxies = len(list_proxis_clean)
    write_top(f"📊 Trojan: всего прокси = {total_proxies}")

    if not list_proxis_clean:
        write_top("❌ Нет данных для обработки Trojan")
        await target_queue.put("Done")
        return

    # 2️⃣ Разбивка на чанки (20% = ~5 воркеров)
    chunks = distribute_by_percent(list_proxis_clean, percent=10)
    write_top(f"📦 Создано {len(chunks)} чанков")
    write_top(f"📊 Размеры чанков: {[len(c) for c in chunks]}")

    list_task_writer = []
    list_task_reader = []

    async with semaphore_local:
        # Семафор для ограничения параллельных запросов внутри reader
        semaphore_for_rt = asyncio.Semaphore(semaphore_limit)

        for idx, chunk in enumerate(chunks):
            task_id = f"trojan-{uuid.uuid4().hex[:8]}"
            await register_task(task_id, f"🦠 ", protocol=protocol)

            # Создаём очередь для коммуникации writer→reader
            queue_obj = asyncio.Queue()
            queue_dict = {f"queue-{task_id}": queue_obj}

            # 📤 Writer task: кладёт прокси в очередь
            task_writer = asyncio.create_task(
                writer_trojan(queue_dict=queue_dict, chunk=chunk, task_id=task_id)
            )
            # await taskregister.add_task_register(task_writer)
            list_task_writer.append(task_writer)

            # 📥 Reader task: забирает, проверяет, валидирует, шлёт в target
            task_reader = asyncio.create_task(
                reader_trojan(
                    queue_dict=queue_dict,
                    task_id=task_id,
                    target_queue=target_queue,
                    semaphore_limit=semaphore_for_rt,
                    queue_name=queue_name,
                )
            )
            # await taskregister.add_task_register(task_reader)
            list_task_reader.append(task_reader)
        list_task_reader.append(task_reader_state)
        # Ждём завершения всех writer'ов
        await asyncio.gather(*list_task_writer)
        # Ждём завершения всех reader'ов
        await asyncio.gather(*list_task_reader)
    # Сигнал завершения для внешнего потребителя target_queue
    await target_queue.put("Done")
    # write_top(f"🏁 Trojan worker завершил работу")
