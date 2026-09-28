import asyncio
import json
import os

import aiofiles


class StateManager:
    def __init__(self) -> None:
        self.queueDist = {}
        self.protocol = None
        self._locks = {}  # protocol -> asyncio.Lock
        self._reader_tasks = {}

    def _get_lock(self, protocol):
        """Получить или создать блокировку для протокола"""
        if protocol not in self._locks:
            self._locks[protocol] = asyncio.Lock()
        return self._locks[protocol]

    async def status_state(self, protocol) -> bool:
        filename = f"state-{protocol}.json"
        if os.path.exists(filename):
            print(f"State exists: {filename}")
            return True
        return False

    async def create_queue_for_protocols(self, protocols):
        self.queueDist[protocols] = asyncio.Queue()
        print(f"Create queue for {protocols}")

    async def create_state(self, protocol) -> str:
        filename = f"state-{protocol}.json"
        file_data = {protocol: {"data": []}}
        lock = self._get_lock(protocol)
        async with lock:
            async with aiofiles.open(filename, "w") as file:
                await file.write(json.dumps(file_data))
        print(f"Создан новый файл: {filename}")

    async def data_add(self, protocol, data):
        data = [data]
        filename = f"state-{protocol}.json"
        lock = self._get_lock(protocol)

        async with lock:
            try:
                async with aiofiles.open(filename, "r") as file:
                    content = await file.read()
                    if not content.strip():
                        data_json = {protocol: {"data": []}}
                    else:
                        data_json = json.loads(content)
            except (json.JSONDecodeError, FileNotFoundError):
                print(f"⚠️ Файл {filename} повреждён, пересоздаю")
                data_json = {protocol: {"data": []}}

            data_json[protocol]["data"].extend(data)

            async with aiofiles.open(filename, "w") as file:
                await file.write(json.dumps(data_json))

    async def save_state(self, protocol, data):
        status = await self.status_state(protocol)
        if status:
            await self.data_add(protocol, data)
            print("Данные успешно добавленны")
        else:
            await self.create_state(protocol)
            await self.data_add(protocol, data)
            print("Состояние созданно и добавленны данные")

    async def reader(self, protocol):

        if protocol not in self.queueDist:
            await self.create_queue_for_protocols(protocol)

        queue = self.queueDist[protocol]
        while True:
            item = await queue.get()
            if item is not None and item != "Done":
                await statemanager.save_state(protocol, item)
            elif item == "Done":
                print("Reader is dead get item[Done]")
                break

    async def get_data_state(self, protocol):
        status = await self.status_state(protocol)
        if status:
            filename = f"state-{protocol}.json"
            lock = self._get_lock(protocol)
            async with lock:
                try:
                    async with aiofiles.open(filename, "r") as file:
                        content = await file.read()
                        if not content.strip():
                            print(f"⚠️ Файл {filename} пуст, возвращаю []")
                            return []
                        data_json = json.loads(content)
                        return data_json[protocol]["data"]
                except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
                    print(f"⚠️ Файл {filename} повреждён: {e}, возвращаю []")
                    return []
        else:
            return []

    async def writear(self, protocol, item):
        queue = self.queueDist[protocol]
        if item is not None and item != "Done":
            await queue.put(item)
        elif item == "Done":
            await queue.put("Done")
            print("writear is dead")

    async def filteringData(self, protocol, list_in):
        list_state_data = await self.get_data_state(protocol)
        data_state = set(list_state_data)
        filtering_output_data = [item for item in list_in if item not in data_state]
        return filtering_output_data

    async def set_reader_task(self, protocol, task):
        self._reader_tasks[protocol] = task

    async def stop_all_readers(self):
        """Принудительно остановить все reader'ы"""
        for protocol, task in list(self._reader_tasks.items()):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._reader_tasks.clear()
        print("🛑 Все reader'ы остановлены")


statemanager = StateManager()


async def loop_w(list_data, protocol):
    await statemanager.writear(protocol=protocol, item=list_data)


async def loop_r(protocol):
    await statemanager.reader(protocol)


# import asyncio
# import json
# import os
#
# import aiofiles
#
#
# class StateManager:
#     def __init__(self) -> None:
#         self.queueDist = {}
#         self.protocol = None
#
#     async def status_state(self, protocol) -> bool:
#         filename = f"state-{protocol}.json"
#         if os.path.exists(filename):
#             print(f"State exists: {filename}")
#             return True
#         return False
#
#     async def create_queue_for_protocols(self, protocols):
#         self.queueDist[protocols] = asyncio.Queue()
#         print(f"Create queue for {protocols}")
#
#     async def create_state(
#         self,
#         protocol,
#     ) -> str:
#         filename = f"state-{protocol}.json"
#         # Создаём правильную структуру
#
#         file_data = {protocol: {"data": []}}
#         async with aiofiles.open(filename, "w") as file:
#             await file.write(json.dumps(file_data))
#         print(f"Создан новый файл: {filename}")
#
#     async def data_add(self, protocol, data):
#         data = [data]
#         filename = f"state-{protocol}.json"
#         async with aiofiles.open(filename, "r") as file:
#             content = await file.read()
#             if not content.strip():
#                 # Файл пуст — создаём заново
#                 data_json = {protocol: {"data": []}}
#             else:
#                 data_json = json.loads(content)
#
#         data_json[protocol]["data"].extend(data)
#
#         async with aiofiles.open(filename, "w") as file:
#             await file.write(json.dumps(data_json))
#
#     async def save_state(self, protocol, data):
#         status = await self.status_state(protocol)
#         if status:
#             await self.data_add(protocol, data)
#             print("Данные успешно добавленны")
#         else:
#             await self.create_state(protocol)
#             await self.data_add(protocol, data)
#             print("Состояние созданно и добавленны данные")
#
#     async def reader(self, protocol):
#         if protocol not in self.queueDist:
#             await self.create_queue_for_protocols(protocol)
#
#         queue = self.queueDist[protocol]
#         while True:
#             item = await queue.get()
#             if item is not None and item != "Done":
#                 await statemanager.save_state(protocol, item)
#
#             elif item == "Done":
#                 print("Reader is dead get item[Done]")
#                 break
#
#     async def get_data_state(self, protocol):
#         status = await self.status_state(protocol)
#         if status:
#             filename = f"state-{protocol}.json"
#             async with aiofiles.open(filename, "r") as file:
#                 content = await file.read()
#                 if not content.strip():  # файл пустой
#                     print(f"⚠️ Файл {filename} пуст, возвращаю []")
#                     return []
#                 try:
#                     data_json = json.loads(content)
#                     list_data_json = data_json[protocol]["data"]
#                     return list_data_json
#                 except (json.JSONDecodeError, KeyError) as e:
#                     print(f"⚠️ Файл {filename} повреждён: {e}, возвращаю []")
#                     return []
#         else:
#             return []
#
#     async def writear(self, protocol, item):
#         queue = self.queueDist[protocol]
#         if item is not None and item != "Done":
#             await queue.put(item)
#         elif item == "Done":
#             await queue.put("Done")
#             print("writear is dead")
#
#     async def filteringData(self, protocol, list_in):
#         list_state_data = await self.get_data_state(protocol)
#         data_state = set(list_state_data)
#         filtering_output_data = [item for item in list_in if item not in data_state]
#
#         return filtering_output_data
#
#
# statemanager = StateManager()
#
#
# async def loop_w(list_data, protocol):
#     # for i in list_data:
#     await statemanager.writear(protocol=protocol, item=list_data)
#
#
# async def loop_r(protocol):
#     await statemanager.reader(protocol)
