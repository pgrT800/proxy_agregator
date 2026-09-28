import asyncio
import gc
import os
import re
import resource
import sys
import uuid
from urllib.parse import parse_qs, unquote, urlparse

from core.custom_widget import register_task, update_task
from core.StateManager.stateCore.stateCore import (
    StateManager,
    loop_r,
    loop_w,
    statemanager,
)
from core.TaskRegisterMainInit.TaskRegister import taskregister
from core.tui_global_set import write_top
from worker_shadowsocks.mWorkerVless.checker.checker import CheckerVless
from worker_shadowsocks.mWorkerVless.validator.validator import ValidatorVless

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def parse_vless_url(line: str) -> dict | None:
    """
    Парсит vless:// строку и возвращает словарь с host, port, и uuid (если есть).
    """
    line = line.strip()
    if not line.startswith("vless://"):
        return None

    raw = line[8:].split("#")[0]

    uuid_match = re.search(
        r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
        raw,
        re.IGNORECASE,
    )
    if not uuid_match:
        return None

    uuid = uuid_match.group(1)

    host_port_match = re.search(rf"{re.escape(uuid)}@([^:?]+):(\d+)", raw)
    if not host_port_match:
        return None

    host = host_port_match.group(1)
    port = int(host_port_match.group(2))

    return {"host": host, "port": port, "uuid": uuid, "type": "vless"}


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
async def writer_vless(chunk: list, queue_dict: dict, task_id: str):
    """Producer: кладёт распарсенные прокси в очередь для reader"""
    queue_writer = queue_dict[f"queue-{task_id}"]

    update_task(
        task_id, total=len(chunk), stage="📥 Queue", progress=0, processed=len(chunk)
    )

    for item in chunk:
        if item is not None:
            await queue_writer.put(item)

    await queue_writer.put("Done")
    write_top(f"✍️ Writer {task_id}: отправлено {len(chunk)} прокси")


# === READER: забирает из очереди, проверяет, валидирует, шлёт в target ===
async def reader_vless(
    queue_dict: dict,
    task_id: str,
    target_queue: asyncio.Queue,
    semaphore_limit: asyncio.Semaphore,
    queue_name: str = "vless",
):
    """Consumer: проверяет и валидирует прокси из очереди"""
    checker = CheckerVless()
    validator = ValidatorVless()
    queue_reader = queue_dict[f"queue-{task_id}"]

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
                    f"✅ VLESS жив: {proxy_dict.get('host')}:{proxy_dict.get('port')}"
                )

                # 2️⃣ Protocol validation (через validator)
                result_validate = await validator.validate_proxy(
                    proxy_dict, semaphore_limit
                )

                if result_validate:
                    item_result = {"vless": result_validate}
                    await target_queue.put(item_result)
                    write_top(f"🎯 Valid VLESS добавлен в результат")

            update_task(task_id, add=1)

        except Exception as e:
            write_top(f"❌ Ошибка обработки {item.get('host', 'unknown')}: {e}")
            update_task(task_id, add=1)
            continue

    update_task(task_id, status="done", stage="✅ Завершён")


# === MAIN WORKER: точная копия архитектуры Trojan ===
async def core_worker_vless(
    list_proxis: list,
    target_queue: asyncio.Queue,
    protocol: str = "vless",
    semaphore_limit: int = 10,
    queue_name: str = "vless",
):
    """Главная функция VLESS-воркера по шаблону Trojan"""

    # Увеличиваем лимит открытых файлов
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))
    except:
        pass
    # Локальный семафор для ограничения параллельных чанков
    semaphore_local = asyncio.Semaphore(10)
    task_reader_state = asyncio.create_task(loop_r(protocol="vless"))
    await statemanager.set_reader_task("vless", task_reader_state)

    list_fitering = await statemanager.filteringData(
        protocol="vless", list_in=list_proxis
    )
    write_top(f"ОТфильрованно {len(list_proxis)-len(list_fitering)}")
    # Собираем все данные
    if list_fitering is not None:
        list_proxis = list_fitering
    # 1️⃣ Парсинг входных данных
    list_proxis_clean = []
    for line in list_proxis:
        try:
            proxy = parse_vless_url(line)
            if proxy is not None and proxy.get("host"):
                list_proxis_clean.append(proxy)
        except Exception as e:
            write_top(f"⚠️ Ошибка парсинга VLESS: {e}")
            continue

    total_proxies = len(list_proxis_clean)
    write_top(f"📊 VLESS: всего прокси = {total_proxies}")

    if not list_proxis_clean:
        write_top("❌ Нет данных для обработки VLESS")
        await target_queue.put("Done")
        return

    # 2️⃣ Разбивка на чанки
    chunks = distribute_by_percent(list_proxis_clean, percent=10)
    write_top(f"📦 Создано {len(chunks)} чанков")
    write_top(f"📊 Размеры чанков: {[len(c) for c in chunks]}")

    list_task_writer = []
    list_task_reader = []

    async with semaphore_local:
        # Семафор для ограничения параллельных запросов внутри reader
        semaphore_for_rt = asyncio.Semaphore(semaphore_limit)

        for idx, chunk in enumerate(chunks):
            task_id = f"vless-{uuid.uuid4().hex[:8]}"
            await register_task(task_id, f"⚡ ", protocol=protocol)

            # Создаём очередь для коммуникации writer→reader
            queue_obj = asyncio.Queue()
            queue_dict = {f"queue-{task_id}": queue_obj}

            # 📤 Writer task: кладёт прокси в очередь
            task_writer = asyncio.create_task(
                writer_vless(queue_dict=queue_dict, chunk=chunk, task_id=task_id)
            )
            list_task_writer.append(task_writer)

            # 📥 Reader task: забирает, проверяет, валидирует, шлёт в target
            task_reader = asyncio.create_task(
                reader_vless(
                    queue_dict=queue_dict,
                    task_id=task_id,
                    target_queue=target_queue,
                    semaphore_limit=semaphore_for_rt,
                    queue_name=queue_name,
                )
            )
            list_task_reader.append(task_reader)
        list_task_reader.append(task_reader_state)
        # Ждём завершения всех writer'ов
        await asyncio.gather(*list_task_writer)
        # Ждём завершения всех reader'ов
        await asyncio.gather(*list_task_reader)

    # Сигнал завершения для внешнего потребителя target_queue
    await target_queue.put("Done")
    write_top("✅ VLESS воркер завершён")
