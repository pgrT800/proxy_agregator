import asyncio
import json
import os

import aiofiles

json_data = {"http": {"data": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}}


async def add_data(filename: str, data_add: list):
    async with aiofiles.open(filename, "r") as file:
        data = await file.read()
        data_json = json.loads(data)

        data_json["http"]["data"].extend(data_add)

    async with aiofiles.open(filename, "w") as file:
        await file.write(json.dumps(data_json))


async def printing(filename: str):
    async with aiofiles.open(filename, "r") as file:
        data = await file.read()
        data = json.loads(data)
    if "http" in data:
        list_d = data["http"]["data"]
        for i in list_d:
            print(i)


async def main():
    async with aiofiles.open("test-state.json", "w") as file:
        await file.write(json.dumps(json_data))

    await printing("test-state.json")
    await add_data("test-state.json", data_add=[44, 22, 66])
    await printing("test-state.json")


asyncio.run(main())
