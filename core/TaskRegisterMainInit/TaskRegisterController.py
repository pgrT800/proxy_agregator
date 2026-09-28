# Управляет задачами и еще отвечает за headless mode и интерфейс tui mode а  также за  --reset для обнуления и БД и state-<protocol>.json
import argparse
import asyncio
import os
import sys

from aiohttp import request

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)


from core.tui_global_set import write_top


class TaskRegisterController:
    def __init__(self) -> None:
        self.path_socket_controller = (
            "/tmp/my_socket_for_server_controller_task_register.sock"
        )
        self.task_list_collect = []

    async def cancel_task(self, task):
        # if not task.done():
        # await task.cancel()
        # task.throw(KeyboardInterrupt)  # мгновенно прерывает корутину
        # task.cancel()
        return True

    async def add_task_register(self, task):
        pass
        self.task_list_collect.append(task)
        print(f"Task is append: {task}")

    async def add_task_list_register(self, list_task: list):
        pass
        if list_task is not None and len(list_task) >= 1:
            self.task_list_collect.extend(list_task)
            print(f"Task list is append")

    async def collect_task_cancel(self):
        # if self.task_list_collect is not None:
        #     if len(self.task_list_collect) >= 1:
        #         for task in self.task_list_collect:
        #             status = await self.cancel_task(task)
        #             if status == True:
        #                 print(f"Task {task} is {status} canceled")
        #             else:
        #                 print(f"Task {task} is {status} not canceled")
        pass

    async def glou_reboot(self):
        print("Reboot")

    async def hadlers_for_client_server(self, reader, writer):
        peername = writer.get_extra_info("peername")
        from core.core import (
            HTTP_SOURCES,
            HTTPS_SOURCES,
            SOCKS5_SOURCES,
            SOURCES_MIX,
            main_without_tui_headless,
        )
        from core.core_tui import ProxyCollectorApp, main_with_tui_interface

        # from core.tui_global_set import write_top

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                signal = data.decode()
                if signal == "Reboot":
                    print("---------Принт получена команда REBOOT-------------------")
                    await self.glou_reboot()
                elif signal == "Reboot to tui":
                    await self.collect_task_cancel()
                    await main_with_tui_interface(
                        HTTP_SOURCES, HTTPS_SOURCES, SOCKS5_SOURCES, SOURCES_MIX
                    )
                elif signal == "Reboot to headless":
                    await self.collect_task_cancel()
                    await main_without_tui_headless(
                        HTTP_SOURCES, HTTPS_SOURCES, SOCKS5_SOURCES, SOURCES_MIX
                    )
                elif signal == "Test lock down":
                    await self.collect_task_cancel()
                writer.write(b"ACK")
                await writer.drain()

        except ConnectionResetError:
            write_top(f"🔌 Клиент {peername} разорвал соединение")
        finally:
            writer.close()
            await writer.wait_closed()

    async def inicialization(self):
        server = await asyncio.start_unix_server(
            self.hadlers_for_client_server, self.path_socket_controller
        )
        async with server:
            await server.serve_forever()
