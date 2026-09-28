import asyncio
import base64
import gc
import json
import os
import re
import resource
import sys
import uuid
from urllib.parse import parse_qs, urlparse

from core.custom_widget import register_task, update_task
from core.StateManager.stateCore.stateCore import (
    StateManager,
    loop_r,
    loop_w,
    statemanager,
)
from core.TaskRegisterMainInit.TaskRegister import taskregister
from core.tui_global_set import write_top
from worker_shadowsocks.mWorkerVmell.checker.checker import CheckerVmess
from worker_shadowsocks.mWorkerVmell.validator.validator import ValidatorVmess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def parse_vmess_url(line: str) -> dict | None:
    """
    Парсит vmess:// строку в словарь
    Формат: vmess://base64(json)
    """
    line = line.strip()
    if not line.startswith("vmess://"):
        return None

    raw = line[8:]

    if "#" in raw:
        raw = raw.split("#")[0]

    if "?" in raw:
        raw = raw.split("?")[0]

    try:
        padding = 4 - (len(raw) % 4)
        if padding != 4:
            raw += "=" * padding

        decoded = base64.b64decode(raw).decode("utf-8")
        config = json.loads(decoded)

        result = {
            "host": config.get("add", ""),
            "port": int(config.get("port", 0)),
            "uuid": config.get("id", ""),
            "aid": int(config.get("aid", "0")),
            "security": config.get("scy", "auto"),
            "type": "vmess",
        }

        network = config.get("net", "tcp")
        result["network"] = network

        if network == "ws":
            result["path"] = config.get("path", "/")
            result["host_header"] = config.get("host", "")

        tls = config.get("tls", "")
        if tls == "tls":
            result["security"] = "tls"
            result["sni"] = config.get("sni", "")
            result["fingerprint"] = config.get("fp", "chrome")
            result["alpn"] = config.get("alpn", "http/1.1")

        return result

    except Exception as e:
        write_top(f"⚠️ Ошибка парсинга VMess: {e}")
        return None


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
async def writer_vmess(chunk: list, queue_dict: dict, task_id: str):
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
async def reader_vmess(
    queue_dict: dict,
    task_id: str,
    target_queue: asyncio.Queue,
    semaphore_limit: asyncio.Semaphore,
    queue_name: str = "vmess",
):
    """Consumer: проверяет и валидирует прокси из очереди"""
    checker = CheckerVmess()
    validator = ValidatorVmess()
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
                    f"✅ VMess жив: {proxy_dict.get('host')}:{proxy_dict.get('port')}"
                )

                # 2️⃣ Protocol validation (через validator)
                result_validate = await validator.validate_proxy(
                    proxy_dict, semaphore_limit
                )

                if result_validate:
                    item_result = {"vmess": result_validate}
                    await target_queue.put(item_result)
                    write_top(f"🎯 Valid VMess добавлен в результат")

            update_task(task_id, add=1)

        except Exception as e:
            write_top(f"❌ Ошибка обработки {item.get('host', 'unknown')}: {e}")
            update_task(task_id, add=1)
            continue

    update_task(task_id, status="done", stage="✅ Завершён")


