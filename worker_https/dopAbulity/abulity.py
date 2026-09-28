import asyncio
import random
import string


#
# class CheckerHttps:
#
#     async def check_proxy(self, host: str, port) -> bool:
#         """
#         proxy: "ip:port"
#         """
#         try:
#             reader, writer = await asyncio.wait_for(
#                 asyncio.open_connection(host, int(port)), timeout=7
#             )
#             writer.close()
#             await writer.wait_closed()
#             # print(f"host {host} is alive")
#             return True
#         except:
#             # print(f"host {host} is dead")
#             return False
class CheckerHttps:
    async def check_proxy(self, host: str, port: int, max_retries: int = 2) -> bool:
        """
        Проверяет HTTP прокси с повторами при временных сбоях
        """
        for attempt in range(max_retries):
            try:

                await asyncio.sleep(random.uniform(0.01, 0.5))
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, int(port)), timeout=5
                )
                writer.close()
                await writer.wait_closed()
                return True

            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Ждём перед повтором
                else:
                    return False

            except (ConnectionRefusedError, OSError):
                return False  # Эти ошибки не лечатся повтором

            except Exception:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    return False

        return False
