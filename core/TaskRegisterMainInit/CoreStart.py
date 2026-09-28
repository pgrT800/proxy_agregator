# Управляет задачами и еще отвечает за headless mode и интерфейс tui mode а  также за  --reset для обнуления и БД и state-<protocol>.json
import argparse
import asyncio
import os
import sys

from aiohttp import request

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)
#

from core.core_tui import ProxyCollectorApp  # main_with_tui_interface
from core.RedisDataBase.redis_main import RedisStorage
from core.StateManager.stateCore.stateCore import StateManager, statemanager
from core.TaskRegisterMainInit.TaskRegister import taskregister
from core.TaskRegisterMainInit.TaskRegisterController import TaskRegisterController
from core.tui_global_set import write_top

parser = argparse.ArgumentParser(description="Прокси-сервер Мозги")
parser.add_argument(
    "--mode",
    choices=["tui", "headless", "reset"],
    default="tui",
    help="Режим запуска: tui (по умолчанию), headless, reset",
)

args = parser.parse_args()


async def reset_db_and_state():
    redis_storage = RedisStorage()
    await redis_storage.connect()
    await redis_storage.flush_all()


async def main_start():

    if args.mode == "tui":
        # 1. Запускаем LDS-сервер как фоновую задачу
        lds_task = asyncio.create_task(taskregister.inicialization())

        # 2. Запускаем TUI как фоновую задачу
        app = ProxyCollectorApp()
        task_tui = asyncio.create_task(app.run_async())
        await asyncio.gather(task_tui)

    elif args.mode == "headless":

        from core.core import (
            HTTP_SOURCES,
            HTTPS_SOURCES,
            SOCKS5_SOURCES,
            SOURCES_MIX,
            main_without_tui_headless,
        )

        await main_without_tui_headless(
            HTTP_SOURCES, HTTPS_SOURCES, SOCKS5_SOURCES, SOURCES_MIX
        )

        await taskregister.inicialization()

    elif args.mode == "reset":
        print("reset")
        list_file_state = [
            "http",
            "https",
            "socks",
            "shadowsocks",
            "vless",
            "vmess",
            "trojan",
        ]
        for i in list_file_state:
            file = f"state-{i}.json"
            if os.path.exists(file):
                print(f"Файл состояния {file} существует и удален")
                os.remove(file)
            else:
                print(f"Файла состояния {file} нет")
        await reset_db_and_state()


asyncio.run(main_start())