# === MAIN WORKER: точная копия архитектуры Trojan ===
async def core_worker_vmess(
    list_proxis: list,
    target_queue: asyncio.Queue,
    protocol: str = "vmess",
    semaphore_limit: int = 10,
    queue_name: str = "vmess",
):
    """Главная функция VMess-воркера по шаблону Trojan"""

    # Увеличиваем лимит открытых файлов
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))
    except:
        pass

    # Локальный семафор для ограничения параллельных чанков
    semaphore_local = asyncio.Semaphore(10)
    task_reader_state = asyncio.create_task(loop_r(protocol="vmess"))
    await statemanager.set_reader_task("vmess", task_reader_state)

    list_fitering = await statemanager.filteringData(
        protocol="vmess", list_in=list_proxis
    )
    write_top(f"ОТфильрованно {len(list_proxis)-len(list_fitering)}")
    # Собираем все данные
    if list_fitering is not None:
        list_proxis = list_fitering

    # 1️⃣ Парсинг входных данных
    list_proxis_clean = []
    for line in list_proxis:
        try:
            proxy = parse_vmess_url(line)
            if proxy and proxy.get("host") and proxy.get("port") and proxy.get("uuid"):
                list_proxis_clean.append(proxy)
        except Exception as e:
            write_top(f"⚠️ Ошибка парсинга VMess: {e}")
            continue

    total_proxies = len(list_proxis_clean)
    write_top(f"📊 VMess: всего прокси = {total_proxies}")

    if not list_proxis_clean:
        write_top("❌ Нет данных для обработки VMess")
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
            task_id = f"vmess-{uuid.uuid4().hex[:8]}"
            await register_task(task_id, f"🚀 ", protocol=protocol)

            # Создаём очередь для коммуникации writer→reader
            queue_obj = asyncio.Queue()
            queue_dict = {f"queue-{task_id}": queue_obj}

            # 📤 Writer task: кладёт прокси в очередь
            task_writer = asyncio.create_task(
                writer_vmess(queue_dict=queue_dict, chunk=chunk, task_id=task_id)
            )
            list_task_writer.append(task_writer)

            # 📥 Reader task: забирает, проверяет, валидирует, шлёт в target
            task_reader = asyncio.create_task(
                reader_vmess(
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
    write_top("✅ VMess воркер завершён")


# import asyncio
# import base64
# import gc
# import json
# import re
# import resource
# import uuid
# from urllib.parse import parse_qs, urlparse
#
# from core.custom_widget import register_task, update_task
# from core.tui_global_set import write_top
# from worker_shadowsocks.mWorkerVmell.checker.checker import CheckerVmess
# from worker_shadowsocks.mWorkerVmell.validator.validator import ValidatorVmess
#
#
# def parse_vmess_url(line: str) -> dict | None:
#     """
#     Парсит vmess:// строку в словарь
#
#     Формат: vmess://base64(json)
#     """
#     line = line.strip()
#     if not line.startswith("vmess://"):
#         return None
#
#     # Убираем vmess://
#     raw = line[8:]
#
#     # Убираем комментарий после #
#     if "#" in raw:
#         raw = raw.split("#")[0]
#
#     # Убираем параметры после ?
#     if "?" in raw:
#         raw = raw.split("?")[0]
#
#     # Декодируем Base64
#     try:
#         # Добавляем padding если нужно
#         padding = 4 - (len(raw) % 4)
#         if padding != 4:
#             raw += "=" * padding
#
#         decoded = base64.b64decode(raw).decode("utf-8")
#         config = json.loads(decoded)
#
#         # Базовые параметры
#         result = {
#             "host": config.get("add", ""),
#             "port": int(config.get("port", 0)),
#             "uuid": config.get("id", ""),
#             "aid": int(config.get("aid", "0")),
#             "security": config.get("scy", "auto"),
#             "type": "vmess",
#         }
#
#         # Сетевые параметры
#         network = config.get("net", "tcp")
#         result["network"] = network
#
#         if network == "ws":
#             result["path"] = config.get("path", "/")
#             result["host_header"] = config.get("host", "")
#
#         # TLS параметры
#         tls = config.get("tls", "")
#         if tls == "tls":
#             result["security"] = "tls"
#             result["sni"] = config.get("sni", "")
#             result["fingerprint"] = config.get("fp", "chrome")
#             result["alpn"] = config.get("alpn", "http/1.1")
#
#         return result
#
#     except Exception as e:
#         write_top(f"⚠️ Ошибка парсинга VMess: {e}")
#         return None
#
#
# def distribute_by_percent(lst: list, percent: int = 10) -> list:
#     """Распределяет элементы по чанкам с заданным процентом"""
#     if not isinstance(lst, list):
#         raise TypeError(f"Ожидался список, получен {type(lst).__name__}")
#
#     if not isinstance(percent, int):
#         raise TypeError(
#             f"Процент должен быть целым числом, получен {type(percent).__name__}"
#         )
#
#     if percent <= 0 or percent > 100:
#         raise ValueError(f"Процент должен быть от 1 до 100, получен {percent}")
#
#     if not lst:
#         return []
#
#     if len(lst) == 1:
#         return [lst]
#
#     if percent == 100:
#         return [lst]
#
#     total = len(lst)
#     chunk_size = int(total * percent / 100)
#
#     if chunk_size == 0:
#         chunk_size = 1
#
#     if chunk_size >= total:
#         return [lst]
#
#     parts = []
#     start = 0
#
#     while start < total:
#         end = min(start + chunk_size, total)
#         parts.append(lst[start:end])
#         start = end
#
#     if len(parts) > 1 and len(parts[-1]) < chunk_size:
#         remainder = parts.pop()
#         for i, item in enumerate(remainder):
#             parts[i % len(parts)].append(item)
#
#     return parts
#
#
# async def validate_corteg(proxy, semaphore, validator, queue, queue_name, task_id):
#     """Валидация одного прокси"""
#     data = await validator.validate_proxy(proxy, semaphore)
#     update_task(task_id, add=1)
#     if data is not None:
#         item = {queue_name: data}
#         await queue.put(item)
#     return data
#
#
# async def process_chunk(
#     queue, queue_name, semaphore, validator, chunk, checker, task_id
# ):
#     """Обрабатывает один чанк прокси"""
#
#     # Устанавливаем максимальное значение = размер чанка
#     update_task(
#         task_id, total=len(chunk), stage="🔍 TCP проверка", status="running", progress=0
#     )
#
#     # TCP проверка
#     list_task_checker = []
#     for proxy in chunk:
#         task = asyncio.create_task(checker.checker(proxy, semaphore, task_id))
#         list_task_checker.append(task)
#
#     result = await asyncio.gather(*list_task_checker)
#
#     # Собираем живые прокси (TCP открыт)
#     list_alive = []
#     for proxy, is_alive in result:
#         if is_alive:
#             list_alive.append(proxy)
#
#     write_top(f"✅ Чанк VMess: живых TCP = {len(list_alive)} из {len(chunk)}")
#
#     # Валидация живых прокси
#     if list_alive:
#         update_task(task_id, total=len(list_alive), stage="✅ Валидация", progress=0)
#
#         list_task_validator = []
#         for proxy in list_alive:
#             task = asyncio.create_task(
#                 validate_corteg(proxy, semaphore, validator, queue, queue_name, task_id)
#             )
#             list_task_validator.append(task)
#
#         if list_task_validator:
#             await asyncio.gather(*list_task_validator)
#
#     update_task(task_id, stage="✅ Завершён", status="done", progress=100)
#
#
# async def core_worker_vmess(list_proxis, queue, queue_name):
#     """Основная функция для обработки VMess прокси"""
#
#     # Увеличиваем лимит открытых файлов
#     try:
#         resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))
#     except:
#         pass
#
#     semaphore = asyncio.Semaphore(3)
#     checker = CheckerVmess()
#     validator = ValidatorVmess()
#
#     # Парсим прокси
#     list_proxis_clean = []
#     for line in list_proxis:
#         try:
#             proxy = parse_vmess_url(line)
#             if proxy and proxy.get("host") and proxy.get("port") and proxy.get("uuid"):
#                 list_proxis_clean.append(proxy)
#         except Exception as e:
#             write_top(f"⚠️ Ошибка парсинга VMess: {e}")
#             continue
#
#     total_items = len(list_proxis_clean)
#     write_top(f"📊 VMess: всего прокси = {total_items}")
#
#     if total_items == 0:
#         write_top("⚠️ Нет VMess прокси для обработки")
#         await queue.put("Done")
#         return
#
#     # Разбиваем на чанки (20% на чанк = 5 воркеров)
#     chunks = distribute_by_percent(list_proxis_clean, percent=20)
#     write_top(f"📦 Создано {len(chunks)} чанков")
#     write_top(f"📊 Размеры чанков: {[len(c) for c in chunks]}")
#
#     list_task = []
#     for idx, chunk in enumerate(chunks):
#         task_id = f"vmess-{uuid.uuid4().hex[:8]}"
#         await register_task(task_id, f"🚀 VMess Worker {idx+1}", protocol="vmess")
#
#         task = asyncio.create_task(
#             process_chunk(
#                 queue, queue_name, semaphore, validator, chunk, checker, task_id
#             )
#         )
#         list_task.append(task)
#
#     await asyncio.gather(*list_task)
#     await queue.put("Done")
#     write_top("✅ VMess воркер завершён")
#
#
