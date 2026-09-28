import asyncio
import base64
import math
import os
import random
import re
import subprocess
import sys
import uuid
import warnings
from turtle import up

import aiohttp
from aiohttp_socks import ProxyConnectionError, ProxyConnector

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
from worker_shadowsocks.mWorkerShadowsocs.checker.checker import CheckerShadowsocks
from worker_shadowsocks.mWorkerShadowsocs.validator.validator import (
    ValidatorShadowsocks,
)

# from aiohttp_socks import ProxyConnector, ProxyConnectionError
# from core.custom_widget import register_task, update_task
# from core.tui_global_set import write_top

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def parse_ss_url(line: str) -> dict | None:
    line = line.strip()
    if any(x in line for x in ["vmess://", "vless://", "trojan://", "ssr://"]):
        return None
    if not line.startswith("ss://"):
        return None

    raw = line[5:]
    if "#" in raw:
        raw = raw.split("#")[0]
    if "?" in raw:
        raw = raw.split("?")[0]
    raw = raw.rstrip("/")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            b64_clean = re.sub(r"[^A-Za-z0-9+/=]", "", raw)
            decoded = base64.b64decode(b64_clean).decode("utf-8")
            if "@" in decoded and ":" in decoded:
                method_pass, host_port = decoded.split("@", 1)
                method, password = method_pass.split(":", 1)
                host, port = host_port.rsplit(":", 1)
                return {
                    "host": host,
                    "port": int(port),
                    "method": method,
                    "password": password,
                    "type": "ss",
                }
        except:
            pass

    match = re.match(r"([^:]+):([^@]+)@([^:]+):(\d+)", raw)
    if match:
        return {
            "host": match.group(3),
            "port": int(match.group(4)),
            "method": match.group(1),
            "password": match.group(2),
            "type": "ss",
        }

    match = re.search(r"([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+|[a-zA-Z0-9\.\-]+):(\d+)", raw)
    if match:
        host = match.group(1)
        if host not in [
            "aes-256-cfb",
            "aes-256-gcm",
            "chacha20",
            "chacha20-ietf-poly1305",
        ]:
            return {"host": host, "port": int(match.group(2)), "type": "ss"}
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


async def collect_all_data(sources, semaphore):
    gitHttp = GitHttp()
    session = aiohttp.ClientSession()
    try:
        list_proxis = []
        tasks = []
        for source in sources:
            task = asyncio.create_task(
                defalt_worker(source, gitHttp, session, semaphore)
            )
            tasks.append(task)
        results = await asyncio.gather(*tasks)
        for result in results:
            if result:
                for line in result:
                    proxy = parse_ss_url(line)
                    if proxy is not None:
                        list_proxis.append(proxy)
        return list_proxis
    finally:
        await session.close()


async def defalt_worker(source, gitHttp, session, semaphore):
    async with semaphore:
        write_top(f"work with {source}")
        list_pro = await gitHttp.get_content(source, session)
        return list_pro


async def writer(chunk, queue_dict, task_id):
    queue_writer = queue_dict[f"queue-{task_id}"]

    # update_task(task_id, stage="Checker", status="running")
    update_task(
        task_id,
        total=len(chunk),
        stage="Work",
        progress=0,
        # status="running",
        processed=len(chunk),
    )
    for item in chunk:
        if item is not None:
            await queue_writer.put(item)
    await queue_writer.put("Done")


async def reader(queue_dict, task_id, target_queue, semaphore_limit):
    checker = CheckerShadowsocks()
    validator = ValidatorShadowsocks()
    queue_reader = queue_dict[f"queue-{task_id}"]
    # update_task(task_id, status="running")

    while True:
        item = await queue_reader.get()
        if item == "Done":
            write_top(f"Task with {task_id} break")
            break

        if item is not None:
            result_checker = await checker.checker(item, semaphore_limit, task_id)
            proxy_dict, is_alive = result_checker

            if is_alive:
                write_top(
                    f"✅ Shadowsocks жив: {proxy_dict.get('host')}:{proxy_dict.get('port')}"
                )
                result_validate = await validator.validate_proxy(
                    proxy_dict, semaphore_limit
                )
                if result_validate:
                    item_result = {"shadowsocks": result_validate}
                    await target_queue.put(item_result)

            update_task(task_id, add=1)
    update_task(task_id, status="done", stage="Done")


async def worker_shadowsocks(list_proxis, target_queue, protocol, semaphore_limit):
    """Главная функция для Shadowsocks воркера с потоковой архитектурой"""
    semaphore_local = asyncio.Semaphore(10)
    task_reader_state = asyncio.create_task(loop_r(protocol="shadowsocks"))
    await statemanager.set_reader_task("shadowsocks", task_reader_state)

    list_fitering = await statemanager.filteringData(
        protocol="shadowsocks", list_in=list_proxis
    )
    write_top(f"ОТфильрованно {len(list_proxis)-len(list_fitering)}")
    # Собираем все данные
    if list_fitering is not None:
        list_proxis = list_fitering
    # Парсим прокси
    list_proxis_clean = []
    for line in list_proxis:
        proxy = parse_ss_url(line)
        if proxy is not None:
            list_proxis_clean.append(proxy)

    total_proxies = len(list_proxis_clean)
    write_top(f"📊 Shadowsocks: всего прокси = {total_proxies}")

    if not list_proxis_clean:
        write_top("❌ Нет данных для обработки Shadowsocks")
        await target_queue.put("Done")
        return

    # Разбиваем на чанки
    chunks = distribute_by_percent(list_proxis_clean, 10)
    write_top(f"📦 Создано {len(chunks)} чанков")
    write_top(f"📊 Размеры чанков: {[len(c) for c in chunks]}")

    list_task_writer = []
    list_task_reader = []

    async with semaphore_local:
        semaphore_for_rt = asyncio.Semaphore(semaphore_limit)

        for idx, chunk in enumerate(chunks):
            task_id = f"shadowsocks-{uuid.uuid4().hex[:8]}"
            await register_task(task_id, f"🛡️ ", protocol=protocol)

            queue_obj = asyncio.Queue()
            queue_dict = {f"queue-{task_id}": queue_obj}

            task_writer = asyncio.create_task(
                writer(queue_dict=queue_dict, chunk=chunk, task_id=task_id)
            )
            list_task_writer.append(task_writer)

            task_reader = asyncio.create_task(
                reader(
                    queue_dict=queue_dict,
                    task_id=task_id,
                    target_queue=target_queue,
                    semaphore_limit=semaphore_for_rt,
                )
            )
            list_task_reader.append(task_reader)
        list_task_reader.append(task_reader_state)
        await asyncio.gather(*list_task_writer)
        await asyncio.gather(*list_task_reader)

    await target_queue.put("Done")
