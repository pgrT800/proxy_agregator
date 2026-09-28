import asyncio
import os
import sys
from asyncio.tasks import FIRST_COMPLETED

import aiohttp

from core.TaskRegisterMainInit.TaskRegister import taskregister
from core.tui_global_set import write_top
from worker_shadowsocks.getData.datagit import GitHttp
from worker_shadowsocks.mWorkerShadowsocs.core.core import worker_shadowsocks
from worker_shadowsocks.mWorkerTrojan.core.core import worker_trojan
from worker_shadowsocks.mWorkerVless.core.core import core_worker_vless
from worker_shadowsocks.mWorkerVmell.core.core import core_worker_vmess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.StateManager.stateCore.stateCore import (
    StateManager,
    loop_r,
    loop_w,
    statemanager,
)


async def core(sources_mix, queue_dict, semaphore_limit):
    """Собирает прокси из источников и распределяет по очередям"""
    session = aiohttp.ClientSession()
    get_data = GitHttp()

    list_ss_proxis = []
    list_trojan_proxis = []
    list_vless_proxis = []
    list_vmess_proxis = []

    for source in sources_mix:
        list_proxis = await get_data.get_content(source, session)
        for line in list_proxis:
            if line.startswith("ss://"):
                list_ss_proxis.append(line)
            elif line.startswith("trojan://"):
                list_trojan_proxis.append(line)
            elif line.startswith("vless://"):
                list_vless_proxis.append(line)
            elif line.startswith("vmess://"):

                list_vmess_proxis.append(line)

    write_top(f"Найдено shadowsocks прокси = {len(list_ss_proxis)}")
    write_top(f"Найдено trojan прокси = {len(list_trojan_proxis)}")
    write_top(f"Найдено vless прокси = {len(list_vless_proxis)}")
    write_top(f"Найдено vmess прокси = {len(list_vmess_proxis)}")
    semaphore_limit_min = 50
    # Запускаем воркеров
    workers = [
        asyncio.create_task(
            worker_shadowsocks(
                list_ss_proxis,
                queue_dict["shadowsocks"],
                "shadowsocks",
                semaphore_limit,
            )
        ),
        asyncio.create_task(
            worker_trojan(
                list_trojan_proxis, queue_dict["trojan"], "trojan", semaphore_limit_min
            )
        ),
        asyncio.create_task(
            core_worker_vless(
                list_vless_proxis, queue_dict["vless"], "vless", semaphore_limit_min
            )
        ),
        asyncio.create_task(
            core_worker_vmess(
                list_vmess_proxis, queue_dict["vmess"], "vmess", semaphore_limit_min
            )
        ),
    ]

    await asyncio.gather(*workers)
    await session.close()


async def worker_shadowsocks_main(
    sources_mix,
    queue_shadowsocks_mix,
    queue_trojan,
    queue_vless,
    queue_vmess,
    semaphore_limit,
):

    list_tasks = []
    all_handlers = []  # ← собираем все обработчики

    # # Создаём очереди для этой группы
    queues = {
        "shadowsocks": queue_shadowsocks_mix,
        "trojan": queue_trojan,
        "vless": queue_vless,
        "vmess": queue_vmess,
    }
    # Запускаем core для этой группы
    task = asyncio.create_task(core(sources_mix, queues, semaphore_limit))
    list_tasks.append(task)

    pending = set(list_tasks)
    while pending:
        done, pending = await asyncio.wait(pending, return_when=FIRST_COMPLETED)
        for task in done:
            result = task.result()
            write_top(f"Завершена core задача, осталось: {len(pending)}")

    write_top(
        "✅ Все core задачи shadowsocks завершены, ожидаем завершения обработчиков..."
    )
    # await queue_shadowsocks_mix.put("Done")
    #
    write_top("✅ worker_shadowsocks_main завершён")
