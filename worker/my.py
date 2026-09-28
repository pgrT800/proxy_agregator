import asyncio
import os
import queue
import sys
from asyncio.tasks import FIRST_COMPLETED

# from tui_global_set import write_top
from typing_extensions import final

from core.custom_widget import register_task, update_task
from core.StateManager.stateCore.stateCore import (
    StateManager,
    loop_r,
    loop_w,
    statemanager,
)
from core.TaskRegisterMainInit.TaskRegister import taskregister
from core.tui_global_set import write_top

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


import uuid

import aiohttp
from aiohttp import *

# from dopAbulity.abulity import CheckerHttp
from function.function import GitHttp

# from pydantic import validator
# from requests import session
from validator.validator import Validator

from worker.dopAbulity.abulity import CheckerHttp


async def collect_all_data(sources, semaphore):
    """Собирает данные со всех источников в единый список"""
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
        await taskregister.add_task_list_register(tasks)
        results = await asyncio.gather(*tasks)
        for result in results:
            if result:
                list_proxis.extend(result)

        return list_proxis
    finally:
        await session.close()


def distribute_by_percent(lst: list, percent: int = 20) -> list:
    """Распределяет элементы по чанкам с заданным процентом"""
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


async def writer(chunk, queue_dict, task_id):
    queue_writer = queue_dict[f"queue-{task_id}"]
    update_task(task_id, total=len(chunk), processed=len(chunk), progress=0)
    for item in chunk:
        if item is not None:
            await queue_writer.put(item)

    await queue_writer.put("Done")


async def defalt_worker(source, gitHttp, session, Semaphore):
    async with Semaphore:
        write_top(f"work with {source}")

        list_pro = await gitHttp.get_content(source, session)

        return list_pro


async def defalt_worker_checker(data_check, checker, Semaphore, task_id):

    async with Semaphore:
        host, port = data_check.split(":")
        result = await checker.check_proxy(host, port, task_id)
        data_result = [host, port, result]
        return data_result


async def defalt_worker_validator(
    data_check_proxy, validator, Semaphore, task_id, session
):
    async with Semaphore:
        host, port = data_check_proxy.split(":")

        result_validate = await validator.check_proxy_target(
            host, port, task_id, session
        )
        return result_validate


async def reader(
    queue_dict, task_id, queue_http, semaphore_for_request_private_work_limit
):

    # session = aiohttp.ClientSession()
    checker = CheckerHttp()
    # gitHttp = GitHttp()
    validator = Validator()
    queue_reader = queue_dict[f"queue-{task_id}"]
    update_task(task_id, stage="Work", status="running")
    # async with semaphore_for_request_private_work_limit:

    async with aiohttp.ClientSession() as session:
        while True:
            item = await queue_reader.get()
            # await loop_w(item, protocol="http")
            if item == "Done":
                write_top(f"Task with {task_id} break")

                break
            # await loop_w(item, protocol="http")
            # write_top("worker task_id get item")
            if item is not None:
                result_checker = await defalt_worker_checker(
                    item, checker, semaphore_for_request_private_work_limit, task_id
                )
                if result_checker[2] == True:
                    write_top(
                        f"Alive proxy is {result_checker[0]}:{result_checker[1]}:{result_checker[2]}"
                    )
                    result_validate = await defalt_worker_validator(
                        item,
                        validator,
                        semaphore_for_request_private_work_limit,
                        task_id,
                        session,
                    )
                    # results.append(result)
                    item_q = {"http": result_validate}

                    await queue_http.put(item_q)
                await loop_w(item, protocol="http")

                update_task(task_id, add=1)


import math


async def worker_http(HTTP_SOURCES, queue_http, adaptivSemaphoreForResquests):
    sources = HTTP_SOURCES
    task_reader_state = asyncio.create_task(loop_r(protocol="http"))
    await statemanager.set_reader_task("http", task_reader_state)

    semaphore_local = asyncio.Semaphore(10)

    list_proxis = await collect_all_data(sources, semaphore_local)
    list_fitering = await statemanager.filteringData(
        protocol="http", list_in=list_proxis
    )
    write_top(f"ОТфильрованно http {len(list_proxis)-len(list_fitering)}")
    if list_fitering is not None:
        list_proxis = list_fitering
    chunks = distribute_by_percent(list_proxis, 5)
    list_task_writer = []
    list_task_reader = []
    async with semaphore_local:

        semaphore_for_request_private_work_limit = adaptivSemaphoreForResquests / len(
            chunks
        )

        semaphore_for_rt = math.floor(semaphore_for_request_private_work_limit)
        write_top(f"Semaphore = {semaphore_for_rt}")
        semaphore_for_rt = asyncio.Semaphore(semaphore_for_rt)
        for chunk in chunks:
            task_id = f"http-{uuid.uuid4().hex[:8]}"
            await register_task(
                task_id,
                f"🌐",
                protocol="http",
            )
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
                    queue_http=queue_http,
                    semaphore_for_request_private_work_limit=semaphore_for_rt,
                )
            )
            list_task_reader.append(task_reader)
        list_task_reader.append(task_reader_state)
        await asyncio.gather(*list_task_writer)
        await asyncio.gather(*list_task_reader)
    await queue_http.put("Done")
